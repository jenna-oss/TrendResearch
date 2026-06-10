"""
Interior Design Professional Trend Collector + Tagger

Four-stage system with adaptive quality gates:
Stage 1: Pull RSS feeds, extract bodies, apply 60-day filter, normalize records
Stage 2: Pre-filter for extraction quality, content-type, and diversity (all adaptive)
Stage 3: Tag with Claude (themes, lifecycle, specificity, strength, trend_signal)
Stage 4: Validate theme grounding and flag recency risks (adaptive sampling)

All filtering is self-correcting and agnostic to source/time/volume.
"""

import feedparser
import trafilatura
import json
import os
import re
import time
import uuid
import hashlib
import random
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    INTERIOR_PRO_OUTPUT_DIR,
    CLAUDE_MODEL,
    RECENCY_FILTER_DAYS,
    MIN_BODY_WORDS,
    TRAFILATURA_FAVOR_PRECISION,
    TAGGER_TEXT_LIMIT,
    TAGGING_BATCH_SIZE,
    FRESH_CURRENT_DAYS,
    FRESH_EDGE_DAYS,
    RECENCY_RISK_DAYS,
    MIN_EXTRACTION_COMPLETENESS_RATE,
    EXTRACTION_QUALITY_RETRY_METHODS,
    SOURCE_DIVERSITY_MULTIPLIER,
    ENABLE_SOURCE_BALANCING,
    ENABLE_CONTENT_TYPE_FILTER,
    OFF_TIER_KEYWORDS,
    ENABLE_THEME_GROUNDING_VALIDATION,
    THEME_VALIDATION_SAMPLE_RATE,
    FEED_HEALTH_TRACKING_ENABLED,
    FEED_FAILURE_BACKOFF_DAYS,
    FEED_FAILURE_THRESHOLD,
)

client_api = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

VERTICAL = "interior_design"
QUESTION_SERVED = "professional_trend"


# ============================================================================
# FEED HEALTH MONITORING (PERSISTENT TRACKING)
# ============================================================================

def get_feed_health_path():
    """Get path to feed health tracking file."""
    logs_dir = os.path.join(INTERIOR_PRO_OUTPUT_DIR, "_feed_health")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "feed_health.json")


def load_feed_health():
    """Load persistent feed health tracking."""
    path = get_feed_health_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_feed_health(health):
    """Save feed health tracking."""
    path = get_feed_health_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2)


def update_feed_health(source_name, succeeded, error_type=None):
    """
    Track feed reliability over time. Auto-backoff feeds with 3+ consecutive failures.
    """
    if not FEED_HEALTH_TRACKING_ENABLED:
        return

    health = load_feed_health()

    if source_name not in health:
        health[source_name] = {
            "success_rate": 1.0,
            "total_runs": 0,
            "successful_runs": 0,
            "last_failure": None,
            "failures_consecutive": 0,
            "backoff_until": None,
            "error_history": []
        }

    entry = health[source_name]
    entry["total_runs"] += 1

    if succeeded:
        entry["successful_runs"] += 1
        entry["failures_consecutive"] = 0
        entry["success_rate"] = entry["successful_runs"] / entry["total_runs"]
    else:
        entry["failures_consecutive"] += 1
        entry["last_failure"] = datetime.now(timezone.utc).isoformat()
        entry["error_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type
        })

        # Auto-backoff on 3+ consecutive failures
        if entry["failures_consecutive"] >= FEED_FAILURE_THRESHOLD:
            backoff_date = (datetime.now(timezone.utc) + timedelta(days=FEED_FAILURE_BACKOFF_DAYS)).date()
            entry["backoff_until"] = backoff_date.isoformat()
            print(f"  🚫 {source_name}: {entry['failures_consecutive']} failures → backoff until {backoff_date}")

    save_feed_health(health)


# ============================================================================
# STAGE 1: COLLECTION + NORMALIZATION (NO LLM)
# ============================================================================

