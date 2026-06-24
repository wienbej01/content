#!/usr/bin/env python3
"""Regression suite CI entrypoint — runs all local no-render checks.

Usage:
  python3 scripts/evals/run_video_regression_suite.py \\
      --fixture fixtures/bad_runs/<production_id> \\
      --out reports/karpathy_loop/regression/latest.json
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PRODUCTION_ID = "prod_2f9bb58c0508465fb51ac6b4578bba92"
DB_PATH = os.environ.get("PRODUCTION_DB_PATH", "db/production.db")


def run(cmd: list, timeout: int = 120) -> dict:
    """Run a command and return result."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"returncode": r.returncode, "stdout": r.stdout[:500], "stderr": r.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "TIMEOUT"}
    except FileNotFoundError:
        return {"returncode": -2, "stdout": "", "stderr": f"Command not found: {cmd[0]}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Video regression suite")
    ap.add_argument("--fixture", type=Path, default=Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92"))
    ap.add_argument("--out", type=Path, default=Path("reports/karpathy_loop/regression/latest.json"))
    args = ap.parse_args(argv)

    fixture = args.fixture
    if not fixture.exists():
        print(f"ERROR: Fixture not found: {fixture}", file=sys.stderr)
        return 1

    mp4 = fixture / "final_16x9.mp4" if fixture.is_dir() else fixture
    if not mp4.exists():
        print(f"ERROR: MP4 not found at {mp4}", file=sys.stderr)
        return 1

    python = sys.executable
    results = []

    # ── EVALS ──────────────────────────────────────────────────────────
    evals = [
        ("static_hold", ["scripts/evals/eval_static_hold.py",
         "--production-id", PRODUCTION_ID, "--out", "/tmp/reg_hold.json", "--db-path", DB_PATH]),

        ("master_window", ["scripts/evals/eval_master_window.py",
         "--production-id", PRODUCTION_ID, "--out", "/tmp/reg_window.json", "--db-path", DB_PATH]),

        ("lipsync_proxy", ["scripts/evals/eval_lipsync.py",
         "--video", str(mp4), "--out", "/tmp/reg_lipsync.json",
         "--subject-id", PRODUCTION_ID]),

        ("graphic_editorial", ["scripts/evals/eval_graphic_editorial.py",
         "--production-id", PRODUCTION_ID, "--out", "/tmp/reg_editorial.json", "--db-path", DB_PATH]),

        ("text_surface", ["scripts/evals/eval_text_surface.py",
         "--production-id", PRODUCTION_ID, "--out", "/tmp/reg_text.json", "--db-path", DB_PATH]),

        ("deterministic_graphics", ["scripts/evals/eval_deterministic_graphics.py",
         "--production-id", PRODUCTION_ID, "--out", "/tmp/reg_dg.json", "--db-path", DB_PATH]),

        ("repair_audit", ["scripts/evals/eval_repair_audit.py",
         "--production-id", PRODUCTION_ID, "--out", "/tmp/reg_audit.json", "--db-path", DB_PATH]),

        ("assembly_transform_ledger", ["scripts/evals/assembly_transform_ledger.py",
         "--production-id", PRODUCTION_ID, "--output", "/tmp/reg_assembly.json", "--db-path", DB_PATH]),
    ]

    for name, cmd in evals:
        r = run([python] + cmd)
        r["eval_name"] = name
        r["command"] = " ".join(cmd)
        results.append(r)

    # ── TESTS ───────────────────────────────────────────────────────────
    test_dirs = ["tests/test_repair_map.py", "tests/test_repair_from_validations.py",
                 "tests/test_minimal_stage_routing.py", "tests/test_repair_audit.py",
                 "tests/test_final_defect_ledger.py", "tests/test_run_comparison.py",
                 "tests/test_gate_b_evidence.py"]
    for td in test_dirs:
        r = run([python, "-m", "pytest", td, "-q", "--tb=short"])
        r["eval_name"] = f"pytest:{td}"
        results.append(r)

    # ── REPORT ──────────────────────────────────────────────────────────
    passes = sum(1 for r in results if r.get("returncode") == 0)
    fails = sum(1 for r in results if r.get("returncode") != 0)

    report = {
        "suite": "video_regression_suite",
        "production_id": PRODUCTION_ID,
        "fixture": str(mp4),
        "fixture_exists": mp4.exists(),
        "sha256": "35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386",
        "total_checks": len(results),
        "passed": passes,
        "failed": fails,
        "details": results,
        "render_lock": {
            "YT_TEST_MODE": os.environ.get("YT_TEST_MODE", "unset"),
            "HIGGSFIELD_DRY_RUN": os.environ.get("HIGGSFIELD_DRY_RUN", "unset"),
            "KARPATHY_LOOP_RENDER_LOCK": os.environ.get("KARPATHY_LOOP_RENDER_LOCK", "unset"),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))

    print(f"\nRegression Suite: {passes}/{len(results)} checks pass ({fails} failed)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
