#!/usr/bin/env python3
"""
Artis Editorial Reasoning Engine
generate_editorial_briefs.py

Takes professional trend patterns, demand trend patterns, and a client blueprint,
and produces:
  1. {slug}_editorial_briefs_YYYY_MM.json  — full Editorial Opportunity Briefs,
     ranked editorial agenda, and strategic summary
  2. {slug}_strategy_YYYY_MM.json          — mapped to the build_dataset.js
     ClientStrategy data contract

This is an editorial reasoning engine, not a recommendation engine. It identifies
where emerging conversations intersect with a client's documented convictions and
determines whether the client should lead, reframe, cautiously acknowledge, or
ignore those conversations in public.

Usage:
  python generate_editorial_briefs.py \
    --pro       path/to/trend_patterns.json \
    --demand    path/to/demand_patterns.json \
    --blueprint path/to/ClientName-internal-blueprint-v6.md \
    --output    path/to/output_directory/
"""

import json
import argparse
import os
import sys
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# Load environment variables before initializing clients
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# UTF-8 handled by run wrapper / terminal

MODEL = "claude-sonnet-4-20250514"

# Initialize Anthropic client
try:
    client_api = anthropic.Anthropic()
except Exception as e:
    sys.stderr.write(f"ERROR: Failed to initialize Anthropic client: {e}\n")
    sys.exit(1)


# ============================================================================
# STEP 1 — Normalize trends (deterministic Python)
# ============================================================================

PRO_SIGNAL_MAP = {
    "rising":    "Rising",
    "peaking":   "Peaking",
    "stable":    "Steady",
    "declining": "Cooling",
}

DEM_SIGNAL_MAP = {
    "breakout":  "Surging",
    "rising":    "Rising",
    "steady":    "Steady",
    "declining": "Cooling",
}

CAT_KEYWORDS = {
    "colour":    ["colour", "color", "oxblood", "verdigris", "lacquer", "palette"],
    "nature":    ["garden", "plant", "botanical", "companion", "floricult", "flower", "outdoor", "wallpaper"],
    "market":    ["marketplace", "shopping", "retail", "platform", "business", "marketing", "event space"],
    "craft":     ["craft", "artisan", "ceramic", "stoneware", "murano", "glass", "millwork", "tile", "marquetry", "weaving"],
    "space":     ["bath", "kitchen", "retreat", "room", "wellness", "spa", "pantry", "closet", "wine", "shower"],
    "materials": ["brass", "steel", "stone", "marble", "travertine", "oak", "wood", "plaster", "burl", "linen"],
    "form":      ["seating", "furniture", "modular", "curved", "sofa", "sculptural", "revival", "modernism"],
}


def slug(s):
    """Slug function — must match build_dataset.js exactly."""
    return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', s.lower()))[:40]


def classify_category(label):
    l = label.lower()
    for cat in ["colour", "nature", "market", "craft", "space", "materials", "form"]:
        if any(k in l for k in CAT_KEYWORDS[cat]):
            return cat
    return "form"


def build_pro_blurb(p):
    """Compose a one-line professional blurb from the pattern."""
    label = p.get("theme_label", "")
    life = p.get("lifecycle_dominant", "")
    n_src = len(p.get("sources", []))
    src_word = "source" if n_src == 1 else "sources"
    tier = p.get("tier", "single_source").replace("_", " ")
    return f"{label} is {life} across {n_src} professional {src_word} ({tier})."


def build_dem_blurb(p):
    """Compose a one-line demand blurb from the pattern."""
    label = p.get("theme_label", "")
    traj = p.get("quant_trajectory") or p.get("direction", "steady")
    parts = [f"{label}: consumer demand {traj}"]
    if p.get("avg_mom_pct") is not None:
        parts.append(f"{p['avg_mom_pct']:+.0f}% MoM")
    if p.get("avg_yoy_pct") is not None:
        parts.append(f"{p['avg_yoy_pct']:+.0f}% YoY")
    if p.get("peak_idx") is not None:
        parts.append(f"idx {p['peak_idx']}")
    return " · ".join(parts) + "."


