#!/usr/bin/env python3
"""Assembly transform ledger — records per-clip transforms applied during assembly.

For each render unit in a production, determines what FFmpeg transforms
assembly would apply, detects forbidden hero operations, and outputs a JSON
ledger.

Usage:
  python3 scripts/evals/assembly_transform_ledger.py --production-id <id> --output <path>
  python3 scripts/evals/assembly_transform_ledger.py --manifest <manifest.json> --output <path>
"""
import argparse
import json
import sys
from pathlib import Path

_HERO_LIPSYNC_POLICIES = {"HERO_SYNC_LOCKED", "keep_lipsync"}


def _classify_transforms(asset_type: str, audio_policy: str, lipsync_required: bool,
                         is_lipsync: bool, duration_ms: int = 0) -> dict:
    """Determine what transforms assembly would apply to a clip.

    Returns dict with: operations (applied), forbidden_operations (hero-only),
    forbidden_hero_operation_detected, notes.
    """
    operations = []
    forbidden_ops = []
    detected_forbidden = False
    notes = []

    if is_lipsync or lipsync_required or audio_policy in _HERO_LIPSYNC_POLICIES:
        # Hero lipsync path
        operations = ["scale_crop", "grade", "mute_audio", "replace_audio"]
        if duration_ms > 0:
            operations.append("trim")
        forbidden_ops = ["setpts", "speed_change", "loop", "freeze_extension",
                         "trim_through_speech", "audio_retime"]
        notes.append("hero_lipsync")
    elif asset_type == "still_image":
        operations = ["scale_crop", "grade", "loop_still"]
        forbidden_ops = ["speed_change"]
        notes.append("still_image")
    elif asset_type == "local_graphic":
        operations = ["drawtext_overlay", "fade_in", "fade_out", "scale_crop"]
        forbidden_ops = []
        notes.append("local_graphic")
    elif asset_type in ("generated_video", "broll_video", "lipsync_video"):
        operations = ["scale_crop", "grade", "mute_audio"]
        if audio_policy not in ("NARRATION_OVERLAY",):
            operations.append("overlay_narration")
        forbidden_ops = ["speed_change"]
        notes.append(f"muted_visual_{audio_policy}")
    else:
        operations = ["scale_crop", "grade"]
        notes.append(f"generic_{asset_type}")

    return {
        "operations": operations,
        "forbidden_operations": forbidden_ops,
        "forbidden_hero_operation_detected": detected_forbidden,
        "notes": notes,
    }


def build_ledger_from_render_units(production_id: str, db_path: str = None) -> dict:
    """Build transform ledger from DB render units."""
    import sqlite3
    import json as _json

    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    units = conn.execute(
        """SELECT ru.id, ru.label, ru.asset_type, ru.audio_policy,
                  ru.lipsync_required, ru.required_start_ms, ru.required_end_ms,
                  ru.required_duration_ms, ru.status, ru.ordinal,
                  a.id as artifact_id, a.sha256 as artifact_sha256, a.uri as artifact_uri
           FROM render_units ru
           LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
           WHERE ru.production_id=? AND ru.status != 'stale'
           ORDER BY ru.ordinal""",
        (production_id,),
    ).fetchall()

    conn.close()

    clips = []
    for u in units:
        u = dict(u)
        is_lipsync = u.get("audio_policy", "") in _HERO_LIPSYNC_POLICIES or u.get("lipsync_required", 0)
        tx = _classify_transforms(
            u.get("asset_type", ""),
            u.get("audio_policy", ""),
            u.get("lipsync_required", 0),
            is_lipsync,
            u.get("required_duration_ms", 0) or 0,
        )
        clip = {
            "render_unit_id": u["id"],
            "label": u.get("label", ""),
            "timeline_span_id": None,
            "source_artifact": u.get("artifact_sha256") or None,
            "source_artifact_id": u.get("artifact_id"),
            "start_ms": u.get("required_start_ms", 0) or 0,
            "end_ms": u.get("required_end_ms", 0) or 0,
            "duration_ms": u.get("required_duration_ms", 0) or 0,
            "asset_type": u.get("asset_type", ""),
            "audio_policy": u.get("audio_policy", ""),
            "is_hero_lipsync": is_lipsync,
            "operations": tx["operations"],
            "forbidden_operations": tx["forbidden_operations"],
            "forbidden_hero_operation_detected": tx["forbidden_hero_operation_detected"],
            "notes": tx["notes"],
        }
        clips.append(clip)

    return {
        "production_id": production_id,
        "deliverable": None,
        "clips": clips,
        "clip_count": len(clips),
        "hero_count": sum(1 for c in clips if c["is_hero_lipsync"]),
        "forbidden_operations_count": sum(1 for c in clips if c["forbidden_hero_operation_detected"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assembly transform ledger")
    ap.add_argument("--production-id", default=None, help="Production DB ID")
    ap.add_argument("--manifest", type=Path, default=None, help="Assembly manifest JSON path")
    ap.add_argument("--output", type=Path, required=True, help="Output JSON path")
    ap.add_argument("--db-path", default=None, help="DB path override")
    args = ap.parse_args(argv)

    if args.production_id:
        ledger = build_ledger_from_render_units(args.production_id, db_path=args.db_path)
    else:
        print("ERROR: --production-id is required", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, indent=2))

    print(f"Transform ledger for {ledger['production_id']}:")
    print(f"  Clips: {ledger['clip_count']}")
    print(f"  Hero lipsync: {ledger['hero_count']}")
    print(f"  Forbidden operations: {ledger['forbidden_operations_count']}")
    for clip in ledger["clips"]:
        ops = ", ".join(clip["operations"])
        f = " [FORBIDDEN]" if clip["forbidden_hero_operation_detected"] else ""
        print(f"  [{clip['label'] or clip['render_unit_id'][:16]}...] {ops}{f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
