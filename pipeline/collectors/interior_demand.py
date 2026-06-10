"""
Interior Design Demand Pipeline

Collects demand signals from six sources across three paths:
- Path A: Quantitative (Pinterest, Google Trends) — trajectory/MoM/YoY numbers
- Path B: Qualitative Prose (Houzz, Sotheby's RSS) — article body extraction
- Path C: Qualitative Extracted (1stDibs, Real Estate Reports) — pre-extracted terms

All converge on a unified demand-signal record with themes, tier, source_weight,
and signal_type. Seasonal movement is never filtered — MoM is headline, YoY context.
"""

import feedparser
import trafilatura
import json
import os
import re
import time
import uuid
import glob
import random
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    DEMAND_INPUTS_DIR,
    DEMAND_OUTPUT_DIR,
    DEMAND_RECENCY_DAYS,
    DEMAND_TAGGING_BATCH_SIZE,
    TRAFILATURA_FAVOR_PRECISION,
    MIN_BODY_WORDS,
    TIER_WEIGHTS,
)

client_api = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

VERTICAL = "interior_design"
QUESTION_SERVED = "demand"


# ============================================================================
# DEMAND SIGNAL RECORD FACTORY
# ============================================================================

def make_signal(source_name: str, tier: int, signal_type: str, snapshot_date: str) -> dict:
    """
    Create a common demand-signal record. All sources normalize to this shape.
    signal_type: quantitative | qualitative_prose | qualitative_extracted
    """
    return {
        "signal_id": str(uuid.uuid4()),
        "vertical": VERTICAL,
        "question_served": QUESTION_SERVED,
        "source_name": source_name,
        "tier": tier,
        "source_weight": TIER_WEIGHTS.get(tier, 1),
        "signal_type": signal_type,
        "snapshot_date": snapshot_date,
        # term
        "term_raw": None,
        "themes": [],
        # quantitative fields (null for qualitative)
        "trajectory": None,
        "mom_pct": None,
        "yoy_pct": None,
        "idx": None,
        # qualitative fields (null for quantitative)
        "presence": None,  # featured | recurring | mentioned
        "context": None,
        "category": None,  # materials_finishes | styles | rooms | structural | color | other
        # shared
        "data_trust": "high",
        "tag_rationale": "",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# PATH C — MANUAL COWORK JSON INPUTS (Qualitative Extracted + Quantitative)
# ============================================================================

def ingest_manual_inputs(inputs_dir: str) -> list:
    """
    Read every *_demand_snapshot_*.json in the Inputs folder,
    route by its 'source' field, normalize into raw signal stubs.
    Quantitative numbers passed through; qualitative term lists flattened.
    """
    from collectors.sources.interior_demand import MANUAL_INPUT_SOURCES

    signals = []
    if not os.path.exists(inputs_dir):
        os.makedirs(inputs_dir, exist_ok=True)
        print(f"  Created inputs directory: {inputs_dir}")
        return signals

    files = glob.glob(os.path.join(inputs_dir, "*_demand_snapshot_*.json"))
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ⚠️  Skipping unreadable input {os.path.basename(path)}: {e}")
            continue

        source = data.get("source", "")
        cfg = MANUAL_INPUT_SOURCES.get(source)
        if not cfg:
            print(f"  ⚠️  Unknown source '{source}' in {os.path.basename(path)} — skipped")
            continue

        snapshot_date = data.get("snapshot_date", datetime.now().strftime("%Y-%m-%d"))
        tier = cfg["tier"]
        stype = cfg["signal_type"]

        if stype == "quantitative":
            signals.extend(_normalize_pinterest(data, source, tier, snapshot_date))
            print(f"  ✓ Ingested Pinterest snapshot: {len(signals)} signals")
        elif source == "1stdibs.com":
            signals.extend(_normalize_1stdibs(data, source, tier, snapshot_date))
            print(f"  ✓ Ingested 1stDibs snapshot: {len(signals)} signals")
        elif source == "luxury_real_estate_reports":
            signals.extend(_normalize_realestate(data, source, tier, snapshot_date))
            print(f"  ✓ Ingested real estate snapshot: {len(signals)} signals")

    return signals


def _normalize_pinterest(data: dict, source: str, tier: int, snapshot_date: str) -> list:
    """Path A/C prep: Pinterest quantitative — pass numbers through."""
    out = []
    tracked = data.get("tracked_keywords", {})

    cat_map = {
        "A_materials_and_finishes": "materials_finishes",
        "B_named_styles_and_movements": "styles",
        "C_rooms_with_luxury_intent": "rooms",
        "D_high_end_structural_millwork": "structural",
        "E_color_and_tonal_direction": "color",
    }

    # Tracked keywords — high trust
    for group_key, terms in tracked.items():
        category = cat_map.get(group_key, "other")
        for t in terms:
            if t.get("trajectory") == "no data":
                continue
            s = make_signal(source, tier, "quantitative", snapshot_date)
            s["term_raw"] = t.get("term")
            s["trajectory"] = t.get("trajectory")
            s["mom_pct"] = t.get("mom_pct")
            s["yoy_pct"] = t.get("yoy_pct")
            s["idx"] = t.get("idx")
            s["category"] = category
            s["data_trust"] = "high"
            out.append(s)

    # Category rising-terms — kept but low trust (guards the +10001% artifact)
    for ck in ("home_decor_rising_terms", "gardening_rising_terms"):
        for t in data.get("categories", {}).get(ck, []):
            s = make_signal(source, tier, "quantitative", snapshot_date)
            s["term_raw"] = t.get("term")
            s["mom_pct"] = t.get("mom_pct")
            s["trajectory"] = "category_rising"
            s["category"] = "other"
            s["data_trust"] = "low"
            s["context"] = f"Pinterest {ck} module"
            out.append(s)

    return out


def _normalize_1stdibs(data: dict, source: str, tier: int, snapshot_date: str) -> list:
    """Path C prep: 1stDibs extracted — flatten term lists with presence + category."""
    out = []
    sections = ["furniture", "lighting", "new_arrivals"]

    field_category = {
        "recurring_materials_finishes": "materials_finishes",
        "recurring_periods_styles": "styles",
        "recurring_designers_makers": "other",
        "featured_collections_themes": "other",
        "trending_popular_editors_picks": "other",
        "foregrounded": "other",
    }

    for sec in sections:
        block = data.get(sec, {})
        for field, category in field_category.items():
            for term in block.get(field, []):
                s = make_signal(source, tier, "qualitative_extracted", snapshot_date)
                s["term_raw"] = term
                # featured/trending => featured; recurring_* => recurring
                if field.startswith("recurring"):
                    s["presence"] = "recurring"
                elif "trending" in field or "featured" in field or field == "foregrounded":
                    s["presence"] = "featured"
                else:
                    s["presence"] = "mentioned"
                s["category"] = category
                s["context"] = f"1stDibs {sec} / {field}"
                out.append(s)

    return out


def _normalize_realestate(data: dict, source: str, tier: int, snapshot_date: str) -> list:
    """Path C prep: Real estate extracted — flatten findings with presence."""
    out = []
    ds = data.get("demand_signals", {})

    field_map = {
        "premium_amenities_features": ("rooms", "featured"),
        "emerging_in_demand_features": ("rooms", "featured"),
        "design_material_preferences": ("materials_finishes", "mentioned"),
        "notable_shifts": ("other", "mentioned"),
    }

    for field, (category, presence) in field_map.items():
        for term in ds.get(field, []):
            s = make_signal(source, tier, "qualitative_extracted", snapshot_date)
            s["term_raw"] = term
            s["presence"] = presence
            s["category"] = category
            s["context"] = f"real estate report / {field}"
            out.append(s)

    return out


# ============================================================================
# PATH B — RSS SOURCES (Qualitative Prose)
# ============================================================================

def collect_rss_demand(sources: list) -> tuple:
    """
    Pull RSS sources, fetch + extract article bodies with trafilatura,
    apply 60-day recency filter. Returns (signals, feed_log).
    """
    signals = []
    feed_log = []
    snapshot_date = datetime.now().strftime("%Y-%m-%d")

    for src in sources:
        result = {
            "source_name": src["source_name"],
            "status": "success",
            "found": 0,
            "kept": 0,
            "error": None,
        }

        try:
            feed = feedparser.parse(src["feed_url"])

            if feed.bozo and not feed.entries:
                result["status"] = "feed_failed"
                result["error"] = str(feed.bozo_exception)[:200]
                feed_log.append(result)
                continue

            result["found"] = len(feed.entries)

            for entry in feed.entries:
                pub_date = _entry_date(entry)
                if pub_date and (datetime.now(timezone.utc) - pub_date).days > DEMAND_RECENCY_DAYS:
                    continue

                url = entry.get("link", "")
                if not url:
                    continue

                body = _fetch_body(url, entry)
                if not body:
                    continue

                title = entry.get("title", "").strip()
                s = make_signal(
                    src["source_name"],
                    src["tier"],
                    "qualitative_prose",
                    snapshot_date,
                )
                s["term_raw"] = title
                s["context"] = f"{title}\n\n{body}"[:6000]  # body for tagger
                s["presence"] = "mentioned"
                signals.append(s)
                result["kept"] += 1

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)[:200]

        feed_log.append(result)
        time.sleep(1)

    return signals, feed_log


