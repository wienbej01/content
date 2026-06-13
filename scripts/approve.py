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
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gates import record_gate, project_dir, gate_status, artifact_sha256, _now  # noqa: E402


def _storyboard_content_hash(sb: dict) -> str:
    """SHA-256 of the storyboard's MEANINGFUL content (approval block excluded).

    Stamping approval into the file must not change this hash — so approval is
    idempotent and 'what was approved' == 'what will render' is verifiable."""
    import copy, hashlib
    body = copy.deepcopy(sb)
    body.pop("approval", None)
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def approve_storyboard(project_id: str, storyboard_path: str | None, approved_by: str) -> None:
    """Human approval of a storyboard (blueprint §4): move approval.status
    draft → approved and stamp approved_by / approved_at / sha256_at_approval.

    Guard: refuses unless the G2 `storyboard_review` gate has passed AND its
    recorded hash still matches the current file (no approving a failed or
    edited-since storyboard)."""
    if storyboard_path is None:
        storyboard_path = str(project_dir(project_id) / "storyboard.json")
    sp = Path(storyboard_path)
    if not sp.exists():
        sys.stderr.write(f"ERROR: storyboard not found: {storyboard_path}\n")
        sys.exit(1)

    # G2 must have passed against the CURRENT storyboard file hash.
    cur_hash = artifact_sha256(str(sp))
    entry = gate_status(project_id, "storyboard_review")
    if entry is None or entry.get("status") != "pass":
        sys.stderr.write(
            "ERROR: storyboard_review (G2) has not passed. Run:\n"
            f"  python3 scripts/review_storyboard.py {storyboard_path} --record-gate\n")
        sys.exit(1)
    if entry.get("artifact_sha256") != cur_hash:
        sys.stderr.write(
            "ERROR: storyboard has changed since G2 review (stale gate). Re-run:\n"
            f"  python3 scripts/review_storyboard.py {storyboard_path} --record-gate\n"
            "  then approve again.\n")
        sys.exit(1)

    sb = json.loads(sp.read_text())
    # Record the CONTENT hash (approval-excluded) so the stamp is idempotent.
    content_hash = _storyboard_content_hash(sb)
    sb["approval"] = {
        "status": "approved",
        "approved_by": approved_by,
        "approved_at": _now(),
        "sha256_at_approval": content_hash,
    }
    sp.write_text(json.dumps(sb, indent=2))
    # Re-record the G2 gate bound to the new FILE hash so require_gates stays fresh.
    record_gate(project_id, "storyboard_review", "pass",
                artifact_path=str(sp), approved_by=approved_by,
                extra={"note": "storyboard human-approved",
                       "content_sha256": content_hash})
    print(f"✓ storyboard approved for {project_id} (approved_by={approved_by})")
    print(f"  approval.status = approved")
    print(f"  content sha256 (approval-excluded) = {content_hash[:12]}")


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


def approve_canary(project_id: str, clip_path: str | None, approved_by: str) -> None:
    """Record the canary (T9b) gate after a human reviews the single canary clip.

    Per the lipsync ticket board, the canary is rendered AFTER media_plan_review +
    budget are fresh, and render_approval (full render) comes AFTER this canary
    human pass. Binds to the reviewed clip's hash when provided so a re-render
    invalidates the approval.
    """
    extra = {"note": "human canary review pass (single shortest lipsync render group)"}
    artifact = None
    if clip_path is not None:
        if not Path(clip_path).exists():
            sys.stderr.write(f"ERROR: canary clip not found: {clip_path}\n")
            sys.exit(1)
        artifact = clip_path
    entry = record_gate(
        project_id, "canary", "pass",
        artifact_path=artifact, approved_by=approved_by, extra=extra)
    print(f"✓ canary recorded for {project_id} (approved_by={approved_by})")
    if artifact:
        print(f"  bound to canary clip: {artifact}")
    print("  full hero render may proceed once render_approval is recorded against the fresh dry-run report.")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Human approval CLI for pipeline gates.")
    ap.add_argument("project_id")
    ap.add_argument("--gate", required=True, choices=["storyboard", "render", "budget", "canary"])
    ap.add_argument("--by", default="human", help="Approver name (recorded in ledger)")
    ap.add_argument("--storyboard", default=None, help="Path to storyboard.json (storyboard gate)")
    ap.add_argument("--dryrun", default=None, help="Path to dry-run report (render gate)")
    ap.add_argument("--media-plan", default=None, help="Path to media_plan.json (budget gate)")
    ap.add_argument("--cap-override", type=float, default=None, help="New USD cap (budget gate)")
    ap.add_argument("--clip", default=None, help="Path to canary clip reviewed (canary gate)")
    args = ap.parse_args(argv)

    if args.gate == "storyboard":
        approve_storyboard(args.project_id, args.storyboard, args.by)
    elif args.gate == "render":
        approve_render(args.project_id, args.dryrun, args.by)
    elif args.gate == "canary":
        approve_canary(args.project_id, args.clip, args.by)
    elif args.gate == "budget":
        if args.media_plan is None or args.cap_override is None:
            ap.error("--gate budget requires --media-plan and --cap-override")
        override_budget(args.project_id, args.media_plan, args.cap_override, args.by)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
