#!/usr/bin/env python3
"""
Client intake + UI refresh stage.

Runs the editorial reasoning engine for EVERY blueprint in the intake folder,
merges per-client strategy + client-card outputs, and rebuilds the web app
dataset (prototype/data.js) so newly-uploaded clients appear next to Doniphan.

Blueprints land in:
  Interior Professional Trends/Client Blueprints/*.md
(uploaded via the website's "Add Client" tab, or dropped in manually)

Run as the final orchestration stage, after both analyses exist.
"""

import sys
import os
import glob
import json
import shutil
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
INTAKE_DIR = str(paths.BLUEPRINTS)
EDITORIAL_DIR = str(paths.EDITORIAL)
PRO_DIR = str(paths.PRO_ANALYSIS)
DEM_DIR = str(paths.DEM_ANALYSIS)
BUILD_DATASET_JS = str(paths.BUILD_DATASET_JS)
CLIENTS_JSON = str(paths.APP_ROOT / "clients.json")
DATA_JS = str(paths.DATA_JS)

NODE = shutil.which("node") or "node"


def latest(globpat):
    files = sorted(glob.glob(globpat))
    return files[-1] if files else None


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")

    pro = os.path.join(PRO_DIR, f"{date_str}_professional_trends_analysis.json")
    dem = os.path.join(DEM_DIR, f"{date_str}_demand_trends_analysis.json")
    if not os.path.exists(pro):
        pro = latest(os.path.join(PRO_DIR, "*_professional_trends_analysis.json"))
    if not os.path.exists(dem):
        dem = latest(os.path.join(DEM_DIR, "*_demand_trends_analysis.json"))
    if not pro or not dem:
        sys.stderr.write("ERROR: analysis files not found; run the analysis stages first.\n")
        sys.exit(1)

    # Pull any blueprints uploaded via the deployed app (GitHub folder) into the
    # local intake dir. No-op if GITHUB_REPO isn't configured.
    os.makedirs(INTAKE_DIR, exist_ok=True)
    try:
        from github_blueprints import pull_blueprints
        print("Syncing blueprints from GitHub...")
        pull_blueprints(INTAKE_DIR)
    except Exception as e:
        sys.stderr.write(f"  GitHub pull skipped: {e}\n")

    blueprints = sorted(glob.glob(os.path.join(INTAKE_DIR, "*.md")))
    if not blueprints:
        print(f"No blueprints in {INTAKE_DIR}; nothing to do.")
        return

    # Research upcoming holidays once (client-agnostic); the editorial engine then
    # judges which ones each client should speak on.
    holidays_path = None
    try:
        from holiday_research import research_holidays
        holidays_path = research_holidays()
    except Exception as e:
        sys.stderr.write(f"  Holiday research skipped: {e}\n")

    os.makedirs(EDITORIAL_DIR, exist_ok=True)
    print(f"Processing {len(blueprints)} blueprint(s) for client strategies...")
    for bp in blueprints:
        print(f"\n{'='*70}\n=== {os.path.basename(bp)} ===\n{'='*70}")
        cmd = [
            sys.executable,
            os.path.join(PIPELINE_DIR, "generate_editorial_briefs.py"),
            "--pro", pro, "--demand", dem, "--blueprint", bp, "--output", EDITORIAL_DIR,
        ]
        if holidays_path:
            cmd += ["--holidays", holidays_path]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.stderr.write(f"  WARNING: briefs failed for {os.path.basename(bp)} (continuing)\n")

    # Month suffix matches generate_editorial_briefs.py output naming
    with open(pro, encoding="utf-8") as f:
        pro_data = json.load(f)
    month = datetime.fromisoformat(pro_data["generated_at"]).strftime("%Y_%m")

    # Merge all per-client strategy files into one object keyed by clientId
    merged = {}
    for p in glob.glob(os.path.join(EDITORIAL_DIR, f"*_strategy_{month}.json")):
        with open(p, encoding="utf-8") as f:
            merged.update(json.load(f))
    merged_path = os.path.join(EDITORIAL_DIR, f"merged_strategy_{month}.json")
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # Collect all client cards into clients.json (Doniphan first)
    cards = []
    for p in sorted(glob.glob(os.path.join(EDITORIAL_DIR, f"*_client_{month}.json"))):
        with open(p, encoding="utf-8") as f:
            cards.append(json.load(f))
    cards.sort(key=lambda c: (c.get("id") != "doniphanmoore", c.get("name", "")))
    clients_path = CLIENTS_JSON
    with open(clients_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    # Rebuild the web app dataset
    data_js = DATA_JS
    print(f"\nRebuilding UI dataset → {data_js}")
    with open(data_js, "w", encoding="utf-8") as out:
        r = subprocess.run(
            [NODE, BUILD_DATASET_JS, pro, dem, clients_path, merged_path],
            stdout=out,
        )
    if r.returncode != 0:
        sys.stderr.write("ERROR: build_dataset.js failed\n")
        sys.exit(1)

    print(f"\n✓ {len(cards)} client(s) wired into the app: "
          f"{', '.join(c.get('id') for c in cards)}")
    print(f"✓ data.js refreshed locally.")

    # Publish to GitHub in ONE atomic commit:
    #   - the LIVE dataset (prototype/data.js → triggers a Vercel redeploy)
    #   - a dated monthly archive: the two source analyses + the opinion/strategy
    #     output + a dataset snapshot
    #   - a manifest index (history + "latest" pointer)
    # No-op if GITHUB_REPO/GITHUB_TOKEN aren't configured.
    try:
        from github_blueprints import push_files, get_file_text

        with open(dem, encoding="utf-8") as f:
            dem_data = json.load(f)
        with open(pro, encoding="utf-8") as f:
            pro_text = f.read()
        with open(dem, encoding="utf-8") as f:
            dem_text = f.read()
        with open(merged_path, encoding="utf-8") as f:
            merged_text = f.read()
        with open(data_js, encoding="utf-8") as f:
            data_js_text = f.read()

        month_dash = datetime.fromisoformat(pro_data["generated_at"]).strftime("%Y-%m")
        adir = os.environ.get("GITHUB_ARCHIVE_DIR", "data")
        data_path = os.environ.get("GITHUB_DATA_PATH", "prototype/data.js")

        # Merge the manifest (newest first; replace any same-month entry)
        manifest = {"latest": month_dash, "issues": []}
        existing = get_file_text(f"{adir}/manifest.json")
        if existing:
            try:
                manifest = json.loads(existing)
            except Exception:
                pass
        entry = {
            "month": month_dash,
            "generated_at": pro_data.get("generated_at"),
            "clients": [c.get("id") for c in cards],
            "professional_trends": pro_data.get("patterns_total"),
            "demand_trends": dem_data.get("trends_total"),
            "path": f"{adir}/{month_dash}",
        }
        issues = [i for i in manifest.get("issues", []) if i.get("month") != month_dash]
        issues.append(entry)
        issues.sort(key=lambda i: i.get("month", ""), reverse=True)
        manifest["issues"] = issues
        manifest["latest"] = issues[0]["month"]

        files = {
            data_path: data_js_text,  # LIVE — the app renders this
            f"{adir}/{month_dash}/professional_trends_analysis.json": pro_text,
            f"{adir}/{month_dash}/demand_trends_analysis.json": dem_text,
            f"{adir}/{month_dash}/editorial_strategy.json": merged_text,
            f"{adir}/{month_dash}/data.js": data_js_text,  # month snapshot
            f"{adir}/manifest.json": json.dumps(manifest, indent=2),
        }
        if holidays_path and os.path.exists(holidays_path):
            with open(holidays_path, encoding="utf-8") as f:
                files[f"{adir}/{month_dash}/holidays_research.json"] = f.read()
        ok, info = push_files(files, f"ARTIS issue {month_dash}: dataset + analysis archive")
        if ok:
            print(f"✓ published issue {month_dash} to GitHub (commit {info}); the live site "
                  f"will redeploy. Archive at {adir}/{month_dash}/")
        else:
            print(f"  (GitHub publish skipped: {info})")
    except Exception as e:
        sys.stderr.write(f"  GitHub publish skipped: {e}\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    main()
