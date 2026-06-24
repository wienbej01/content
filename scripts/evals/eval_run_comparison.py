#!/usr/bin/env python3
"""Run comparison report — compares baseline bad fixture against candidate output.

If no candidate exists (render locked), produces diagnostic baseline-only report.

Usage:
  python3 scripts/evals/eval_run_comparison.py --out <json>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PRODUCTION_ID = "prod_2f9bb58c0508465fb51ac6b4578bba92"
FIXTURE = Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")

# Eval scripts that can run independently (no DB, no candidate artifact required)
EVAL_SCRIPTS = [
    ("lipsync_mouth_motion_proxy", "scripts/evals/eval_lipsync.py",
     ["--video", str(FIXTURE)]),
    # provider_audio_correlation skipped: requires two separate WAV files, not fixture MP4
    # Can be run manually with prepared test fixtures after Sprint 06 unlock
    ("static_hold", "scripts/evals/eval_static_hold.py",
     ["--production-id", PRODUCTION_ID]),
    ("graphic_editorial", "scripts/evals/eval_graphic_editorial.py",
     ["--production-id", PRODUCTION_ID]),
    ("text_surface", "scripts/evals/eval_text_surface.py",
     ["--production-id", PRODUCTION_ID]),
    ("master_window", "scripts/evals/eval_master_window.py",
     ["--production-id", PRODUCTION_ID]),
    ("deterministic_graphics", "scripts/evals/eval_deterministic_graphics.py",
     ["--production-id", PRODUCTION_ID]),
    ("repair_audit", "scripts/evals/eval_repair_audit.py",
     ["--production-id", PRODUCTION_ID]),
]

# DB-based evals that need explicit db-path
DB_EVAL_SCRIPTS = [
    ("assembly_transform_ledger", "scripts/evals/assembly_transform_ledger.py",
     ["--production-id", PRODUCTION_ID]),
]


def run_eval(name: str, script: str, args: list, db_path: str = None) -> dict:
    """Run an eval script and capture its output."""
    cmd = [sys.executable, script]
    if db_path:
        cmd.extend(["--db-path", db_path])
    cmd.extend(args)
    out = f"/tmp/eval_comparison_{name}.json"
    # Add output flag if the script doesn't already have one
    args_str = " ".join(args)
    if "--out" not in args_str and "--output" not in args_str:
        cmd.extend(["--out", out])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        success = r.returncode == 0
        output = r.stdout.strip()
        error = r.stderr.strip()[:500] if r.stderr else ""
    except subprocess.TimeoutExpired:
        success = False
        output = ""
        error = "TIMEOUT"

    result_file = Path(out)
    result_data = None
    if result_file.exists():
        try:
            result_data = json.loads(result_file.read_text())
            result_file.unlink()  # clean up
        except json.JSONDecodeError:
            pass

    return {
        "eval_name": name,
        "script": script,
        "success": success,
        "result": result_data,
        "stdout": output[:200] if output else "",
        "error": error[:200] if error else "",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run comparison report")
    ap.add_argument("--out", type=Path,
                    default=Path("reports/karpathy_loop/sprint_05/S05_T002/eval_result_before.json"))
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    baseline_results = []
    failed_count = 0

    print("Running comparison evals...")
    # Run all independent evals
    for name, script, script_args in EVAL_SCRIPTS:
        result = run_eval(name, script, script_args, db_path=args.db_path)
        baseline_results.append(result)
        status = "OK" if result["success"] else "FAIL"
        result_type = type(result["result"]).__name__ if result["result"] else "no_output"
        print(f"  [{status}] {name}: {result_type}")
        if not result["success"]:
            failed_count += 1

    # Run DB-dependent evals
    for name, script, script_args in DB_EVAL_SCRIPTS:
        result = run_eval(name, script, script_args, db_path=args.db_path)
        baseline_results.append(result)
        status = "OK" if result["success"] else "FAIL"
        print(f"  [{status}] {name}: {result_type}")
        if not result["success"]:
            failed_count += 1

    # Build report
    report = {
        "production_id": PRODUCTION_ID,
        "fixture": str(FIXTURE),
        "fixture_size_bytes": FIXTURE.stat().st_size if FIXTURE.exists() else 0,
        "fixture_sha256": "35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386",
        "candidate_available": False,
        "candidate_path": None,
        "candidate_note": "No candidate output available — render lock active (Sprint 05: RENDER_LEVEL <= 3). "
                          "Candidate can be produced in Sprint 06 after readiness unlock.",
        "baseline_count": len(baseline_results),
        "baseline_passed": sum(1 for r in baseline_results if r["success"]),
        "baseline_failed": failed_count,
        "baseline_results": baseline_results,
        "comparison": {
            "status": "baseline_only",
            "note": "Diagnostic baseline-only report. No candidate to compare against.",
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))

    print(f"\nComparison report for {PRODUCTION_ID}:")
    print(f"  Baseline evals: {report['baseline_count']}")
    print(f"  Passed: {report['baseline_passed']}")
    print(f"  Failed: {report['baseline_failed']}")
    print(f"  Candidate: {'N/A' if not report['candidate_available'] else report['candidate_path']}")
    print(f"  Status: {report['comparison']['status']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