def collect_interior_professional(sources: list) -> dict:
    """
    Stage 1: pull RSS feeds, fetch + extract bodies, apply recency filter,
    reshape into common signal records. Fully mechanical — no LLM.
    Returns signals, feed log, completeness counts.
    """
    signals = []
    feed_log = []
    seen_hashes = set()
    completeness_counts = {
        "complete": 0,
        "partial": 0,
        "summary_only": 0,
        "empty": 0,
    }

    for source in sources:
        result = {
            "source_name": source["source_name"],
            "status": "success",
            "articles_found": 0,
            "articles_kept": 0,
            "filtered_old": 0,
            "filtered_dup": 0,
            "filtered_empty": 0,
            "error": None,
        }

        try:
            feed = feedparser.parse(source["feed_url"])

            if feed.bozo and not feed.entries:
                result["status"] = "feed_failed"
                result["error"] = str(feed.bozo_exception)[:200]
                update_feed_health(source["source_name"], False, "feed_parse_failed")
                feed_log.append(result)
                continue

            update_feed_health(source["source_name"], True)
            result["articles_found"] = len(feed.entries)

            for entry in feed.entries:
                pub_date, date_confidence = extract_date(entry)

                # 60-day recency — hard filter, dated articles only
                if pub_date is not None and not within_recency(pub_date):
                    result["filtered_old"] += 1
                    continue

                url = entry.get("link", "")
                if not url:
                    continue

                title = entry.get("title", "").strip()

                # Improved dedup: source + title + url to catch redirects
                dedup_key = hashlib.md5(
                    f"{source['source_name']}:{title}:{url}".lower().encode()
                ).hexdigest()

                if dedup_key in seen_hashes:
                    result["filtered_dup"] += 1
                    continue

                seen_hashes.add(dedup_key)

                # Extract body with retry chain
                body, completeness, extraction_method = fetch_and_extract(url, entry)
                completeness_counts[completeness] += 1

                if completeness == "empty":
                    result["filtered_empty"] += 1
                    continue

                raw_text = f"{title}\n\n{body}".strip()
                freshness = grade_freshness(pub_date, date_confidence)

                signals.append({
                    "signal_id": generate_id(url),
                    "vertical": VERTICAL,
                    "question_served": QUESTION_SERVED,
                    "source_name": source["source_name"],
                    "source_url": url,
                    "luxury_confidence": source["luxury_confidence"],
                    "source_paywall": source["paywall"],
                    "title": title,
                    "raw_text": raw_text,
                    "body_word_count": len(body.split()),
                    "content_completeness": completeness,
                    "extraction_method": extraction_method,
                    "published_date": pub_date.isoformat() if pub_date else None,
                    "date_confidence": date_confidence,
                    "freshness": freshness,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })

                result["articles_kept"] += 1

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)[:200]
            update_feed_health(source["source_name"], False, "collection_error")

        feed_log.append(result)
        time.sleep(1)

    return {
        "signals": signals,
        "feed_log": feed_log,
        "completeness_counts": completeness_counts,
    }


def fetch_and_extract(url, entry):
    """
    Extraction retry chain: try methods in order of quality before falling back to RSS.
    Improvement #6: Adaptive fallback strategy.

    Returns (body_text, completeness_flag, extraction_method).
    """
    # Try trafilatura with multiple settings before falling back
    methods = [
        ("trafilatura_precision", lambda: trafilatura.fetch_url(url), {"favor_precision": True}),
        ("trafilatura_balanced", lambda: trafilatura.fetch_url(url), {"favor_precision": False}),
        ("trafilatura_no_comments", lambda: trafilatura.fetch_url(url), {"include_comments": False}),
    ]

    for method_name, fetch_fn, extract_kwargs in methods:
        try:
            downloaded = fetch_fn()
            if not downloaded:
                continue

            try:
                body = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    **extract_kwargs
                )

                if body:
                    wc = len(body.split())
                    if wc >= MIN_BODY_WORDS:
                        return body, "complete", method_name
                    if wc > 0:
                        return body, "partial", method_name
            except Exception:
                continue

        except Exception:
            continue

    # Fallback: RSS summary as last resort
    summary = entry.get("summary", "") or entry.get("description", "")
    summary = strip_html(summary)

    if summary and len(summary.split()) > 10:
        return summary, "summary_only", "rss_summary"

    return "", "empty", "failed"