def _fetch_body(url: str, entry: dict) -> str:
    """Extract article body with trafilatura, fallback to RSS summary."""
    try:
        dl = trafilatura.fetch_url(url)
        if dl:
            body = trafilatura.extract(
                dl,
                include_comments=False,
                include_tables=False,
                favor_precision=TRAFILATURA_FAVOR_PRECISION,
            )
            if body and len(body.split()) >= MIN_BODY_WORDS:
                return body
            if body:
                return body
    except Exception:
        pass

    # Fallback to RSS summary
    summary = entry.get("summary", "") or entry.get("description", "")
    return re.sub(r"<[^>]+>", "", summary or "").strip() or None


def _entry_date(entry: dict) -> datetime:
    """Extract publish date from entry."""
    for f in ("published", "updated", "pubDate"):
        v = entry.get(f)
        if v:
            try:
                d = date_parser.parse(v)
                return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
            except Exception:
                continue
    return None


# ============================================================================
# PATH A — GOOGLE TRENDS (Automated Quantitative)
# ============================================================================

def collect_google_trends(keywords: list) -> list:
    """
    Pull MoM/YoY/index per keyword via pytrends.
    On 429 rate-limit, log and continue so partial pull yields signals.
    Seasonality is NOT removed — YoY carried as context only.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("  ⚠️  pytrends not installed — skipping Google Trends")
        return []

    signals = []
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    pytrends = TrendReq(hl="en-US", tz=360)

    # pytrends allows up to 5 terms per request
    for i in range(0, len(keywords), 5):
        batch = keywords[i : i + 5]

        for attempt in range(2):
            try:
                pytrends.build_payload(batch, timeframe="today 12-m", geo="US")
                df = pytrends.interest_over_time()

                if df.empty:
                    break

                for kw in batch:
                    if kw not in df.columns:
                        continue

                    series = df[kw]
                    mom = _pct_change(series, 4, 4)
                    yoy = _pct_change(series, 8, "first8")
                    idx = int(series.iloc[-1]) if len(series) else None

                    s = make_signal("Google Trends", 2, "quantitative", snapshot_date)
                    s["term_raw"] = kw
                    s["mom_pct"] = mom
                    s["yoy_pct"] = yoy
                    s["idx"] = idx
                    s["trajectory"] = _trajectory(mom)
                    s["data_trust"] = "high"
                    signals.append(s)

                break

            except Exception as e:
                if attempt == 0:
                    time.sleep(30)  # rate-limit backoff
                else:
                    print(f"  Google Trends batch failed (kept going): {e}")

        time.sleep(2)

    return signals


def _pct_change(series, recent_n: int, prior) -> float:
    """Calculate percent change MoM or YoY."""
    if len(series) < recent_n * 2:
        return None

    recent = series.iloc[-recent_n:].mean()

    if prior == "first8":
        base = series.iloc[:8].mean()
    else:
        base = series.iloc[-(recent_n * 2) : -recent_n].mean()

    if base == 0:
        return None

    return round((recent - base) / base * 100, 1)


def _trajectory(mom: float) -> str:
    """Map MoM percent to trajectory label."""
    if mom is None:
        return "no data"
    if mom > 40:
        return "breakout"
    if mom >= 20:
        return "rising"
    if mom >= 8:
        return "growing"
    if mom >= -8:
        return "steady"
    return "declining"


# ============================================================================
# STAGE 2 — TAGGING (Three Paths, One Output)
# ============================================================================

QUANT_TAG_PROMPT = """
You are normalizing demand-signal terms from luxury interior design
search data into consistent themes. Each term already carries its
own trajectory numbers — you do NOT assess trends or movement.

