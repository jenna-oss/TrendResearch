"""
Artis Demand Analyzer

Analyzes raw demand signals to extract, cluster, and rank luxury interior design demand patterns.

Input:  interior_demand_signals.json
Output: demand_patterns.json

Usage:
  python analyze_demand.py --input path/to/interior_demand_signals.json
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
QUANT_WEIGHT = {"breakout": 3.0, "growing": 2.0, "rising": 2.0, "steady": 1.0, "declining": 0.3}
QUAL_WEIGHT = {"featured": 2.0, "recurring": 1.5}

TRAJECTORY_RANKING = {"breakout": 4, "growing": 3, "rising": 3, "steady": 2, "declining": 1}


# ============================================================================
# STEP 1: Filter signals
# ============================================================================

def filter_signals(signals):
    """
    Remove signals with low data_trust or context containing "recurring_designers_makers".
    """
    filtered = []
    filtered_out = 0

    for sig in signals:
        # Filter rule 1: low data_trust
        if sig.get("data_trust") == "low":
            filtered_out += 1
            continue

        # Filter rule 2: recurring_designers_makers in context
        context = sig.get("context", "")
        if context and "recurring_designers_makers" in context.lower():
            filtered_out += 1
            continue

        filtered.append(sig)

    print(f"  Filtered {filtered_out} signals. {len(filtered)} remaining.")
    return filtered


# ============================================================================
# STEP 2: Extract unique themes with context
# ============================================================================

def extract_unique_themes(signals):
    """
    Extract unique raw theme strings with their strongest context.
    """
    theme_map = {}  # theme_string -> context_obj

    for sig in signals:
        source = sig.get("source_name", "unknown")
        tier = sig.get("tier", 2)
        signal_type = sig.get("signal_type", "unknown")

        # Build context based on signal type
        if signal_type == "quantitative":
            trajectory = sig.get("trajectory")
            mom = sig.get("mom_pct")
            yoy = sig.get("yoy_pct")
            idx = sig.get("idx")
            context = f"trajectory:{trajectory} mom:{mom}% yoy:{yoy}% idx:{idx}"
        elif signal_type == "qualitative_extracted":
            context = sig.get("context", "")
        elif signal_type == "qualitative_prose":
            context = (sig.get("context") or sig.get("term_raw", ""))[:300]
        else:
            context = ""

        for theme in sig.get("themes", []):
            if theme not in theme_map:
                # First occurrence, store it
                theme_map[theme] = {
                    "theme": theme,
                    "source": source,
                    "signal_type": signal_type,
                    "tier": tier,
                    "context": context,
                }
            else:
                # Prefer tier 1; if same tier, prefer quantitative with trajectory
                existing = theme_map[theme]
                if tier < existing["tier"]:
                    # Lower tier number = higher priority (tier 1 > tier 2)
                    theme_map[theme] = {
                        "theme": theme,
                        "source": source,
                        "signal_type": signal_type,
                        "tier": tier,
                        "context": context,
                    }
                elif tier == existing["tier"] and signal_type == "quantitative" and existing["signal_type"] != "quantitative":
                    # Prefer quantitative at same tier
                    theme_map[theme] = {
                        "theme": theme,
                        "source": source,
                        "signal_type": signal_type,
                        "tier": tier,
                        "context": context,
                    }

    unique_themes = list(theme_map.values())
    print(f"  Extracted {len(unique_themes)} unique raw theme strings from {len(signals)} signals")

    return unique_themes


# ============================================================================
# STEP 3: Normalize and cluster via Claude
# ============================================================================

def normalize_and_cluster_themes(unique_themes):
    """
    Send unique themes to Claude for clustering.
    Returns list of {label, variants} cluster objects.
    """
    if not unique_themes:
        return []

    # Limit themes to avoid Claude response truncation
    max_themes = 250
    if len(unique_themes) > max_themes:
        print(f"  WARNING: {len(unique_themes)} themes exceeds {max_themes} limit, sampling...")
        import random
        unique_themes = random.sample(unique_themes, max_themes)

    # Format theme input
    themes_json = json.dumps(unique_themes, indent=2)

    system_prompt = """You are a luxury residential design demand analyst. You understand what high-net-worth
