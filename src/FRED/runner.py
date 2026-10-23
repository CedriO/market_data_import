import sys
import time
import importlib
from pathlib import Path
import traceback

# Ensure src/ is on the Python path
FRED_DIR = Path(__file__).resolve().parent
SRC_DIR = FRED_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))


def find_job_modules():
    """Scans src/FRED for all files starting with job_*.py (excluding runner.py)."""
    job_files = sorted(FRED_DIR.glob("job_*.py"))
    return [f.stem for f in job_files]


def get_job_callable(module_name: str):
    """Dynamically imports the module and finds its executable entrypoint."""
    module = importlib.import_module(f"FRED.{module_name}")

    # Standard candidate function names
    candidate_funcs = ["run_scheduled_job", "main", "run_job"]
    for func_name in candidate_funcs:
        func = getattr(module, func_name, None)
        if callable(func):
            return func

    raise AttributeError(
        f"Module '{module_name}' has no standard entrypoint function "
        f"({', '.join(candidate_funcs)})."
    )


def run_all_reports():
    """Orchestrates all discovered FRED report jobs sequentially.
    
    Fault tolerant: A failure in one report does not stop subsequent reports.
    """
    job_modules = find_job_modules()

    if not job_modules:
        print("[RUNNER] No report jobs found (expected files matching 'job_*.py').")
        return

    print("==================================================")
    print("        STARTING FRED DATA IMPORT RUNNER          ")
    print(f"  Discovered {len(job_modules)} report job(s):")
    for j in job_modules:
        print(f"   • {j}")
    print("==================================================\n")

    summary = []
    total_start = time.time()

    for idx, module_name in enumerate(job_modules, start=1):
        report_display = module_name.replace("job_", "").replace("_", " ").title()
        print(f"[{idx}/{len(job_modules)}] Running Report: {report_display} ({module_name})")
        
        job_start = time.time()
        try:
            job_func = get_job_callable(module_name)
            job_func()
            elapsed = round(time.time() - job_start, 2)
            print(f"✓ [{report_display}] Finished successfully in {elapsed}s.\n")
            summary.append((report_display, "SUCCESS", elapsed, None))

        except Exception as e:
            elapsed = round(time.time() - job_start, 2)
            print(f"✗ [{report_display}] FAILED after {elapsed}s: {e}")
            traceback.print_exc()
            print("→ Continuing to next report...\n")
            summary.append((report_display, "FAILED", elapsed, str(e)))

    total_elapsed = round(time.time() - total_start, 2)

    # Execution Summary Table
    print("==================================================")
    print("               PIPELINE RUN SUMMARY               ")
    print("==================================================")
    for report, status, duration, error in summary:
        status_icon = "✓" if status == "SUCCESS" else "✗"
        err_msg = f" | Error: {error}" if error else ""
        print(f"{status_icon} {report:<25} [{status}] ({duration}s){err_msg}")
    print("--------------------------------------------------")
    print(f"Total Duration: {total_elapsed}s")
    print("==================================================")


if __name__ == "__main__":
    run_all_reports()