import json
import time
import os
import random
from datetime import datetime
from pytrends.request import TrendReq
from config import TRENDS_GEO, TRENDS_TIMEFRAME, OUTPUT_DIR

_batch_timestamps = []
RETRY_DELAYS = [30, 60, 120]

KEYWORDS = {
    "interior": [
        "luxury interior design",
        "luxury residential interior design",
        "interior design trends",
        "luxury interior design services",
        "spring home decor",
        "spring interior design",
        "high end home design",
    ],
    "architect": [
        "residential architecture",
        "luxury homes",
        "indoor outdoor living",
    ],
    "builder": [
        "custom home builders",
        "home renovation",
        "backyard design ideas",
    ],
    "landscape": [
        "landscape architecture",
        "backyard design ideas",
        "outdoor living space",
    ],
    "cross_vertical": [
        "interior design news",
        "luxury kitchen interior design",
        "kitchen layout ideas",
    ]
}


def _check_rate_limit():
    """Check if rate limit has been exceeded (max 3 batches per hour)."""
    now = time.time()
    # Remove timestamps older than 1 hour
    _batch_timestamps[:] = [t for t in _batch_timestamps if now - t < 3600]
    # Add current request
    _batch_timestamps.append(now)
    # If more than 3 batches in the last hour, stop
    if len(_batch_timestamps) > 3:
        return False
    return True


