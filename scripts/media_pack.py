#!/usr/bin/env python3
"""media_pack.py — Asset planning and validation for the video pipeline.

Not a media generator. Helps plan what assets are needed, validates they exist
and are compatible, then produces a ready-to-use script for tts.py.

Usage:
  python scripts/media_pack.py scripts/sample_script.json --brief
  python scripts/media_pack.py scripts/sample_script.json --validate
  python scripts/media_pack.py scripts/sample_script.json --write-ready-script
  python scripts/media_pack.py scripts/sample_script.json --brief --validate --write-ready-script
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

VALID_MEDIA_TYPES = ("lipsync_video", "broll_video", "image", "title_card", "chart", "screen_recording")
VIDEO_TYPES = ("lipsync_video", "broll_video", "screen_recording")
IMAGE_TYPES = ("image", "title_card", "chart")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

DEFAULT_EXT = {
    "lipsync_video": ".mp4", "broll_video": ".mp4", "screen_recording": ".mp4",
    "image": ".png", "title_card": ".png", "chart": ".png",
}


def resolve(base, p):
    if p is None:
        return None
    path = Path(p)
    return path if path.is_absolute() else (base / path).resolve()


def probe_video(path):
    """Return dict with width, height, duration, has_audio for a video file."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=width,height,codec_type", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    data = json.loads(r.stdout)
    info = {"width": 0, "height": 0, "duration": 0.0, "has_audio": False}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            info["width"] = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
    info["duration"] = float(data.get("format", {}).get("duration", 0))
    return info


