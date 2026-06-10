"""
Central path configuration for the ARTIS pipeline.

Every script imports its directories from here instead of hardcoding absolute
Windows paths, so the same code runs locally (Windows) and in GitHub Actions (Linux).

Override via environment variables (the GitHub Actions workflow sets these):
  ARTIS_REPO_ROOT   repo checkout root        (default: two levels up from this file)
  ARTIS_ROOT        runtime data working tree (default: <repo>/pipeline/workdir)
  ARTIS_BLUEPRINTS  client blueprints folder  (default: <repo>/blueprints)
  ARTIS_APP_ROOT    where build_dataset.js + prototype/ live (default: <repo>)
"""

import os
from pathlib import Path


def _env_path(name, default):
    v = os.environ.get(name)
    return Path(v) if v else Path(default)


# Repo root = .../TrendResearch  (this file is at <repo>/pipeline/paths.py)
REPO_ROOT = _env_path("ARTIS_REPO_ROOT", Path(__file__).resolve().parents[1])

# Runtime data tree — holds the "Interior Professional Trends" folder during a run.
ROOT = _env_path("ARTIS_ROOT", REPO_ROOT / "pipeline" / "workdir")
IPT = ROOT / "Interior Professional Trends"

PRO_RESEARCH = IPT / "Professional Trends Data" / "Research Data"
PRO_ANALYSIS = IPT / "Professional Trends Data" / "Analysis"
DEM_RESEARCH = IPT / "Demand Trends Data" / "Research Data"
DEM_ANALYSIS = IPT / "Demand Trends Data" / "Analysis"
DEM_COWORK = DEM_RESEARCH / "Cowork Inputs"
EDITORIAL = IPT / "Editorial Briefs"
REPORTS = IPT / "Reports"
HOLIDAYS = IPT / "Holidays"

# Blueprints: in CI the runner has them checked out at <repo>/blueprints; locally
# they live alongside the other working data. Configurable either way.
BLUEPRINTS = _env_path("ARTIS_BLUEPRINTS", REPO_ROOT / "blueprints")

# Web app (one-repo layout): build_dataset.js + prototype/data.js at the repo root.
APP_ROOT = _env_path("ARTIS_APP_ROOT", REPO_ROOT)
BUILD_DATASET_JS = APP_ROOT / "build_dataset.js"
DATA_JS = APP_ROOT / "prototype" / "data.js"


def ensure_dirs():
    """Create the working-tree folders if they don't exist."""
    for d in (PRO_RESEARCH, PRO_ANALYSIS, DEM_RESEARCH, DEM_ANALYSIS,
              DEM_COWORK, EDITORIAL, REPORTS, HOLIDAYS, BLUEPRINTS):
        d.mkdir(parents=True, exist_ok=True)


# Convenience string forms (some call sites want str, not Path)
def s(p):
    return str(p)
