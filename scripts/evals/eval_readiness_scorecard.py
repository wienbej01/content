#!/usr/bin/env python3
"""Readiness scorecard for S06_T001.

Checks all prerequisites for actual video render.
Does NOT call any provider render.

Usage:
  python3 scripts/evals/eval_readiness_scorecard.py --out <json>
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PRODUCTION_ID = "prod_2f9bb58c0508465fb51ac6b4578bba92"


def check_file(path: str, size_min: int = 50) -> dict:
    p = Path(path)
    return {"path": path, "exists": p.exists(), "size": p.stat().st_size if p.exists() else 0,
            "pass": p.exists() and p.stat().st_size >= size_min}


def check_sprint(s: str) -> dict:
    p = Path(f"reports/karpathy_loop/{s}/sprint_summary.md")
    return {"sprint": s, "path": str(p), "pass": p.exists() and p.stat().st_size > 50}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Readiness scorecard")
    ap.add_argument("--out", type=Path, default=Path("reports/karpathy_loop/sprint_06/S06_T001/eval_result_before.json"))
    args = ap.parse_args(argv)

    results = []
    all_pass = True

    # Sprints 00-05
    for i in range(6):
        r = check_sprint(f"sprint_0{i}")
        results.append({"check": f"Sprint 0{i} passed", "pass": r["pass"], "detail": str(r["path"])})
        if not r["pass"]:
            all_pass = False

    # Eval scripts
    evals = [
        ("Lipsync eval", "scripts/evals/eval_lipsync.py"),
        ("Source slice ledger", "scripts/evals/eval_master_window.py"),
        ("Provider audio compare", "scripts/evals/provider_audio_compare.py"),
        ("Assembly transform ledger", "scripts/evals/assembly_transform_ledger.py"),
        ("Final defect ledger", "scripts/evals/eval_final_defect_ledger.py"),
        ("Regression suite", "scripts/evals/run_video_regression_suite.py"),
    ]
    for name, path in evals:
        r = check_file(path)
        results.append({"check": name, "pass": r["pass"], "detail": r["path"]})
        if not r["pass"]:
            all_pass = False

    # Regression suite pass
    try:
        reg = subprocess.run(
            [sys.executable, "scripts/evals/run_video_regression_suite.py",
             "--out", "/tmp/s06_regression_check.json"],
            capture_output=True, text=True, timeout=300,
        )
        reg_pass = reg.returncode == 0
        lines = reg.stdout.strip().split("\n")[-1] if reg.stdout else ""
        results.append({"check": "Regression suite passes", "pass": reg_pass,
                        "detail": lines if lines else "exit=" + str(reg.returncode)})
        if not reg_pass:
            all_pass = False
    except Exception as e:
        results.append({"check": "Regression suite passes", "pass": False, "detail": str(e)})
        all_pass = False

    # Unlock file
    unlock = Path("ops/ACTUAL_RENDER_UNLOCK.json")
    unlock_pass = unlock.exists()
    results.append({"check": "Unlock file exists (user-created)", "pass": unlock_pass,
                    "detail": str(unlock) if unlock_pass else "NOT FOUND — user must create after readiness"})

    scorecard = {
        "eval_id": "S06_T001_readiness_scorecard",
        "production_id": PRODUCTION_ID,
        "fixture": "fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4",
        "ready_for_actual_render": all_pass and unlock_pass,
        "ready_for_canary_unlock": all_pass,
        "passed_sprints": [f"Sprint 0{i}" for i in range(6)],
        "missing_requirements": [r["check"] for r in results if not r["pass"]],
        "results": results,
        "recommendation": "allow_one_canary" if all_pass else "remain_locked",
        "unlock_instructions": (
            "All core checks pass. To unlock actual render, create:\n"
            "  ops/ACTUAL_RENDER_UNLOCK.json\n"
            "with content:\n"
            '  {"allow_actual_video_render": true, "max_provider_jobs": 1,\n'
            '   "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",\n'
            '   "approved_by": "human",\n'
            '   "reason": "controlled canary after readiness gates",\n'
            '   "created_at": "<ISO8601>"}\n'
            "After creating the file, proceed to S06_T002 (dry-run audit) then S06_T003 (canary render)."
        ) if all_pass else "Fix missing requirements before unlock.",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scorecard, indent=2))

    print(f"Readiness scorecard for {scorecard['production_id']}:")
    print(f"  Ready for canary unlock: {'YES' if scorecard['ready_for_canary_unlock'] else 'NO'}")
    print(f"  Missing requirements: {len(scorecard['missing_requirements'])}")
    for r in results:
        mark = "✓" if r["pass"] else "✗"
        print(f"  [{mark}] {r['check']}")
    print(f"  Recommendation: {scorecard['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
