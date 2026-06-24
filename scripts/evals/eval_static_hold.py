#!/usr/bin/env python3
"""Static graphic hold gate eval.

Checks that local graphic units exceed hold thresholds and that the
assembly gate would flag them.

Usage:
  python3 scripts/evals/eval_static_hold.py --production-id <id> --out <json>
"""
import argparse
import json
import logging
import sys
from pathlib import Path

WARN_MS = 4000
FAIL_MS = 6000


def eval_production(production_id: str, db_path: str = None) -> dict:
    """Check local graphic units for excessive hold durations."""
    import sqlite3
    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    units = conn.execute("""
        SELECT ru.id, ru.label, ru.required_start_ms, ru.required_end_ms,
               ru.required_duration_ms, ru.asset_type, ru.metadata_json
        FROM render_units ru
        WHERE ru.production_id=? AND ru.asset_type='local_graphic'
          AND ru.status NOT IN ('stale', 'cancelled')
        ORDER BY ru.ordinal
    """, (production_id,)).fetchall()

    if not units:
        return {"production_id": production_id, "count": 0, "status": "pass",
                "results": [], "note": "no local graphic units"}

    results = []
    for u in units:
        ru = dict(u)
        dur = ru.get("required_duration_ms", 0) or 0
        start = ru.get("required_start_ms", 0) or 0
        end = ru.get("required_end_ms", 0) or 0
        label = (ru.get("label") or "").lower()
        is_hold = "hold" in label

        if dur > FAIL_MS and not is_hold:
            status = "fail"
            issue = f"hold_{dur}ms_exceeds_{FAIL_MS}ms"
        elif dur > WARN_MS and not is_hold:
            status = "warn"
            issue = f"hold_{dur}ms_exceeds_{WARN_MS}ms"
        elif dur > FAIL_MS and is_hold:
            status = "pass"
            issue = f"hold_{dur}ms_allowed_via_hold_policy"
        elif dur > WARN_MS and is_hold:
            status = "pass"
            issue = f"hold_{dur}ms_allowed_via_hold_policy"
        else:
            status = "pass"
            issue = f"hold_{dur}ms_within_threshold"

        entry = {
            "render_unit_id": ru["id"],
            "label": ru.get("label", ""),
            "duration_ms": dur,
            "hold_ms": dur,
            "start_ms": start,
            "end_ms": end,
            "warn_threshold_ms": WARN_MS,
            "fail_threshold_ms": FAIL_MS,
            "is_explicit_hold": is_hold,
            "status": status,
            "issue": issue,
        }
        results.append(entry)

    conn.close()

    statuses = [r["status"] for r in results]
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"
    else:
        overall = "pass"

    return {
        "production_id": production_id,
        "count": len(results),
        "status": overall,
        "thresholds": {"warn_static_graphic_hold_ms": WARN_MS, "fail_static_graphic_hold_ms": FAIL_MS},
        "results": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Static graphic hold gate eval")
    ap.add_argument("--production-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = eval_production(args.production_id, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Static hold eval for {result['production_id']}:")
    print(f"  Graphics: {result['count']}, Status: {result['status']}")
    print(f"  Thresholds: warn={WARN_MS}ms fail={FAIL_MS}ms")
    for r in result.get("results", []):
        print(f"  [{r['label']}] {r['duration_ms']}ms status={r['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