def extract_date(entry):
    """Returns (datetime|None, confidence: high|low|none)."""
    for field in ["published", "updated", "pubDate"]:
        val = entry.get(field)
        if val:
            try:
                return date_parser.parse(val), "high"
            except Exception:
                continue

    if getattr(entry, "published_parsed", None):
        try:
            dt = datetime.fromtimestamp(
                time.mktime(entry.published_parsed), tz=timezone.utc
            )
            return dt, "low"
        except Exception:
            pass

    return None, "none"


def within_recency(pub_date):
    """Check if article is within RECENCY_FILTER_DAYS."""
    now = datetime.now(timezone.utc)
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    return (now - pub_date).days <= RECENCY_FILTER_DAYS


def grade_freshness(pub_date, date_confidence):
    """Grade freshness as current_cycle, edge_of_window, or trailing."""
    if pub_date is None:
        return "undated"

    now = datetime.now(timezone.utc)
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)

    age = (now - pub_date).days

    if age <= FRESH_CURRENT_DAYS:
        band = "current_cycle"
    elif age <= FRESH_EDGE_DAYS:
        band = "edge_of_window"
    else:
        band = "trailing"

    if date_confidence == "low" and band == "current_cycle":
        return "current_cycle_unconfirmed"

    return band


def generate_id(url):
    """Generate UUID5 from URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def strip_html(text):
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


# ============================================================================
# STAGE 2: PRE-FILTERS (AGNOSTIC, ADAPTIVE)
# ============================================================================

def filter_by_extraction_quality(signals):
    """
    Improvement #1: Automatic extraction quality gates.
    Sources with <MIN_EXTRACTION_COMPLETENESS_RATE get downsampled.
    Adapts to any feed quality without manual tuning.
    """
    if not signals:
        return signals, {}

    # Measure extraction quality per source
    source_metrics = {}
    signals_by_source = {}

    for signal in signals:
        source = signal["source_name"]
        if source not in signals_by_source:
            signals_by_source[source] = []
        signals_by_source[source].append(signal)

    filtered = []

    for source_name, source_signals in signals_by_source.items():
        complete_count = sum(1 for s in source_signals if s["content_completeness"] == "complete")
        complete_rate = complete_count / len(source_signals) if source_signals else 0
        source_metrics[source_name] = {
            "total": len(source_signals),
            "complete": complete_count,
            "complete_rate": complete_rate,
            "action": "full"
        }

        if complete_rate < MIN_EXTRACTION_COMPLETENESS_RATE:
            # Keep only complete articles from this source
            source_metrics[source_name]["action"] = "downsampled"
            source_signals = [s for s in source_signals if s["content_completeness"] == "complete"]
            print(f"  ⚠️  {source_name}: {complete_rate:.1%} complete → downsampled to {len(source_signals)} signals")

        filtered.extend(source_signals)

    return filtered, source_metrics


def filter_by_content_type(signals):
    """
    Improvement #4: Content-type filtering (before tagging).
    Pre-filter off-tier content (restaurant, hospitality, retail, etc.)
    to avoid wasting Claude tokens.
    """
    if not ENABLE_CONTENT_TYPE_FILTER:
        return signals, {}

    filtered = []
    off_tier_reasons = {}

    for signal in signals:
        title = signal["title"].lower()
        text_sample = signal["raw_text"][:800].lower()

        off_tier = False
        for keyword in OFF_TIER_KEYWORDS:
            if keyword in title or keyword in text_sample:
                off_tier = True
                off_tier_reasons[keyword] = off_tier_reasons.get(keyword, 0) + 1
                break

        if not off_tier:
            filtered.append(signal)
        else:
            signal["_filtered_reason"] = f"off_tier_keyword_detected"

    if off_tier_reasons:
        total_filtered = len(signals) - len(filtered)
        print(f"  📋 Content-type filter: removed {total_filtered} off-tier signals")

    return filtered, off_tier_reasons


def balance_sources_by_diversity(signals):
    """
    Improvement #2: Automatic source diversity balancing.
    Caps per-source signal count at 1.5x median to prevent over-weighting.
    Adapts to any feed size distribution.
    """
    if not ENABLE_SOURCE_BALANCING or not signals:
        return signals, {}

    signals_by_source = {}
    for signal in signals:
        source = signal["source_name"]
        if source not in signals_by_source:
            signals_by_source[source] = []
        signals_by_source[source].append(signal)

    # Calculate adaptive cap based on median source volume
    source_counts = [len(sigs) for sigs in signals_by_source.values()]
    median_count = sorted(source_counts)[len(source_counts) // 2]
    cap = max(int(median_count * SOURCE_DIVERSITY_MULTIPLIER), 15)  # min 15 per source

    balanced = []
    balancing_log = {}

    for source_name, source_signals in signals_by_source.items():
        if len(source_signals) > cap:
            # Keep most recent, random sample the rest to vary selection
            sorted_signals = sorted(
                source_signals,
                key=lambda s: s["published_date"] or "",
                reverse=True
            )
            kept = sorted_signals[:cap]
            remaining = sorted_signals[cap:]
            if remaining:
                kept.extend(random.sample(remaining, min(cap // 3, len(remaining))))

            balancing_log[source_name] = {
                "original": len(source_signals),
                "capped_at": len(kept),
                "cap_reason": f"exceeded {cap} (median={median_count}, multiplier={SOURCE_DIVERSITY_MULTIPLIER})"
            }
            print(f"  ⚖️  {source_name}: {len(source_signals)} → {len(kept)} signals (capped at {cap})")
            balanced.extend(kept)
        else:
            balancing_log[source_name] = {
                "original": len(source_signals),
                "capped_at": len(source_signals),
                "cap_reason": "within diversity threshold"
            }
            balanced.extend(source_signals)

    return balanced, balancing_log


def flag_recency_risks(signals):
    """
    Improvement #8: Recency risk detection.
    Flag signals within RECENCY_RISK_DAYS of the 60-day cutoff.
    They'll become stale next month.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=RECENCY_FILTER_DAYS)
    risk_threshold = cutoff_date + timedelta(days=RECENCY_RISK_DAYS)

    at_risk = 0
    for signal in signals:
        if signal["published_date"]:
            try:
                pub_dt = datetime.fromisoformat(signal["published_date"])
                if pub_dt < risk_threshold:
                    signal["recency_risk"] = "critical"
                    signal["days_until_stale"] = (
                        RECENCY_FILTER_DAYS - (datetime.now(timezone.utc) - pub_dt).days
                    )
                    at_risk += 1
                else:
                    signal["recency_risk"] = "safe"
            except Exception:
                signal["recency_risk"] = "unknown"
        else:
            signal["recency_risk"] = "undated"

    if at_risk > 0:
        print(f"  ⏰ {at_risk} signals nearing recency cutoff (will be stale in <{RECENCY_RISK_DAYS} days)")

    return signals


