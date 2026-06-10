#!/usr/bin/env python3
"""
Artis Interior Design Research Orchestrator

Runs professional and demand trend pipelines in parallel:
- Professional: Research → Analysis (sequential)
- Demand: Research → Analysis (sequential)
Both pipelines run concurrently
"""

import os
import subprocess
import sys
import threading
from datetime import datetime

# Directory holding the pipeline scripts (run_*.py); used as subprocess cwd so the
# same code runs locally and in CI regardless of where it's launched from.
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))


class PipelineExecutor:
    """Executes a pipeline and tracks results."""

    def __init__(self, name):
        self.name = name
        self.steps = []
        self.results = {}
        self.success = True

    def add_step(self, step_name, command, description=""):
        """Add a step to the pipeline."""
        self.steps.append({
            "name": step_name,
            "command": command,
            "description": description
        })

    def run(self):
        """Execute all steps in sequence."""
        print(f"\n{'='*70}")
        print(f"Starting: {self.name}")
        print(f"{'='*70}\n")

        for step in self.steps:
            print(f"\n[{self.name}] {step['name']}")
            if step['description']:
                print(f"  {step['description']}")
            print(f"  Command: {' '.join(step['command'])}")
            print("-" * 70)

            try:
                result = subprocess.run(
                    step["command"],
                    cwd=PIPELINE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=600
                )

                self.results[step["name"]] = {
                    "returncode": result.returncode,
                    "success": result.returncode == 0
                }

                if result.returncode == 0:
                    print(f"✅ {step['name']} completed successfully")
                    if result.stdout:
                        print(result.stdout)
                else:
                    print(f"❌ {step['name']} failed with return code {result.returncode}")
                    if result.stderr:
                        print("STDERR:", result.stderr)
                    if result.stdout:
                        print("STDOUT:", result.stdout)
                    self.success = False
                    break

            except subprocess.TimeoutExpired:
                print(f"❌ {step['name']} timed out (>600s)")
                self.results[step["name"]] = {"success": False, "error": "timeout"}
                self.success = False
                break

            except Exception as e:
                print(f"❌ {step['name']} failed: {e}")
                self.results[step["name"]] = {"success": False, "error": str(e)}
                self.success = False
                break

        print(f"\n{'='*70}")
        print(f"Completed: {self.name}")
        print(f"Status: {'✅ SUCCESS' if self.success else '❌ FAILED'}")
        print(f"{'='*70}\n")


def main():
    """Main orchestrator."""
    import paths
    paths.ensure_dirs()  # create the working-tree folders before any stage runs

    print(f"\n{'='*80}")
    print(f"ARTIS INTERIOR DESIGN RESEARCH ORCHESTRATOR")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")

    # Professional pipeline (sequential)
    professional = PipelineExecutor("Professional Trends Pipeline")
    professional.add_step(
        "Research",
        [sys.executable, "run_interior_professional.py"],
        "Collecting professional trend data from RSS feeds"
    )
    professional.add_step(
        "Analysis",
        [sys.executable, "run_analyze_professional_trends.py"],
        "Analyzing and clustering professional trends"
    )

    # Demand pipeline (sequential)
    demand = PipelineExecutor("Demand Trends Pipeline")
    demand.add_step(
        "Research",
        [sys.executable, "run_interior_demand.py"],
        "Collecting demand trend data from APIs and manual inputs"
    )
    demand.add_step(
        "Analysis",
        [sys.executable, "run_demand_analysis.py"],
        "Analyzing and clustering demand trends"
    )

    # Run pipelines in parallel
    print(f"\n{'='*80}")
    print(f"Launching parallel pipelines...")
    print(f"{'='*80}\n")

    prof_thread = threading.Thread(target=professional.run, daemon=False)
    demand_thread = threading.Thread(target=demand.run, daemon=False)

    prof_thread.start()
    demand_thread.start()

    # Wait for both to complete
    prof_thread.join()
    demand_thread.join()

    # Report generation (sequential, after both analyses complete)
    print(f"\n{'='*80}")
    print(f"Generating Trend Report...")
    print(f"{'='*80}\n")

    report = PipelineExecutor("Report Generation")
    report.add_step(
        "Generate",
        [sys.executable, "run_generate_report.py"],
        "Creating Artis-branded HTML and PDF trend report"
    )
    report.run()

    # Client strategies + UI refresh (processes every uploaded blueprint).
    # Runs as a streaming stage — editorial reasoning is long-running, well past
    # the per-step capture timeout used above.
    print(f"\n{'='*80}")
    print(f"Building Client Strategies + Web App Dataset...")
    print(f"{'='*80}\n")
    intake_success = True
    try:
        r = subprocess.run(
            [sys.executable, "run_client_intake.py"],
            cwd=PIPELINE_DIR,
        )
        intake_success = (r.returncode == 0)
    except Exception as e:
        print(f"❌ Client intake failed: {e}")
        intake_success = False

    # Summary report
    print(f"\n{'='*80}")
    print(f"ORCHESTRATION COMPLETE")
    print(f"{'='*80}\n")

    all_success = professional.success and demand.success

    print("Professional Trends Pipeline:")
    for step_name, result in professional.results.items():
        status = "✅" if result.get("success") else "❌"
        print(f"  {status} {step_name}: {'Success' if result.get('success') else 'Failed'}")

    print("\nDemand Trends Pipeline:")
    for step_name, result in demand.results.items():
        status = "✅" if result.get("success") else "❌"
        print(f"  {status} {step_name}: {'Success' if result.get('success') else 'Failed'}")

    print("\nReport Generation:")
    for step_name, result in report.results.items():
        status = "✅" if result.get("success") else "❌"
        print(f"  {status} {step_name}: {'Success' if result.get('success') else 'Failed'}")

    print("\nClient Strategies + Web App:")
    print(f"  {'✅' if intake_success else '❌'} Intake & UI dataset: {'Success' if intake_success else 'Failed'}")

    all_success = professional.success and demand.success and report.success and intake_success

    print(f"\n{'='*80}")
    print(f"Overall Status: {'✅ ALL PIPELINES COMPLETE' if all_success else '❌ SOME PIPELINES FAILED'}")
    print(f"{'='*80}\n")

    if all_success:
        print("📊 Output Files Generated:")
        date_str = datetime.now().strftime("%Y-%m-%d")
        print(f"  Professional Trends Research:")
        print(f"    Interior Professional Trends/Professional Trends Data/Research Data/")
        print(f"    {date_str}_professional_trends_research.json")
        print(f"  Professional Trends Analysis:")
        print(f"    Interior Professional Trends/Professional Trends Data/Analysis/")
        print(f"    {date_str}_professional_trends_analysis.json")
        print(f"  Demand Trends Research:")
        print(f"    Interior Professional Trends/Demand Trends Data/Research Data/")
        print(f"    {date_str}_demand_trends_research.json")
        print(f"  Demand Trends Analysis:")
        print(f"    Interior Professional Trends/Demand Trends Data/Analysis/")
        print(f"    {date_str}_demand_trends_analysis.json")
        print(f"  Trend Report:")
        print(f"    Interior Professional Trends/Reports/")
        print(f"    artis_interior_design_trend_report_{date_str.replace('-', '_')}.html")
        print(f"    artis_interior_design_trend_report_{date_str.replace('-', '_')}.pdf")
        print()
        sys.exit(0)
    else:
        print("⚠️  Check error messages above for failed steps.\n")
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        main()
    except Exception as e:
        print(f"\n❌ ORCHESTRATOR ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
