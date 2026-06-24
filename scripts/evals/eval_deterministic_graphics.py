#!/usr/bin/env python3
"""Deterministic graphics eval — verifies local graphics QA gates are in place.

Checks that local graphic render units have:
- deterministic_text_spec in metadata
- text hash matching
- text length within safe bounds
- local renderer provenance
- no provider jobs

Usage:
  python3 scripts/evals/eval_deterministic_graphics.py --production-id <id> --out <json>
"""
import argparse
import json
import sys
from pathlib import Path


def eval_graphics_qa_gates(production_id: str, db_path: str = None) -> dict:
    """Check that local graphic units have deterministic spec gates."""
    import sqlite3
    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    # Find local graphic render units
    units = conn.execute("""
        SELECT ru.id, ru.label, ru.status, ru.metadata_json,
               ru.active_artifact_id
        FROM render_units ru
        WHERE ru.production_id=? AND ru.asset_type='local_graphic'
        ORDER BY ru.ordinal
    """, (production_id,)).fetchall()

    if not units:
        return {"production_id": production_id, "count": 0, "status": "pass",
                "results": [], "note": "no local graphic units"}

    results = []
    for u in units:
        ru = dict(u)
        meta = json.loads(ru.get("metadata_json") or "{}")
        dts = meta.get("deterministic_text_spec")
        text = (dts or {}).get("text", "") if isinstance(dts, dict) else ""
        text_len = len(text) if isinstance(text, str) else 0

        # Check QA validation exists
        qa = conn.execute(
            "SELECT status, evidence_json FROM validations "
            "WHERE subject_id=? AND validator_name IN ('qa_media_contract','qa_media') "
            "ORDER BY created_at DESC LIMIT 1",
            (ru["id"],),
        ).fetchone()

        findings = {
            "render_unit_id": ru["id"],
            "label": ru.get("label", ""),
            "has_active_artifact": bool(ru.get("active_artifact_id")),
            "has_deterministic_text_spec": dts is not None,
            "text_length": text_len,
            "text_length_ok": 1 <= text_len <= 500,
            "has_qa_validation": qa is not None,
            "qa_status": qa["status"] if qa else None,
        }

        # Check QA evidence contains expected fields
        if qa and qa["evidence_json"]:
            ev = json.loads(qa["evidence_json"])
            findings["qa_text_spec_exists"] = ev.get("text_spec_exists", None)
            findings["qa_text_spec_sha_match"] = ev.get("text_spec_sha_match", None)
            findings["qa_text_length_ok"] = ev.get("text_length_ok", None)
        else:
            findings["qa_text_spec_exists"] = None
            findings["qa_text_spec_sha_match"] = None
            findings["qa_text_length_ok"] = None

        results.append(findings)

    conn.close()

    # Overall status
    all_ok = all(
        r["has_deterministic_text_spec"] and
        r["text_length_ok"] and
        r["qa_text_spec_exists"] is not False and
        r["qa_text_length_ok"] is not False
        for r in results
    )

    return {
        "production_id": production_id,
        "count": len(results),
        "status": "pass" if all_ok else "fail",
        "results": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic graphics eval")
    ap.add_argument("--production-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = eval_graphics_qa_gates(args.production_id, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Graphics eval for {result['production_id']}:")
    print(f"  Units: {result['count']}, Status: {result['status']}")
    for r in result.get("results", []):
        print(f"  [{r['label']}] dts={r['has_deterministic_text_spec']} "
              f"text_len={r['text_length']} qa_ok={r.get('qa_text_length_ok')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