def normalize_pro(p):
    return {
        "trend_id":          "p-" + slug(p["theme_label"]),
        "lens":              "pro",
        "title":             p["theme_label"],
        "category":          classify_category(p["theme_label"]),
        "signal":            PRO_SIGNAL_MAP.get(p["lifecycle_dominant"], "Steady"),
        "momentum":          p["weighted_score"],
        "tier":              p.get("tier", "single_source"),
        "sources":           p.get("sources", []),
        "signal_count":      p.get("signal_count", 0),
        "trend_signal_rate": p.get("trend_signal_rate", 0),
        "blurb":             build_pro_blurb(p),
        "rationales":        [r["tag_rationale"] for r in p.get("representative_signals", [])
                              if r.get("tag_rationale")][:3],
        "raw": p,
    }


def normalize_dem(p):
    traj = p.get("quant_trajectory") or p.get("direction", "steady")
    return {
        "trend_id":     "d-" + slug(p["theme_label"]),
        "lens":         "dem",
        "title":        p["theme_label"],
        "category":     classify_category(p["theme_label"]),
        "signal":       DEM_SIGNAL_MAP.get(traj, "Steady"),
        "momentum":     p.get("weighted_score", 0),
        "tier":         p.get("tier_label", ""),
        "sources":      p.get("sources", []),
        "signal_count": p.get("signal_count", 0),
        "mom_pct":      p.get("avg_mom_pct"),
        "yoy_pct":      p.get("avg_yoy_pct"),
        "peak_idx":     p.get("peak_idx"),
        "trajectory":   traj,
        "blurb":        build_dem_blurb(p),
        "raw": p,
    }


# ============================================================================
# STEP 2 — Cross-pipeline matching (Claude API Call 1)
# ============================================================================