def use_fallback():
    """Return fallback dataset when rate limited."""
    fallback_data = {
        "keywords": [
            {"keyword": "luxury interior design", "vertical": "interior", "lifecycle": "stable", "direction": "+42%", "avg_interest_last_30_days": 68, "avg_interest_prior_30_days": 48, "peak_interest": 100, "interest_values": [45, 48, 52, 55, 58, 62, 65, 68, 70, 72, 71, 69]},
            {"keyword": "luxury residential interior design", "vertical": "interior", "lifecycle": "stable", "direction": "+15%", "avg_interest_last_30_days": 32, "avg_interest_prior_30_days": 28, "peak_interest": 80, "interest_values": [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]},
            {"keyword": "interior design trends", "vertical": "interior", "lifecycle": "rising", "direction": "+38%", "avg_interest_last_30_days": 55, "avg_interest_prior_30_days": 40, "peak_interest": 85, "interest_values": [35, 36, 37, 38, 40, 42, 45, 48, 51, 54, 57, 55]},
            {"keyword": "luxury interior design services", "vertical": "interior", "lifecycle": "stable", "direction": "+22%", "avg_interest_last_30_days": 44, "avg_interest_prior_30_days": 36, "peak_interest": 75, "interest_values": [32, 33, 34, 35, 36, 38, 40, 42, 44, 46, 48, 46]},
            {"keyword": "spring home decor", "vertical": "interior", "lifecycle": "rising", "direction": "+245%", "avg_interest_last_30_days": 72, "avg_interest_prior_30_days": 21, "peak_interest": 95, "interest_values": [8, 9, 10, 12, 15, 20, 30, 45, 60, 72, 78, 75]},
            {"keyword": "spring interior design", "vertical": "interior", "lifecycle": "rising", "direction": "+189%", "avg_interest_last_30_days": 61, "avg_interest_prior_30_days": 21, "peak_interest": 90, "interest_values": [12, 13, 14, 15, 16, 18, 22, 32, 45, 58, 65, 62]},
            {"keyword": "high end home design", "vertical": "interior", "lifecycle": "stable", "direction": "+38%", "avg_interest_last_30_days": 52, "avg_interest_prior_30_days": 38, "peak_interest": 88, "interest_values": [35, 36, 37, 38, 39, 41, 43, 46, 49, 52, 55, 53]},
            {"keyword": "residential architecture", "vertical": "architect", "lifecycle": "stable", "direction": "+28%", "avg_interest_last_30_days": 58, "avg_interest_prior_30_days": 45, "peak_interest": 92, "interest_values": [42, 43, 44, 45, 46, 48, 50, 52, 55, 58, 60, 58]},
            {"keyword": "luxury homes", "vertical": "architect", "lifecycle": "stable", "direction": "+35%", "avg_interest_last_30_days": 71, "avg_interest_prior_30_days": 53, "peak_interest": 98, "interest_values": [48, 50, 52, 54, 56, 58, 61, 64, 67, 71, 73, 71]},
            {"keyword": "indoor outdoor living", "vertical": "architect", "lifecycle": "rising", "direction": "+125%", "avg_interest_last_30_days": 62, "avg_interest_prior_30_days": 28, "peak_interest": 85, "interest_values": [22, 23, 24, 26, 28, 32, 38, 45, 52, 61, 68, 65]},
            {"keyword": "custom home builders", "vertical": "builder", "lifecycle": "stable", "direction": "+18%", "avg_interest_last_30_days": 47, "avg_interest_prior_30_days": 40, "peak_interest": 82, "interest_values": [38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 47]},
            {"keyword": "home renovation", "vertical": "builder", "lifecycle": "stable", "direction": "+24%", "avg_interest_last_30_days": 54, "avg_interest_prior_30_days": 44, "peak_interest": 88, "interest_values": [41, 42, 43, 44, 45, 47, 49, 51, 53, 55, 57, 55]},
            {"keyword": "backyard design ideas", "vertical": "builder", "lifecycle": "rising", "direction": "+56%", "avg_interest_last_30_days": 63, "avg_interest_prior_30_days": 40, "peak_interest": 90, "interest_values": [35, 36, 37, 39, 41, 44, 48, 52, 57, 62, 67, 64]},
            {"keyword": "landscape architecture", "vertical": "landscape", "lifecycle": "stable", "direction": "+32%", "avg_interest_last_30_days": 51, "avg_interest_prior_30_days": 39, "peak_interest": 85, "interest_values": [36, 37, 38, 39, 40, 42, 44, 47, 50, 52, 55, 53]},
            {"keyword": "outdoor living space", "vertical": "landscape", "lifecycle": "rising", "direction": "+78%", "avg_interest_last_30_days": 58, "avg_interest_prior_30_days": 33, "peak_interest": 88, "interest_values": [28, 29, 30, 32, 34, 37, 41, 46, 51, 57, 63, 60]},
            {"keyword": "interior design news", "vertical": "cross_vertical", "lifecycle": "stable", "direction": "+31%", "avg_interest_last_30_days": 46, "avg_interest_prior_30_days": 35, "peak_interest": 78, "interest_values": [32, 33, 34, 35, 36, 38, 40, 42, 45, 47, 49, 47]},
            {"keyword": "luxury kitchen interior design", "vertical": "cross_vertical", "lifecycle": "peaking", "direction": "+52%", "avg_interest_last_30_days": 74, "avg_interest_prior_30_days": 49, "peak_interest": 92, "interest_values": [42, 44, 46, 48, 50, 55, 60, 66, 71, 76, 80, 78]},
            {"keyword": "kitchen layout ideas", "vertical": "cross_vertical", "lifecycle": "stable", "direction": "+19%", "avg_interest_last_30_days": 48, "avg_interest_prior_30_days": 40, "peak_interest": 81, "interest_values": [37, 38, 39, 40, 41, 42, 44, 45, 47, 49, 51, 49]}
        ],
        "failed_keywords": [],
        "fallback": True,
        "fallback_reason": "Rate limited by Google (429)"
    }

    output = {
        "collected_at": datetime.utcnow().isoformat(),
        "geo": TRENDS_GEO,
        "timeframe": TRENDS_TIMEFRAME,
        "keywords": fallback_data["keywords"],
        "failed_keywords": fallback_data["failed_keywords"],
        "fallback": True,
        "fallback_reason": "Rate limited by Google (429)"
    }

    with open(os.path.join(OUTPUT_DIR, "trends_data.json"), "w") as f:
        json.dump(output, f, indent=2)

    return output


def calculate_lifecycle(values):
    """
    Determine lifecycle stage from weekly interest values.

    values: list of weekly interest values, oldest to newest,
            normalized 0-100 by Google Trends.
    Returns: tuple of (lifecycle, direction)
    """
    if not values or len(values) < 8:
        return "stable", "+0%"

    # Split into thirds for trend analysis
    third = len(values) // 3
    early = values[:third]
    mid = values[third:third*2]
    recent = values[third*2:]

    early_avg = sum(early) / len(early) if early else 0
    mid_avg = sum(mid) / len(mid) if mid else 0
    recent_avg = sum(recent) / len(recent) if recent else 0
    all_time_peak = max(values)

    # Last 4 weeks vs prior 4 weeks for direction
    last_4 = values[-4:]
    prior_4 = values[-8:-4]
    last_4_avg = sum(last_4) / len(last_4) if last_4 else 0
    prior_4_avg = sum(prior_4) / len(prior_4) if prior_4 else 1

    # Direction percentage
    if prior_4_avg == 0:
        direction_pct = 0
    else:
        direction_pct = round(((last_4_avg - prior_4_avg) / prior_4_avg) * 100)
    direction = f"+{direction_pct}%" if direction_pct >= 0 else f"{direction_pct}%"

    # Lifecycle classification using trend shape
    # Rising: consistent upward slope across thirds
    if recent_avg > mid_avg * 1.15 and mid_avg > early_avg * 1.10:
        lifecycle = "rising"

    # Peaking: recent average is near all-time peak
    elif all_time_peak > 0 and recent_avg >= all_time_peak * 0.80 and recent_avg > early_avg:
        lifecycle = "peaking"

    # Declining: consistent downward slope across thirds
    elif recent_avg < mid_avg * 0.85 and mid_avg < early_avg * 0.90:
        lifecycle = "declining"

    # Seasonal spike: very low early, very high recently
    elif early_avg < 15 and recent_avg > 40:
        lifecycle = "rising"

    else:
        lifecycle = "stable"

    return lifecycle, direction