Your only job: for each term, produce 1-2 normalized themes — the
clean, canonical phrasing of what is being demanded. Collapse
variants to a shared theme so they match across sources.

Examples:
- "burl wood furniture" -> "burl wood"
- "limewash bedroom" and "limewash living room" -> "limewash"
- "marble kitchen" -> "marble"

Keep the theme specific and luxury-appropriate; do not flatten
"calacatta marble" all the way to "marble" if the specific stone
is named.

Return ONLY valid JSON, no fences:
{"tagged":[{"signal_id":"...","themes":["..."]}]}
"""

PROSE_TAG_PROMPT = """
You are tagging article content from luxury home / real estate
publications to extract DEMAND signal for interior design — what
features, materials, styles, or amenities the piece indicates
people want in high-end homes right now.

For each signal you receive the article text in its context field.

Produce:
- themes: 1-4 specific, luxury-appropriate emergent themes naming
  the materials, styles, features, or amenities the piece is about.
  Specific over generic ("limewash plaster" not "wall finishes").
- presence: how prominently the demand shows up:
  * featured (the piece is centrally about it)
  * recurring (mentioned as a notable trend among others)
  * mentioned (in passing)
- category: materials_finishes | styles | rooms | structural | color | other
- luxury_check: confirmed | off_tier (off if it reads mass-market/budget)

