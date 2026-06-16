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


def load_music_config(project_dir, format_str="short", project_id=None):
    """Load music config from constraints.json. Returns (dict, error_or_None).

    Selection logic:
    1. If default_path is set AND the file exists, use it (explicit override).
    2. Else select deterministically from library_dir based on project_id.
    3. If library is empty/missing and format requires music, error.
    """
    import hashlib

    constraints_path = ROOT / "docs" / "channel_universe" / "constraints.json"
    if not constraints_path.exists():
        return {"enabled": False, "reason": "constraints.json not found"}, None

    constraints = json.loads(constraints_path.read_text())
    music_cfg = constraints.get("music", {})
    required_formats = music_cfg.get("required_for_formats", [])
    required = format_str in required_formats

    # Use project_dir name as fallback project_id
    if project_id is None:
        project_id = Path(project_dir).name if project_dir else "default"

    audio_policy = constraints.get("audio_policy", {})

    def _make_result(path, selected_by=None):
        result = {
            "enabled": True,
            "path": str(path),
            "volume_db": music_cfg.get("volume_db", audio_policy.get("music_bed_db_target", -28)),
            "fade_in_sec": music_cfg.get("fade_in_sec", 1.0),
            "fade_out_sec": music_cfg.get("fade_out_sec", 2.0),
        }
        if selected_by:
            result["selected_by"] = selected_by
            result["project_id"] = project_id
        return result, None

    # 1. Explicit override: default_path set and exists
    default_path = music_cfg.get("default_path")
    if default_path:
        resolved = ROOT / default_path
        if resolved.exists():
            return _make_result(default_path)

    # 2. Library-based deterministic selection
    library_dir = music_cfg.get("library_dir")
    if library_dir:
        lib_path = ROOT / library_dir
        if lib_path.is_dir():
            tracks = sorted(
                p.name for p in lib_path.iterdir()
                if p.suffix.lower() in (".mp3", ".wav", ".m4a") and p.is_file()
            )
            if tracks:
                h = int(hashlib.sha256(project_id.encode()).hexdigest(), 16)
                selected = tracks[h % len(tracks)]
                rel_path = str(Path(library_dir) / selected)
                return _make_result(rel_path, selected_by="deterministic_per_project")

    # 3. No track available
    if required:
        return None, f"Music required for format '{format_str}' but no track available (library empty or missing)"
    return {"enabled": False, "reason": "no music track available"}, None


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
    clips_by_id = {}
    try:
        import clip_db
        try:
            clips = clip_db.list_clips(project_id)
        except Exception:
            clips = []  # table missing — legacy project
        if clips:
            clips_by_id = {clip["clip_id"]: clip for clip in clips}
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

    # Index timing by beat_id (used only as narration reference, not per-clip duration)
    timing_by_id = {}
    for t in timing_map.get("beats", []):
        timing_by_id[t["beat_id"]] = t

    plan_beats = plan.get("beats", [])

    # UCI-01: clip_id is the uniqueness key, not beat_id.
    # Detect duplicate clip_id (the correct invariant).
    seen_clip_ids = set()
    for b in plan_beats:
        cid = b.get("clip_id") or b.get("beat_id")
        if cid in seen_clip_ids:
            errors.append(f"Duplicate clip_id in media_plan: {cid}")
        seen_clip_ids.add(cid)

    if errors:
        return None, errors, warnings

    # UCI-02: timing-map-vs-plan cardinality check REMOVED.
    # The beat_timing_map is frozen at the creative storyboard (pre-split) and never
    # rebuilt after production splits (B011→B011a/B011b). Per-clip timing now comes
    # from each clip's own required_start_sec/required_end_sec in the plan.

    # Build segments — one per clip (plan row), using per-clip timing
    segments = []
    timeline_total = 0.0
    for b in plan_beats:
        bid = b["beat_id"]
        clip_id = b.get("clip_id") or bid  # fallback for legacy plans
        db_clip = clips_by_id.get(clip_id)
        if not b.get("clip_id"):
            warnings.append(f"Beat {bid}: no clip_id — using beat_id as key (legacy)")

        # The clip DB owns the timeline contract. The media plan is a serialized
        # handoff and is used only when no DB row exists (legacy projects).
        if db_clip:
            timing_in = db_clip["required_start_sec"]
            timing_out = db_clip["required_end_sec"]
        else:
            has_per_clip_timing = ("required_start_sec" in b and "required_end_sec" in b
                               and b["required_start_sec"] is not None
                               and b["required_end_sec"] is not None)
            if has_per_clip_timing:
                timing_in = b["required_start_sec"]
                timing_out = b["required_end_sec"]
            else:
                # Fallback to beat_timing_map for legacy plans
                timing = timing_by_id.get(bid)
                if not timing:
                    # UCI-02: split children inherit timing from parent (source_beat_id)
                    source = b.get("source_beat_id")
                    parent_timing = timing_by_id.get(source) if source and source != bid else None
                    if parent_timing:
                        # Distribute parent timing among siblings proportionally
                        siblings = [sb for sb in plan_beats if sb.get("source_beat_id") == source
                                    and sb["beat_id"] != source]
                        if not siblings:
                            siblings = [b]
                        total_target = sum(sb.get("duration_target_sec", 0) for sb in siblings) or 1.0
                        parent_start = parent_timing["start"]
                        parent_dur = parent_timing["end"] - parent_timing["start"]
                        offset = 0.0
                        for sb in siblings:
                            frac = (sb.get("duration_target_sec", 0) / total_target) * parent_dur
                            if sb["beat_id"] == bid:
                                timing_in = parent_start + offset
                                timing_out = parent_start + offset + frac
                                break
                            offset += frac
                        else:
                            errors.append(f"Clip {clip_id} (beat {bid}): split child not found in siblings")
                            continue
                    else:
                        errors.append(f"Clip {clip_id} (beat {bid}): no per-clip timing and not in timing_map")
                        continue
                else:
                    timing_in = timing["start"]
                    timing_out = timing["end"]

        duration = timing_out - timing_in

        media_path_rel = db_clip["output_path"] if db_clip else b.get("output_path", "")
        # local_graphic media beats are rendered to a .png (render_graphics step), not .mp4.
        asset_type = db_clip["asset_type"] if db_clip else b.get("asset_type", "generated_video")
        audio_policy = db_clip["audio_policy"] if db_clip else b.get("audio_policy", "strip")
        is_local_graphic = (b.get("model") == "local_graphic" or asset_type == "local_graphic")
        if is_local_graphic and media_path_rel.endswith(".mp4"):
            media_path_rel = media_path_rel[:-4] + ".png"
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
            errors.append(f"Clip {clip_id}: media file not found: {media_path}")

        seg = {
            "clip_id": clip_id,
            "id": clip_id,
            "source_beat_id": (db_clip["source_beat_id"] if db_clip else b.get("source_beat_id", bid)),
            "segment_id": b.get("segment_id"),
            "media": media_path_rel,
            "media_sha256": media_sha,
            "timing_in": timing_in,
            "timing_out": timing_out,
            "duration_required": round(duration, 6),
            "audio_policy": audio_policy,
            # Carry the authoritative asset_type so assemble derives behaviour from the
            # DB/plan contract, not from re-inferring it from the media file extension.
            "asset_type": asset_type,
        }

        # Lipsync provenance
        if b.get("lipsync_required") and b.get("audio_slice"):
            seg["audio_policy"] = "keep_lipsync"
            seg["speech_len_sec"] = (db_clip.get("speech_len_sec") if db_clip else None) or b["audio_slice"]["speech_len_sec"]
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
                    errors.append(f"Clip {clip_id}: required overlay asset not found: {overlay_path}")
            else:
                errors.append(f"Clip {clip_id}: graphic.required=true but no asset_path")
            seg["overlay"] = graphic

        segments.append(seg)
        timeline_total += duration

    # Sort segments by timeline position (required_start_sec)
    segments.sort(key=lambda s: s["timing_in"])

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
    music, music_err = load_music_config(project_dir, format_str, project_id=project_id)
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