# ============================================================================
# STAGE 3: THEME GROUNDING VALIDATION (PRE-TAGGING FILTER)
# ============================================================================

def validate_theme_grounding(signal):
    """
    Improvement #5: Theme specificity validation (anti-hallucination).
    Spot-check: do the themes Claude assigned actually appear in source text?
    Downgrades strength if themes aren't grounded.
    """
    if not ENABLE_THEME_GROUNDING_VALIDATION:
        return signal

    # Sample check: only validate 10% for speed
    if random.random() > THEME_VALIDATION_SAMPLE_RATE:
        return signal

    themes = signal.get("themes", [])
    if not themes:
        return signal

    raw_text_lower = signal["raw_text"].lower()

    for theme in themes:
        theme_lower = theme.lower()

        # Direct match
        if theme_lower in raw_text_lower:
            continue

        # Key phrase match: at least one significant word from theme
        key_words = [w for w in theme.split() if len(w) > 4]
        if key_words and any(kw.lower() in raw_text_lower for kw in key_words):
            continue

        # Theme not grounded: downgrade strength
        if signal.get("signal_strength") in ("strong", "moderate"):
            signal["signal_strength"] = "weak"
            signal["grounding_check"] = "failed"
            signal["ungrounded_theme"] = theme
            return signal

    # All themes grounded
    signal["grounding_check"] = "passed"
    return signal