clients search for, specify, and purchase — materials, finishes, styles, room types, and amenities. Your sources
include 1stDibs, Pinterest, Google Trends, Houzz, Sotheby's listings, and luxury real estate reports."""

    user_prompt = f"""Below is a list of theme strings from luxury interior design demand signals. Each entry
includes source, signal type, tier (1=HNW, 2=consumer search), and context.

Group them into clusters of related demand concepts. Assign each cluster a clean canonical label.

RULES:

1. Merge strings representing the same client demand across sources.
   Example: "wine cellar" (Pinterest, +386% yoy) and "wine cellar" (real estate report, featured) → one cluster.
   Example: "wellness amenities" (real estate) and "spa bathroom" (Pinterest, idx 100) → cluster as "spa and wellness spaces" if context confirms overlap.

2. Do NOT merge concepts with clearly different demand trajectories.
   "unlacquered brass" (steady, +37% yoy) and "antique brass" (declining, -38% yoy) are different — keep separate.

3. Houzz and Sotheby's themes are elaborate article phrases. Bridge them to simpler canonical terms where they
   clearly overlap with Pinterest/1stDibs signals. Keep as-is if no overlap exists.

4. Every input theme string must appear in exactly one cluster. Nothing left out.

5. Canonical labels should be concise and demand-fluent — how a luxury client or designer would describe
   the preference.

6. Output ONLY a valid JSON array. No explanation, no markdown, no preamble.
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
# STEP 4: Build lookup and group signals
# ============================================================================

def build_theme_lookup(clusters):
    """Build mapping from raw theme string to canonical label."""
    lookup = {}
    for cluster in clusters:
        label = cluster.get("label", "")
        for variant in cluster.get("variants", []):
            lookup[variant] = label
    return lookup


def group_signals_by_label(signals, theme_lookup):
    """Group signals by canonical label."""
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
    """Compute all metrics for a demand pattern group."""

    signal_count = len(signals)
    sources = set(sig.get("source_name") for sig in signals)
    source_count = len(sources)
    source_list = sorted(list(sources))

    # Tier presence
    t1_present = any(sig.get("tier") == 1 for sig in signals)
    t2_present = any(sig.get("tier") == 2 for sig in signals)

    # Weighted score
    weighted_score = 0.0
    for sig in signals:
        source_weight = 3 if sig.get("tier") == 1 else 2
        signal_type = sig.get("signal_type")

        if signal_type == "quantitative":
            trajectory = sig.get("trajectory")
            weight = QUANT_WEIGHT.get(trajectory, 0.5)
            weighted_score += source_weight * weight
        else:  # qualitative
            presence = sig.get("presence")
            weight = QUAL_WEIGHT.get(presence, 1.0)
            weighted_score += source_weight * weight

    weighted_score = round(weighted_score, 1)

    # Quantitative aggregates
    quant_signals = [
        s for s in signals
        if s.get("signal_type") == "quantitative" and s.get("data_trust") != "low"
    ]

    quant_trajectory = None
    avg_mom_pct = None
    avg_yoy_pct = None
    peak_idx = None

    if quant_signals:
        # Dominant trajectory
        traj_counts = defaultdict(int)
        for sig in quant_signals:
            traj = sig.get("trajectory")
            if traj:
                traj_counts[traj] += 1

        if traj_counts:
            quant_trajectory = max(
                traj_counts.keys(),
                key=lambda k: (traj_counts[k], TRAJECTORY_RANKING.get(k, 0)),
            )

        # Average MoM and YoY
        mom_values = [s.get("mom_pct") for s in quant_signals if s.get("mom_pct") is not None]
        yoy_values = [s.get("yoy_pct") for s in quant_signals if s.get("yoy_pct") is not None]
        idx_values = [s.get("idx") for s in quant_signals if s.get("idx") is not None]

        if mom_values:
            avg_mom_pct = round(sum(mom_values) / len(mom_values), 1)
        if yoy_values:
            avg_yoy_pct = round(sum(yoy_values) / len(yoy_values), 1)
        if idx_values:
            peak_idx = max(idx_values)

    # Direction label
    if quant_trajectory in ("breakout", "growing", "rising"):
        direction = "rising"
    elif quant_trajectory == "steady":
        direction = "steady"
    elif quant_trajectory == "declining":
        direction = "declining"
    elif t1_present and not t2_present:
        direction = "hnw_confirmed"
    else:
        direction = "present"

    # Tier label
    if t1_present and t2_present:
        tier_label = "cross_source"
    elif t1_present:
        tier_label = "hnw_only"
    elif t2_present:
        tier_label = "consumer_only"
    else:
        tier_label = "unknown"

    # Representative signals (top 3 by tier then strength)
    def sort_key(sig):
        tier_rank = 0 if sig.get("tier") == 1 else 1
        presence_rank = 1 if sig.get("presence") in ("featured", "recurring") else 0
        return (-tier_rank, -presence_rank)

    representative = sorted(signals, key=sort_key)[:3]
    representative_signals = [
        {
            "term_raw": sig.get("term_raw", ""),
            "source_name": sig.get("source_name", ""),
            "tier": sig.get("tier", 2),
            "signal_type": sig.get("signal_type", ""),
            "presence": sig.get("presence"),
            "trajectory": sig.get("trajectory"),
            "mom_pct": sig.get("mom_pct"),
            "yoy_pct": sig.get("yoy_pct"),
            "idx": sig.get("idx"),
        }
        for sig in representative
    ]

    return {
        "signal_count": signal_count,
        "source_count": source_count,
        "source_list": source_list,
        "t1_present": t1_present,
        "t2_present": t2_present,
        "weighted_score": weighted_score,
        "quant_trajectory": quant_trajectory,
        "avg_mom_pct": avg_mom_pct,
        "avg_yoy_pct": avg_yoy_pct,
        "peak_idx": peak_idx,
        "direction": direction,
        "tier_label": tier_label,
        "representative_signals": representative_signals,
    }


# ============================================================================
# STEP 6: Filter and rank
# ============================================================================

def filter_and_rank_patterns(patterns_data):
    """
    Filter out weak patterns and rank by convergence + strength.
    """
    filtered = []

    for label, strength in patterns_data.items():
        source_count = strength["source_count"]
        signal_count = strength["signal_count"]
        peak_idx = strength["peak_idx"]
        direction = strength["direction"]
        t1_present = strength["t1_present"]
        t2_present = strength["t2_present"]

        # Include rule 1: cross-source (2+ sources)
        if source_count >= 2:
            filtered.append((label, strength))
            continue

        # Include rule 2: strong single-source quantitative
        if peak_idx is not None and peak_idx >= 70 and direction in ("rising", "steady"):
            filtered.append((label, strength))
            continue

        # Include rule 3: multiple T1 signals
        if t1_present and signal_count >= 2:
            filtered.append((label, strength))
            continue

    # Sort: source_count desc, then weighted_score desc
    filtered.sort(key=lambda x: (-x[1]["source_count"], -x[1]["weighted_score"]))

    # Build final pattern list with rank
    patterns = []
    for rank, (label, strength) in enumerate(filtered, 1):
        pattern = {
            "rank": rank,
            "theme_label": label,
            "direction": strength["direction"],
            "tier_label": strength["tier_label"],
            "source_count": strength["source_count"],
            "sources": strength["source_list"],
            "t1_present": strength["t1_present"],
            "t2_present": strength["t2_present"],
            "signal_count": strength["signal_count"],
            "weighted_score": strength["weighted_score"],
            "quant_trajectory": strength["quant_trajectory"],
            "avg_mom_pct": strength["avg_mom_pct"],
            "avg_yoy_pct": strength["avg_yoy_pct"],
            "peak_idx": strength["peak_idx"],
            "representative_signals": strength["representative_signals"],
        }
        patterns.append(pattern)

    return patterns


# ============================================================================
# STEP 7: Write output
# ============================================================================

def write_output(output_path, input_signals, clusters, filtered_patterns):
    """
    Write analysis to JSON file.
    """
    # Count patterns by tier
    cross_source = sum(1 for p in filtered_patterns if p["source_count"] >= 2)
    single_source = sum(1 for p in filtered_patterns if p["source_count"] == 1)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vertical": "interior_design",
        "question_served": "demand",
        "input_signal_count": len(input_signals),
        "canonical_cluster_count": len(clusters),
        "trends_total": len(filtered_patterns),
        "trends_cross_source": cross_source,
        "trends_single_source": single_source,
        "patterns": filtered_patterns,
    }

    # Write to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"  Wrote {output_path}")
    print(f"    Patterns: {cross_source} cross-source, {single_source} single-source")


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def analyze_demand(input_path):
    """
    Main orchestrator for demand analysis.
    """

    print(f"\n{'='*80}")
    print(f"Artis Demand Analyzer")
    print(f"{'='*80}\n")

    # Load input
    print("Step 1: Filtering signals...")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    all_signals = data.get("signals", [])
    print(f"  Loaded {len(all_signals)} signals from {input_path}")

    signals = filter_signals(all_signals)

    # Extract unique themes
    print("\nStep 2: Extracting unique themes...")
    unique_themes = extract_unique_themes(signals)

    # Normalize and cluster
    print("\nStep 3: Normalizing and clustering themes...")
    clusters = normalize_and_cluster_themes(unique_themes)

    if not clusters:
        print("ERROR: Clustering failed")
        return

    # Build lookup
    print("\nStep 4: Building theme lookup and grouping signals...")
    theme_lookup = build_theme_lookup(clusters)
    print(f"  Built lookup for {len(theme_lookup)} theme mappings")

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
    print(f"  Filtered to {len(filtered_patterns)} qualified patterns")

    # Write output
    print("\nStep 7: Writing output...")
    output_dir = str(paths.DEM_ANALYSIS)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"{date_str}_demand_trends_analysis.json"
    output_path = os.path.join(output_dir, output_filename)

    write_output(output_path, signals, clusters, filtered_patterns)

    print(f"\n{'='*80}")
    print(f"Analysis complete")
    print(f"{'='*80}\n")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze luxury interior design demand from raw signals"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to demand_trends_research.json",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    analyze_demand(args.input)
