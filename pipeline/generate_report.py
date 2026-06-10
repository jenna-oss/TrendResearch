#!/usr/bin/env python3
"""
Artis Trend Report Generator

Takes professional and demand trend analysis outputs, performs cross-pipeline
matching, generates editorial briefs, and produces a branded PDF report.

Usage:
  python generate_report.py \
    --pro path/to/trend_patterns.json \
    --demand path/to/demand_patterns.json \
    --output optional/output/dir
"""

import json
import argparse
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
import html as html_lib
import anthropic

# Load environment variables before initializing clients
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# UTF-8 handled by run script

# Try to import playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️  Warning: playwright not installed. PDF generation will be skipped.")
    print("   Install with: pip install playwright && playwright install chromium")

# Initialize Anthropic client
try:
    client_api = anthropic.Anthropic()
except Exception as e:
    print(f"ERROR: Failed to initialize Anthropic client: {e}")
    sys.exit(1)


# ============================================================================
# STEP 1: Load and validate inputs
# ============================================================================

def load_and_validate(pro_path, demand_path):
    """Load and validate both JSON files."""
    print("\n" + "="*80)
    print("ARTIS TREND REPORT GENERATOR")
    print("="*80)

    print("\nStep 1: Loading and validating inputs...")

    # Load professional patterns
    with open(pro_path, encoding="utf-8") as f:
        pro_data = json.load(f)

    # Load demand patterns
    with open(demand_path, encoding="utf-8") as f:
        demand_data = json.load(f)

    # Validate
    assert pro_data.get("vertical") == "interior_design", "Professional data vertical mismatch"
    assert demand_data.get("vertical") == "interior_design", "Demand data vertical mismatch"
    assert len(pro_data.get("patterns", [])) > 0, "No professional patterns"
    assert len(demand_data.get("patterns", [])) > 0, "No demand patterns"

    pro_signal_count = pro_data.get("input_signal_count", 0)
    demand_signal_count = demand_data.get("input_signal_count", 0)
    pro_source_count = len(set(
        s for p in pro_data["patterns"] for s in p.get("sources", [])
    ))
    demand_source_count = len(set(
        s for p in demand_data["patterns"] for s in p.get("sources", [])
    ))

    print(f"  ✓ Professional: {len(pro_data['patterns'])} patterns, {pro_source_count} sources, {pro_signal_count} signals")
    print(f"  ✓ Demand: {len(demand_data['patterns'])} patterns, {demand_source_count} sources, {demand_signal_count} signals")

    return pro_data, demand_data, pro_signal_count, demand_signal_count, pro_source_count, demand_source_count


# ============================================================================
# STEP 2: Cross-pipeline matching
# ============================================================================

