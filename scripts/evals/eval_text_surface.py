#!/usr/bin/env python3
"""Provider text surface detection eval.

Scans BROLL_FLEX / generated_video units with NO_VISIBLE_TEXT policy and
checks whether QA enforced the policy via OCR.

Output: per-unit pass/fail/inconclusive.

Usage:
  python3 scripts/evals/eval_text_surface.py --production-id <id> --out <json>
"""
import argparse
import json
import os
import sys
from pathlib import Path


def eval_production(production_id: str, db_path: str = None) -> dict:
    """Check text-policy enforcement for all b-roll/provider video units."""
    import sqlite3
    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    # Find units with NO_VISIBLE_TEXT policy
    units = conn.execute("""
        SELECT ru.id, ru.label, ru.text_policy, ru.audio_policy, ru.asset_type,
               ru.status, ru.active_artifact_id
        FROM render_units ru
        WHERE ru.production_id=?
          AND (ru.text_policy='NO_VISIBLE_TEXT' OR ru.text_policy IS NOT NULL)
          AND ru.status NOT IN ('stale', 'cancelled')
        ORDER BY ru.ordinal
    """, (production_id,)).fetchall()

    if not units:
        return {
            "production_id": production_id,
            "count": 0, "status": "pass",
            "results": [], "note": "no units with text_policy found",
        }

    results = []
    for u in units:
        ru = dict(u)
        policy = (ru.get("text_policy") or "").strip().upper()

        # Get latest QA validation
        qa = conn.execute(
            "SELECT id, status, evidence_json FROM validations "
            "WHERE subject_id=? AND validator_name IN ('qa_media_contract','qa_media') "
            "ORDER BY created_at DESC LIMIT 1",
            (ru["id"],),
        ).fetchone()

        entry = {
            "render_unit_id": ru["id"],
            "label": ru.get("label", ""),
            "text_policy": policy,
            "audio_policy": ru.get("audio_policy", ""),
            "asset_type": ru.get("asset_type", ""),
            "has_qa": qa is not None,
            "qa_status": qa["status"] if qa else None,
        }

        if qa and qa["evidence_json"]:
            ev = json.loads(qa["evidence_json"])
            entry["ocr_available"] = ev.get("ocr_available", None)
            entry["ocr_frames_checked"] = ev.get("ocr_frames_checked", 0)
            entry["text_detected"] = ev.get("text_detected", None)
            entry["text_policy_ok"] = ev.get("text_policy_ok", None)
            entry["ocr_error"] = ev.get("ocr_error", None)
        else:
            entry["ocr_available"] = None
            entry["ocr_frames_checked"] = 0
            entry["text_detected"] = None
            entry["text_policy_ok"] = None

        # Determine status
        if policy == "NO_VISIBLE_TEXT":
            if entry.get("text_policy_ok") is True:
                entry["status"] = "pass"
            elif entry.get("text_policy_ok") is False:
                if entry.get("text_detected"):
                    entry["status"] = "fail"
                    entry["note"] = "visible_text_detected"
                elif entry.get("ocr_error"):
                    entry["status"] = "fail"
                    entry["note"] = f"ocr_unavailable: {entry['ocr_error']}"
                else:
                    entry["status"] = "fail"
                    entry["note"] = "text_policy_violation"
            else:
                # No QA or incomplete evidence
                entry["status"] = "inconclusive"
                entry["note"] = "requires_human_review: ocr_not_performed"
        else:
            entry["status"] = "pass"
            entry["note"] = f"policy_{policy}_no_enforcement_needed"

        results.append(entry)

    conn.close()

    # Summarize
    statuses = [r["status"] for r in results]
    if "fail" in statuses:
        overall = "fail"
    elif "inconclusive" in statuses:
        overall = "inconclusive"
    else:
        overall = "pass"

    return {
        "production_id": production_id,
        "count": len(results),
        "status": overall,
        "results": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Provider text surface detection")
    ap.add_argument("--production-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = eval_production(args.production_id, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Text surface eval for {result['production_id']}:")
    print(f"  Units: {result['count']}, Status: {result['status']}")
    for r in result.get("results", []):
        print(f"  [{r['label']}] policy={r['text_policy']} "
              f"status={r['status']} "
              f"ocr={'ok' if r.get('text_policy_ok') else 'unavailable' if r.get('ocr_error') else 'pending'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