# ============================================================================
# STAGE 4: TAGGING (THE MAIN LLM STAGE)
# ============================================================================

INTERIOR_TAGGING_PROMPT = """
You are tagging signals about the luxury interior design
profession. These are articles from high-end interior design
publications. Your job is to identify what each signal reveals
about where the profession is moving.

Every signal here is already confirmed to be about the interior
design vertical, from a luxury-tier professional source, serving
the professional-trend question. So you do NOT tag vertical,
luxury fit, or question served. You tag what the signal is ABOUT
and where it sits in its trend lifecycle.

THEMES — open and emergent:
Generate the themes you actually observe. Do NOT map to a fixed
list. Name the specific movement, material, technique, reference,
or shift, using the language a luxury interior design
professional would use. Prefer specific over generic:
"limewash plaster walls" not "wall treatments"; "collectible
Italian postmodern" not "vintage furniture." 1-4 themes per
signal, each a short phrase.

LIFECYCLE:
- rising: gaining momentum, framed as emerging or returning
- peaking: at maximum attention, described as everywhere now
- stable: established, consistently present
- declining: fading, framed as overdone or past

SPECIFICITY:
- named: cites specific materials, designers, makers, places, or techniques by name
- directional: describes a movement or mood without named anchors

SIGNAL_STRENGTH:
- strong: clear, well-evidenced, multiple concrete details
- moderate: present but lighter evidence
- weak: passing mention, thin

TREND_SIGNAL — descriptive flag, NOT a filter:
Does this piece read as a trend signal on its own?
- yes: describes a movement/direction, generalizes across multiple projects or designers, or reports field-level recognition (awards, fairs, "what we're seeing")
- no: single-project coverage, product news, or profile with no movement framing

Metadata only — nothing is removed based on it. A "no" may still
carry a theme that converges with others in analysis.

LUXURY_CHECK — light validation:
- confirmed: reads as genuinely high-end / luxury
- off_tier: slipped through but reads as mass-market or budget

Return ONLY valid JSON. No preamble. No markdown fences.

{
  "tagged": [
    {
      "signal_id": "...",
      "themes": ["...", "..."],
      "lifecycle": "rising | peaking | stable | declining",
      "specificity": "named | directional",
      "signal_strength": "strong | moderate | weak",
      "trend_signal": "yes | no",
      "luxury_check": "confirmed | off_tier",
      "rationale": "one sentence on themes, lifecycle, trend_signal call"
    }
  ]
}
"""


def cap_strength_by_completeness(signal):
    """
    Improvement #7: Completeness-aware signal strength capping.
    Auto-cap strength based on extraction quality and evidence quantity.
    Signal strength should reflect confidence in the theme.
    """
    body_words = signal.get("body_word_count", 0)
    completeness = signal.get("content_completeness")
    current_strength = signal.get("signal_strength")

    if current_strength is None:
        return signal

    # Full body + complete extraction = trust original strength
    if completeness == "complete" and body_words >= 500:
        return signal

    # Partial extraction or 300-500 words = moderate strength max
    if completeness == "partial" or (300 <= body_words < 500):
        if current_strength == "strong":
            signal["signal_strength"] = "moderate"
            signal["strength_capped_reason"] = "partial_content"
        return signal

    # Thin evidence (summary_only or <300 words) = weak max
    if completeness == "summary_only" or body_words < 300:
        signal["signal_strength"] = "weak"
        signal["strength_capped_reason"] = "thin_evidence"
        return signal

    return signal


