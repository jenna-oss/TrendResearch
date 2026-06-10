import json
from datetime import datetime, timedelta
from config import HOLIDAY_WINDOW_DAYS, OUTPUT_DIR
import os

INDUSTRY_OBSERVANCES = [
    # Month-long observances
    {
        "name": "World Landscape Architecture Month",
        "month": 4, "day_start": 1, "day_end": 30,
        "type": "month_long",
        "verticals": ["landscape"],
        "content_angles": ["outdoor environment design", "ecology", "sustainability"]
    },
    {
        "name": "National Garden Month",
        "month": 4, "day_start": 1, "day_end": 30,
        "type": "month_long",
        "verticals": ["landscape", "builder"],
        "content_angles": ["planting", "outdoor spaces", "native plants"]
    },
    {
        "name": "National Home Improvement Month",
        "month": 5, "day_start": 1, "day_end": 31,
        "type": "month_long",
        "verticals": ["builder", "interior"],
        "content_angles": ["renovations", "before and after", "material upgrades"]
    },
    {
        "name": "World Watercolor Month",
        "month": 7, "day_start": 1, "day_end": 31,
        "type": "month_long",
        "verticals": ["interior", "architect"],
        "content_angles": ["hand renderings", "color studies", "process and craft"]
    },
    {
        "name": "National Water Gardening Month",
        "month": 7, "day_start": 1, "day_end": 31,
        "type": "month_long",
        "verticals": ["landscape"],
        "content_angles": ["water features", "pools", "reflecting elements"]
    },
    {
        "name": "Plastic Free July",
        "month": 7, "day_start": 1, "day_end": 31,
        "type": "month_long",
        "verticals": ["landscape", "architect", "builder"],
        "content_angles": ["sustainable materials", "eco-conscious material choices"]
    },
    {
        "name": "National Great Outdoors Month",
        "month": 6, "day_start": 1, "day_end": 30,
        "type": "month_long",
        "verticals": ["landscape", "architect", "builder"],
        "content_angles": ["outdoor living", "nature integration", "wellness"]
    },

    # Single day observances
    {
        "name": "World Heritage Day",
        "month": 4, "day": 18,
        "type": "single_day",
        "verticals": ["architect"],
        "content_angles": ["historical references", "preservation", "craftsmanship and legacy"]
    },
    {
        "name": "Earth Day",
        "month": 4, "day": 22,
        "type": "single_day",
        "verticals": ["landscape", "architect", "builder"],
        "content_angles": ["sustainable architecture", "materials and sourcing", "environmental integration"]
    },
    {
        "name": "National Pool Opening Day",
        "month": 4, "day": 26,
        "type": "single_day",
        "verticals": ["builder", "landscape"],
        "content_angles": ["outdoor living", "backyard design", "indoor-outdoor transitions"]
    },
    {
        "name": "World Bee Day",
        "month": 5, "day": 20,
        "type": "single_day",
        "verticals": ["landscape"],
        "content_angles": ["biodiversity", "pollinator gardens", "native planting"]
    },
    {
        "name": "World Environment Day",
        "month": 6, "day": 5,
        "type": "single_day",
        "verticals": ["landscape", "architect", "builder"],
        "content_angles": ["sustainability", "materials", "energy efficiency", "design impact"]
    },
    {
        "name": "First Day of Summer",
        "month": 6, "day": 21,
        "type": "single_day",
        "verticals": ["interior", "architect", "landscape", "builder"],
        "content_angles": ["outdoor spaces", "light", "travel homes", "hospitality inspiration"]
    },
    {
        "name": "World Architecture Day",
        "month": 10, "day": 7,
        "type": "single_day",
        "verticals": ["architect"],
        "content_angles": ["design philosophy", "legacy", "built environment"]
    },
    {
        "name": "National Wallpaper Day",
        "month": 10, "day": 26,
        "type": "single_day",
        "verticals": ["interior"],
        "content_angles": ["wallcovering", "pattern", "material storytelling"]
    },
    {
        "name": "National Interior Design Day",
        "month": 4, "day": 5,
        "type": "single_day",
        "verticals": ["interior"],
        "content_angles": ["design philosophy", "process", "client relationships"]
    },

    # Floating observances — calculated at runtime
    {
        "name": "Mother's Day",
        "type": "floating",
        "rule": "second_sunday_of_month",
        "month": 5,
        "verticals": ["interior"],
        "content_angles": ["home as gathering space", "comfort", "warmth"]
    },
    {
        "name": "Father's Day",
        "type": "floating",
        "rule": "third_sunday_of_month",
        "month": 6,
        "verticals": ["interior", "builder"],
        "content_angles": ["home office", "workshop", "outdoor entertaining spaces"]
    },
    {
        "name": "Memorial Day",
        "type": "floating",
        "rule": "last_monday_of_month",
        "month": 5,
        "verticals": ["builder", "landscape", "architect"],
        "content_angles": ["outdoor living", "start of summer", "second homes"]
    },
    {
        "name": "Thanksgiving",
        "type": "floating",
        "rule": "fourth_thursday_of_month",
        "month": 11,
        "verticals": ["interior"],
        "content_angles": ["hosting spaces", "dining rooms", "warmth and gathering"]
    },
]

