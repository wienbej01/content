#!/usr/bin/env python3
"""assemble.py — Manifest-driven video assembly engine.

Produces branded 16:9 and 9:16 videos from pre-generated assets.
Deterministic: same manifest + same assets = same output.

Usage:
  python scripts/assemble.py scripts/sample_manifest.json
  python scripts/assemble.py manifest.json --formats 16x9
  python scripts/assemble.py manifest.json --tmp /fast/disk/tmp

Inputs (specified in manifest):
  - Video clips or still images (per segment)
  - Optional separate narration audio (per segment)
  - Word counts (per segment, for WPS alignment)
  - Music config (generate or provide file)
  - Brand assets (endcard, lower-third)

Outputs (in manifest output.directory):
  - {prefix}_16x9.mp4
  - {prefix}_9x16.mp4
  - {prefix}_log.json  (execution log)

Paths in the manifest are relative to the manifest file's directory.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from narrative_speed import measure as measure_pace
from generate_music import generate as gen_music, write_wav


def run(cmd, label=""):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = r.stderr[-2000:] if r.stderr else ""
        raise RuntimeError(f"ffmpeg failed ({label}): {err}")
    return r


TAIL_PAD = 0.25   # seconds appended after narration ends (prevents last-word cut-off)


def probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def resolve(base, p):
    """Resolve a path relative to manifest directory."""
    if p is None:
        return None
    path = Path(p)
    if path.is_absolute():
        return path
    return (base / path).resolve()
    """Resolve a path relative to manifest directory."""
    if p is None:
        return None
    path = Path(p)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def validate_manifest(manifest, base):
    """Validate manifest structure and file existence. Returns list of error strings."""
    errors = []

    if not isinstance(manifest, dict):
        return ["Manifest must be a JSON object"]

    if "id" not in manifest or not manifest["id"]:
        errors.append("Missing required field: 'id'")

    segments = manifest.get("segments")
    if not segments or not isinstance(segments, list):
        errors.append("'segments' must be a non-empty array")
        return errors  # can't validate further

    pacing = manifest.get("pacing", {})
    ref = pacing.get("reference", 0)
    if not isinstance(ref, int) or ref < 0 or ref >= len(segments):
        errors.append(f"pacing.reference={ref} is out of range (0..{len(segments)-1})")

    baseline = pacing.get("baseline_speed", 1.0)
    if not isinstance(baseline, (int, float)) or baseline <= 0:
        errors.append(f"pacing.baseline_speed must be > 0, got {baseline}")

    for i, seg in enumerate(segments):
        prefix = f"segments[{i}]"
        if "media" not in seg:
            errors.append(f"{prefix}: missing 'media'")
        else:
            media = resolve(base, seg["media"])
            if not media.exists():
                errors.append(f"{prefix}.media: file not found: {media}")

        if "words" not in seg:
            errors.append(f"{prefix}: missing 'words'")
        elif not isinstance(seg["words"], int) or seg["words"] <= 0:
            errors.append(f"{prefix}.words: must be a positive integer, got {seg['words']}")

        trim = seg.get("trim_end")
        if trim is not None and (not isinstance(trim, (int, float)) or trim <= 0):
            errors.append(f"{prefix}.trim_end: must be > 0 or null, got {trim}")

        audio = seg.get("audio")
        if audio:
            audio_path = resolve(base, audio)
            if not audio_path.exists():
                errors.append(f"{prefix}.audio: file not found: {audio_path}")

        lt = seg.get("lower_third")
        if lt:
            lt_path = resolve(base, lt)
            if not lt_path.exists():
                errors.append(f"{prefix}.lower_third: file not found: {lt_path}")

        is_image = seg.get("media", "").lower().split(".")[-1] in ("png", "jpg", "jpeg", "webp")
        if is_image and not audio:
            errors.append(f"{prefix}: image media requires 'audio' field")

    # Validate brand assets (non-fatal if missing — endcard is optional)
    brand = manifest.get("brand", {})
    for key in ("endcard_16x9", "endcard_9x16"):
        val = brand.get(key)
        if val:
            p = resolve(base, val)
            if not p.exists():
                errors.append(f"brand.{key}: file not found: {p}")

    # Validate output directory is creatable
    out_dir = resolve(base, manifest.get("output", {}).get("directory", "."))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        errors.append(f"output.directory: cannot create {out_dir}: {e}")

    return errors


# --- Core pipeline stages ---

def compute_speeds(segments, pacing, base):
    """Measure WPS per segment and compute alignment speeds."""
    ref_idx = pacing.get("reference", 0)
    baseline = pacing.get("baseline_speed", 1.0)

    wps_list = []
    for seg in segments:
        # Measure narration audio for WPS — use separate audio if provided (generated_tts),
        # fall back to media file (baked_in lipsync clips where audio IS the narration).
        audio_file = resolve(base, seg.get("audio"))
        probe_target = audio_file if (audio_file and audio_file.exists()) else resolve(base, seg["media"])
        words = seg["words"]
        pace = measure_pace(probe_target, words)
        wps_list.append(pace.wps)

    ref_wps = wps_list[ref_idx]
    speeds = [baseline * ref_wps / w for w in wps_list]
    return speeds, wps_list, ref_wps


def process_segment(seg, speed, w, h, fps, grade, crf, tmp, base, idx, allow_looping=False):
    """Normalize one segment: scale/crop, speed, grade, optional lower-third.
    When narration is longer than the video, hold the last frame (premium 'linger')
    instead of looping — unless allow_looping=True."""
    media = resolve(base, seg["media"])
    trim_end = seg.get("trim_end")
    lower_third = resolve(base, seg.get("lower_third"))

    trim_args = ["-t", str(trim_end)] if trim_end else []
    pts = f"setpts={1.0/speed:.4f}*PTS," if abs(speed - 1.0) > 1e-3 else ""
    atempo = f"atempo={speed:.4f}," if abs(speed - 1.0) > 1e-3 else ""

    scale_crop = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"
    vf = f"{pts}{scale_crop},{grade}"

    dst = tmp / f"seg_{idx}.mp4"

    is_image = media.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")

    if is_image:
        # Still image → video of narration duration + tail pad (prevents last-word cut-off)
        audio = resolve(base, seg.get("audio"))
        if not audio:
            raise ValueError(f"Segment {idx}: image media requires 'audio' field")
        audio_dur = probe_dur(audio) / speed
        out_dur = audio_dur + TAIL_PAD
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(media),
             *trim_args, "-i", str(audio),
             "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},{grade}",
             "-af", f"{atempo}aresample=48000",
             "-t", f"{out_dur:.3f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}_image")
    elif lower_third:
        # Video with lower-third overlay
        src_dur = trim_end if trim_end else probe_dur(media)
        d = src_dur / speed
        fin, fout = 0.6, 0.6
        show_from, show_to = 0.8, max(d - 1.0, 1.2)
        fc = (
            f"[0:v]{pts}{scale_crop},{grade}[base];"
            f"[1:v]format=rgba,"
            f"fade=t=in:st={show_from}:d={fin}:alpha=1,"
            f"fade=t=out:st={show_to}:d={fout}:alpha=1[lt];"
            f"[base][lt]overlay=70:H-h-70:"
            f"enable='between(t,{show_from},{show_to+fout})'[v]"
        )
        run(["ffmpeg", "-y", *trim_args, "-i", str(media),
             "-loop", "1", "-i", str(lower_third),
             "-filter_complex", fc, "-map", "[v]", "-map", "0:a",
             "-af", f"{atempo}aresample=48000", "-shortest",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}_lt")
    else:
        # Plain video segment
        audio_src = seg.get("audio")
        if audio_src:
            # Replace video audio with provided narration.
            # If narration is longer than video: loop (if allowed) or hold last frame (default).
            audio_path = resolve(base, audio_src)
            audio_dur = probe_dur(audio_path) / speed
            out_dur = audio_dur + TAIL_PAD
            media_dur = (trim_end if trim_end else probe_dur(media)) / speed
            if media_dur >= out_dur - 0.05:
                run(["ffmpeg", "-y", *trim_args, "-i", str(media), "-i", str(audio_path),
                     "-vf", vf, "-af", f"{atempo}aresample=48000",
                     "-t", f"{out_dur:.3f}", "-map", "0:v", "-map", "1:a",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                     "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}")
            elif allow_looping:
                run(["ffmpeg", "-y", "-stream_loop", "-1", *trim_args, "-i", str(media),
                     "-i", str(audio_path), "-vf", vf, "-af", f"{atempo}aresample=48000",
                     "-t", f"{out_dur:.3f}", "-map", "0:v", "-map", "1:a",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                     "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}")
            else:
                # Default: hold last frame (no visible repetition)
                pad_dur = out_dur - media_dur
                vf_freeze = f"{pts}{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={pad_dur:.3f}"
                run(["ffmpeg", "-y", *trim_args, "-i", str(media), "-i", str(audio_path),
                     "-vf", vf_freeze, "-af", f"{atempo}aresample=48000",
                     "-t", f"{out_dur:.3f}", "-map", "0:v", "-map", "1:a",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                     "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}")
        else:
            run(["ffmpeg", "-y", *trim_args, "-i", str(media),
                 "-vf", vf, "-af", f"{atempo}aresample=48000",
                 "-map", "0:v", "-map", "0:a",
                 "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}")

    return dst


def make_endcard(endcard_path, duration, w, h, fps, crf, tmp):
    dst = tmp / "endcard.mp4"
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(endcard_path),
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-vf", f"scale={w}:{h},fps={fps},fade=t=in:st=0:d=0.6,fade=t=out:st={duration-0.6}:d=0.6",
         "-t", str(duration),
         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-pix_fmt", "yuv420p", str(dst)], "endcard")
    return dst


def gap_concat(parts, gap_s, audio_fade, w, h, fps, crf, tmp):
    """Concatenate clips with silent gaps (prevents VO overlap)."""
    # Prep each clip: add audio fade-out at tail
    prepped = []
    for i, p in enumerate(parts):
        d = probe_dur(p)
        fo_start = max(d - audio_fade, 0)
        dst = tmp / f"prep_{i}.mp4"
        run(["ffmpeg", "-y", "-i", str(p),
             "-vf", f"fade=t=out:st={fo_start:.3f}:d={audio_fade}",
             "-af", f"afade=t=in:st=0:d={audio_fade},afade=t=out:st={fo_start:.3f}:d={audio_fade}",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-pix_fmt", "yuv420p", str(dst)], f"prep_{i}")
        prepped.append(dst)

    # Create gap clip
    gap_clip = tmp / "gap.mp4"
    run(["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={gap_s}",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-t", str(gap_s),
         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-pix_fmt", "yuv420p", str(gap_clip)], "gap")

    # Concat list (escape paths for ffmpeg concat demuxer)
    concat_list = tmp / "concat.txt"
    with open(concat_list, "w") as f:
        for i, p in enumerate(prepped):
            safe = str(p).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
            if i < len(prepped) - 1:
                safe_gap = str(gap_clip).replace("'", "'\\''")
                f.write(f"file '{safe_gap}'\n")

    joined = tmp / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-pix_fmt", "yuv420p", str(joined)], "concat")
    return joined


def make_music_bed(duration, music_cfg, tmp, base):
    """Generate or load music, apply level + fades."""
    music_file = resolve(base, music_cfg.get("file"))
    level_db = music_cfg.get("level_db", -16)

    if music_file and music_file.exists():
        src = music_file
    else:
        wav = tmp / "music.wav"
        mood = music_cfg.get("mood", "calm")
        stereo = gen_music(duration, mood)
        write_wav(stereo, wav)
        src = wav

    bed = tmp / "music_bed.m4a"
    fo_start = max(duration - 1.4, 0)
    run(["ffmpeg", "-y", "-i", str(src),
         "-t", f"{duration:.3f}",
         "-af", (f"volume={level_db}dB,"
                 f"afade=t=in:st=0:d=1.2,"
                 f"afade=t=out:st={fo_start:.3f}:d=1.4,"
                 f"aresample=48000"),
         "-ac", "2", "-c:a", "aac", "-b:a", "192k", str(bed)], "music_bed")
    return bed


def mix_music(video, bed, tmp):
    dst = tmp / "mixed.mp4"
    run(["ffmpeg", "-y", "-i", str(video), "-i", str(bed),
         "-filter_complex",
         "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         str(dst)], "mix")
    return dst


def loudnorm(src, dst):
    run(["ffmpeg", "-y", "-i", str(src),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(dst)], "loudnorm")


# --- Main assembly ---

FORMAT_SPECS = {
    "16x9": {"w": 1920, "h": 1080, "endcard_key": "endcard_16x9"},
    "9x16": {"w": 1080, "h": 1920, "endcard_key": "endcard_9x16"},
}


def assemble_format(manifest, fmt, speeds, base, tmp, allow_looping=False):
    """Assemble one output format. Returns the output path."""
    spec = FORMAT_SPECS[fmt]
    w, h = spec["w"], spec["h"]
    segments = manifest["segments"]
    render = manifest.get("render", {})
    brand = manifest.get("brand", {})
    fps = render.get("fps", 24)
    crf = render.get("crf", 18)
    grade = render.get("grade", "eq=contrast=1.04:saturation=1.05:gamma=0.98")

    fmt_tmp = tmp / fmt
    fmt_tmp.mkdir(exist_ok=True)

    # 1. Process segments
    norm_clips = []
    for i, seg in enumerate(segments):
        clip = process_segment(seg, speeds[i], w, h, fps, grade, crf, fmt_tmp, base, i, allow_looping=allow_looping)
        norm_clips.append(clip)

    # 2. Endcard
    endcard_path = resolve(base, brand.get(spec["endcard_key"]))
    endcard_dur = brand.get("endcard_duration", 3.0)
    if endcard_path and endcard_path.exists():
        ec = make_endcard(endcard_path, endcard_dur, w, h, fps, crf, fmt_tmp)
        norm_clips.append(ec)

    # 3. Gap-concat
    gap_s = brand.get("gap_seconds", 0.4)
    audio_fade = brand.get("audio_fade", 0.3)
    joined = gap_concat(norm_clips, gap_s, audio_fade, w, h, fps, crf, fmt_tmp)

    # 4. Music
    total_dur = probe_dur(joined)
    bed = make_music_bed(total_dur, manifest.get("music", {}), fmt_tmp, base)
    mixed = mix_music(joined, bed, fmt_tmp)

    # 5. Loudnorm → final
    out_dir = resolve(base, manifest.get("output", {}).get("directory", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = manifest.get("output", {}).get("prefix", manifest.get("id", "output"))
    final = out_dir / f"{prefix}_{fmt}.mp4"
    loudnorm(mixed, final)

    return final


def assemble(manifest_path, formats=None, tmp_base=None, allow_looping=False):
    """Main entry: load manifest, build all formats, return log dict."""
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.exists():
        raise ValueError(f"Manifest file not found: {manifest_path}")
    base = manifest_path.parent

    with open(manifest_path) as f:
        try:
            manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest: {e}")

    # Validate before doing any work
    errors = validate_manifest(manifest, base)
    if errors:
        raise ValueError("Manifest validation failed:\n  " + "\n  ".join(errors))

    if formats is None:
        formats = ["16x9", "9x16"]

    # Setup tmp
    if tmp_base:
        tmp = Path(tmp_base)
    else:
        out_dir = resolve(base, manifest.get("output", {}).get("directory", "."))
        tmp = out_dir / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    log = {
        "id": manifest.get("id"),
        "manifest": str(manifest_path),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "formats": {},
        "pacing": {},
    }

    # Compute speeds (once, shared across formats)
    speeds, wps_list, ref_wps = compute_speeds(
        manifest["segments"], manifest.get("pacing", {}), base)

    log["pacing"] = {
        "wps_per_segment": [round(w, 3) for w in wps_list],
        "speeds": [round(s, 4) for s in speeds],
        "target_wps": round(ref_wps * manifest.get("pacing", {}).get("baseline_speed", 1.0), 3),
    }

    # Build each format
    for fmt in formats:
        t0 = time.time()
        final = assemble_format(manifest, fmt, speeds, base, tmp, allow_looping=allow_looping)
        dur = probe_dur(final)
        log["formats"][fmt] = {
            "path": str(final),
            "duration_s": round(dur, 2),
            "build_time_s": round(time.time() - t0, 1),
        }

    log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    # Write log
    out_dir = resolve(base, manifest.get("output", {}).get("directory", "."))
    prefix = manifest.get("output", {}).get("prefix", manifest.get("id", "output"))
    log_path = out_dir / f"{prefix}_log.json"
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)

    return log


def main():
    ap = argparse.ArgumentParser(description="Assemble branded video from manifest + assets.")
    ap.add_argument("manifest", help="Path to manifest JSON")
    ap.add_argument("--formats", default="16x9,9x16", help="Comma-separated: 16x9,9x16")
    ap.add_argument("--tmp", default=None, help="Temp directory (default: output/_tmp)")
    ap.add_argument("--allow-looping", action="store_true", help="Allow short clips to loop (default: hold last frame)")
    args = ap.parse_args()

    formats = [f.strip() for f in args.formats.split(",")]
    try:
        log = assemble(args.manifest, formats, args.tmp, allow_looping=args.allow_looping)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"\nDONE — {log['id']}")
    for fmt, info in log["formats"].items():
        print(f"  {fmt}: {info['path']}  ({info['duration_s']}s, built in {info['build_time_s']}s)")
    print(f"  log: {Path(log['formats'][formats[0]]['path']).parent / (log['id'] + '_log.json')}")


if __name__ == "__main__":
    main()