def tag_signals(signals: list) -> list:
    """
    Stage 4: tag in batches, merge back by signal_id.
    Sends only TAGGER_TEXT_LIMIT chars of raw_text; full body stays stored.
    Includes grounding validation post-tagging.
    """
    taggable = [s for s in signals if s["content_completeness"] != "empty"]
    tag_lookup = {}

    print(f"  Stage 4: Tagging {len(taggable)} signals in batches of {TAGGING_BATCH_SIZE}...")

    for i in range(0, len(taggable), TAGGING_BATCH_SIZE):
        batch = taggable[i : i + TAGGING_BATCH_SIZE]
        batch_num = (i // TAGGING_BATCH_SIZE) + 1
        total_batches = (len(taggable) + TAGGING_BATCH_SIZE - 1) // TAGGING_BATCH_SIZE

        batch_input = "\n\n".join(
            [
                f"signal_id: {s['signal_id']}\n"
                f"source: {s['source_name']}\n"
                f"completeness: {s['content_completeness']}\n"
                f"extraction_method: {s.get('extraction_method', 'unknown')}\n"
                f"text: {s['raw_text'][:TAGGER_TEXT_LIMIT]}"
                for s in batch
            ]
        )

        for attempt in range(2):
            try:
                response = client_api.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=3000,
                    system=INTERIOR_TAGGING_PROMPT,
                    messages=[{"role": "user", "content": batch_input}],
                )

                raw = response.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

                tagged = json.loads(raw.strip())

                for t in tagged.get("tagged", []):
                    tag_lookup[t["signal_id"]] = t

                print(f"    Batch {batch_num}/{total_batches} tagged")
                break

            except Exception as e:
                if attempt == 0:
                    print(f"    Batch {batch_num} failed, retrying...")
                    time.sleep(5)
                else:
                    print(f"    Batch {batch_num} failed: {e}")

    # Merge tags back into signals
    untagged_count = 0
    for s in signals:
        t = tag_lookup.get(s["signal_id"])

        if t:
            s["themes"] = t.get("themes", [])
            s["lifecycle"] = t.get("lifecycle")
            s["specificity"] = t.get("specificity")
            s["signal_strength"] = t.get("signal_strength")
            s["trend_signal"] = t.get("trend_signal")
            s["luxury_check"] = t.get("luxury_check")
            s["tag_rationale"] = t.get("rationale", "")

            # Apply completeness-aware strength capping (Improvement #7)
            s = cap_strength_by_completeness(s)

            # Apply theme grounding validation (Improvement #5)
            s = validate_theme_grounding(s)
        else:
            s["themes"] = []
            s["lifecycle"] = None
            s["specificity"] = None
            s["signal_strength"] = None
            s["trend_signal"] = None
            s["luxury_check"] = None
            s["tag_rationale"] = "untagged"
            untagged_count += 1

    if untagged_count > 0:
        print(f"  ⚠️  {untagged_count} signals fell through tagging — investigate batch failures")

    return signals


# ============================================================================
# MAIN RUNNER
# ============================================================================

