# collectors/sources/interior_demand.py
#
# Demand signal source registry for Interior Design Demand Pipeline.
# Three source types: RSS feeds (Path B), manual Cowork JSON (Path C),
# and automated Google Trends (Path A).

# ============================================================================
# PATH B — RSS SOURCES (Qualitative Prose)
# ============================================================================
DEMAND_RSS_SOURCES = [
    {
        "source_name": "Houzz",
        "feed_url": "https://feeds.feedburner.com/houzz",
        "tier": 1,
        "signal_type": "qualitative_prose",
        "luxury_note": "weight high-spend/premium content; Houzz aggregate skews mixed",
    },
    {
        "source_name": "Sotheby's International Realty (Extraordinary Living)",
        "feed_url": "https://www.sothebysrealty.com/extraordinary-living-blog/feed/",
        "tier": 1,
        "signal_type": "qualitative_prose",
        "luxury_note": "inherently luxury; lifestyle-leaning content",
    },
]

# ============================================================================
# PATH C — MANUAL COWORK JSON INPUTS
# ============================================================================
# Identified by their "source" field in the JSON file, not hardcoded paths.
# Any matching *_demand_snapshot_*.json file dropped in DEMAND_INPUTS_DIR
# is automatically ingested.
MANUAL_INPUT_SOURCES = {
    "1stdibs.com": {
        "tier": 1,
        "signal_type": "qualitative_extracted",
    },
    "trends.pinterest.com": {
        "tier": 2,
        "signal_type": "quantitative",
    },
    "luxury_real_estate_reports": {
        "tier": 1,
        "signal_type": "qualitative_extracted",
    },
}

# ============================================================================
# PATH A — GOOGLE TRENDS (Automated Quantitative)
# ============================================================================
# Keyword list mirrors Pinterest tracked list so cross-source convergence
# stays clean. Seasonality is NOT removed — YoY carried as context only.
GOOGLE_TRENDS_KEYWORDS = [
    # Group A — materials/finishes
    "limewash plaster",
    "venetian plaster",
    "tadelakt",
    "travertine",
    "calacatta marble",
    "arabescato marble",
    "onyx countertop",
    "burl wood furniture",
    "unlacquered brass",
    "antique brass hardware",
    "aged bronze fixtures",
    "plaster range hood",
    "reeded wood",
    "fluted detailing",
    "boucle furniture",
    "cerused oak",
    "honed stone",
    "soapstone countertop",
    # Group B — styles/movements
    "warm minimalism",
    "quiet luxury interior",
    "english country house",
    "modern mediterranean interior",
    "organic modern",
    "art deco interior",
    "maximalist interior design",
    "japandi",
    "old money aesthetic",
    "european farmhouse",
    "belgian interior design",
    "grandmillennial",
    # Group C — rooms
    "luxury kitchen design",
    "custom kitchen cabinetry",
    "luxury primary bathroom",
    "designer powder room",
    "wine cellar design",
    "home library design",
    "butlers pantry",
    "scullery kitchen",
    "spa bathroom design",
    "dressing room closet",
    # Group D — structural/millwork
    "custom millwork",
    "statement staircase",
    "paneled walls",
    "board and batten",
    "arched doorways",
    "coffered ceiling",
    "integrated appliances",
    "steel windows and doors",
    # Group E — color/tonal
    "moody interior",
    "earth tone interior",
    "warm white paint",
    "color drenching",
    "limewash paint",
    "plaster pink",
]
