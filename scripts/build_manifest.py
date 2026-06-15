#!/usr/bin/env python3
"""scripts/build_manifest.py — Build and validate manifest.json from media plan + timing map.

Reads media_plan.json and beat_timing_map.json from a project directory,
enriches each beat with timing_in/out, media_sha256, overlay specs, and
assembles a music block. Validates completeness before writing.

Usage:
    python3 scripts/build_manifest.py <project_dir> [--allow-missing]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_file(path):
    """Return hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_music_config(project_dir, format_str="short"):
    """Load music config from constraints.json. Returns (dict, error_or_None)."""
    constraints_path = ROOT / "docs" / "channel_universe" / "constraints.json"
    if not constraints_path.exists():
        return {"enabled": False, "reason": "constraints.json not found"}, None

    constraints = json.loads(constraints_path.read_text())
    music_cfg = constraints.get("music", {})
    required_formats = music_cfg.get("required_for_formats", [])
    default_path = music_cfg.get("default_path")

    if not default_path:
        if format_str in required_formats:
            return None, f"Music required for format '{format_str}' but no default_path configured"
        return {"enabled": False, "reason": "no default_path configured"}, None

    resolved = ROOT / default_path
    if not resolved.exists():
        if format_str in required_formats:
            return None, f"Music required for format '{format_str}' but file not found: {default_path}"
        return {"enabled": False, "reason": f"file not found: {default_path}"}, None

    audio_policy = constraints.get("audio_policy", {})
    return {
        "enabled": True,
        "path": default_path,
        "volume_db": music_cfg.get("volume_db", audio_policy.get("music_bed_db_target", -28)),
        "fade_in_sec": music_cfg.get("fade_in_sec", 1.0),
        "fade_out_sec": music_cfg.get("fade_out_sec", 2.0),
    }, None


