import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LOOKBACK_DAYS = 30
HOLIDAY_WINDOW_DAYS = 45
TRENDS_GEO = "US"
TRENDS_TIMEFRAME = "today 12-m"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
TAGGING_BATCH_SIZE = 20

import paths  # central path resolver (repo-relative + env-overridable)

BASE_OUTPUT_DIR = str(paths.ROOT / "Research")
OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, datetime.now().strftime("%Y-%m-%d"))
CLIENT_CONTEXT_OUTPUT_DIR = str(paths.ROOT / "Client Context Output")
TREND_SUMMARY_DIR = str(paths.ROOT / "Trend Summary")
OPPORTUNITIES_OUTPUT_DIR = str(paths.ROOT / "Opportunities Output")
CLIENT_ENGAGEMENT_ANALYSIS_DIR = str(paths.ROOT / "Client Engagement Analysis")
CONTENT_BRIEFS_DIR = str(paths.ROOT / "Content Briefs")

# Interior Professional Trend Collector
INTERIOR_PRO_OUTPUT_DIR = str(paths.IPT)

# Interior Demand Pipeline
DEMAND_INPUTS_DIR = str(paths.DEM_COWORK)              # manual Cowork JSON inputs
DEMAND_RESEARCH_DIR = str(paths.DEM_RESEARCH)          # demand collector output
DEMAND_OUTPUT_DIR = str(paths.IPT / "Demand Trends Data")
DEMAND_RECENCY_DAYS = 60          # for RSS sources only
DEMAND_TAGGING_BATCH_SIZE = 12
TIER_WEIGHTS = {1: 3, 2: 2, 3: 1}  # multiply by signal strength in analysis layer

# Collection dials — tunable parameters
RECENCY_FILTER_DAYS = 60          # hard cutoff at collection (dated articles only)
MIN_BODY_WORDS = 200              # below this = likely paywall truncation
TRAFILATURA_FAVOR_PRECISION = True  # True = cleaner text, drops borderline content
TAGGER_TEXT_LIMIT = 4000          # chars of raw_text sent to tagger (full body always stored)
TAGGING_BATCH_SIZE = 12

# Freshness grading bands (within the 60-day window)
FRESH_CURRENT_DAYS = 30           # 0-30 days = current_cycle
FRESH_EDGE_DAYS = 45              # 31-45 = edge_of_window, 46-60 = trailing
RECENCY_RISK_DAYS = 7             # flag articles within N days of cutoff as "at risk"

# Extraction quality gates (adaptive, source-agnostic)
MIN_EXTRACTION_COMPLETENESS_RATE = 0.70  # sources with <70% complete extraction get downsampled
EXTRACTION_QUALITY_RETRY_METHODS = True  # enable fallback chain for extraction

# Source diversity balancing (adaptive, feed-agnostic)
SOURCE_DIVERSITY_MULTIPLIER = 1.5  # max signals per source = 1.5x median_source_volume
ENABLE_SOURCE_BALANCING = True

# Content-type filtering (pre-tagging semantic filter)
ENABLE_CONTENT_TYPE_FILTER = True
OFF_TIER_KEYWORDS = [
    "restaurant interior", "cafe design", "bar concept",
    "hospitality design", "retail environment",
    "celebrity home", "designer showcase", "real estate",
    "hotel lobby", "nightclub design", "commercial space"
]

# Theme validation (grounding check against source text)
ENABLE_THEME_GROUNDING_VALIDATION = True
THEME_VALIDATION_SAMPLE_RATE = 0.10  # sample 10% of signals for validation

# Feed health monitoring (persistent tracking)
FEED_HEALTH_TRACKING_ENABLED = True
FEED_FAILURE_BACKOFF_DAYS = 7
FEED_FAILURE_THRESHOLD = 3  # consecutive failures before backoff
