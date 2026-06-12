#!/usr/bin/env python3
"""approve.py — Thin human-approval CLI that writes gates into the ledger.

This is the switch that arms generate_media.py. No render_approval entry in
gates.json → generate_media.py exits 1 before any Higgsfield call (blueprint G7).

It also provides the human override path for the budget gate (G4): a human can
raise the cap, which writes an audited ledger entry rather than silently passing.

Usage:
    # Human render approval (G7) — must reference the dry-run report just read.
    python3 scripts/approve.py <project_id> --gate render \
        --dryrun Videos/Projects/<id>/dryrun_report.json --by "operator"

    # Budget override (G4) — explicit, audited cap raise.
    python3 scripts/approve.py <project_id> --gate budget \
        --media-plan Videos/Projects/<id>/media_plan.json --cap-override 90 --by "operator"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gates import record_gate, project_dir  # noqa: E402


def approve_render(project_id: str, dryrun_path: str | None, approved_by: str) -> None:
    """Record the render_approval (G7) gate, binding it to the dry-run report hash."""
    if dryrun_path is None:
        # Default to the conventional location.
        dryrun_path = str(project_dir(project_id) / "dryrun_report.json")
    if not Path(dryrun_path).exists():
        sys.stderr.write(
            f"ERROR: dry-run report not found: {dryrun_path}\n"
            f"  Run: python3 scripts/generate_media.py <media_plan.json> --dry-run\n"
            f"  before approving — a human must read the report being approved.\n")
        sys.exit(1)
    entry = record_gate(
        project_id, "render_approval", "pass",
        artifact_path=dryrun_path, approved_by=approved_by,
        extra={"note": "human render approval; binds to dry-run report hash"})
    print(f"✓ render_approval recorded for {project_id} (approved_by={approved_by})")
    print(f"  bound to dry-run report: {dryrun_path}")
    print(f"  generate_media.py is now armed to spend for this project.")
    return entry


def override_budget(project_id: str, media_plan_path: str, cap_override: float,
                    approved_by: str) -> None:
    """Record an audited budget (G4) override."""
    if not Path(media_plan_path).exists():
        sys.stderr.write(f"ERROR: media plan not found: {media_plan_path}\n")
        sys.exit(1)
    entry = record_gate(
        project_id, "budget", "pass",
        artifact_path=media_plan_path, approved_by=approved_by, forced=True,
        extra={"override": True, "cap_override_usd": cap_override,
               "note": "human budget override — cap raised explicitly"})
    sys.stderr.write(
        f"\033[33m⚠ BUDGET OVERRIDE: cap raised to ${cap_override:.2f} for "
        f"{project_id} by {approved_by}. Audited in gates.json.\033[0m\n")
    print(f"✓ budget override recorded for {project_id} (cap=${cap_override:.2f}, by={approved_by})")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Human approval CLI for pipeline gates.")
    ap.add_argument("project_id")
    ap.add_argument("--gate", required=True, choices=["render", "budget"])
    ap.add_argument("--by", default="human", help="Approver name (recorded in ledger)")
    ap.add_argument("--dryrun", default=None, help="Path to dry-run report (render gate)")
    ap.add_argument("--media-plan", default=None, help="Path to media_plan.json (budget gate)")
    ap.add_argument("--cap-override", type=float, default=None, help="New USD cap (budget gate)")
    args = ap.parse_args(argv)

    if args.gate == "render":
        approve_render(args.project_id, args.dryrun, args.by)
    elif args.gate == "budget":
        if args.media_plan is None or args.cap_override is None:
            ap.error("--gate budget requires --media-plan and --cap-override")
        override_budget(args.project_id, args.media_plan, args.cap_override, args.by)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