def build(project_dir, allow_missing=False, format_str=None):
    """Build manifest from plan + timing map. Returns (manifest_dict, errors, warnings)."""
    errors = []
    warnings = []

    # Resolve project format
    if format_str is None:
        state_path = project_dir / "state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text())
            format_str = state.get("format", "short")
        else:
            format_str = "short"

    plan_path = project_dir / "media_plan.json"
    timing_path = project_dir / "narration" / "beat_timing_map.json"

    if not plan_path.exists():
        errors.append(f"media_plan.json not found: {plan_path}")
        return None, errors, warnings
    if not timing_path.exists():
        errors.append(f"beat_timing_map.json not found: {timing_path}")
        return None, errors, warnings

    plan = json.loads(plan_path.read_text())
    timing_map = json.loads(timing_path.read_text())

    # --- CDB-06: Golden-truth gate — all clips must be valid ---
    project_id = plan.get("project_id", project_dir.name)
    try:
        import clip_db
        try:
            clips = clip_db.list_clips(project_id)
        except Exception:
            clips = []  # table missing — legacy project
        if clips:
            ok, problems = clip_db.assert_all_valid(project_id)
            if not ok:
                lines = ["Clip DB golden-truth gate FAILED — cannot build manifest:"]
                for p in problems:
                    if "change_type" in p:
                        lines.append(
                            f"  ✗ clip={p.get('clip_id')} open_request: "
                            f"type={p['change_type']} target_step={p.get('target_step')} "
                            f"reason={p.get('reason')}")
                    else:
                        lines.append(
                            f"  ✗ clip={p.get('clip_id')} status={p.get('status')} "
                            f"reason={p.get('status_reason', 'n/a')}")
                raise RuntimeError("\n".join(lines))
        else:
            warnings.append("clip_db: no clips for project (legacy/not migrated) — skipping assertion")
    except ImportError:
        warnings.append("clip_db not available — skipping golden-truth assertion")

    # Index timing by beat_id
    timing_by_id = {}
    for t in timing_map.get("beats", []):
        timing_by_id[t["beat_id"]] = t

    # Index plan beats by beat_id, detect duplicates
    plan_beats = plan.get("beats", [])
    seen_ids = set()
    for b in plan_beats:
        bid = b["beat_id"]
        if bid in seen_ids:
            errors.append(f"Duplicate beat_id in media_plan: {bid}")
        seen_ids.add(bid)

    if errors:
        return None, errors, warnings

    # Check all timing-map beats have plan entries
    for bid in timing_by_id:
        if bid not in seen_ids:
            errors.append(f"Beat {bid} in timing_map but missing from media_plan")

    if errors:
        return None, errors, warnings

    # Build segments
    segments = []
    timeline_total = 0.0
    for b in plan_beats:
        bid = b["beat_id"]
        timing = timing_by_id.get(bid)
        if not timing:
            errors.append(f"Beat {bid} in media_plan but missing from timing_map")
            continue

        media_path_rel = b.get("output_path", "")
        media_path = None
        if media_path_rel:
            # Resolve: try project_dir-relative, then ROOT-relative
            candidate = project_dir / media_path_rel
            if candidate.exists():
                media_path = candidate
            else:
                media_path = ROOT / media_path_rel

        # Compute SHA-256
        media_sha = None
        if media_path and media_path.exists():
            media_sha = sha256_file(media_path)
        elif media_path and not allow_missing:
            errors.append(f"Beat {bid}: media file not found: {media_path}")

        duration = timing["end"] - timing["start"]
        seg = {
            "id": bid,
            "segment_id": b.get("segment_id"),
            "media": media_path_rel,
            "media_sha256": media_sha,
            "timing_in": timing["start"],
            "timing_out": timing["end"],
            "duration_required": round(duration, 6),
            "audio_policy": b.get("audio_policy", "strip"),
        }

        # Lipsync provenance
        if b.get("lipsync_required") and b.get("audio_slice"):
            seg["audio_policy"] = "keep_lipsync"
            seg["speech_len_sec"] = b["audio_slice"]["speech_len_sec"]
            seg["lipsync_provenance"] = {
                "slice_sha256": b["audio_slice"].get("slice_sha256"),
                "parent_mp3_sha256": b["audio_slice"].get("parent_mp3_sha256"),
            }
        else:
            seg["words"] = len(b.get("narration_text", "").split())

        # Overlay spec
        graphic = b.get("graphic", {})
        if graphic.get("required"):
            overlay_path = graphic.get("asset_path")
            if overlay_path:
                full = ROOT / overlay_path
                if not full.exists():
                    errors.append(f"Beat {bid}: required overlay asset not found: {overlay_path}")
            else:
                errors.append(f"Beat {bid}: graphic.required=true but no asset_path")
            seg["overlay"] = graphic

        segments.append(seg)
        timeline_total += duration

    if errors:
        return None, errors, warnings

    # Validate timeline total vs timing_map total
    map_total = timing_map.get("total_duration", 0.0)
    if abs(timeline_total - map_total) > 0.25:
        errors.append(
            f"Timeline mismatch: beats sum to {timeline_total:.3f}s "
            f"but timing_map total is {map_total:.3f}s (delta={abs(timeline_total - map_total):.3f}s > 0.25s)"
        )
        return None, errors, warnings

    # Music
    music, music_err = load_music_config(project_dir, format_str)
    if music_err:
        errors.append(music_err)
        return None, errors, warnings
    if not music.get("enabled"):
        warnings.append(f"Music disabled: {music.get('reason', 'unknown')}")

    manifest = {
        "id": plan.get("project_id", project_dir.name),
        "format": format_str,
        "narration_mode": "continuous_voiceover",
        "continuous_audio": "narration/continuous.mp3",
        "beat_timing_map": "narration/beat_timing_map.json",
        "music": music,
        "segments": segments,
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "render": {"fps": 24, "crf": 18},
        "brand": {},
        "output": {"directory": "."},
    }
    return manifest, errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Build manifest.json from media plan + timing map")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--allow-missing", action="store_true",
                        help="Don't fail on missing media files (useful during generation)")
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    manifest, errors, warnings = build(project_dir, allow_missing=args.allow_missing)

    for w in warnings:
        print(f"  ⚠ {w}", file=sys.stderr)

    if errors:
        print("ERROR: Manifest validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)

    out_path = project_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2))
    print(f"  ✓ manifest: {len(manifest['segments'])} segments, "
          f"music={'enabled' if manifest['music'].get('enabled') else 'disabled'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