def run_interior_professional_collection():
    """
    Main orchestrator: Four-stage pipeline with adaptive quality gates.
    Stage 1: Collect + normalize
    Stage 2: Pre-filter (extraction quality, content-type, diversity)
    Stage 3: Tag with Claude
    Stage 4: Validate themes + cap strength
    """
    from collectors.sources.interior_professional import INTERIOR_PROFESSIONAL_SOURCES

    start = datetime.now()
    print(
        f"\n{'='*70}"
    )
    print(
        f"Interior Professional Trend Collector — AGNOSTIC IMPROVEMENTS"
    )
    print(f"{start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    # STAGE 1: Collect + Normalize
    print("  STAGE 1: Collecting + normalizing (no LLM)...")
    collected = collect_interior_professional(INTERIOR_PROFESSIONAL_SOURCES)
    signals = collected["signals"]
    print(f"  ✓ {len(signals)} signals after Stage 1\n")

    # STAGE 2: Pre-filters (all adaptive, source-agnostic)
    print("  STAGE 2: Pre-filtering (extraction quality, content-type, diversity)...")

    # Filter #1: Extraction quality gates
    signals, extraction_metrics = filter_by_extraction_quality(signals)
    print(f"  ✓ After extraction quality filter: {len(signals)} signals\n")

    # Filter #4: Content-type filtering
    signals, off_tier_keywords = filter_by_content_type(signals)
    print(f"  ✓ After content-type filter: {len(signals)} signals\n")

    # Filter #2: Source diversity balancing
    signals, balancing_log = balance_sources_by_diversity(signals)
    print(f"  ✓ After source diversity balancing: {len(signals)} signals\n")

    # Flag #8: Recency risks
    signals = flag_recency_risks(signals)
    print(f"  ✓ After recency risk flagging: {len(signals)} signals\n")

    # STAGE 3: Tag with Claude (includes grounding validation)
    print("  STAGE 3-4: Tagging with theme grounding validation...")
    signals = tag_signals(signals)
    print(f"  ✓ Tagging complete\n")

    # Compute summary stats
    fresh_counts = {}
    trend_yes = 0
    off_tier = 0
    tagged_count = 0
    themes_with_grounding_check = 0

    for s in signals:
        fresh_counts[s["freshness"]] = fresh_counts.get(s["freshness"], 0) + 1
        if s.get("trend_signal") == "yes":
            trend_yes += 1
        if s.get("luxury_check") == "off_tier":
            off_tier += 1
        if s.get("themes"):
            tagged_count += 1
        if s.get("grounding_check"):
            themes_with_grounding_check += 1

    # Write outputs
    os.makedirs(INTERIOR_PRO_OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(INTERIOR_PRO_OUTPUT_DIR, "Professional Trends Data", "Research Data")
    os.makedirs(out_dir, exist_ok=True)

    # Main signals file only (no logs)
    output_filename = f"{date_str}_professional_trends_research.json"
    output_path = os.path.join(out_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "vertical": VERTICAL,
                "question_served": QUESTION_SERVED,
                "recency_filter_days": RECENCY_FILTER_DAYS,
                "signal_count": len(signals),
                "quality_gates_applied": {
                    "extraction_quality_filtering": len(extraction_metrics) > 0,
                    "content_type_filtering": len(off_tier_keywords) > 0,
                    "source_diversity_balancing": len(balancing_log) > 0,
                    "recency_risk_flagging": True,
                    "theme_grounding_validation": themes_with_grounding_check > 0
                },
                "signals": signals,
            },
            f,
            indent=2,
        )

    # Print summary
    succeeded = [
        f["source_name"]
        for f in collected["feed_log"]
        if f["status"] == "success"
    ]
    failed = [
        f["source_name"]
        for f in collected["feed_log"]
        if f["status"] != "success"
    ]

    print(f"\n{'='*70}")
    print(f"COLLECTION COMPLETE — Professional Trends Research")
    print(f"{'='*70}")
    print(f"  Signals (after all filters): {len(signals)}")
    print(f"  Sources succeeded:           {len(succeeded)}/{len(INTERIOR_PROFESSIONAL_SOURCES)}")
    if failed:
        print(f"  Sources failed:              {failed}")
    print(f"  Trend signals (yes):         {trend_yes}")
    print(f"  Off-tier flagged:            {off_tier}")
    print(f"  Freshness:                   {fresh_counts}")
    print(f"  Themes with grounding check: {themes_with_grounding_check}")
    print(f"  Duration:                    {(datetime.now() - start).seconds}s")
    print(f"  Output file:                 {output_path}")
    print(f"  Feed health tracking:        {FEED_HEALTH_TRACKING_ENABLED}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_interior_professional_collection()