Do NOT assign trajectory or lifecycle — demand prose tells you
something is wanted/present, not its velocity.

Return ONLY valid JSON, no fences:
{"tagged":[{"signal_id":"...","themes":["..."],"presence":"...","category":"...","luxury_check":"..."}]}
"""

EXTRACTED_TAG_PROMPT = """
You are normalizing already-extracted demand terms from inherently
luxury sources (a high-end marketplace and luxury market reports)
into consistent themes for an interior design trend tool.

Each term already has a presence and category assigned. Your only
job: produce 1-2 normalized themes per term — the clean canonical
phrasing — so terms match across sources.

Collapse variants:
- "walnut burl" and "burl wood" -> "burl wood"
- "Murano glass" stays "Murano glass"

Designer/maker names: keep as the theme (e.g. "Paavo Tynell")
since named-maker demand is itself a signal.

Keep specificity; do not over-flatten named materials or periods.

Return ONLY valid JSON, no fences:
{"tagged":[{"signal_id":"...","themes":["..."]}]}
"""


def tag_all(signals: list) -> list:
    """Dispatch signals by signal_type to the appropriate tagger."""
    paths = {
        "quantitative": (QUANT_TAG_PROMPT, _merge_quant),
        "qualitative_prose": (PROSE_TAG_PROMPT, _merge_prose),
        "qualitative_extracted": (EXTRACTED_TAG_PROMPT, _merge_extracted),
    }

    for stype, (prompt, merge_fn) in paths.items():
        subset = [s for s in signals if s["signal_type"] == stype]
        if not subset:
            continue

        print(f"  Tagging {len(subset)} {stype} signals...")
        _run_tagger(subset, prompt, merge_fn)

    return signals


def _run_tagger(subset: list, prompt: str, merge_fn):
    """Batch tag signals via Claude."""
    for i in range(0, len(subset), DEMAND_TAGGING_BATCH_SIZE):
        batch = subset[i : i + DEMAND_TAGGING_BATCH_SIZE]
        batch_num = (i // DEMAND_TAGGING_BATCH_SIZE) + 1
        total_batches = (len(subset) + DEMAND_TAGGING_BATCH_SIZE - 1) // DEMAND_TAGGING_BATCH_SIZE

        payload = "\n\n".join(
            f"signal_id: {s['signal_id']}\nterm: {s['term_raw']}\n"
            f"category: {s['category']}\npresence: {s['presence']}\n"
            f"context: {(s['context'] or '')[:1500]}"
            for s in batch
        )

        lookup = {}

        for attempt in range(2):
            try:
                resp = client_api.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=3000,
                    system=prompt,
                    messages=[{"role": "user", "content": payload}],
                )

                raw = resp.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

                for t in json.loads(raw.strip()).get("tagged", []):
                    lookup[t["signal_id"]] = t

                break

            except Exception as e:
                if attempt == 0:
                    time.sleep(5)
                else:
                    print(f"    Batch {batch_num}/{total_batches} failed: {e}")

        for s in batch:
            merge_fn(s, lookup.get(s["signal_id"]))

        print(f"    Batch {batch_num}/{total_batches} tagged")


def _merge_quant(s: dict, t: dict):
    """Merge quantitative tag result."""
    s["themes"] = t.get("themes", []) if t else []
    if not s["themes"]:
        s["tag_rationale"] = "untagged"


def _merge_prose(s: dict, t: dict):
    """Merge qualitative prose tag result."""
    if t:
        s["themes"] = t.get("themes", [])
        s["presence"] = t.get("presence", s["presence"])
        s["category"] = t.get("category", s["category"])
        s["luxury_check"] = t.get("luxury_check")
    else:
        s["themes"] = []
        s["tag_rationale"] = "untagged"


def _merge_extracted(s: dict, t: dict):
    """Merge qualitative extracted tag result."""
    s["themes"] = t.get("themes", []) if t else []
    if not s["themes"]:
        s["tag_rationale"] = "untagged"


# ============================================================================
# MAIN RUNNER
# ============================================================================

def run_interior_demand():
    """Orchestrate all three collection paths, tag, output."""
    from collectors.sources.interior_demand import DEMAND_RSS_SOURCES

    if hasattr(run_interior_demand, '_running'):
        print("⚠️  Already running")
        return

    run_interior_demand._running = True

    try:
        start = datetime.now()
        print(f"\n{'='*70}")
        print(f"Interior Demand Pipeline — {start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        signals = []

        # PATH C — Manual Cowork JSON inputs
        print("  PATH C: Ingesting manual Cowork JSON inputs...")
        signals += ingest_manual_inputs(DEMAND_INPUTS_DIR)

        # PATH B — RSS demand sources
        print("  PATH B: Collecting RSS demand sources...")
        rss_signals, feed_log = collect_rss_demand(DEMAND_RSS_SOURCES)
        signals += rss_signals
        print(f"  ✓ Collected {len(rss_signals)} RSS signals")

        # PATH A — Google Trends
        print("  PATH A: Collecting Google Trends...")
        try:
            gt_signals = collect_google_trends(
                __import__(
                    "collectors.sources.interior_demand", fromlist=["GOOGLE_TRENDS_KEYWORDS"]
                ).GOOGLE_TRENDS_KEYWORDS
            )
            signals += gt_signals
            print(f"  ✓ Collected {len(gt_signals)} Google Trends signals")
        except Exception as e:
            print(f"  ⚠️  Google Trends unavailable: {e}")

        print(f"\n  Total signals before tagging: {len(signals)}")
        print("  Tagging across 3 paths...")
        signals = tag_all(signals)

        # Compute summary stats
        by_source = {}
        by_type = {}
        by_tier = {}

        for s in signals:
            by_source[s["source_name"]] = by_source.get(s["source_name"], 0) + 1
            by_type[s["signal_type"]] = by_type.get(s["signal_type"], 0) + 1
            by_tier[s["tier"]] = by_tier.get(s["tier"], 0) + 1

        # Write outputs
        date_str = datetime.now().strftime("%Y-%m-%d")
        from config import DEMAND_RESEARCH_DIR
        out_dir = DEMAND_RESEARCH_DIR
        os.makedirs(out_dir, exist_ok=True)

        output_filename = f"{date_str}_demand_trends_research.json"
        with open(
            os.path.join(out_dir, output_filename),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "vertical": VERTICAL,
                    "question_served": QUESTION_SERVED,
                    "signal_count": len(signals),
                    "by_source": by_source,
                    "by_signal_type": by_type,
                    "by_tier": by_tier,
                    "signals": signals,
                },
                f,
                indent=2,
            )

        # Print summary
        print(f"\n{'='*70}")
        print(f"DEMAND PIPELINE COMPLETE")
        print(f"{'='*70}")
        print(f"  Total signals:     {len(signals)}")
        print(f"  By source:         {by_source}")
        print(f"  By signal type:    {by_type}")
        print(f"  By tier:           {by_tier}")
        print(f"  Duration:          {(datetime.now() - start).seconds}s")
        print(f"  Output:            {out_dir}")
        print(f"{'='*70}\n")

    finally:
        delattr(run_interior_demand, '_running')


if __name__ == "__main__":
    run_interior_demand()
