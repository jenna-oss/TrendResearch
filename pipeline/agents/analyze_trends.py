"""
Artis Trend Analyzer

Analyzes raw tagged signals to extract, cluster, and rank luxury interior design trends.

Input:  interior_professional_signals.json
Output: trend_patterns.json

Usage:
  python analyze_trends.py --input path/to/interior_professional_signals.json
"""

import json
import argparse
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict
import anthropic

# Make the pipeline dir importable so `import paths` works regardless of caller.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

# UTF-8 handled by run script

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Initialize Anthropic client (it reads ANTHROPIC_API_KEY from environment automatically)
try:
    client_api = anthropic.Anthropic()
except Exception as e:
    print(f"ERROR: Failed to initialize Anthropic client: {e}")
    sys.exit(1)

# Scoring weights
STRENGTH_WEIGHT = {"strong": 3, "moderate": 2, "weak": 1}
LIFECYCLE_WEIGHT = {"rising": 3, "peaking": 2, "stable": 1, "declining": 0}
FRESHNESS_WEIGHT = {"current_cycle": 1.0, "edge_of_window": 0.7, "trailing": 0.4, "undated": 0.3}
TREND_SIGNAL_WEIGHT = {"yes": 1.0, "no": 0.3}

LIFECYCLE_RANKING = {"rising": 3, "peaking": 2, "stable": 1, "declining": 0}


# ============================================================================
# STEP 1: Extract unique raw themes with context
# ============================================================================

def extract_unique_themes(signals):
    """
    Extract unique raw theme strings with their strongest context.
    Returns list of {theme, source, context} objects.
    """
    theme_map = {}  # theme_string -> (context_obj, strength_rank)

    for sig in signals:
        source = sig.get("source_name", "unknown")
        context = sig.get("tag_rationale", "")
        strength = sig.get("signal_strength", "weak")
        strength_rank = STRENGTH_WEIGHT.get(strength, 1)

        for theme in sig.get("themes", []):
            if theme not in theme_map:
                # First occurrence, store it
                theme_map[theme] = (
                    {"theme": theme, "source": source, "context": context},
                    strength_rank,
                )
            else:
                # Keep the one with higher strength
                existing_obj, existing_rank = theme_map[theme]
                if strength_rank > existing_rank:
                    theme_map[theme] = (
                        {"theme": theme, "source": source, "context": context},
                        strength_rank,
                    )

    unique_themes = [obj for obj, _ in theme_map.values()]
    print(f"  Extracted {len(unique_themes)} unique raw theme strings from {len(signals)} signals")

    return unique_themes


# ============================================================================
# STEP 2: Normalize and cluster via Claude
# ============================================================================

def normalize_and_cluster_themes(unique_themes):
    """
    Send unique themes to Claude for clustering.
    Returns list of {label, variants} cluster objects.
    """
    if not unique_themes:
        return []

    # Limit themes to avoid Claude response truncation
    # If too many, sample them
    max_themes = 250
    if len(unique_themes) > max_themes:
        print(f"  WARNING: {len(unique_themes)} themes exceeds {max_themes} limit, sampling...")
        import random
        unique_themes = random.sample(unique_themes, max_themes)

    # Format theme input
    themes_json = json.dumps(unique_themes, indent=2)

    system_prompt = """You are a luxury interior design trend analyst with deep fluency in professional design publications — Architectural Digest, Veranda, World of Interiors, Business of Home, Sight Unseen, Galerie. You understand the difference between a named designer movement, a material trend, a professional practice shift, and a cultural or historical reference."""

    user_prompt = f"""Below is a list of theme strings extracted from tagged luxury interior design articles. Each entry includes the publication it came from and the analyst's rationale for why it was tagged. Use this context to make accurate clustering decisions.

Group them into clusters of related concepts and assign each cluster a clean canonical label.

RULES:

1. Merge strings that describe the same underlying concept. Use the source and context to confirm — two themes from different articles with rationales pointing at the same movement or material should cluster together even if phrased differently.
   Example: "California casual luxury" (AD, "revival of Michael Taylor's West Coast look") and "California decorating heritage" (Elle Decor, "Michael S. Smith on the California design tradition") → one cluster.

2. Do NOT over-merge. Use the context to keep genuinely different things separate.
   "Murano glass processes" (Sight Unseen, "goti de fornasa glassblowing technique") and "ceramic-metal lighting collaborations" (Sight Unseen, "Devin Wilde ceramics paired with metal frameworks") are different trends even though both are craft materials. The rationales confirm they are separate.

3. Every input theme string must appear in exactly one cluster. Nothing left out.

4. The canonical label should be precise and luxury-fluent. Use the best phrasing from the input strings or a clean synthesized phrase if merging several.

5. Output ONLY a valid JSON array. No explanation, no markdown, no preamble.
   Format exactly:
   [
     {{"label": "canonical label", "variants": ["raw string 1", "raw string 2"]}},
     ...
   ]

THEME STRINGS WITH CONTEXT:

{themes_json}"""

    print("  Normalizing and clustering themes via Claude...")

    for attempt in range(2):
        try:
            response = client_api.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw = response.content[0].text.strip()

            # Parse JSON response
            clusters = json.loads(raw)

            print(f"  Claude returned {len(clusters)} clusters from {len(unique_themes)} raw theme strings")

            return clusters

        except json.JSONDecodeError as e:
            if attempt == 0:
                print(f"  JSON parse failed, retrying...")
            else:
                print(f"  CLUSTERING FAILED: {e}")
                return []
        except Exception as e:
            print(f"  CLUSTERING FAILED: {e}")
            return []

    return []