FEDERAL_HOLIDAYS = [
    # 2026
    {"name": "New Year's Day", "month": 1, "day": 1},
    {"name": "MLK Day", "month": 1, "rule": "third_monday_of_month"},
    {"name": "Presidents' Day", "month": 2, "rule": "third_monday_of_month"},
    {"name": "Memorial Day", "month": 5, "rule": "last_monday_of_month"},
    {"name": "Independence Day", "month": 7, "day": 4},
    {"name": "Labor Day", "month": 9, "rule": "first_monday_of_month"},
    {"name": "Columbus Day", "month": 10, "rule": "second_monday_of_month"},
    {"name": "Veterans Day", "month": 11, "day": 11},
    {"name": "Thanksgiving", "month": 11, "rule": "fourth_thursday_of_month"},
    {"name": "Christmas Day", "month": 12, "day": 25},
]


def nth_weekday_of_month(year, month, weekday, n):
    """Returns the date of the nth occurrence of weekday in month (Monday=0, Sunday=6)"""
    from datetime import date
    first_day = date(year, month, 1)
    first_weekday = first_day.weekday()
    days_ahead = (weekday - first_weekday) % 7
    target_day = 1 + days_ahead + (n - 1) * 7
    return date(year, month, target_day)


def last_weekday_of_month(year, month, weekday):
    """Returns the date of the last occurrence of weekday in month"""
    from datetime import date
    if month == 12:
        first_day_next = date(year + 1, 1, 1)
    else:
        first_day_next = date(year, month + 1, 1)
    last_day_current = first_day_next - timedelta(days=1)
    current_weekday = last_day_current.weekday()
    days_back = (current_weekday - weekday) % 7
    return last_day_current - timedelta(days=days_back)


def get_federal_holiday_date(holiday, year):
    """Get the date of a federal holiday for a given year"""
    if "day" in holiday:
        from datetime import date
        return date(year, holiday["month"], holiday["day"])

    from datetime import date
    rule = holiday.get("rule")
    if rule == "third_monday_of_month":
        return nth_weekday_of_month(year, holiday["month"], 0, 3)
    elif rule == "first_monday_of_month":
        return nth_weekday_of_month(year, holiday["month"], 0, 1)
    elif rule == "second_monday_of_month":
        return nth_weekday_of_month(year, holiday["month"], 0, 2)
    elif rule == "fourth_thursday_of_month":
        return nth_weekday_of_month(year, holiday["month"], 3, 4)
    elif rule == "last_monday_of_month":
        return last_weekday_of_month(year, holiday["month"], 0)

    return None


