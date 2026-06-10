#!/usr/bin/env python3
"""
Run Demand Analysis on collected demand signals
"""
import sys
import os
from datetime import datetime


def main():
    try:
        # Make the pipeline dir importable (agents/, paths, config)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import paths

        # Get today's date for the input file path
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Input path from demand collection
        input_path = os.path.join(
            str(paths.DEM_RESEARCH),
            f"{date_str}_demand_trends_research.json"
        )

        if not os.path.exists(input_path):
            sys.stderr.write(f"ERROR: Input file not found at {input_path}\n")
            sys.stderr.write("Please run the demand collector first: python run_interior_demand.py\n")
            sys.exit(1)

        from agents.analyze_demand import analyze_demand
        analyze_demand(input_path)

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