# ============================================================================
# STEP 3: Build lookup: raw theme → canonical label
# ============================================================================

def build_theme_lookup(clusters):
    """
    Build dictionary mapping raw theme strings to canonical labels.
    """
    lookup = {}
    for cluster in clusters:
        label = cluster.get("label", "")
        for variant in cluster.get("variants", []):
            lookup[variant] = label

    return lookup


# ============================================================================
# STEP 4: Group signals by canonical label
# ============================================================================

def group_signals_by_label(signals, theme_lookup):
    """
    For each canonical label, collect all signals that mention that label.
    """
    groups = defaultdict(list)

    for sig in signals:
        for raw_theme in sig.get("themes", []):
            canonical_label = theme_lookup.get(raw_theme)
            if canonical_label:
                groups[canonical_label].append(sig)

    return groups


# ============================================================================
# STEP 5: Compute pattern strength
# ============================================================================

def compute_pattern_strength(label, signals):
    """
    Compute all metrics for a pattern group.
    """
    signal_count = len(signals)
    sources = set(sig.get("source_name") for sig in signals)
    source_count = len(sources)
    source_list = sorted(list(sources))

    # 5a: Counts
    # (already computed above)

    # 5b: Weighted score
    weighted_score = 0.0
    for sig in signals:
        strength = sig.get("signal_strength", "weak")
        lifecycle = sig.get("lifecycle", "stable")
        freshness = sig.get("freshness", "undated")
        trend_signal = sig.get("trend_signal", "no")

        s_weight = STRENGTH_WEIGHT.get(strength, 1)
        l_weight = LIFECYCLE_WEIGHT.get(lifecycle, 0)
        f_weight = FRESHNESS_WEIGHT.get(freshness, 0.3)
        t_weight = TREND_SIGNAL_WEIGHT.get(trend_signal, 0.3)

        score = s_weight * l_weight * f_weight * t_weight
        weighted_score += score

    weighted_score = round(weighted_score, 1)

    # 5c: Lifecycle direction
    lifecycle_counts = defaultdict(int)
    for sig in signals:
        lc = sig.get("lifecycle", "stable")
        lifecycle_counts[lc] += 1

    lifecycle_dominant = max(
        lifecycle_counts.keys(),
        key=lambda k: (lifecycle_counts[k], LIFECYCLE_RANKING.get(k, 0)),
    )
    lifecycle_agreement = round(lifecycle_counts[lifecycle_dominant] / signal_count, 2)

    # 5d: Trend signal rate
    trend_yes = sum(1 for sig in signals if sig.get("trend_signal") == "yes")
    trend_signal_rate = round(trend_yes / signal_count, 2)

    # 5e: Luxury integrity
    luxury_confirmed = sum(
        1 for sig in signals if sig.get("luxury_check") == "confirmed"
    )
    luxury_integrity = round(luxury_confirmed / signal_count, 2)

    # 5f: Tier
    if source_count >= 3:
        tier = "confirmed"
    elif source_count == 2:
        tier = "cross_source"
    else:
        tier = "single_source"

    # 5g: Representative signals (top 3)
    def sort_key(sig):
        strength_rank = STRENGTH_WEIGHT.get(sig.get("signal_strength", "weak"), 1)
        trend_rank = 1 if sig.get("trend_signal") == "yes" else 0
        return (-strength_rank, -trend_rank)

    representative = sorted(signals, key=sort_key)[:3]
    representative_signals = [
        {
            "title": sig.get("title", ""),
            "source_name": sig.get("source_name", ""),
            "source_url": sig.get("source_url", ""),
            "lifecycle": sig.get("lifecycle", ""),
            "signal_strength": sig.get("signal_strength", ""),
            "freshness": sig.get("freshness", ""),
            "tag_rationale": sig.get("tag_rationale", ""),
        }
        for sig in representative
    ]

    return {
        "signal_count": signal_count,
        "source_count": source_count,
        "source_list": source_list,
        "weighted_score": weighted_score,
        "lifecycle_dominant": lifecycle_dominant,
        "lifecycle_agreement": lifecycle_agreement,
        "trend_signal_rate": trend_signal_rate,
        "luxury_integrity": luxury_integrity,
        "tier": tier,
        "representative_signals": representative_signals,
    }