def probe_image(path):
    """Return width, height for an image. Uses ffprobe (no PIL dependency)."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    data = json.loads(r.stdout)
    streams = data.get("streams", [])
    if not streams:
        return None
    return {"width": int(streams[0].get("width", 0)), "height": int(streams[0].get("height", 0))}


def expected_path(output_dir, seg_id, media_type):
    ext = DEFAULT_EXT.get(media_type, ".mp4")
    return output_dir / "media" / f"{seg_id}{ext}"


# --- Brief generation ---

def generate_brief(script, base):
    project_id = script["project_id"]
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{project_id}"))
    segments = script["segments"]

    brief_segments = []
    for seg in segments:
        sid = seg["id"]
        req = seg.get("media_request", {})
        mtype = req.get("type", "lipsync_video" if seg.get("audio_mode") == "baked_in" else "broll_video")
        desc = req.get("description", seg.get("text", ""))
        orientation = req.get("orientation", "landscape")
        duration_policy = req.get("duration_policy", "use_media_duration" if seg.get("audio_mode") == "baked_in" else "match_audio")
        required = req.get("required", True)

        # Use existing media path if specified, else generate expected path
        if seg.get("media"):
            exp = str(resolve(base, seg["media"]))
        else:
            exp = str(expected_path(output_dir, sid, mtype))

        brief_segments.append({
            "id": sid,
            "audio_mode": seg.get("audio_mode"),
            "media_request": {
                "type": mtype,
                "description": desc[:200],
                "orientation": orientation,
                "duration_policy": duration_policy,
                "required": required,
            },
            "expected_path": exp,
            "human_status": "found" if Path(exp).exists() else "needed",
            "notes": "",
        })

    return {
        "project_id": project_id,
        "title": script.get("title", ""),
        "output_dir": str(output_dir),
        "segments": brief_segments,
    }


# --- Validation ---

def validate_media(script, base):
    """Validate all media assets. Returns (errors, warnings)."""
    project_id = script["project_id"]
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{project_id}"))
    errors, warnings = [], []

    for i, seg in enumerate(script["segments"]):
        sid = seg.get("id", f"seg_{i}")
        prefix = f"[{sid}]"
        req = seg.get("media_request", {})
        mtype = req.get("type", "lipsync_video" if seg.get("audio_mode") == "baked_in" else "broll_video")
        required = req.get("required", True)
        orientation = req.get("orientation", "either")
        audio_mode = seg.get("audio_mode", "generated_tts")

        if mtype not in VALID_MEDIA_TYPES:
            errors.append(f"{prefix} unknown media_request.type: '{mtype}'")
            continue

        # Resolve media path
        if seg.get("media"):
            media_path = resolve(base, seg["media"])
        else:
            media_path = expected_path(output_dir, sid, mtype)

        # Existence
        if not media_path.exists():
            if required:
                errors.append(f"{prefix} MISSING: {media_path}")
            else:
                warnings.append(f"{prefix} optional media not found: {media_path}")
            continue

        ext = media_path.suffix.lower()

        # Type/extension compatibility
        if mtype in VIDEO_TYPES and ext not in VIDEO_EXTS:
            errors.append(f"{prefix} expected video but got '{ext}': {media_path}")
            continue
        if mtype in IMAGE_TYPES and ext not in IMAGE_EXTS:
            errors.append(f"{prefix} expected image but got '{ext}': {media_path}")
            continue
        if ext not in VIDEO_EXTS and ext not in IMAGE_EXTS:
            errors.append(f"{prefix} unknown file extension '{ext}': {media_path}")
            continue

        # Probe
        is_video = ext in VIDEO_EXTS
        if is_video:
            info = probe_video(media_path)
            if info is None:
                errors.append(f"{prefix} ffprobe failed on: {media_path}")
                continue

            w, h = info["width"], info["height"]
            dur = info["duration"]
            has_audio = info["has_audio"]

            # Audio policy checks
            if audio_mode == "baked_in" and not has_audio:
                errors.append(f"{prefix} audio_mode=baked_in but media has NO audio stream")
            if audio_mode == "generated_tts" and has_audio and mtype == "broll_video":
                warnings.append(f"{prefix} B-roll has audio stream — it will be replaced by generated narration")

            # Orientation
            if orientation == "landscape" and h > w:
                warnings.append(f"{prefix} expected landscape but media is portrait ({w}x{h})")
            elif orientation == "portrait" and w > h:
                warnings.append(f"{prefix} expected portrait but media is landscape ({w}x{h})")

            print(f"  {prefix} ✓ {media_path.name} ({w}x{h}, {dur:.1f}s, audio={'yes' if has_audio else 'no'})")
        else:
            info = probe_image(media_path)
            if info is None:
                errors.append(f"{prefix} cannot read image: {media_path}")
                continue
            w, h = info["width"], info["height"]

            if audio_mode == "baked_in":
                errors.append(f"{prefix} audio_mode=baked_in but media is an image (no audio possible)")

            if orientation == "landscape" and h > w:
                warnings.append(f"{prefix} expected landscape but image is portrait ({w}x{h})")
            elif orientation == "portrait" and w > h:
                warnings.append(f"{prefix} expected portrait but image is landscape ({w}x{h})")

            print(f"  {prefix} ✓ {media_path.name} ({w}x{h}, image)")

    return errors, warnings


# --- Write ready script ---

def write_ready_script(script, base):
    """Copy script with validated media paths filled in. Returns output path."""
    project_id = script["project_id"]
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{project_id}"))
    output_dir.mkdir(parents=True, exist_ok=True)

    ready = json.loads(json.dumps(script))  # deep copy

    for seg in ready["segments"]:
        if seg.get("media"):
            # Resolve from original base, then express relative to output_dir
            media_abs = resolve(base, seg["media"])
            if not media_abs.exists():
                raise ValueError(f"Required media missing for [{seg['id']}]: {media_abs}")
            import os
            seg["media"] = os.path.relpath(str(media_abs), str(output_dir))
        else:
            req = seg.get("media_request", {})
            mtype = req.get("type", "lipsync_video" if seg.get("audio_mode") == "baked_in" else "broll_video")
            exp = expected_path(output_dir, seg["id"], mtype)
            if exp.exists():
                import os
                seg["media"] = os.path.relpath(str(exp), str(output_dir))
            else:
                raise ValueError(f"Required media missing for [{seg['id']}]: {exp}")

        # Resolve lower_third too
        if seg.get("lower_third"):
            lt_abs = resolve(base, seg["lower_third"])
            import os
            seg["lower_third"] = os.path.relpath(str(lt_abs), str(output_dir))

    # Adjust output_dir to "." (script lives in output_dir)
    ready["output_dir"] = "."

    out_path = output_dir / "script_with_media.json"
    with open(out_path, "w") as f:
        json.dump(ready, f, indent=2)
    return out_path


# --- Main ---

def main():
    ap = argparse.ArgumentParser(description="Plan and validate media assets for the video pipeline.")
    ap.add_argument("script", help="Path to reviewed script JSON")
    ap.add_argument("--brief", action="store_true", help="Generate media_brief.json")
    ap.add_argument("--validate", action="store_true", help="Validate media assets exist and are compatible")
    ap.add_argument("--write-ready-script", action="store_true", help="Write script_with_media.json")
    args = ap.parse_args()

    if not any([args.brief, args.validate, args.write_ready_script]):
        ap.error("Specify at least one of: --brief, --validate, --write-ready-script")

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    base = script_path.parent

    with open(script_path) as f:
        try:
            script = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)

    if args.brief:
        brief = generate_brief(script, base)
        output_dir = Path(brief["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        brief_path = output_dir / "media_brief.json"
        with open(brief_path, "w") as f:
            json.dump(brief, f, indent=2)
        print(f"  media brief: {brief_path}")
        needed = sum(1 for s in brief["segments"] if s["human_status"] == "needed")
        found = sum(1 for s in brief["segments"] if s["human_status"] == "found")
        print(f"  {found} found, {needed} needed")

    if args.validate:
        print("Validating media assets...")
        errors, warnings = validate_media(script, base)
        for w in warnings:
            print(f"  ⚠ {w}")
        if errors:
            print(f"\n  FAILED: {len(errors)} error(s):")
            for e in errors:
                print(f"    ✗ {e}")
            if not args.brief:
                sys.exit(1)
        else:
            print(f"  PASSED ({len(warnings)} warning(s))")

    if args.write_ready_script:
        # Validate first
        errors, _ = validate_media(script, base)
        if errors:
            print(f"ERROR: Cannot write ready script — {len(errors)} validation error(s):", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
            sys.exit(1)
        try:
            out = write_ready_script(script, base)
            print(f"  ready script: {out}")
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