def cross_pipeline_match(pro_data, demand_data):
    """Match professional patterns to demand patterns."""
    print("\nStep 2: Cross-pipeline matching...")

    pro_list = "\n".join([
        f"- {p['theme_label']} (lifecycle: {p.get('lifecycle_dominant')}, score: {p['weighted_score']})"
        for p in pro_data["patterns"][:20]
    ])

    demand_list = "\n".join([
        f"- {p['theme_label']} (direction: {p.get('direction')}, sources: {p['source_count']})"
        for p in demand_data["patterns"][:20]
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
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system="You are a luxury interior design trend analyst who matches professional and consumer trends.",
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        if not raw:
            print(f"  ⚠️  Cross-pipeline matching failed: Empty response from Claude")
            return []

        # Try to extract JSON if Claude wrapped it in markdown
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
# STEP 3: Assign patterns to sections
# ============================================================================

def escape_html(text):
    """Escape HTML special characters."""
    return html_lib.escape(text)


def assign_to_sections(pro_data, demand_data, matches):
    """Assign patterns to report sections."""
    print("\nStep 3: Assigning patterns to sections...")

    # Build match lookup
    match_dict = {}
    for m in matches:
        pro_label = m.get("pro_label", "")
        demand_label = m.get("demand_label", "")
        relationship = m.get("relationship", "")
        match_dict[pro_label] = {"demand_label": demand_label, "relationship": relationship}
        match_dict[demand_label] = {"pro_label": pro_label, "relationship": relationship}

    sections = {
        "confirmed": [],
        "act_now": [],
        "horizon": [],
        "decline": [],
    }

    # Section 1: Confirmed Trends
    for d in demand_data["patterns"]:
        label = d["theme_label"]
        if match_dict.get(label, {}).get("relationship") == "convergent":
            sections["confirmed"].append(d)
        elif d["source_count"] >= 3:
            sections["confirmed"].append(d)

    sections["confirmed"] = sorted(
        sections["confirmed"][:6],
        key=lambda p: (-p.get("source_count", 0), -p.get("weighted_score", 0))
    )

    # Section 2: Act Now
    for d in demand_data["patterns"]:
        label = d["theme_label"]
        if label in [p["theme_label"] for p in sections["confirmed"]]:
            continue
        if d.get("direction") in ("rising", "breakout") and d.get("source_count", 0) >= 2:
            rel = match_dict.get(label, {}).get("relationship")
            if rel not in ("convergent", "pro_leading"):
                sections["act_now"].append(d)

    sections["act_now"] = sorted(
        sections["act_now"][:8],
        key=lambda p: (-(p.get("peak_idx") or 0), -(p.get("avg_yoy_pct") or 0))
    )

    # Section 3: On the Horizon
    for p in pro_data["patterns"]:
        label = p["theme_label"]
        if label in [pp["theme_label"] for pp in sections["confirmed"]]:
            continue
        if p.get("lifecycle_dominant") == "rising" and p.get("weighted_score", 0) >= 18:
            if not match_dict.get(label):
                sections["horizon"].append(p)

    sections["horizon"] = sorted(
        sections["horizon"][:5],
        key=lambda p: -p.get("weighted_score", 0)
    )

    # Section 4: Move Away From
    for d in demand_data["patterns"]:
        if d.get("direction") == "declining" and d.get("source_count", 0) >= 2:
            sections["decline"].append(d)

    sections["decline"] = sorted(
        sections["decline"],
        key=lambda p: p.get("avg_mom_pct", 0)
    )

    print(f"  ✓ Section 1 (Confirmed): {len(sections['confirmed'])} trends")
    print(f"  ✓ Section 2 (Act Now): {len(sections['act_now'])} trends")
    print(f"  ✓ Section 3 (Horizon): {len(sections['horizon'])} patterns")
    print(f"  ✓ Section 4 (Decline): {len(sections['decline'])} trends")

    return sections


# ============================================================================
# STEP 4: Generate briefs
# ============================================================================

def generate_briefs(sections, pro_data, demand_data):
    """Generate editorial briefs via Claude."""
    print("\nStep 4: Generating editorial briefs...")

    section_1_text = "\n".join([
        f"- {t['theme_label']}: {', '.join(t.get('sources', [])[:3])} | Score: {t.get('weighted_score')}"
        for t in sections["confirmed"]
    ])

    section_2_text = "\n".join([
        f"- {t['theme_label']}: {t.get('direction')} | {(t.get('avg_yoy_pct') or 0):.0f}% YoY | Idx {(t.get('peak_idx') or 0)}"
        for t in sections["act_now"]
    ])

    section_3_text = "\n".join([
        f"- {p['theme_label']}: {', '.join(p.get('sources', [])[:2])} | {p.get('lifecycle_dominant')}"
        for p in sections["horizon"]
    ])

    section_4_text = "\n".join([
        f"- {t['theme_label']}: {(t.get('avg_mom_pct') or 0):.1f}% MoM | {(t.get('avg_yoy_pct') or 0):.0f}% YoY"
        for t in sections["decline"]
    ])

    user_prompt = f"""Generate editorial brief text (2-3 sentences each) for these trends. Final sentence should be <strong>bolded action</strong>.

Also generate one-line data summaries (3-4 data points · separated, ALL CAPS) for the 5 marketing themes.

Output ONLY JSON:
{{
  "briefs": {{"trend_label": "brief text", ...}},
  "theme_data_lines": {{"Theme Title": "DATA · POINT · DATA", ...}}
}}

SECTION 1 — CONFIRMED TRENDS:
{section_1_text}

SECTION 2 — ACT NOW:
{section_2_text}

SECTION 3 — ON THE HORIZON:
{section_3_text}

SECTION 4 — MOVE AWAY FROM:
{section_4_text}"""

    try:
        response = client_api.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=4000,
            system="Write editorial briefs for luxury design firms. Direct, authoritative, specific. No fluff.",
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()

        if not raw:
            print(f"  ⚠️  Brief generation failed: Empty response — using fallback templates")
            return {}, {}

        # Try to extract JSON if Claude wrapped it in markdown
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        briefs = result.get("briefs", {})
        theme_data = result.get("theme_data_lines", {})
        if len(briefs) > 0:
            print(f"  ✓ Generated {len(briefs)} briefs and {len(theme_data)} theme data lines")
            print(f"    Claude brief keys: {list(briefs.keys())[:3]}...")
        else:
            print(f"  ⚠️  Claude generated 0 briefs")
        return briefs, theme_data

    except Exception as e:
        print(f"  ⚠️  Brief generation failed: {e} — using fallback templates")
        return {}, {}


def generate_missing_briefs(briefs, sections):
    """Generate fallback briefs for trends that Claude missed."""
    fallback_templates = {
        "confirmed": "Confirmed by both professional publications and consumer demand. <strong>Prioritize this direction.</strong>",
        "act_now": "Rising demand with strong professional validation. <strong>Develop positioning immediately.</strong>",
        "horizon": "Emerging in professional circles ahead of mainstream adoption. <strong>Monitor and prepare assets.</strong>",
        "decline": "Declining across sources. <strong>Transition audience away from this aesthetic.</strong>"
    }

    for section_type, trends in sections.items():
        for trend in trends:
            label = trend["theme_label"]
            if label not in briefs:
                briefs[label] = fallback_templates.get(section_type, fallback_templates["horizon"])
                print(f"    Added fallback brief for: {label}")

    return briefs


# ============================================================================
# STEP 5: Build HTML
# ============================================================================

def format_source_line(pattern):
    """Format source line for display."""
    src_map = {
        "Architectural Digest": "AD",
        "trends.pinterest.com": "Pinterest",
        "1stdibs.com": "1stDibs",
        "Google Trends": "Google Trends",
        "Houzz": "Houzz",
        "luxury_real_estate_reports": "Real Estate",
        "Sotheby's International Realty (Extraordinary Living)": "Sotheby's",
        "The World of Interiors": "World of Interiors",
        "Veranda": "Veranda",
        "Business of Home": "BoH",
    }

    parts = []
    for src in pattern.get("sources", [])[:3]:
        parts.append(src_map.get(src, src))

    if pattern.get("avg_yoy_pct") and abs(pattern["avg_yoy_pct"]) > 10:
        yoy = pattern["avg_yoy_pct"]
        parts.append(f"{'+' if yoy > 0 else ''}{yoy:.0f}% YoY")

    if pattern.get("peak_idx") and pattern["peak_idx"] >= 70:
        parts.append(f"Idx {pattern['peak_idx']}")

    return " · ".join(parts)


def format_decline_stat(pattern):
    """Format decline statistics."""
    parts = []
    if pattern.get("avg_mom_pct"):
        parts.append(f"{pattern['avg_mom_pct']:+.1f}% MoM")
    if pattern.get("avg_yoy_pct"):
        parts.append(f"{pattern['avg_yoy_pct']:+.1f}% YoY")
    if pattern.get("peak_idx") is not None:
        parts.append(f"Idx {pattern['peak_idx']}")
    return " · ".join(parts) if parts else "Declining"


def build_section_html(section_type, trends, briefs):
    """Build HTML for sections 1, 2, 4."""
    html = ""
    for t in trends:
        label = escape_html(t["theme_label"])
        brief = escape_html(briefs.get(t["theme_label"], "No brief available."))
        sources = format_source_line(t)

        if section_type == "decline":
            stat = format_decline_stat(t)
            html += f"""
    <div class="decline-entry">
      <div>
        <div class="decline-name">{label}</div>
        <div class="decline-stat">{stat}</div>
      </div>
      <p class="decline-reason">{brief}</p>
    </div>"""
        else:
            html += f"""
    <div class="trend-entry">
      <div class="trend-name">{label}</div>
      <div class="trend-sources">{sources}</div>
      <p class="trend-brief">{brief}</p>
    </div>"""

    return html


def build_horizon_html(patterns, briefs):
    """Build HTML for Section 3 (On the Horizon)."""
    html = ""
    for p in patterns:
        label = escape_html(p["theme_label"])
        brief = escape_html(briefs.get(p["theme_label"], "No brief available."))
        sources = "<br>".join([
            {
                "Architectural Digest": "AD",
                "Elle Decor": "Elle Decor",
                "Veranda": "Veranda",
                "Business of Home": "BoH",
                "Sight Unseen": "Sight Unseen",
                "Galerie": "Galerie",
                "The World of Interiors": "WoI",
                "Dezeen": "Dezeen",
            }.get(s, s) for s in p.get("sources", [])[:3]
        ])

        html += f"""
    <div class="horizon-entry">
      <div class="horizon-source">{sources}<br>Rising</div>
      <div>
        <div class="horizon-name">{label}</div>
        <p class="horizon-brief">{brief}</p>
      </div>
    </div>"""

    return html


def build_section_5_html(theme_data_lines):
    """Build Section 5 (Marketing Themes)."""
    themes = [
        {
            "number": "Theme 01",
            "title": "The Specific Specialist",
            "body": "Generic luxury language is losing search effectiveness. Clients are not searching for \"luxury\" — they are searching for the exact thing they want. The firms that name what they do specifically are more findable, more memorable, and attract clients who have already decided they want what that firm offers.",
            "pivot_label": "The positioning shift",
            "pivot": "Away from \"We create beautiful, luxurious spaces\" — toward naming the specific spaces, materials, and capabilities that define the practice. The designer known for extraordinary primary suites attracts exactly those clients.",
        },
        {
            "number": "Theme 02",
            "title": "The Home as Sanctuary",
            "body": "The most confirmed macro theme across both datasets. This extends beyond bathrooms — nostalgic gardens, biodynamic planting, naturalistic landscapes, and restorative materials are all rising in parallel. The aspiration is shifting from \"impressive\" to \"restorative.\" HNW clients want homes that give energy back.",
            "pivot_label": "The positioning shift",
            "pivot": "Away from showcasing drama and visual complexity — toward showing how a space makes daily life quieter, slower, and more restored. Every room has a primary function that serves the person living in it.",
        },
        {
            "number": "Theme 03",
            "title": "Restraint as Conviction",
            "body": "The professional world is converging on a counter-aesthetic to the maximalist moment — honest materials, decisive editing, confidence without excess. Maximalist and organic modern are both confirmed declining. What's replacing them has no agreed name yet, but the direction is unambiguous: less is decisive, not minimal.",
            "pivot_label": "The positioning shift",
            "pivot": "Away from styling, layering, and opulence — toward editing, restraint, and conviction. The vocabulary: considered, honest, authentic, deliberate. Every element in the room is there because it belongs there.",
        },
        {
            "number": "Theme 04",
            "title": "Material Authorship",
            "body": "Clients are searching by specific material name, not by room or style. They know these terms and they're looking for designers who know them better. Designers who speak fluently about why they chose a specific material — its provenance, its maker, its properties — convert skeptical luxury clients.",
            "pivot_label": "The positioning shift",
            "pivot": "Away from beautiful imagery with minimal explanation — toward named materials, named makers, sourcing decisions, technique. Not \"a custom light fixture\" but the specific glassblower, the specific process, and why it was chosen.",
        },
        {
            "number": "Theme 05",
            "title": "Place and Character",
            "body": "Abstract style labels are losing relevance while place-rooted aesthetics are ascending. Designers whose work has a distinct character tied to place, climate, or cultural origin have a stronger positioning story than those working in abstract style categories.",
            "pivot_label": "The positioning shift",
            "pivot": "Away from style category labels — toward a sense of place, climate, and character. What makes your work feel rooted in where it exists? What influences from the world outside design shape how you see a space?",
        },
    ]

    html = ""
    for t in themes:
        data_line = escape_html(theme_data_lines.get(t["title"], ""))
        body = escape_html(t["body"])
        pivot = escape_html(t["pivot"])

        html += f"""
    <div class="theme-entry">
      <div class="theme-number">{t['number']}</div>
      <div class="theme-title">{t['title']}</div>
      <div class="theme-data">{data_line}</div>
      <p class="theme-body">{body}</p>
      <div class="theme-pivot">
        <span class="theme-pivot-label">{t['pivot_label']}</span>
        {pivot}
      </div>
    </div>"""

    return html


# ============================================================================
# STEP 6: Generate PDF
# ============================================================================

def generate_pdf(html_content, output_path):
    """Generate PDF from HTML using Playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        print(f"  ⚠️  PDF generation skipped (playwright not installed)")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            page.set_content(html_content, wait_until="domcontentloaded")

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
                prefer_css_page_size=False,
            )

            browser.close()
            return True

    except Exception as e:
        print(f"  ⚠️  PDF generation failed: {e}")
        return False


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate Artis Trend Report")
    parser.add_argument("--pro", required=True, help="Path to professional trends JSON")
    parser.add_argument("--demand", required=True, help="Path to demand trends JSON")
    parser.add_argument("--output", help="Output directory (defaults to pro input directory)")

    args = parser.parse_args()

    # Step 1: Load and validate
    pro_data, demand_data, pro_sig, demand_sig, pro_src, demand_src = load_and_validate(
        args.pro, args.demand
    )

    # Step 2: Cross-pipeline matching
    matches = cross_pipeline_match(pro_data, demand_data)

    # Step 3: Assign to sections
    sections = assign_to_sections(pro_data, demand_data, matches)

    # Step 4: Generate briefs
    briefs, theme_data_lines = generate_briefs(sections, pro_data, demand_data)

    # Fill in any missing briefs with fallback templates
    briefs = generate_missing_briefs(briefs, sections)

    # Step 5: Build HTML
    print("\nStep 5: Building HTML report...")

    report_date = datetime.fromisoformat(pro_data["generated_at"])
    month_year = report_date.strftime("%B %Y")
    year = report_date.strftime("%Y")

    s1_html = build_section_html("trend", sections["confirmed"], briefs)
    s2_html = build_section_html("trend", sections["act_now"], briefs)
    s3_html = build_horizon_html(sections["horizon"], briefs)
    s4_html = build_section_html("decline", sections["decline"], briefs)
    s5_html = build_section_5_html(theme_data_lines)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Artis — Interior Design Trend Report — {month_year}</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Jost:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg:          #EDE5CF;
    --text:        #1C0707;
    --text-dim:    #5A2C2C;
    --text-faint:  #9C7070;
    --maroon:      #2A0909;
    --rule:        rgba(42,9,9,0.12);
    --rule-strong: rgba(42,9,9,0.28);
  }}
  body {{
    background: var(--bg); color: var(--text);
    font-family: 'Jost', sans-serif; font-weight: 300;
    font-size: 15px; line-height: 1.7;
    -webkit-font-smoothing: antialiased;
  }}
  .page {{ max-width: 820px; margin: 0 auto; padding: 0 48px 0; }}
  .report-header {{
    padding: 56px 0 48px; border-bottom: 1px solid var(--rule-strong);
    display: flex; justify-content: space-between; align-items: flex-end;
  }}
  .brand-name {{
    font-family: 'Cormorant Garamond', serif; font-weight: 300;
    font-size: 46px; letter-spacing: 0.04em; line-height: 1; color: var(--maroon);
  }}
  .brand-tag {{
    font-size: 10.5px; letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--text-faint); margin-top: 7px;
  }}
  .report-title {{
    text-align: right; font-size: 10.5px; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--text-faint); line-height: 2;
  }}
  .report-intro {{ padding: 48px 0; border-bottom: 1px solid var(--rule); }}
  .intro-headline {{
    font-family: 'Cormorant Garamond', serif; font-size: 36px; font-weight: 300;
    line-height: 1.3; color: var(--maroon); max-width: 600px; margin-bottom: 20px;
  }}
  .intro-body {{ font-size: 14px; line-height: 1.9; color: var(--text-dim); max-width: 580px; }}
  .report-section {{ padding: 56px 0; border-bottom: 1px solid var(--rule); }}
  .section-eyebrow {{
    font-size: 10px; letter-spacing: 0.26em; text-transform: uppercase;
    color: var(--text-faint); margin-bottom: 10px;
  }}
  .section-title {{
    font-family: 'Cormorant Garamond', serif; font-weight: 400;
    font-size: 30px; color: var(--maroon); margin-bottom: 10px;
  }}
  .section-subtitle {{
    font-size: 13.5px; color: var(--text-dim); line-height: 1.8;
    max-width: 560px; margin-bottom: 44px;
  }}
  .trend-entry {{ padding: 32px 0; border-top: 1px solid var(--rule); }}
  .trend-entry:first-child {{ border-top: none; padding-top: 0; }}
  .trend-name {{
    font-family: 'Cormorant Garamond', serif; font-size: 23px; font-weight: 400;
    color: var(--maroon); margin-bottom: 10px; line-height: 1.2;
  }}
  .trend-sources {{
    font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--text-faint); margin-bottom: 16px;
  }}
  .trend-brief {{ font-size: 14px; color: var(--text-dim); line-height: 1.85; max-width: 640px; }}
  .trend-brief strong {{ color: var(--text); font-weight: 400; }}
  .horizon-entry {{
    padding: 30px 0; border-top: 1px solid var(--rule);
    display: grid; grid-template-columns: 130px 1fr; gap: 32px; align-items: start;
  }}
  .horizon-entry:first-child {{ border-top: none; padding-top: 0; }}
  .horizon-source {{
    font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--text-faint); padding-top: 4px; line-height: 2;
  }}
  .horizon-name {{
    font-family: 'Cormorant Garamond', serif; font-size: 21px; font-weight: 400;
    color: var(--maroon); margin-bottom: 10px; line-height: 1.25;
  }}
  .horizon-brief {{ font-size: 14px; color: var(--text-dim); line-height: 1.85; }}
  .decline-entry {{
    padding: 26px 0; border-top: 1px solid var(--rule);
    display: grid; grid-template-columns: 260px 1fr; gap: 40px; align-items: baseline;
  }}
  .decline-entry:first-child {{ border-top: none; padding-top: 0; }}
  .decline-name {{
    font-family: 'Cormorant Garamond', serif; font-size: 20px; font-weight: 400;
    color: var(--maroon); text-decoration: line-through;
    text-decoration-color: rgba(42,9,9,0.35); margin-bottom: 5px;
  }}
  .decline-stat {{
    font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-faint);
  }}
  .decline-reason {{ font-size: 13.5px; color: var(--text-dim); line-height: 1.8; }}
  .theme-entry {{ padding: 40px 0; border-top: 1px solid var(--rule); }}
  .theme-entry:first-child {{ border-top: none; padding-top: 0; }}
  .theme-number {{
    font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--text-faint); margin-bottom: 8px;
  }}
  .theme-title {{
    font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 400;
    font-style: italic; color: var(--maroon); margin-bottom: 10px;
  }}
  .theme-data {{
    font-size: 10px; letter-spacing: 0.13em; text-transform: uppercase;
    color: var(--text-faint); margin-bottom: 18px;
  }}
  .theme-body {{ font-size: 14px; color: var(--text-dim); line-height: 1.9; max-width: 620px; margin-bottom: 20px; }}
  .theme-pivot {{
    padding-left: 20px; border-left: 1px solid var(--rule-strong);
    font-size: 13.5px; color: var(--text-dim); line-height: 1.8; max-width: 560px;
  }}
  .theme-pivot-label {{
    display: block; font-size: 9.5px; letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--text-faint); margin-bottom: 5px;
  }}
  .report-footer {{
    background: var(--maroon); margin: 0 -48px;
    padding: 38px 48px 34px; display: flex; justify-content: space-between; align-items: flex-end;
  }}
  .footer-brand {{
    font-family: 'Cormorant Garamond', serif; font-size: 30px; font-weight: 300;
    letter-spacing: 0.04em; color: var(--bg);
  }}
  .footer-sub {{
    font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase;
    color: rgba(237,229,207,0.4); margin-top: 6px;
  }}
  .footer-meta {{
    text-align: right; font-size: 10.5px; letter-spacing: 0.1em;
    color: rgba(237,229,207,0.4); line-height: 2.1;
  }}
</style>
</head>
<body>
<div class="page">
  <header class="report-header">
    <div>
      <div class="brand-name">artis</div>
      <div class="brand-tag">In service of beauty</div>
    </div>
    <div class="report-title">
      Interior Design Trend Report<br>
      {month_year} · Interior Design Vertical
    </div>
  </header>

  <div class="report-intro">
    <div class="intro-headline">What the industry is moving toward — and what it's leaving behind.</div>
    <p class="intro-body">This report synthesizes signals from {pro_src} luxury design publications and {demand_src} demand sources — {pro_sig} professional editorial signals and {demand_sig} client demand signals — into a single view of where interior design is heading this month. Each section is grounded in data. The final section translates findings into strategic positioning themes for your practice.</p>
  </div>

  <section class="report-section">
    <div class="section-eyebrow">Section 01</div>
    <h2 class="section-title">Confirmed Trends</h2>
    <p class="section-subtitle">Both the professional press and client demand data signal these simultaneously. Your clients are already searching for these, and your peers are writing about them.</p>
    {s1_html}
  </section>

  <section class="report-section">
    <div class="section-eyebrow">Section 02</div>
    <h2 class="section-title">Act Now</h2>
    <p class="section-subtitle">Demand is rising — in some cases breaking out — but professional press coverage is minimal or absent. The designers who build content around these themes now will own them before competitors follow.</p>
    {s2_html}
  </section>

  <section class="report-section">
    <div class="section-eyebrow">Section 03</div>
    <h2 class="section-title">On the Horizon</h2>
    <p class="section-subtitle">The professional press is rising on these — clients haven't begun searching for them yet. Adjust positioning language and aesthetic associations now. Expect client requests in 6 to 12 months.</p>
    {s3_html}
  </section>

  <section class="report-section">
    <div class="section-eyebrow">Section 04</div>
    <h2 class="section-title">Move Away From</h2>
    <p class="section-subtitle">Confirmed declining signals — data-backed, not opinion. Designers whose feeds are still associated with these should begin a deliberate pivot.</p>
    {s4_html}
  </section>

  <section class="report-section" style="border-bottom:none;">
    <div class="section-eyebrow">Section 05</div>
    <h2 class="section-title">Marketing Themes &amp; Strategy</h2>
    <p class="section-subtitle">Five positioning platforms grounded in this month's data. Choose the one or two that authentically match your practice — these shape how you frame your work, not what you post.</p>
    {s5_html}
  </section>

</div>
<footer class="report-footer">
  <div>
    <div class="footer-brand">artis</div>
    <div class="footer-sub">In service of beauty</div>
  </div>
  <div class="footer-meta">
    hello@artis.ai · artis.ai<br>
    Austin, TX · ©{year}
  </div>
</footer>
</body>
</html>"""

    print(f"  ✓ HTML assembled")

    # Step 6: Save HTML and generate PDF
    print("\nStep 6: Saving output files...")

    run_date_str = report_date.strftime("%Y_%m_%d")
    base_name = f"artis_interior_design_trend_report_{run_date_str}"

    output_dir = Path(args.output) if args.output else Path(args.pro).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{base_name}.html"
    pdf_path = output_dir / f"{base_name}.pdf"

    html_path.write_text(html_template, encoding="utf-8")
    print(f"  ✓ HTML saved: {html_path}")

    if PLAYWRIGHT_AVAILABLE:
        if generate_pdf(html_template, str(pdf_path)):
            print(f"  ✓ PDF saved: {pdf_path}")

    print(f"\n{'='*80}")
    print(f"REPORT GENERATION COMPLETE")
    print(f"{'='*80}\n")
    print(f"📊 Output Files:")
    print(f"  HTML: {html_path}")
    print(f"  PDF:  {pdf_path}\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
