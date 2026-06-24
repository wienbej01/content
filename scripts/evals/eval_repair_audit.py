#!/usr/bin/env python3
"""Repair audit report — shows what repair would do and whether it would spend/render.

Usage:
  python3 scripts/evals/eval_repair_audit.py --production-id <id> --out <json>
"""
import argparse
import json
import os
import sys
from pathlib import Path


RENDER_LOCK_ENVS = {
    "YT_TEST_MODE": "1",
    "HIGGSFIELD_DRY_RUN": "1",
    "KARPATHY_LOOP_RENDER_LOCK": "1",
}

# Stages that would call a provider render
PROVIDER_RENDER_STAGES = {"render_media"}


def audit_production(production_id: str, db_path: str = None) -> dict:
    """Produce repair audit report."""
    import sqlite3
    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    # 1. Load open change_requests
    crs = conn.execute(
        "SELECT * FROM change_requests WHERE production_id=? AND status='open'",
        (production_id,),
    ).fetchall()

    # 2. Load failed validations (no repair action yet)
    failed_vals = conn.execute(
        "SELECT id, subject_id, validator_name, status, evidence_json "
        "FROM validations WHERE production_id=? AND status='fail'",
        (production_id,),
    ).fetchall()

    conn.close()

    change_requests = []
    for cr in crs:
        crd = dict(cr)
        target = crd.get("target_stage", "unknown")
        change_requests.append({
            "id": crd["id"],
            "subject_id": crd.get("subject_id"),
            "change_type": crd.get("change_type"),
            "target_stage": target,
            "reason": crd.get("reason"),
            "would_call_provider_render": target in PROVIDER_RENDER_STAGES,
        })

    # 3. Would any planned repair call provider render?
    would_render = any(cr["would_call_provider_render"] for cr in change_requests)

    # 4. Render lock status
    all_locked = all(
        os.environ.get(env) == val for env, val in RENDER_LOCK_ENVS.items()
    )
    render_lock_status = "PASS" if all_locked else "FAIL"

    # 5. Minimality check: are any change_requests targeting render_media
    #    when a non-render stage would suffice?
    issues = []
    for cr in change_requests:
        if cr["target_stage"] == "render_media":
            from repair_map import target_stage_for as _map_stage
            reason = cr.get("reason", "")
            fc = reason.replace("repair: ", "") if reason else ""
            mapped = _map_stage(fc) if fc else None
            if mapped and mapped != "render_media":
                issues.append(
                    f"change_request {cr['id']} routes to render_media but "
                    f"repair_map suggests {mapped} for {fc}"
                )

    # 6. Failing validations with no change_request
    if failed_vals:
        failed_ids = [v["subject_id"] for v in failed_vals]
        cr_subject_ids = {cr.get("subject_id") for cr in change_requests}
        unmatched = [fid for fid in failed_ids if fid not in cr_subject_ids]
        if unmatched:
            issues.append(f"{len(unmatched)} failed validations without open change_request: {unmatched[:3]}...")

    audit = {
        "production_id": production_id,
        "change_requests": change_requests,
        "failed_validation_count": len(failed_vals),
        "open_change_request_count": len(change_requests),
        "would_call_provider_render": would_render,
        "render_lock_status": render_lock_status,
        "minimality_ok": len(issues) == 0,
        "issues": issues,
    }
    return audit


def main(argv=None):
    ap = argparse.ArgumentParser(description="Repair audit report")
    ap.add_argument("--production-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = audit_production(args.production_id, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Repair audit for {result['production_id']}:")
    print(f"  Open change requests: {result['open_change_request_count']}")
    print(f"  Would call provider render: {result['would_call_provider_render']}")
    print(f"  Render lock status: {result['render_lock_status']}")
    print(f"  Minimality OK: {result['minimality_ok']}")
    if result.get("issues"):
        for iss in result["issues"]:
            print(f"  ! {iss}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