# ============================================================================
# STEP 6: Filter and rank
# ============================================================================

def filter_and_rank_patterns(patterns_data):
    """
    Filter out low-quality patterns and rank by convergence + strength.
    """
    filtered = []

    for label, strength in patterns_data.items():
        # Filter rule 1: luxury_integrity < 0.5
        if strength["luxury_integrity"] < 0.5:
            continue

        # Filter rule 2: single signal + not a trend
        if strength["signal_count"] == 1 and strength["trend_signal_rate"] == 0:
            continue

        filtered.append(
            {
                "theme_label": label,
                "tier": strength["tier"],
                "source_count": strength["source_count"],
                "sources": strength["source_list"],
                "signal_count": strength["signal_count"],
                "weighted_score": strength["weighted_score"],
                "lifecycle_dominant": strength["lifecycle_dominant"],
                "lifecycle_agreement": strength["lifecycle_agreement"],
                "trend_signal_rate": strength["trend_signal_rate"],
                "luxury_integrity": strength["luxury_integrity"],
                "representative_signals": strength["representative_signals"],
            }
        )

    # Sort: source_count desc, then weighted_score desc
    filtered.sort(
        key=lambda p: (-p["source_count"], -p["weighted_score"])
    )

    # Assign ranks
    for i, pattern in enumerate(filtered, 1):
        pattern["rank"] = i

    return filtered


# ============================================================================
# STEP 7: Write output
# ============================================================================

def write_output(output_path, input_signals, clusters, filtered_patterns):
    """
    Write trend_patterns.json to disk.
    """
    # Count patterns by tier
    confirmed = sum(1 for p in filtered_patterns if p["tier"] == "confirmed")
    cross_source = sum(1 for p in filtered_patterns if p["tier"] == "cross_source")
    single_source = sum(1 for p in filtered_patterns if p["tier"] == "single_source")

    # Build output structure
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vertical": "interior_design",
        "question_served": "professional_trend",
        "input_signal_count": len(input_signals),
        "canonical_cluster_count": len(clusters),
        "patterns_total": len(filtered_patterns),
        "patterns_confirmed": confirmed,
        "patterns_cross_source": cross_source,
        "patterns_single_source": single_source,
        "patterns": filtered_patterns,
    }

    # Write to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"  Wrote {output_path}")
    print(f"    Patterns: {confirmed} confirmed, {cross_source} cross-source, {single_source} single-source")


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def analyze_trends(input_path):
    """
    Main orchestrator for trend analysis.
    """
    print(f"\n{'='*80}")
    print(f"Artis Trend Analyzer")
    print(f"{'='*80}\n")

    # Load input
    print("Step 1: Extracting unique themes...")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    signals = data.get("signals", [])
    print(f"  Loaded {len(signals)} signals from {input_path}")

    unique_themes = extract_unique_themes(signals)

    # Normalize and cluster
    print("\nStep 2: Normalizing and clustering themes...")
    clusters = normalize_and_cluster_themes(unique_themes)

    if not clusters:
        print("ERROR: Clustering failed")
        return

    # Build lookup
    print("\nStep 3: Building theme lookup...")
    theme_lookup = build_theme_lookup(clusters)
    print(f"  Built lookup for {len(theme_lookup)} theme mappings")

    # Group signals
    print("\nStep 4: Grouping signals by canonical label...")
    groups = group_signals_by_label(signals, theme_lookup)
    print(f"  Created {len(groups)} pattern groups")

    # Compute strengths
    print("\nStep 5: Computing pattern strength...")
    patterns_data = {}
    for label, group_signals in groups.items():
        patterns_data[label] = compute_pattern_strength(label, group_signals)

    # Filter and rank
    print("\nStep 6: Filtering and ranking patterns...")
    filtered_patterns = filter_and_rank_patterns(patterns_data)
    print(f"  Filtered to {len(filtered_patterns)} high-quality patterns")

    # Write output
    print("\nStep 7: Writing output...")
    output_dir = str(paths.PRO_ANALYSIS)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(output_dir, f"{date_str}_professional_trends_analysis.json")

    write_output(output_path, signals, clusters, filtered_patterns)

    print(f"\n{'='*80}")
    print(f"Analysis complete")
    print(f"{'='*80}\n")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze luxury interior design trends from raw signals"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to interior_professional_signals.json",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    analyze_trends(args.input)
