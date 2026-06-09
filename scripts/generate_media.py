#!/usr/bin/env python3
"""generate_media.py — Generate video clips from visual briefs via Higgsfield CLI.

Pipeline:  script.json → generate_media.py → MP4s at segment media paths → tts.py → assemble.py

Usage:
  python3 scripts/generate_media.py scripts/generated/script.json --validate-only
  python3 scripts/generate_media.py scripts/generated/script.json --dry-run
  python3 scripts/generate_media.py scripts/generated/script.json
  python3 scripts/generate_media.py scripts/generated/script.json --force
  python3 scripts/generate_media.py scripts/generated/script.json --assemble

Requires: @higgsfield/cli authenticated (node node_modules/@higgsfield/cli/bin/higgsfield.js auth login)
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF_BIN = ROOT / "node_modules" / "@higgsfield" / "cli" / "bin" / "higgsfield.js"
DEFAULT_LIPSYNC_MODEL = "seedance_2_0"
DEFAULT_BROLL_MODEL = "wan2_7"
WAIT_TIMEOUT = "15m"
WAIT_INTERVAL = "10s"

# Realism constraints injected into every b-roll prompt
BROLL_REALISM_PREFIX = (
    "Premium realistic business cinematography, realistic scale and proportions, "
    "modern office or finance or knowledge-work setting, natural lighting, "
    "cinematic quality, believable interior architecture, human-scale furniture and rooms. "
    "No readable text anywhere — no letters, no numbers, no logos, no UI text, "
    "no whiteboard writing, no document text, no slide or PowerPoint text, no chart labels. "
    "Any screens, documents, or whiteboards must be blank, blurred, out of focus, "
    "or seen at an angle where no text is legible. "
)
BROLL_NEGATIVE = (
    "readable text, letters, numbers, symbols, fake writing, gibberish text, AI text, "
    "logos, watermark, UI text, whiteboard text, slide deck text, PowerPoint text, "
    "document text, chart labels, subtitles, captions, "
    "portrait laptop screens, miniature or toy-like interiors, warped architecture, "
    "fisheye distortion, surreal proportions, fake celebrities, "
    "neon, cyberpunk, sci-fi, futuristic holograms"
)


def hf_cmd(args, json_output=True):
    """Run a Higgsfield CLI command. Returns parsed JSON or raises."""
    cmd = ["node", str(HF_BIN)] + args
    if json_output:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=700)
    if r.returncode != 0:
        err = (r.stdout + r.stderr).strip()
        if "Not authenticated" in err:
            raise RuntimeError("Higgsfield not authenticated. Run: node node_modules/@higgsfield/cli/bin/higgsfield.js auth login")
        raise RuntimeError(f"Higgsfield CLI error: {err[:500]}")
    if json_output:
        return json.loads(r.stdout)
    return r.stdout.strip()


def resolve(base, p):
    """Resolve a path. ROOT-relative for bare paths (e.g. 'Videos/...');
    script-relative for explicit relative paths (e.g. '../../assets/...')."""
    if p is None:
        return None
    path = Path(p)
    if path.is_absolute():
        return path
    # Explicit relative (starts with ../ or ./) → relative to script location
    if str(p).startswith("..") or str(p).startswith("./"):
        return (base / path).resolve()
    # Bare path → ROOT-relative convention
    return (ROOT / path).resolve()


def probe_video(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=width,height,codec_type", "-of", "json", str(path)],
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


# --- Validation ---

def validate_script(script, base):
    errors = []
    if not script.get("project_id"):
        errors.append("Missing 'project_id'")
    segments = script.get("segments")
    if not segments:
        errors.append("No segments")
        return errors
    for i, seg in enumerate(segments):
        prefix = f"[{seg.get('id', i)}]"
        if not seg.get("id"):
            errors.append(f"{prefix} missing 'id'")
        if not seg.get("visual_brief"):
            errors.append(f"{prefix} missing 'visual_brief' (needed for media generation)")
        if not seg.get("media"):
            errors.append(f"{prefix} missing 'media' path (where to save the clip)")
    return errors


def check_hf_available():
    """Check Higgsfield CLI is installed and authenticated. Never prints credentials."""
    if not HF_BIN.exists():
        return False, "Higgsfield CLI not installed (node_modules/@higgsfield/cli missing)"
    try:
        # auth token returns the token string — capture but do NOT print/log it
        cmd = ["node", str(HF_BIN), "auth", "token"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or "Not authenticated" in (r.stdout + r.stderr):
            return False, "Not authenticated. Run: node node_modules/@higgsfield/cli/bin/higgsfield.js auth login"
        return True, "authenticated"
    except Exception as e:
        return False, str(e)


# --- Generation ---

def generate_segment(seg, media_path, model, dry_run=False):
    """Generate one video clip. Returns job result dict or None for dry_run."""
    audio_mode = seg.get("audio_mode", "generated_tts")

    # Build effective prompt — override takes priority over visual_brief
    if seg.get("visual_prompt_override"):
        positive = seg["visual_prompt_override"]
    elif audio_mode == "generated_tts":
        positive = BROLL_REALISM_PREFIX + seg.get("visual_brief", "")
    else:
        positive = seg.get("visual_brief", "")

    # Negative prompt — segment override or default
    negative = seg.get("negative_prompt") or (BROLL_NEGATIVE if audio_mode == "generated_tts" else "")
    if negative:
        prompt = positive + f". Avoid: {negative}"
    else:
        prompt = positive

    seg_id = seg["id"]
    ref_image = seg.get("reference_image")

    if dry_run:
        print(f"  [{seg_id}] DRY RUN:")
        print(f"    model:    {model}")
        print(f"    prompt:   {prompt[:120]}...")
        if negative:
            print(f"    negative: {negative[:80]}...")
        if ref_image:
            print(f"    ref img:  {ref_image}")
        print(f"    output:   {media_path}")
        return None

    print(f"  [{seg_id}] generating ({model})...", end=" ", flush=True)

    cmd = ["node", str(HF_BIN), "generate", "create", model, "--prompt", prompt]

    # Reference image support (optional per-segment field)
    if ref_image:
        ref_path = Path(ref_image)
        if ref_path.exists():
            r = subprocess.run(["node", str(HF_BIN), "upload", "create", str(ref_path), "--json"],
                             capture_output=True, text=True)
            uid = json.loads(r.stdout).get("id")
            if uid:
                cmd += ["--image", uid]
        else:
            print(f"  [{seg_id}] WARNING: reference_image not found: {ref_image}")

    cmd += ["--wait", "--wait-timeout", WAIT_TIMEOUT, "--wait-interval", WAIT_INTERVAL, "--json"]

    # hf_cmd prepends "node HF_BIN"; extract args after the binary
    hf_args = cmd[2:]  # strip "node HF_BIN" we added
    result = hf_cmd(hf_args)

    # Download the result
    # Result contains output URLs; download the video
    # --wait may return a list; take the first (and only) item
    if isinstance(result, list):
        result = result[0] if result else {}

    # Extract the download URL
    url = (result.get("result_url")
           or result.get("output_url")
           or next(iter(result.get("outputs") or result.get("output_urls") or []), None))

    if not url:
        raise RuntimeError(f"[{seg_id}] no result_url in response: {json.dumps(result)[:300]}")

    media_path.parent.mkdir(parents=True, exist_ok=True)

    import urllib.request
    raw_path = media_path.parent / f".raw_{media_path.name}"
    urllib.request.urlretrieve(url, str(raw_path))

    # Strip audio from b-roll (generated_tts segments use ElevenLabs narration,
    # not random Higgsfield ambient audio). Keep video-only at the final target.
    audio_mode = seg.get("audio_mode", "generated_tts")
    if audio_mode == "generated_tts":
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw_path), "-an", "-c:v", "copy", str(media_path)],
            capture_output=True)
    else:
        import shutil
        shutil.move(str(raw_path), str(media_path))

    # Clean up raw if final exists
    if media_path.exists() and raw_path.exists():
        raw_path.unlink()

    info = probe_video(media_path)
    if info is None:
        raise RuntimeError(f"[{seg_id}] downloaded file is not a valid video: {media_path}")

def build_storyboard(script, base):
    """Derive a lightweight storyboard plan to check coherence before generation."""
    VISUAL_ROLES = ["hook", "credibility", "insight", "system", "give_back", "audience", "promise", "cta"]
    segs = script["segments"]
    plan = []
    prev_scene = None
    warnings = []
    for i, seg in enumerate(segs):
        sid = seg["id"]
        mode = seg.get("audio_mode", "generated_tts")
        role = VISUAL_ROLES[i] if i < len(VISUAL_ROLES) else "support"
        if mode == "baked_in":
            scene_type = "A_ROLL_JAMES"
        elif mode == "silent":
            scene_type = "TITLE_OR_TRANSITION"
        else:
            scene_type = "B_ROLL_SUPPORTING"
        # Flag adjacent repeated scene types (b-roll spam)
        if scene_type == prev_scene == "B_ROLL_SUPPORTING":
            warnings.append(f"{sid}: two adjacent B_ROLL segments — risk of monotony")
        prev_scene = scene_type
        plan.append({
            "segment_id": sid,
            "visual_role": role,
            "scene_type": scene_type,
            "audio_mode": mode,
            "forbidden_elements": ["readable_text", "logos", "fake_ui", "miniature_scale"],
        })
    a_roll = sum(1 for p in plan if p["scene_type"] == "A_ROLL_JAMES")
    pct = round(100 * a_roll / len(plan))
    return {"project_id": script["project_id"], "james_presence_pct": pct,
            "segments": plan, "warnings": warnings}


def media_review(script, base, selected=None):
    """PART F: extract review frames (20/50/80%) + media_review.json with risk flags."""
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    review_dir = output_dir / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    fmt = script.get("defaults", {}).get("format", "mp3")
    narration_dir = output_dir / "narration"
    TEXT_RISK = ["screen", "laptop", "whiteboard", "document", "report",
                 "powerpoint", "slide", "chart", "dashboard", "monitor", "deck"]
    entries = []
    for seg in script["segments"]:
        sid = seg["id"]
        if selected and sid not in selected:
            continue
        media_path = resolve(base, seg["media"])
        if not media_path.exists():
            entries.append({"segment_id": sid, "status": "missing"})
            continue
        info = probe_video(media_path)
        frames = []
        for pct in (0.2, 0.5, 0.8):
            t = info["duration"] * pct
            fp = review_dir / f"{sid}_{int(pct*100)}.jpg"
            subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.1f}", "-i", str(media_path),
                            "-frames:v", "1", "-q:v", "3", str(fp)], capture_output=True)
            if fp.exists():
                frames.append(str(fp))
        brief = (seg.get("visual_brief", "") + " " + (seg.get("visual_prompt_override") or "")).lower()
        warnings = []
        if any(w in brief for w in TEXT_RISK):
            warnings.append("possible_text_risk")
            if any(w in brief for w in ["screen", "laptop", "monitor"]):
                warnings.append("screen_scene")
            if "whiteboard" in brief:
                warnings.append("whiteboard_scene")
            if any(w in brief for w in ["document", "report", "slide", "powerpoint", "deck"]):
                warnings.append("document_scene")
        nar = narration_dir / f"{sid}.{fmt}"
        nar_dur = None
        if nar.exists():
            r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","default=noprint_wrappers=1:nokey=1",str(nar)],capture_output=True,text=True)
            try: nar_dur = float(r.stdout.strip())
            except ValueError: pass
        if nar_dur and info["duration"] < nar_dur:
            warnings += ["duration_short", "loop_risk"]
        entries.append({
            "segment_id": sid, "media_path": str(media_path),
            "duration": round(info["duration"], 2), "resolution": f"{info['width']}x{info['height']}",
            "has_audio": info["has_audio"],
            "expected_narration_duration": round(nar_dur, 2) if nar_dur else None,
            "duration_pass": (info["duration"] >= nar_dur) if nar_dur else None,
            "frames": frames, "warnings": warnings,
        })
        wstr = f" ⚠ {', '.join(warnings)}" if warnings else " ✓"
        print(f"  [{sid}] {info['duration']:.1f}s {info['width']}x{info['height']}{wstr}")
    out = output_dir / "media_review.json"
    with open(out, "w") as f:
        json.dump({"project_id": script["project_id"], "segments": entries}, f, indent=2)
    print(f"  review: {out}")


def extract_review_frame(media_path, out_dir):
    """Extract a representative mid-point frame for visual review."""
    info = probe_video(media_path)
    if not info:
        return None
    mid = info["duration"] / 2
    frame_path = out_dir / f"{Path(media_path).stem}_review.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{mid:.1f}", "-i", str(media_path),
         "-frames:v", "1", "-q:v", "3", str(frame_path)],
        capture_output=True)
    return frame_path if frame_path.exists() else None


def run(script_path, dry_run=False, force=False, validate_only=False,
        do_assemble=False, selected_segments=None):
    script_path = Path(script_path).resolve()
    if not script_path.exists():
        raise ValueError(f"Script not found: {script_path}")
    base = script_path.parent

    with open(script_path) as f:
        script = json.load(f)

    errors = validate_script(script, base)
    if errors:
        raise ValueError("Script validation failed:\n  " + "\n  ".join(errors))

    if validate_only:
        print(f"VALID: {len(script['segments'])} segments with visual briefs")
        for seg in script["segments"]:
            media_path = resolve(base, seg["media"])
            status = "✓ exists" if media_path.exists() else "○ needed"
            selected = " [SELECTED]" if selected_segments and seg["id"] in selected_segments else ""
            print(f"  [{seg['id']}] {status}{selected} → {media_path}")
        return

    # Check Higgsfield availability
    available, msg = check_hf_available()
    if not available and not dry_run:
        raise RuntimeError(f"BLOCKED: {msg}")

    model = script.get("defaults", {}).get("video_model", None)
    results = []
    generated = 0
    skipped = 0

    for seg in script["segments"]:
        seg_id = seg["id"]

        # Selective regeneration: skip segments not in the selection
        if selected_segments and seg_id not in selected_segments:
            media_path = resolve(base, seg["media"])
            status = "✓ exists" if media_path.exists() else "○ needed"
            print(f"  [{seg_id}] skip (not selected) — {status}")
            skipped += 1
            continue

        media_path = resolve(base, seg["media"])
        # Pick model: lipsync clips use Seedance 2.0 Fast, b-roll uses cheaper wan2_7
        seg_model = model or (DEFAULT_LIPSYNC_MODEL if seg.get("audio_mode") == "baked_in" else DEFAULT_BROLL_MODEL)

        if media_path.exists() and not force:
            info = probe_video(media_path)
            if info:
                print(f"  [{seg_id}] reused ({info['width']}x{info['height']}, {info['duration']:.1f}s)")
                skipped += 1
                continue

        try:
            result = generate_segment(seg, media_path, seg_model, dry_run=dry_run)
            if result:
                results.append(result)
                generated += 1
                # Extract review frame for generated segments
                output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
                review_dir = output_dir / "review_frames"
                review_dir.mkdir(parents=True, exist_ok=True)
                frame = extract_review_frame(media_path, review_dir)
                if frame:
                    print(f"    frame: {frame}")
        except RuntimeError as e:
            print(f"  [{seg_id}] FAILED: {e}", file=sys.stderr)
            raise

    if not dry_run:
        print(f"\n  generated: {generated}, reused: {skipped}, total: {len(script['segments'])}")

        # Write generation log (provenance tracking, no credentials)
        output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
        output_dir.mkdir(parents=True, exist_ok=True)
        log_entries = []
        for seg in script["segments"]:
            media_path = resolve(base, seg["media"])
            info = probe_video(media_path) if media_path.exists() else None
            # Determine provenance
            matched = [r for r in results if r["id"] == seg["id"]]
            if matched:
                action = "generated_higgsfield"
            elif media_path.exists():
                action = "reused_existing"
            else:
                action = "missing"
            log_entries.append({
                "segment_id": seg["id"],
                "target_path": str(media_path),
                "action": action,
                "model": (DEFAULT_LIPSYNC_MODEL if seg.get("audio_mode") == "baked_in" else DEFAULT_BROLL_MODEL) if matched else None,
                "prompt_excerpt": seg.get("visual_brief", "")[:80],
                "width": info["width"] if info else None,
                "height": info["height"] if info else None,
                "duration": info["duration"] if info else None,
                "has_audio": info["has_audio"] if info else None,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z") if matched else None,
            })
        log_path = output_dir / "media_generation_log.json"
        with open(log_path, "w") as f:
            json.dump({"project_id": script["project_id"], "segments": log_entries}, f, indent=2)
        print(f"  log: {log_path}")

    # Optionally assemble
    if do_assemble and not dry_run:
        print("\n  Running TTS + assembly...")
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "tts.py"), str(script_path), "--assemble"],
            cwd=str(ROOT))
        if r.returncode != 0:
            raise RuntimeError(f"TTS/assembly failed (exit {r.returncode})")


def main():
    ap = argparse.ArgumentParser(description="Generate video clips from visual briefs via Higgsfield.")
    ap.add_argument("script", help="Path to script JSON with visual_brief per segment")
    ap.add_argument("--validate-only", action="store_true", help="Check schema and existing media")
    ap.add_argument("--dry-run", action="store_true", help="Print prompts/paths, no API calls")
    ap.add_argument("--force", action="store_true", help="Regenerate all media (overwrite existing)")
    ap.add_argument("--segment", action="append", dest="segments", metavar="SEG_ID",
                    help="Regenerate only this segment (repeat for multiple)")
    ap.add_argument("--segments", dest="segments_csv", default=None,
                    help="Comma-separated segment IDs to regenerate")
    ap.add_argument("--storyboard-only", action="store_true", help="Output storyboard plan, no generation")
    ap.add_argument("--review", action="store_true", help="Generate review frames + media_review.json")
    ap.add_argument("--assemble", action="store_true", help="Run tts.py --assemble after generation")
    ap.add_argument("--model", default=None, help="Override video model")
    args = ap.parse_args()

    selected = set(args.segments) if args.segments else set()
    if args.segments_csv:
        selected |= {s.strip() for s in args.segments_csv.split(",")}
    selected = selected or None

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"ERROR: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    script = json.load(open(script_path))
    base = script_path.parent

    try:
        if args.storyboard_only:
            sb = build_storyboard(script, base)
            out = script_path.with_name(f"{script_path.stem}_storyboard.json")
            with open(out, "w") as f:
                json.dump(sb, f, indent=2)
            print(f"Storyboard plan ({sb['james_presence_pct']}% James A-roll):")
            for p in sb["segments"]:
                print(f"  [{p['segment_id']}] {p['visual_role']:12s} {p['scene_type']}")
            for w in sb["warnings"]:
                print(f"  ⚠ {w}")
            print(f"  storyboard: {out}")
            return

        if args.review:
            media_review(script, base, selected)
            return

        run(args.script, dry_run=args.dry_run, force=args.force,
            validate_only=args.validate_only, do_assemble=args.assemble,
            selected_segments=selected)
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