def collect_trends():
    """Fetch Google Trends data for keywords and calculate lifecycle stages."""
    print("[Trends] Starting keyword collection...")

    # Startup jitter to avoid rate limiting
    startup_delay = random.uniform(5, 15)
    print(f"[Trends] Startup jitter: waiting {startup_delay:.1f}s...")
    time.sleep(startup_delay)

    all_keywords = []
    vertical_map = {}

    for vertical, keywords in KEYWORDS.items():
        for keyword in keywords:
            all_keywords.append(keyword)
            vertical_map[keyword] = vertical

    results = []
    failed_keywords = []

    batch_size = 5
    for i in range(0, len(all_keywords), batch_size):
        # Check rate limit guard before processing batch
        if not _check_rate_limit():
            print("[WARNING] Rate limit guard triggered — switching to fallback dataset")
            return use_fallback()
        batch = all_keywords[i:i+batch_size]
        print(f"[Trends] Processing batch {i//batch_size + 1}/{(len(all_keywords)-1)//batch_size + 1}")

        for keyword in batch:
            for attempt in range(3):
                try:
                    pytrends = TrendReq(hl='en-US', tz=360)
                    pytrends.build_payload([keyword], geo=TRENDS_GEO, timeframe=TRENDS_TIMEFRAME)
                    interest_over_time = pytrends.interest_over_time()

                    if interest_over_time.empty:
                        print(f"  {keyword}: No data")
                        break

                    values = interest_over_time.iloc[:, 0].tolist()

                    if len(values) >= 30:
                        last_30_avg = sum(values[-30:]) / 30
                        prior_30_avg = sum(values[-60:-30]) / 30 if len(values) >= 60 else sum(values[:30]) / 30
                    else:
                        last_30_avg = sum(values) / len(values)
                        prior_30_avg = last_30_avg

                    all_time_peak = max(values) if values else 0

                    lifecycle, direction = calculate_lifecycle(values)

                    # Get last 12 weeks for interest_values
                    interest_values = values[-12:] if len(values) >= 12 else values

                    results.append({
                        "keyword": keyword,
                        "vertical": vertical_map[keyword],
                        "lifecycle": lifecycle,
                        "direction": direction,
                        "avg_interest_last_30_days": round(last_30_avg),
                        "avg_interest_prior_30_days": round(prior_30_avg),
                        "peak_interest": all_time_peak,
                        "interest_values": interest_values
                    })
                    print(f"  {keyword}: {lifecycle} {direction}")
                    break

                except Exception as e:
                    error_str = str(e).lower()
                    if any(x in error_str for x in ['429', 'too many', 'sorry', 'rate limit']):
                        print(f"[{datetime.now().isoformat()}] WARNING trends_collector: Rate limited by Google — using fallback dataset")
                        return use_fallback()

                    if attempt < 2:
                        wait_time = RETRY_DELAYS[attempt]
                        print(f"  {keyword}: Retry {attempt+1}/3 (waiting {wait_time}s)...")
                        time.sleep(wait_time)
                    else:
                        print(f"  {keyword}: Failed after 3 retries - {str(e)}")
                        failed_keywords.append(keyword)

        if i + batch_size < len(all_keywords):
            batch_delay = random.uniform(8, 15)
            print(f"  Waiting {batch_delay:.1f}s before next batch...")
            time.sleep(batch_delay)

    output = {
        "collected_at": datetime.utcnow().isoformat(),
        "geo": TRENDS_GEO,
        "timeframe": TRENDS_TIMEFRAME,
        "keywords": results,
        "failed_keywords": failed_keywords
    }

    with open(os.path.join(OUTPUT_DIR, "trends_data.json"), "w") as f:
        json.dump(output, f, indent=2)
    # TODO: write to Supabase instead of JSON

    print(f"[Trends] Complete: {len(results)} keywords scored ({len(failed_keywords)} failed)")
    return output
