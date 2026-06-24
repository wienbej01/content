#!/usr/bin/env python3
"""Master audio window verification eval.

For each HERO_SYNC_LOCKED render unit, verifies that the master audio
window (speech_start_sample → speech_end_sample) matches the required
timeline window (required_start_ms → required_end_ms).

Usage:
  python3 scripts/evals/eval_master_window.py --production-id <id> --out <json>
"""
import argparse
import json
import sys
from pathlib import Path

# The sample rate used for speech sample storage (provider sample rate)
PROVIDER_SAMPLE_RATE = 48000
# Tolerance for window mismatch (ms)
WINDOW_TOLERANCE_MS = 100


def eval_hero_unit(ru: dict) -> dict:
    """Evaluate one HERO_SYNC_LOCKED unit's master window alignment."""
    unit_id = ru["id"]
    label = ru.get("label", "")
    req_start_ms = ru.get("required_start_ms", 0) or 0
    req_end_ms = ru.get("required_end_ms", 0) or 0
    req_dur_ms = ru.get("required_duration_ms", 0) or 0
    sp_start = ru.get("speech_start_sample")
    sp_end = ru.get("speech_end_sample")
    lead_silence = ru.get("leading_silence_samples", 0) or 0
    trail_silence = ru.get("trailing_silence_samples", 0) or 0
    slice_sha = ru.get("source_slice_sha256")
    master_sha = ru.get("master_audio_sha256")

    issues = []

    # 1. Check speech sample fields exist
    if sp_start is None or sp_end is None:
        return {
            "render_unit_id": unit_id, "label": label,
            "source_slice_sha256": slice_sha,
            "master_window_start_ms": None, "master_window_end_ms": None,
            "estimated_offset_ms": None, "duration_delta_ms": None,
            "status": "blocked",
            "issues": ["speech_samples_missing"],
        }

    # 2. Convert samples to ms
    sp_start_ms = int(sp_start / PROVIDER_SAMPLE_RATE * 1000)
    sp_end_ms = int(sp_end / PROVIDER_SAMPLE_RATE * 1000)
    sp_dur_ms = sp_end_ms - sp_start_ms

    # 3. Compare sample window with timeline window
    start_delta = sp_start_ms - req_start_ms
    end_delta = sp_end_ms - req_end_ms
    dur_delta = abs(req_dur_ms - sp_dur_ms)

    # 4. Include silence padding in window
    lead_ms = int((lead_silence or 0) / PROVIDER_SAMPLE_RATE * 1000)
    trail_ms = int((trail_silence or 0) / PROVIDER_SAMPLE_RATE * 1000)
    padded_start_ms = sp_start_ms - lead_ms
    padded_end_ms = sp_end_ms + trail_ms
    padded_dur_ms = padded_end_ms - padded_start_ms

    # 5. Determine status
    if abs(start_delta) > WINDOW_TOLERANCE_MS or abs(end_delta) > WINDOW_TOLERANCE_MS:
        status = "fail"
        if abs(start_delta) > WINDOW_TOLERANCE_MS:
            issues.append(f"window_start_offset_{start_delta}ms")
        if abs(end_delta) > WINDOW_TOLERANCE_MS:
            issues.append(f"window_end_offset_{end_delta}ms")
    elif dur_delta > WINDOW_TOLERANCE_MS and req_dur_ms > 0:
        status = "warn"
        issues.append(f"duration_delta_{dur_delta}ms")
    else:
        status = "pass"

    # 6. Check source_slice_sha256 (if column exists)
    if slice_sha is None:
        issues.append("source_slice_sha256_missing")
        if status == "pass":
            status = "warn"

    return {
        "render_unit_id": unit_id,
        "label": label,
        "source_slice_sha256": slice_sha,
        "master_audio_sha256": master_sha,
        "master_window_start_ms": sp_start_ms,
        "master_window_end_ms": sp_end_ms,
        "padded_window_start_ms": padded_start_ms,
        "padded_window_end_ms": padded_end_ms,
        "required_start_ms": req_start_ms,
        "required_end_ms": req_end_ms,
        "estimated_offset_ms": start_delta,
        "duration_delta_ms": dur_delta,
        "status": status,
        "issues": issues,
    }


def eval_production(production_id: str, db_path: str = None) -> dict:
    """Run master window eval for all hero units in a production."""
    import sqlite3

    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    # Check if source_slice_sha256 column exists
    cols = [c[1] for c in conn.execute("PRAGMA table_info(render_units)").fetchall()]
    has_slice_col = "source_slice_sha256" in cols

    units = conn.execute(f"""
        SELECT id, label, required_start_ms, required_end_ms, required_duration_ms,
               speech_start_sample, speech_end_sample,
               leading_silence_samples, trailing_silence_samples,
               {'source_slice_sha256,' if has_slice_col else ''}
               master_audio_sha256, audio_policy
        FROM render_units
        WHERE production_id=? AND status='valid' AND lipsync_required=1
    """, (production_id,)).fetchall()
    conn.close()

    if not units:
        return {
            "production_id": production_id,
            "hero_unit_count": 0,
            "status": "blocked",
            "results": [],
            "issues": ["no_valid_hero_units_found"],
        }

    results = [eval_hero_unit(dict(u)) for u in units]
    statuses = [r["status"] for r in results]
    if "blocked" in statuses:
        overall = "blocked"
    elif "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"
    else:
        overall = "pass"

    return {
        "production_id": production_id,
        "hero_unit_count": len(results),
        "status": overall,
        "results": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Master audio window verification")
    ap.add_argument("--production-id", required=True, help="Production DB ID")
    ap.add_argument("--out", type=Path, required=True, help="Output JSON path")
    ap.add_argument("--db-path", default=None, help="DB path override")
    args = ap.parse_args(argv)

    result = eval_production(args.production_id, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Master window eval for {result['production_id']}:")
    print(f"  Hero units: {result['hero_unit_count']}")
    print(f"  Overall: {result['status']}")
    for r in result.get("results", []):
        print(f"  [{r['label']}] status={r['status']} "
              f"window={r.get('master_window_start_ms')}->{r.get('master_window_end_ms')}ms "
              f"delta={r.get('estimated_offset_ms')}ms "
              f"issues={r.get('issues', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
