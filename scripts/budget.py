#!/usr/bin/env python3
"""budget.py — G4 budget gate for the YTchannel pipeline.

Reads media_plan.json totals vs caps (from configs/james/model_routing.yaml),
flags any beat costing >$3 without a justification field, requires ≥15% of
beats on $0 routes, and writes a gates.py ledger entry.

Human override only via:
  python3 scripts/approve.py <project_id> --gate budget --cap-override <usd>

Usage:
  python3 scripts/budget.py Videos/Projects/<id>/media_plan.json
  python3 scripts/budget.py media_plan.json --record-gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTING_PATH = ROOT / "configs" / "james" / "model_routing.yaml"
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_caps():
    try:
        import yaml
        cfg = yaml.safe_load(ROUTING_PATH.read_text()) if ROUTING_PATH.exists() else {}
    except Exception:
        cfg = {}
    caps = cfg.get("budget_caps", {})
    return {"explainer": caps.get("explainer", 60), "short": caps.get("short", 25)}


def check(plan: dict) -> tuple[list[str], list[str]]:
    """Return (blocking_errors, warnings)."""
    blocking, warnings = [], []
    beats = plan.get("beats", [])
    totals = plan.get("totals", {})
    video_type = plan.get("video_type", "explainer")
    caps = _load_caps()
    cap = caps.get(video_type, caps["explainer"])

    est_usd = totals.get("est_usd", 0)
    if est_usd > cap:
        blocking.append(
            f"est_usd ${est_usd:.2f} exceeds budget cap ${cap:.2f} for {video_type!r}. "
            f"Override via: python3 scripts/approve.py <project_id> --gate budget "
            f"--cap-override <usd> --by <name>")

    # Per-beat anomaly: >$3 without justification.
    for b in beats:
        usd = b.get("cost", {}).get("est_usd", 0)
        if usd > 3.0 and not b.get("justification"):
            blocking.append(f"beat {b.get('beat_id')}: ${usd:.2f} > $3 without justification")

    # ≥15% of beats must be on $0 routes.
    total_beats = len(beats)
    zero_beats = sum(1 for b in beats if b.get("cost", {}).get("est_usd", 0) == 0)
    zero_pct = round(100 * zero_beats / total_beats, 1) if total_beats else 0
    if zero_pct < 15:
        blocking.append(
            f"only {zero_pct}% of beats on $0 routes (minimum 15%); "
            "move more graphics/kinetic/stills to local rendering")
    else:
        warnings.append(f"{zero_pct}% of beats are $0 local/still paths (≥15% ✓)")

    return blocking, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Budget gate G4 for media_plan.json.")
    ap.add_argument("media_plan", help="Path to media_plan.json")
    ap.add_argument("--record-gate", action="store_true",
                    help="Write the budget gate result to the project ledger")
    ap.add_argument("--project-id", default=None)
    ap.add_argument("--report", default=None, metavar="FILE",
                    help="Write budget report JSON to FILE")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print results without recording the gate")
    args = ap.parse_args(argv)

    path = Path(args.media_plan).resolve()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1

    plan = json.loads(path.read_text())
    blocking, warnings = check(plan)

    status = "pass" if not blocking else "fail"
    report = {
        "gate": "budget", "status": status,
        "est_usd": plan.get("totals", {}).get("est_usd"),
        "blocking": blocking, "warnings": warnings,
    }

    for w in warnings:
        print(f"  ℹ {w}")
    if blocking:
        for b in blocking:
            print(f"  ✗ {b}", file=sys.stderr)
    else:
        print(f"  ✓ budget OK: ${plan.get('totals',{}).get('est_usd',0):.2f}")

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"  report: {args.report}")

    if args.record_gate and not args.dry_run:
        from gates import record_gate
        pid = args.project_id or plan.get("project_id")
        if not pid:
            print("ERROR: --record-gate needs a project id", file=sys.stderr)
            return 1
        record_gate(pid, "budget", status, artifact_path=str(path),
                    extra={"est_usd": plan.get("totals", {}).get("est_usd"),
                           "blocking": len(blocking)})
        print(f"  gate budget={status} recorded for {pid}")

    return 0 if not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