def collect_holidays():
    """Collect holidays and observances within the window."""
    print("[Holidays] Starting collection...")

    today = datetime.utcnow().date()
    window_end = today + timedelta(days=HOLIDAY_WINDOW_DAYS)

    holidays = []

    for fed_holiday in FEDERAL_HOLIDAYS:
        for year in [today.year, today.year + 1]:
            holiday_date = get_federal_holiday_date(fed_holiday, year)
            if holiday_date and today <= holiday_date <= window_end:
                days_away = (holiday_date - today).days
                holidays.append({
                    "name": fed_holiday["name"],
                    "date": holiday_date.isoformat(),
                    "days_away": days_away,
                    "type": "federal",
                    "verticals": ["interior", "architect", "landscape", "builder"],
                    "content_angles": []
                })

    for obs in INDUSTRY_OBSERVANCES:
        if obs["type"] == "month_long":
            obs_start = datetime(today.year, obs["month"], obs["day_start"]).date()
            obs_end = datetime(today.year, obs["month"], obs["day_end"]).date()

            if obs_start > window_end:
                continue
            if obs_end < today and obs["month"] < 12:
                continue

            if obs["month"] >= today.month or (obs["month"] < today.month and today.year < 2027):
                if obs_start <= window_end and obs_end >= today:
                    days_away = max(0, (obs_start - today).days)
                    holidays.append({
                        "name": obs["name"],
                        "date_start": obs_start.isoformat(),
                        "date_end": obs_end.isoformat(),
                        "days_away": days_away,
                        "type": "month_long",
                        "verticals": obs["verticals"],
                        "content_angles": obs["content_angles"]
                    })

        elif obs["type"] == "single_day":
            obs_date = datetime(today.year, obs["month"], obs["day"]).date()
            if obs_date < today:
                obs_date = datetime(today.year + 1, obs["month"], obs["day"]).date()

            if today <= obs_date <= window_end:
                days_away = (obs_date - today).days
                holidays.append({
                    "name": obs["name"],
                    "date": obs_date.isoformat(),
                    "days_away": days_away,
                    "type": "single_day",
                    "verticals": obs["verticals"],
                    "content_angles": obs["content_angles"]
                })

        elif obs["type"] == "floating":
            for year in [today.year, today.year + 1]:
                rule = obs.get("rule")
                if rule == "second_sunday_of_month":
                    floating_date = nth_weekday_of_month(year, obs["month"], 6, 2)
                elif rule == "third_sunday_of_month":
                    floating_date = nth_weekday_of_month(year, obs["month"], 6, 3)
                elif rule == "last_monday_of_month":
                    floating_date = last_weekday_of_month(year, obs["month"], 0)
                elif rule == "fourth_thursday_of_month":
                    floating_date = nth_weekday_of_month(year, obs["month"], 3, 4)
                else:
                    continue

                if today <= floating_date <= window_end:
                    days_away = (floating_date - today).days
                    holidays.append({
                        "name": obs["name"],
                        "date": floating_date.isoformat(),
                        "days_away": days_away,
                        "type": "floating",
                        "verticals": obs["verticals"],
                        "content_angles": obs["content_angles"]
                    })

    holidays.sort(key=lambda x: x.get("date") or x.get("date_start"))

    output = {
        "collected_at": datetime.utcnow().isoformat(),
        "window_days": HOLIDAY_WINDOW_DAYS,
        "window_end": window_end.isoformat(),
        "holiday_count": len(holidays),
        "holidays": holidays
    }

    with open(os.path.join(OUTPUT_DIR, "holidays.json"), "w") as f:
        json.dump(output, f, indent=2)
    # TODO: write to Supabase instead of JSON

    print(f"[Holidays] Complete: {len(holidays)} events in next {HOLIDAY_WINDOW_DAYS} days")
    return output
