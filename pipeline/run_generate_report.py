#!/usr/bin/env python3
"""
Run Artis Trend Report Generation
Generates HTML and PDF report from professional and demand analysis outputs
"""
import sys
import os
from datetime import datetime


def main():
    try:
        # Make the pipeline dir importable (generate_report, paths)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import paths

        # Get today's date
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Input paths
        pro_path = os.path.join(
            str(paths.PRO_ANALYSIS),
            f"{date_str}_professional_trends_analysis.json"
        )

        demand_path = os.path.join(
            str(paths.DEM_ANALYSIS),
            f"{date_str}_demand_trends_analysis.json"
        )

        # Output directory
        output_dir = str(paths.REPORTS)

        if not os.path.exists(pro_path):
            sys.stderr.write(f"ERROR: Professional analysis file not found at {pro_path}\n")
            sys.exit(1)

        if not os.path.exists(demand_path):
            sys.stderr.write(f"ERROR: Demand analysis file not found at {demand_path}\n")
            sys.exit(1)

        from generate_report import main as generate_report

        # Mock args object
        class Args:
            pro = pro_path
            demand = demand_path
            output = output_dir

        sys.argv = ["generate_report.py", "--pro", pro_path, "--demand", demand_path, "--output", output_dir]
        generate_report()

    except Exception as e:
        sys.stderr.write(f"\nERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    main()