def cross_pipeline_match(pro_patterns, dem_patterns):
    """Match professional patterns to demand patterns (reused from generate_report.py)."""
    print("\nStep 2: Cross-pipeline matching...")

    pro_list = "\n".join([
        f"- {p['theme_label']} (lifecycle: {p.get('lifecycle_dominant')}, score: {p['weighted_score']})"
        for p in pro_patterns[:20]
    ])

    demand_list = "\n".join([
        f"- {p['theme_label']} (direction: {p.get('direction')}, sources: {p['source_count']})"
        for p in dem_patterns[:20]
    ])

    user_prompt = f"""Below are two lists of interior design trend patterns. Match where they describe the same concept.

For each match, assign: "convergent" (both signalling), "pro_leading" (pro ahead), or "demand_leading" (demand ahead).

Output ONLY JSON array. No explanation.
[{{"pro_label": "...", "demand_label": "...", "relationship": "..."}}, ...]

PROFESSIONAL PATTERNS:
{pro_list}

DEMAND PATTERNS:
{demand_list}"""

    try:
        response = client_api.messages.create(
            model=MODEL,
            max_tokens=2000,
            system="You are a luxury interior design trend analyst who matches professional and consumer trends.",
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        if not raw:
            print("  ⚠️  Cross-pipeline matching failed: Empty response")
            return []

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        matches = json.loads(raw)
        print(f"  ✓ Found {len(matches)} cross-pipeline matches")
        return matches

    except Exception as e:
        print(f"  ⚠️  Cross-pipeline matching failed: {e}")
        return []


# ============================================================================
# STEP 3 — Extract editorial profile (Claude API Call 2)
# ============================================================================

def extract_editorial_profile(blueprint_text):
    print("\nStep 3: Extracting editorial profile from blueprint...")

    system_prompt = (
        "You extract structured editorial profiles from luxury design client content blueprints. "
        "Your output is a precise JSON representation of the client's convictions, anti-beliefs, "
        "obsessions, voice constraints, and content quality tests. You extract what is documented — "
        "you do not infer, embellish, or add beliefs not evidenced in the text."
    )

    user_prompt = f"""Extract a structured editorial profile from this client blueprint. Every field must be
grounded in explicit evidence from the document.

Output ONLY a valid JSON object in this exact structure. No explanation, no markdown.

{{
  "client_name": "exact name from blueprint",
  "convictions": [
    {{
      "label": "short label",
      "statement": "the belief as a declarative sentence",
      "evidence": "direct quote or reference from blueprint",
      "strength": "non-negotiable | strong | consistent | weak"
    }}
  ],
  "anti_beliefs": [
    {{
      "category": "forbidden_framing | banned_terminology | aesthetic_pet_peeve | positioning_boundary | communication_style",
      "description": "what is rejected and why",
      "blueprint_source": "section or direct quote"
    }}
  ],
  "obsessions": [
    {{
      "topic": "the recurring theme",
      "evidence": "where it appears across the blueprint",
      "intensity": "defining | recurring | present"
    }}
  ],
  "voice_constraints": {{
    "sentence_structure": "description of preferred sentence forms",
    "registers": ["list of acceptable tonal registers"],
    "compression": "how much compression the voice requires",
    "pronouns": "acceptable pronoun usage",
    "rhetorical_tendencies": ["list of rhetorical moves the client uses"],
    "hard_boundaries": ["explicit voice rules from 2d. Voice Boundaries"]
  }},
  "content_tests": [
    {{
      "name": "test name e.g. Swap Test",
      "question": "the question this test asks",
      "fail_condition": "what failure looks like"
    }}
  ],
  "verbatim_phrases": ["exact phrases from 2b. Deploy These Verbatim"]
}}

BLUEPRINT:
{blueprint_text}"""

    response = client_api.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    profile = json.loads(raw)
    print(f"  ✓ Convictions: {len(profile.get('convictions', []))}, "
          f"Anti-beliefs: {len(profile.get('anti_beliefs', []))}, "
          f"Obsessions: {len(profile.get('obsessions', []))}, "
          f"Content tests: {len(profile.get('content_tests', []))}")
    return profile


# ============================================================================
# STEP 4 — Generate editorial briefs (Claude API Call 3, batched)
# ============================================================================

BATCH_SIZE = 8


def trend_context(t, cross_matches, all_dem, all_pro):
    obj = {
        "trend_id":   t["trend_id"],
        "title":      t["title"],
        "lens":       t["lens"],
        "category":   t["category"],
        "signal":     t["signal"],
        "momentum":   round(t["momentum"], 1),
        "tier":       t.get("tier", ""),
        "sources":    t.get("sources", []),
        "blurb":      t.get("blurb", ""),
        "rationales": t.get("rationales", []),
    }

    if t["lens"] == "pro":
        match = next((m for m in cross_matches if m.get("pro_label") == t["title"]), None)
        if match:
            dem = next((d for d in all_dem if d["title"] == match.get("demand_label")), None)
            if dem:
                obj["consumer_signal"] = {
                    "title":    dem["title"],
                    "signal":   dem["signal"],
                    "momentum": round(dem["momentum"], 1),
                    "mom_pct":  dem.get("mom_pct"),
                    "yoy_pct":  dem.get("yoy_pct"),
                    "sources":  dem.get("sources", []),
                }
                obj["convergence"] = match.get("relationship")

    if t["lens"] == "dem":
        match = next((m for m in cross_matches if m.get("demand_label") == t["title"]), None)
        if match:
            pro = next((p for p in all_pro if p["title"] == match.get("pro_label")), None)
            if pro:
                obj["professional_signal"] = {
                    "title":    pro["title"],
                    "signal":   pro["signal"],
                    "momentum": round(pro["momentum"], 1),
                    "tier":     pro.get("tier", ""),
                    "sources":  pro.get("sources", []),
                }
                obj["convergence"] = match.get("relationship")

    return obj


EDITORIAL_SYSTEM = (
    "You are the editorial creative director for Artis, a content strategy agency serving "
    "luxury residential design firms. You reason about trend data through the lens of a "
    "specific client's documented worldview.\n\n"
    "Your job is not to identify what is popular. Your job is to determine where emerging "
    "conversations intersect with this client's convictions — and whether the client should "
    "lead, reframe, cautiously acknowledge, or ignore those conversations in public.\n\n"
    "You reason with the precision of a creative director who has read the client blueprint "
    "many times. You do not produce generic recommendations. Every output must be specific "
    "to this client and could not be said by any of their competitors."
)


def build_editorial_prompt(client_name, editorial_profile, trend_contexts, batch_number, total_batches):
    return f"""Perform editorial reasoning for {client_name} against the following trends.
Use the editorial profile as the authoritative source of truth for this client's
identity, voice, and worldview.

---
EDITORIAL PROFILE
{json.dumps(editorial_profile, indent=2)}

---
TRENDS TO EVALUATE (batch {batch_number} of {total_batches})
{json.dumps(trend_contexts, indent=2)}

---
INSTRUCTIONS

For each trend, produce a complete Editorial Opportunity Brief by performing all
seven evaluations in order. Apply them rigorously. Do not default to generic language.
Every field must be specific to this client.

SEVEN EVALUATIONS:

1. BELIEF INTERACTION
   Which of the client's convictions does this trend reinforce, challenge, complicate,
   or contradict? Name the specific convictions involved. Assign conviction_collision
   0-100: trends activating non-negotiable convictions score 80+; aesthetic preferences
   score 30-60.

2. DISCERNMENT POTENTIAL
   Could a sophisticated observer reasonably disagree about this trend? Can this client
   contribute a nuanced perspective beyond mere description? Score 0-100: trends that
   only invite observation score low; trends generating tension or competing
   interpretations score high.

3. ANTI-PATTERN EXPOSURE
   Does this trend contain elements the client historically critiques? Check against
   the client's anti_beliefs. Score 0-100 based on how much anti-pattern material
   is present and how directly it conflicts.

4. SPECIFICITY POTENTIAL
   Can the client discuss this trend using concrete references — named materials,
   vendors, artworks, projects, techniques, objects, decisions? Score 0-100:
   abstract-only discussions score low; highly specific commentary scores high.
   The Swap Test: could this opinion be attributed to any competitor?
   Fail = 0; pass = score based on specificity level.

5. AUDIENCE ELEVATION
   Does the resulting perspective invite the audience into a more sophisticated way
   of seeing, rather than instructing or correcting? "You should" framing fails.
   Rewarding curiosity and discernment scores high. Score 0-100.

6. CONVERSATIONAL OWNERSHIP
   Would this client naturally volunteer an opinion without prompting? Distinguish
   between topics the client merely respects and topics the client repeatedly returns
   to. Score 0-100: passive appreciation = 20-40; defining obsession = 80-100.

7. MARKET CONTEXT
   Is consumer demand accelerating, cooling, or absent? Is professional adoption
   ahead of, behind, or aligned with consumer demand? Does expressing an opinion
   strengthen commercial relevance or drag the client into foreign territory?

EDITORIAL POSTURE — after all seven evaluations, determine one of:
- Agreement: trend reinforces existing convictions
- Critique: trend exposes anti-patterns worth challenging
- Reframe: underlying need is valid, prevailing interpretation is flawed
- Resistance: trend sits outside the client's worldview — ignore or reject
- Observation: client may acknowledge without adopting a position
- Curiosity: emerging interest not yet ready to own

BUSINESS RECOMMENDATION:
- Lead: editorial_opportunity_score >= 72 AND posture in (Agreement, Reframe, Critique)
- Watch: editorial_opportunity_score 45-71, OR posture = Observation/Curiosity
- Skip: editorial_opportunity_score < 45 OR posture = Resistance

VOICE OUTPUT — write likely_opinion in the client's authentic voice:
- Apply all voice_constraints from the editorial profile
- Apply all verbatim_phrases where they fit naturally — never forced
- The opinion must pass every content_test in the profile
- Swap Test: would this fail if the client's name were swapped for a competitor? If it
  would still work, rewrite until it cannot.
- Sophistication Test: does it reward discernment or perform expertise?

CONTENT ANGLES — provide 2-4 distinct angles (agreement/critique/reframe/observation/
resistance) representing different ways of discussing this trend while staying faithful
to the client's identity.

OUTPUT — valid JSON array of Editorial Opportunity Brief objects.
No explanation, no markdown, no preamble. Array only.

[
  {{
    "trend_id": "",
    "trend_title": "",
    "category": "",
    "trend_summary": "",
    "market_context": {{
      "professional_signal": {{
        "momentum": 0, "signal": "", "tier": "", "sources": [], "summary": ""
      }},
      "consumer_signal": {{
        "momentum": 0, "signal": "", "mom_growth": 0, "yoy_growth": 0, "summary": ""
      }},
      "convergence": {{ "status": "", "strength": 0, "summary": "" }}
    }},
    "editorial_reasoning": {{
      "activated_convictions": [],
      "anti_patterns_triggered": [],
      "belief_interaction": "",
      "discernment_opportunity": "",
      "audience_elevation": "",
      "specificity_opportunity": ""
    }},
    "editorial_position": {{
      "stance": "",
      "confidence": 0,
      "business_recommendation": "",
      "why_now": ""
    }},
    "voice_output": {{
      "likely_opinion": "",
      "voice_notes": [],
      "swap_test": true,
      "sophistication_test": true
    }},
    "content_angles": [
      {{ "type": "", "angle": "" }}
    ],
    "scoring": {{
      "conviction_collision": 0,
      "discernment": 0,
      "anti_pattern_exposure": 0,
      "specificity": 0,
      "audience_elevation": 0,
      "conversational_ownership": 0,
      "professional_momentum": 0,
      "consumer_momentum": 0,
      "convergence_strength": 0,
      "editorial_opportunity_score": 0
    }}
  }}
]"""


def _parse_json_array(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def call_editorial_reasoning(client_name, editorial_profile, batch, batch_number, total_batches):
    prompt = build_editorial_prompt(
        client_name, editorial_profile, batch, batch_number, total_batches
    )

    for attempt in (1, 2):
        try:
            response = client_api.messages.create(
                model=MODEL,
                max_tokens=7000,
                system=EDITORIAL_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            return _parse_json_array(raw)
        except Exception as e:
            if attempt == 1:
                print(f"    ⚠️  Batch {batch_number} parse/call failed (attempt 1): {e} — retrying...")
                time.sleep(2)
            else:
                print(f"    ❌ Batch {batch_number} failed twice: {e} — skipping batch")
                return []


def generate_editorial_briefs(client_name, editorial_profile, all_trends,
                              cross_matches, all_dem, all_pro):
    print("\nStep 4: Generating editorial briefs (batched)...")

    contexts = [trend_context(t, cross_matches, all_dem, all_pro) for t in all_trends]
    batches = [contexts[i:i + BATCH_SIZE] for i in range(0, len(contexts), BATCH_SIZE)]
    total_batches = len(batches)

    all_briefs = []
    for idx, batch in enumerate(batches, start=1):
        t0 = time.time()
        briefs = call_editorial_reasoning(
            client_name, editorial_profile, batch, idx, total_batches
        )
        all_briefs.extend(briefs)
        print(f"    Batch {idx}/{total_batches}: {len(briefs)} briefs ({time.time() - t0:.0f}s)")

    print(f"  ✓ Generated {len(all_briefs)} briefs from {len(all_trends)} trends")

    # Report any missing trend_ids
    produced_ids = {b.get("trend_id") for b in all_briefs}
    missing = [t["trend_id"] for t in all_trends if t["trend_id"] not in produced_ids]
    if missing:
        print(f"  ⚠️  Missing briefs for {len(missing)} trend_ids: {missing}")

    return all_briefs


# ============================================================================
# STEP 5 — Compute editorial_opportunity_score (deterministic Python)
# ============================================================================

WEIGHTS = {
    "conviction_collision":     0.20,
    "discernment":              0.15,
    "anti_pattern_exposure":    0.10,
    "specificity":              0.15,
    "audience_elevation":       0.10,
    "conversational_ownership": 0.15,
    "professional_momentum":    0.08,
    "consumer_momentum":        0.05,
    "convergence_strength":     0.02,
}


def compute_eos(scoring):
    return round(sum(scoring.get(k, 0) * w for k, w in WEIGHTS.items()), 1)


def enforce_recommendation(brief):
    eos = brief["scoring"]["editorial_opportunity_score"]
    stance = brief["editorial_position"].get("stance", "")
    if eos >= 72 and stance in ("Agreement", "Reframe", "Critique"):
        return "Lead"
    elif eos >= 45 and stance not in ("Resistance",):
        return "Watch"
    else:
        return "Skip"


def finalize_scores(all_briefs):
    print("\nStep 5: Computing editorial opportunity scores...")
    for brief in all_briefs:
        scoring = brief.setdefault("scoring", {})
        scoring["editorial_opportunity_score"] = compute_eos(scoring)
        brief.setdefault("editorial_position", {})
        brief["editorial_position"]["business_recommendation"] = enforce_recommendation(brief)
    print(f"  ✓ Scored and classified {len(all_briefs)} briefs")


# ============================================================================
# STEP 6 — Build ranked editorial agenda (deterministic Python)
# ============================================================================

def build_ranked_agenda(all_briefs):
    print("\nStep 6: Building ranked editorial agenda...")
    ranked = sorted(all_briefs, key=lambda x: -x["scoring"]["editorial_opportunity_score"])
    agenda = [
        {
            "rank": i + 1,
            "trend_id": b.get("trend_id", ""),
            "trend_title": b.get("trend_title", ""),
            "editorial_opportunity_score": b["scoring"]["editorial_opportunity_score"],
            "business_recommendation": b["editorial_position"]["business_recommendation"],
            "stance": b["editorial_position"].get("stance", ""),
            "category": b.get("category", ""),
        }
        for i, b in enumerate(ranked)
    ]
    print(f"  ✓ Ranked {len(agenda)} opportunities")
    return agenda


# ============================================================================
# STEP 7 — Generate strategic summary (Claude API Call 4)
# ============================================================================

def generate_strategic_summary(client_name, issue_label, editorial_profile,
                               ranked_agenda, lead_count, watch_count, skip_count):
    print("\nStep 7: Generating strategic summary...")

    system_prompt = (
        "You synthesize editorial strategy for luxury design clients. Given a ranked agenda of "
        "editorial opportunities and a client editorial profile, you identify the editorial "
        "territory this client should own this cycle and the narrative that unifies it."
    )

    convictions = [c.get("statement", "") for c in editorial_profile.get("convictions", [])]
    anti_beliefs = [a.get("description", "") for a in editorial_profile.get("anti_beliefs", [])]
    obsessions = [o.get("topic", "") for o in editorial_profile.get("obsessions", [])]

    user_prompt = f"""Generate a strategic summary for {client_name}, {issue_label}.

EDITORIAL PROFILE (abbreviated):
Convictions: {json.dumps(convictions)}
Anti-beliefs: {json.dumps(anti_beliefs)}
Obsessions: {json.dumps(obsessions)}

RANKED EDITORIAL AGENDA (top 10):
{json.dumps(ranked_agenda[:10], indent=2)}

RECOMMENDED MIX (derived from all trends):
Lead: {lead_count}, Watch: {watch_count}, Skip: {skip_count}

Output ONLY a valid JSON object. No explanation, no markdown.

{{
  "editorial_thesis": "2-3 sentences identifying the editorial territory available to
    this client this cycle. Specific to their convictions and the ranked opportunities.",

  "territories_to_own": ["3-5 specific thematic territories, not generic themes"],

  "territories_to_avoid": ["3-4 specific territories that would dilute the positioning"],

  "recommended_mix": {{
    "lead": {lead_count},
    "watch": {watch_count},
    "skip": {skip_count}
  }},

  "editorial_narrative": "2-3 sentences. The strategic logic unifying the agenda —
    why these opportunities exist for THIS client at THIS moment."
}}"""

    try:
        response = client_api.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        summary = json.loads(raw)
        print("  ✓ Strategic summary generated")
        return summary
    except Exception as e:
        print(f"  ⚠️  Strategic summary failed: {e} — using fallback")
        return {
            "editorial_thesis": "",
            "territories_to_own": [],
            "territories_to_avoid": [],
            "recommended_mix": {"lead": lead_count, "watch": watch_count, "skip": skip_count},
            "editorial_narrative": "",
        }


# ============================================================================
# STEP 8 — Extract client profile card (Claude API Call 5)
# ============================================================================

def extract_client_card(blueprint_text, editorial_profile, client_name):
    """Derive the UI Client-card fields (name, region, palette, etc.) from the blueprint."""
    print("\nStep 8: Extracting client profile card...")

    system_prompt = (
        "You extract a concise brand-identity card for a luxury interior design firm from its "
        "content blueprint. Output strict JSON only. Ground every field in the document — do not invent."
    )

    ctx = {
        "convictions": [c.get("statement") for c in editorial_profile.get("convictions", [])],
        "obsessions": [o.get("topic") for o in editorial_profile.get("obsessions", [])],
    }

    user_prompt = f"""From this blueprint, produce a brand-identity card as strict JSON (no markdown):

{{
  "name": "firm name",
  "principal": "lead designer full name",
  "region": "cities / markets, ' · '-separated",
  "base": "clientele or project types, short",
  "tagline": "<= 6 word positioning line in the firm's spirit",
  "aesthetic": "one-line design language",
  "palette": ["#hex", "#hex", "#hex"]
}}

Rules:
- palette = exactly 3 hex colors derived from NAMED materials, finishes, or signature
  colors in the blueprint (specific stones, metals, hues). Ground each in the text.
- tagline and aesthetic must use the firm's documented voice; no cliches.

EDITORIAL PROFILE (context):
{json.dumps(ctx)}

BLUEPRINT:
{blueprint_text}"""

    try:
        response = client_api.messages.create(
            model=MODEL, max_tokens=900,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        card = json.loads(raw)
        print(f"  ✓ Client card: {card.get('name')} — palette {card.get('palette')}")
        return card
    except Exception as e:
        print(f"  ⚠️  Client card extraction failed: {e} — using minimal fallback")
        return {
            "name": client_name, "principal": "", "region": "", "base": "",
            "tagline": "", "aesthetic": "", "palette": ["#6a4636", "#b07d33", "#cabfae"],
        }


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Artis Editorial Reasoning Engine")
    parser.add_argument("--pro", required=True, help="Path to professional trend_patterns.json")
    parser.add_argument("--demand", required=True, help="Path to demand_patterns.json")
    parser.add_argument("--blueprint", required=True, help="Path to client blueprint .md")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    t_start = time.time()
    print("=" * 80)
    print("ARTIS EDITORIAL REASONING ENGINE")
    print("=" * 80)

    # Load inputs
    with open(args.pro, encoding="utf-8") as f:
        pro_data = json.load(f)
    with open(args.demand, encoding="utf-8") as f:
        dem_data = json.load(f)
    with open(args.blueprint, encoding="utf-8") as f:
        blueprint_text = f.read()

    pro_patterns = pro_data["patterns"]
    dem_patterns = dem_data["patterns"]

    # ----- Step 1: Normalize -----
    print("\nStep 1: Normalizing trends...")
    all_pro = [normalize_pro(p) for p in pro_patterns]
    all_dem = [normalize_dem(p) for p in dem_patterns]
    all_trends = all_pro + all_dem
    print(f"  Normalized {len(all_pro)} professional trends, {len(all_dem)} demand trends.")

    # ----- Step 2: Cross-pipeline matching -----
    cross_matches = cross_pipeline_match(pro_patterns, dem_patterns)

    # ----- Step 3: Editorial profile -----
    editorial_profile = extract_editorial_profile(blueprint_text)
    client_name = editorial_profile.get("client_name", "Client")

    # ----- Step 4: Editorial briefs -----
    all_briefs = generate_editorial_briefs(
        client_name, editorial_profile, all_trends, cross_matches, all_dem, all_pro
    )

    if not all_briefs:
        sys.stderr.write("ERROR: No briefs generated. Aborting.\n")
        sys.exit(1)

    # ----- Step 5: Scores -----
    finalize_scores(all_briefs)

    # ----- Step 6: Ranked agenda -----
    ranked_agenda = build_ranked_agenda(all_briefs)

    # Mix counts
    lead_count = sum(1 for b in all_briefs
                     if b["editorial_position"]["business_recommendation"] == "Lead")
    watch_count = sum(1 for b in all_briefs
                      if b["editorial_position"]["business_recommendation"] == "Watch")
    skip_count = sum(1 for b in all_briefs
                     if b["editorial_position"]["business_recommendation"] == "Skip")

    # ----- Naming -----
    run_date = datetime.fromisoformat(pro_data["generated_at"])
    month_str = run_date.strftime("%Y_%m")
    issue_label = run_date.strftime("%B %Y")
    stem = Path(args.blueprint).stem
    slug_name = re.sub(r'-internal-blueprint.*$', '', stem)

    # ----- Step 7: Strategic summary -----
    strategic_summary = generate_strategic_summary(
        client_name, issue_label, editorial_profile, ranked_agenda,
        lead_count, watch_count, skip_count
    )

    # ----- Step 8: Write editorial_briefs.json -----
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    briefs_sorted = sorted(all_briefs, key=lambda x: -x["scoring"]["editorial_opportunity_score"])

    editorial_output = {
        "client": client_name,
        "issue": issue_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "editorial_profile_summary": {
            "conviction_count": len(editorial_profile.get("convictions", [])),
            "anti_belief_count": len(editorial_profile.get("anti_beliefs", [])),
            "obsession_count": len(editorial_profile.get("obsessions", [])),
            "content_test_count": len(editorial_profile.get("content_tests", [])),
        },
        "strategic_summary": strategic_summary,
        "editorial_agenda": ranked_agenda,
        "briefs": briefs_sorted,
    }

    briefs_path = output_dir / f"{slug_name}_editorial_briefs_{month_str}.json"
    with open(briefs_path, "w", encoding="utf-8") as f:
        json.dump(editorial_output, f, indent=2, ensure_ascii=False)

    # ----- Step 9: Write strategy.json (build_dataset.js contract) -----
    client_id = re.sub(r'-internal-blueprint.*$', '', stem).lower().replace('_', '-')

    picks = {}
    for brief in all_briefs:
        picks[brief["trend_id"]] = {
            "verdict": brief["editorial_position"]["business_recommendation"],
            "fit":     round(brief["scoring"]["editorial_opportunity_score"]),
            "why":     brief["editorial_position"].get("why_now", ""),
            "opinion": brief.get("voice_output", {}).get("likely_opinion", "")[:200],
        }

    strategy = {
        client_id: {
            "brief": (strategic_summary.get("editorial_thesis", "") + " " +
                      strategic_summary.get("editorial_narrative", "")).strip(),
            "counts": {
                "Lead":  sum(1 for p in picks.values() if p["verdict"] == "Lead"),
                "Watch": sum(1 for p in picks.values() if p["verdict"] == "Watch"),
                "Skip":  sum(1 for p in picks.values() if p["verdict"] == "Skip"),
            },
            "picks": picks,
        }
    }

    strategy_path = output_dir / f"{slug_name}_strategy_{month_str}.json"
    with open(strategy_path, "w", encoding="utf-8") as f:
        json.dump(strategy, f, indent=2, ensure_ascii=False)

    # ----- Step 8: Write client profile card (build_dataset.js Client contract) -----
    card = extract_client_card(blueprint_text, editorial_profile, client_name)
    parts = [p for p in re.split(r"\s+", (card.get("principal") or card.get("name") or client_name).strip()) if p]
    card["id"] = client_id  # MUST match the STRATEGY key
    card["initials"] = ("".join(p[0] for p in parts[:2]).upper() or "DM")
    card_path = output_dir / f"{slug_name}_client_{month_str}.json"
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2, ensure_ascii=False)

    # ----- Done -----
    print("\n" + "=" * 80)
    print("EDITORIAL REASONING COMPLETE")
    print("=" * 80)
    print(f"  Client:   {client_name}  ({client_id})")
    print(f"  Issue:    {issue_label}")
    print(f"  Trends:   {len(all_trends)}  |  Briefs: {len(all_briefs)}")
    print(f"  Mix:      Lead {lead_count} · Watch {watch_count} · Skip {skip_count}")
    print(f"  Duration: {time.time() - t_start:.0f}s")
    print(f"\n  📄 Briefs:   {briefs_path}")
    print(f"  📊 Strategy: {strategy_path}")
    print(f"  👤 Client:   {card_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    main()
