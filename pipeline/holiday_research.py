#!/usr/bin/env python3
"""
Holiday & observance research for the upcoming ~month.

Combines a deterministic calendar (U.S. federal holidays + known industry
observances — reused from collectors/holiday_collector.py) with a Claude research
pass over the design & art world (design weeks, major fairs, museum moments,
art/design anniversaries, craft/material observances) so the editorial engine can
later decide which holidays a specific client should speak on.

Output: <paths.HOLIDAYS>/<YYYY-MM>_holidays_research.json

Usage:
  python holiday_research.py            # next ~35 days
"""

import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

import anthropic

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Reuse the existing research tool's calendar data + date helpers
from collectors.holiday_collector import (
    FEDERAL_HOLIDAYS, INDUSTRY_OBSERVANCES,
    get_federal_holiday_date, nth_weekday_of_month, last_weekday_of_month,
)

MODEL = "claude-sonnet-4-20250514"
WINDOW_DAYS = 35  # "the next month"

_client = anthropic.Anthropic()


def _deterministic(today, window_end):
    """Federal holidays + known industry observances falling within the window."""
    out = []

    for fed in FEDERAL_HOLIDAYS:
        for year in (today.year, today.year + 1):
            d = get_federal_holiday_date(fed, year)
            if d and today <= d <= window_end:
                out.append({
                    "name": fed["name"], "date": d.isoformat(),
                    "days_away": (d - today).days, "category": "general",
                    "type": "federal", "significance": "U.S. federal holiday",
                    "content_angles": [], "source": "calendar",
                })

    for obs in INDUSTRY_OBSERVANCES:
        t = obs["type"]
        if t == "single_day":
            d = datetime(today.year, obs["month"], obs["day"]).date()
            if d < today:
                d = datetime(today.year + 1, obs["month"], obs["day"]).date()
            if today <= d <= window_end:
                out.append({
                    "name": obs["name"], "date": d.isoformat(),
                    "days_away": (d - today).days, "category": "design_art",
                    "type": "single_day", "significance": "industry observance",
                    "content_angles": obs.get("content_angles", []), "source": "calendar",
                })
        elif t == "month_long":
            start = datetime(today.year, obs["month"], obs["day_start"]).date()
            end = datetime(today.year, obs["month"], obs["day_end"]).date()
            if start <= window_end and end >= today:
                out.append({
                    "name": obs["name"], "date_start": start.isoformat(),
                    "date_end": end.isoformat(), "days_away": max(0, (start - today).days),
                    "category": "design_art", "type": "month_long",
                    "significance": "month-long industry observance",
                    "content_angles": obs.get("content_angles", []), "source": "calendar",
                })
        elif t == "floating":
            rule = obs.get("rule")
            for year in (today.year, today.year + 1):
                if rule == "second_sunday_of_month":
                    d = nth_weekday_of_month(year, obs["month"], 6, 2)
                elif rule == "third_sunday_of_month":
                    d = nth_weekday_of_month(year, obs["month"], 6, 3)
                elif rule == "last_monday_of_month":
                    d = last_weekday_of_month(year, obs["month"], 0)
                elif rule == "fourth_thursday_of_month":
                    d = nth_weekday_of_month(year, obs["month"], 3, 4)
                else:
                    continue
                if today <= d <= window_end:
                    out.append({
                        "name": obs["name"], "date": d.isoformat(),
                        "days_away": (d - today).days, "category": "general",
                        "type": "floating", "significance": "observance",
                        "content_angles": obs.get("content_angles", []), "source": "calendar",
                    })
    return out


def _researched(today, window_end):
    """Claude research over general + design/art holidays and cultural moments."""
    prompt = f"""Today is {today.isoformat()}. List notable holidays, observances, and
cultural moments occurring between {today.isoformat()} and {window_end.isoformat()}
that a LUXURY INTERIOR DESIGN firm could credibly reference in editorial content.

Cover two buckets:
1. GENERAL — widely-observed public/cultural holidays in this window.
2. DESIGN & ART — the design and art world specifically: design weeks and fairs
   (e.g. major furniture/design fairs), notable art fairs, significant museum or
   exhibition openings/anniversaries, art-historical birthdays or anniversaries,
   and craft/material observances.

Only include REAL, recognizable dates that actually fall in this window. Prefer
moments with genuine cultural weight over obscure "national ___ day" filler.

Output ONLY a JSON array, no prose:
[
  {{
    "name": "",
    "date": "YYYY-MM-DD or 'YYYY-MM-DD to YYYY-MM-DD' for ranges",
    "category": "general" | "design_art",
    "significance": "one sentence on why it matters",
    "content_angles": ["2-4 angles a luxury designer could take"]
  }}
]"""

    try:
        resp = _client.messages.create(
            model=MODEL, max_tokens=2500,
            system="You are a cultural calendar researcher for luxury design brands. "
                   "You know the art and design world's events, fairs, and anniversaries.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        items = json.loads(raw)
        for it in items:
            it["source"] = "researched"
            it.setdefault("type", "researched")
        return items
    except Exception as e:
        print(f"  ⚠️  Holiday research pass failed: {e}")
        return []


def research_holidays():
    """Run both passes, merge (dedupe by name), write JSON, return the output path."""
    print("\n[Holidays] Researching the upcoming month...")
    today = datetime.utcnow().date()
    window_end = today + timedelta(days=WINDOW_DAYS)

    calendar = _deterministic(today, window_end)
    researched = _researched(today, window_end)
    print(f"  calendar: {len(calendar)} · researched: {len(researched)}")

    # Merge, dedupe by lowercased name (calendar entries win — they're authoritative dates)
    seen = {h["name"].strip().lower(): h for h in researched}
    for h in calendar:
        seen[h["name"].strip().lower()] = h
    holidays = list(seen.values())
    holidays.sort(key=lambda x: x.get("date") or x.get("date_start") or "")

    paths.HOLIDAYS.mkdir(parents=True, exist_ok=True)
    month = today.strftime("%Y-%m")
    out_path = paths.HOLIDAYS / f"{month}_holidays_research.json"
    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "window_days": WINDOW_DAYS,
        "window_end": window_end.isoformat(),
        "holiday_count": len(holidays),
        "holidays": holidays,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ {len(holidays)} holidays → {out_path}")
    return str(out_path)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    research_holidays()
