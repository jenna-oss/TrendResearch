#!/usr/bin/env python3
"""
Run Professional Trends Analysis
Analyzes raw professional trend signals to extract, cluster, and rank patterns
"""
import sys
import os
from datetime import datetime

# Set UTF-8 encoding for Windows before any imports
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    try:
        # Make the pipeline dir importable (agents/, paths, config)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import paths

        # Get today's date
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Input path from professional trend collection
        input_path = os.path.join(
            str(paths.PRO_RESEARCH),
            f"{date_str}_professional_trends_research.json"
        )

        if not os.path.exists(input_path):
            sys.stderr.write(f"ERROR: Input file not found at {input_path}\n")
            sys.stderr.write("Please run the professional trend collector first: python run_interior_professional.py\n")
            sys.exit(1)

        from agents.analyze_trends import analyze_trends
        analyze_trends(input_path)

    except Exception as e:
        sys.stderr.write(f"\nERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
