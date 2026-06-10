#!/usr/bin/env python3
"""
Run Interior Professional Trend Collection
Collects RSS feed data from professional design publications
"""
import sys
import os

# Set UTF-8 encoding for Windows before any imports
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Make the pipeline dir importable (collectors/, config, paths live here)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        from collectors.interior_professional import run_interior_professional_collection
        run_interior_professional_collection()

    except Exception as e:
        sys.stderr.write(f"\nERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
