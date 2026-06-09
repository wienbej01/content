#!/usr/bin/env python3
"""tts.py — Generate narration audio from a reviewed script, produce an assembly manifest.

Pipeline:  reviewed_script.json → ElevenLabs TTS → narration audio → manifest.json → assemble.py

Usage:
  python scripts/tts.py scripts/sample_script.json                 # generate narration + manifest
  python scripts/tts.py scripts/sample_script.json --force         # regenerate all narration
  python scripts/tts.py scripts/sample_script.json --assemble      # + run assemble.py after
  python scripts/tts.py scripts/sample_script.json --validate-only # validate without API calls

Reads ELEVENLABS_API_KEY from environment or ~/.config/ytchannel/runtime.env.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ENV = Path.home() / ".config" / "ytchannel" / "runtime.env"

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_SPEED = 1.0        # Top-level speed param (1.0 = normal; reference file used 1.05)
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.50,
    "similarity_boost": 0.75,
    "style": 0.12,
    "use_speaker_boost": True,
}

# ElevenLabs UI → API parameter mapping:
# UI "Stability"         → voice_settings.stability       (0.0–1.0)
# UI "Similarity Boost"  → voice_settings.similarity_boost (0.0–1.0)
# UI "Style Exaggeration"→ voice_settings.style            (0.0–1.0)
# UI "Speaker Boost"     → voice_settings.use_speaker_boost (bool)
# UI "Speed"             → top-level body param: speed      (0.7–1.2; default 1.0)
# Model "Eleven Multilingual v2" → model_id: "eleven_multilingual_v2"


def load_runtime_env():
    """Load KEY=VALUE from runtime.env into os.environ (does not override existing)."""
    import os
    if not RUNTIME_ENV.exists():
        return
    for raw in RUNTIME_ENV.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key():
    """Return ELEVENLABS_API_KEY or None."""
    import os
    load_runtime_env()
    return os.environ.get("ELEVENLABS_API_KEY") or None


def get_voice_id(script_voice):
    """Resolve voice_id: script JSON > env > fail."""
    import os
    load_runtime_env()
    vid = script_voice.get("voice_id")
    if vid and vid != "SET_YOUR_VOICE_ID_HERE":
        return vid
    vid = os.environ.get("ELEVENLABS_VOICE_ID")
    if vid:
        return vid
    return None


def probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except (ValueError, IndexError):
        raise FileNotFoundError(f"Cannot probe duration: {path}")


def media_has_audio(path):
    """Return True if the file contains an audio stream (i.e., is a lipsync clip)."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return "audio" in r.stdout


def word_count(text):
    return len(text.split())


def resolve(base, p):
    if p is None:
        return None
    path = Path(p)
    return path if path.is_absolute() else (base / path).resolve()


VALID_AUDIO_MODES = ("generated_tts", "baked_in", "silent")


# --- Validation ---

def validate_script(script, base):
    """Validate script structure. Returns list of error strings."""
    errors = []
    if not isinstance(script, dict):
        return ["Script must be a JSON object"]

    if not script.get("project_id"):
        errors.append("Missing required field: 'project_id'")

    segments = script.get("segments")
    if not segments or not isinstance(segments, list):
        errors.append("'segments' must be a non-empty array")
        return errors

    voice = script.get("voice", {})
    load_runtime_env()
    import os as _os
    if not voice.get("voice_id") and not _os.environ.get("ELEVENLABS_VOICE_ID"):
        errors.append("voice.voice_id is required (or set ELEVENLABS_VOICE_ID in env)")

    for i, seg in enumerate(segments):
        prefix = f"segments[{i}]"
        if not seg.get("id"):
            errors.append(f"{prefix}: missing 'id'")

        # audio_mode is required — no silent guessing
        mode = seg.get("audio_mode")
        if not mode:
            errors.append(
                f"{prefix}: missing 'audio_mode'. Set to 'generated_tts', 'baked_in', or 'silent'.")
        elif mode not in VALID_AUDIO_MODES:
            errors.append(
                f"{prefix}: unknown audio_mode '{mode}'. Must be one of: {VALID_AUDIO_MODES}")
        elif mode == "generated_tts":
            if not seg.get("text"):
                errors.append(f"{prefix}: audio_mode=generated_tts requires 'text'")
        elif mode == "baked_in":
            media = seg.get("media")
            if media:
                media_path = resolve(base, media)
                if media_path.exists() and not media_has_audio(media_path):
                    errors.append(f"{prefix}: audio_mode=baked_in but media has no audio stream")

        media = seg.get("media")
        if media:
            media_path = resolve(base, media)
            if not media_path.exists():
                errors.append(f"{prefix}.media: file not found: {media_path}")
        else:
            errors.append(f"{prefix}: missing 'media' (required for assembly)")

    return errors


# --- TTS ---

def synthesize_segment(text, voice_id, model_id, voice_settings, api_key, speed=None):
    """Call ElevenLabs TTS API. Returns audio bytes (mp3).

    speed is ALWAYS sent inside voice_settings (ElevenLabs' documented location for
    eleven_multilingual_v2), including speed=1.0, for deterministic/explicit behavior.
    If the API rejects speed in voice_settings, we retry without it and log the fallback.
    """
    url = f"{ELEVENLABS_URL}/{voice_id}"
    vs = dict(voice_settings)
    if speed is not None:
        vs["speed"] = speed  # always explicit, including 1.0
    payload = {"text": text, "model_id": model_id, "voice_settings": vs}
    body = json.dumps(payload).encode()

    req = urllib.request.Request(url, data=body, headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"ElevenLabs API error {resp.status}")
            return resp.read()
    except urllib.error.HTTPError as e:
        # If speed in voice_settings is rejected, retry without it and report.
        if speed is not None and e.code in (400, 422):
            print(f"  WARN: ElevenLabs rejected speed in voice_settings ({e.code}); "
                  f"retrying without explicit speed.", file=sys.stderr)
            vs2 = dict(voice_settings)
            payload2 = {"text": text, "model_id": model_id, "voice_settings": vs2}
            req2 = urllib.request.Request(url, data=json.dumps(payload2).encode(), headers={
                "xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
            with urllib.request.urlopen(req2, timeout=60) as resp2:
                return resp2.read()
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"ElevenLabs API {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs connection failed: {e.reason}")


# --- Manifest generation ---

def _rel_to(path, base_dir):
    """Make an absolute path relative to base_dir, or return absolute if not possible."""
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        # Can't make relative, use os.path.relpath
        import os
        return os.path.relpath(str(path), str(base_dir))


def build_manifest(script, narration_dir, base):
    """Build an assemble.py-compatible manifest from the script + generated narration."""
    segments = script["segments"]
    project_id = script["project_id"]
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{project_id}"))
    defaults = script.get("defaults", {})
    fmt = defaults.get("format", "mp3")

    manifest_segments = []
    for seg in segments:
        seg_id = seg["id"]
        mode = seg.get("audio_mode", "generated_tts")
        media_abs = resolve(base, seg["media"])

        entry = {"media": _rel_to(media_abs, output_dir)}

        if mode == "generated_tts":
            audio_path = narration_dir / f"{seg_id}.{fmt}"
            entry["audio"] = _rel_to(audio_path, output_dir)
            entry["words"] = word_count(seg.get("text", ""))
        elif mode == "baked_in":
            entry["words"] = word_count(seg.get("text", "")) if seg.get("text") else 0
        elif mode == "silent":
            entry["words"] = 0

        if seg.get("trim_end"):
            entry["trim_end"] = seg["trim_end"]
        if seg.get("lower_third"):
            lt_abs = resolve(base, seg["lower_third"])
            entry["lower_third"] = _rel_to(lt_abs, output_dir)

        manifest_segments.append(entry)

    # Pacing: reference is the longest segment (most words) for natural pacing
    ref_idx = max(range(len(manifest_segments)), key=lambda i: manifest_segments[i]["words"])

    # Brand assets relative to output_dir
    brand_dir = ROOT / "brand" / "assets"
    manifest = {
        "id": project_id,
        "segments": manifest_segments,
        "pacing": {
            "reference": ref_idx,
            "baseline_speed": 0.85,
        },
        "music": {
            "mood": "calm",
            "level_db": -16,
        },
        "brand": {
            "endcard_16x9": _rel_to(brand_dir / "endcard_16x9.png", output_dir),
            "endcard_9x16": _rel_to(brand_dir / "endcard_9x16.png", output_dir),
            "endcard_duration": 3.0,
            "gap_seconds": 0.4,
            "audio_fade": 0.3,
        },
        "render": {
            "fps": 24,
            "crf": 18,
            "grade": "eq=contrast=1.04:saturation=1.05:gamma=0.98,colorbalance=rs=0.02:gs=0.0:bs=-0.03:rm=0.02:bm=-0.02",
        },
        "output": {
            "directory": ".",
            "prefix": project_id,
        },
    }

    # Override music if specified in script defaults
    music_file = defaults.get("music")
    if music_file:
        music_abs = resolve(base, music_file)
        manifest["music"]["file"] = _rel_to(music_abs, output_dir)

    return manifest


# --- Main workflow ---

def run_tts(script_path, force=False, do_assemble=False, validate_only=False):
    script_path = Path(script_path).resolve()
    if not script_path.exists():
        raise ValueError(f"Script file not found: {script_path}")
    base = script_path.parent

    with open(script_path) as f:
        try:
            script = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    # Validate
    errors = validate_script(script, base)
    if errors:
        raise ValueError("Script validation failed:\n  " + "\n  ".join(errors))

    if validate_only:
        import os as _os
        load_runtime_env()
        voice_id_disp = get_voice_id(script.get("voice", {})) or "[not configured]"
        effective_speed = float(_os.environ.get("ELEVENLABS_SPEED", script.get("voice", {}).get("speed", DEFAULT_SPEED)))
        effective_settings = {**DEFAULT_VOICE_SETTINGS, **script.get("voice", {}).get("settings", {})}
        print("VALID: script passes validation")
        print(f"  project_id:        {script['project_id']}")
        print(f"  segments:          {len(script['segments'])}")
        print(f"  voice_id:          {voice_id_disp}")
        print(f"  model:             {script.get('voice', {}).get('model_id', DEFAULT_MODEL)}")
        print(f"  speed:             {effective_speed}")
        print(f"  stability:         {effective_settings['stability']}")
        print(f"  similarity_boost:  {effective_settings['similarity_boost']}")
        print(f"  style:             {effective_settings['style']}")
        print(f"  use_speaker_boost: {effective_settings['use_speaker_boost']}")
        return None

    # Setup output
    project_id = script["project_id"]
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{project_id}"))
    output_dir.mkdir(parents=True, exist_ok=True)
    narration_dir = output_dir / "narration"
    narration_dir.mkdir(exist_ok=True)
    fmt = script.get("defaults", {}).get("format", "mp3")

    # Require API key only if there are generated_tts segments that need work
    needs_tts = any(
        seg.get("audio_mode") == "generated_tts"
        and (force or not (narration_dir / f"{seg['id']}.{fmt}").exists())
        for seg in script["segments"]
    )
    api_key = get_api_key()
    if needs_tts and not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set. Add it to environment or ~/.config/ytchannel/runtime.env")

    # Voice config
    voice = script.get("voice", {})
    voice_id = get_voice_id(voice)
    if needs_tts and not voice_id:
        raise RuntimeError(
            "No voice_id configured. Set voice.voice_id in the script JSON "
            "or ELEVENLABS_VOICE_ID in environment/runtime.env")
    model_id = voice.get("model_id", DEFAULT_MODEL)
    voice_settings = {**DEFAULT_VOICE_SETTINGS, **voice.get("settings", {})}
    import os as _os2
    speed = float(_os2.environ.get("ELEVENLABS_SPEED", voice.get("speed", DEFAULT_SPEED)))
    segments = script["segments"]
    log_entries = []

    for seg in segments:
        seg_id = seg["id"]
        mode = seg.get("audio_mode", "generated_tts")

        if mode != "generated_tts":
            print(f"  [{seg_id}] {mode} (skipped TTS)")
            log_entries.append({"id": seg_id, "action": mode, "duration": None})
            continue

        audio_path = narration_dir / f"{seg_id}.{fmt}"

        if audio_path.exists() and not force:
            duration = probe_dur(audio_path)
            print(f"  [{seg_id}] reused existing ({duration:.2f}s)")
            log_entries.append({"id": seg_id, "action": "reused", "duration": duration})
            continue

        print(f"  [{seg_id}] generating TTS...", end=" ", flush=True)
        audio_bytes = synthesize_segment(seg["text"], voice_id, model_id, voice_settings, api_key, speed=speed)
        audio_path.write_bytes(audio_bytes)
        duration = probe_dur(audio_path)
        print(f"done ({duration:.2f}s, {len(audio_bytes)//1024}KB)")
        log_entries.append({"id": seg_id, "action": "generated", "duration": duration})

    # Build manifest
    manifest = build_manifest(script, narration_dir, base)
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Write generation log
    gen_log = {
        "project_id": project_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "segments": log_entries,
        "manifest": str(manifest_path),
    }
    log_path = output_dir / "tts_log.json"
    with open(log_path, "w") as f:
        json.dump(gen_log, f, indent=2)

    print(f"\n  manifest: {manifest_path}")
    print(f"  narration: {narration_dir}/")
    print(f"  Next: python scripts/assemble.py {manifest_path}")

    # Optionally assemble
    if do_assemble:
        print(f"\n  Running assembly...")
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "assemble.py"), str(manifest_path)],
            cwd=str(ROOT))
        if r.returncode != 0:
            raise RuntimeError(f"Assembly failed (exit {r.returncode})")

    return manifest_path


def _find_segment(script, text_contains=None, segment_id=None):
    for seg in script["segments"]:
        if segment_id and seg["id"] == segment_id:
            return seg
        if text_contains and text_contains.lower() in seg.get("text", "").lower():
            return seg
    return None


def show_segment_audio(script_path, text_contains=None, segment_id=None):
    """PHASE 0/8: print inspection info for one segment (no regeneration)."""
    script = json.load(open(script_path))
    base = Path(script_path).resolve().parent
    seg = _find_segment(script, text_contains, segment_id)
    if not seg:
        print(f"No segment matching id={segment_id} text_contains={text_contains!r}")
        return
    sid = seg["id"]
    proj = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    nar = proj / "narration" / f"{sid}.mp3"
    media = resolve(base, seg["media"])
    txt = seg.get("text", "")
    wc = word_count(txt)
    nd = probe_dur(nar) if nar.exists() else None
    md = probe_dur(media) if media.exists() else None
    voice = script.get("voice", {})
    settings = {**DEFAULT_VOICE_SETTINGS, **voice.get("settings", {})}
    print(f"segment_id:        {sid}")
    print(f"audio_mode:        {seg.get('audio_mode')}")
    print(f"narration_path:    {nar}  (exists={nar.exists()})")
    print(f"media_path:        {media}")
    print(f"script_text:       {txt}")
    print(f"word_count:        {wc}")
    print(f"narration_duration:{nd}")
    print(f"media_duration:    {md}")
    if nd:
        print(f"WPS:               {wc/nd:.2f}")
    print(f"TTS settings:      model={voice.get('model_id', DEFAULT_MODEL)} "
          f"stability={settings['stability']} similarity_boost={settings['similarity_boost']} "
          f"style={settings['style']} use_speaker_boost={settings['use_speaker_boost']} "
          f"speed={voice.get('speed', DEFAULT_SPEED)}")
    print(f"is_lipsync:        {seg.get('audio_mode') == 'baked_in'}")
    print(f"note: narration generated with the speed/payload fix applied as of M3-C (speed sent explicitly).")


def make_audio_compare_pack(script_path, segment_id, speeds=(1.0, 1.05, 1.10, 1.15)):
    """PHASE 1: build a manual-comparison pack + calibration candidates for one segment."""
    import hashlib
    script = json.load(open(script_path))
    base = Path(script_path).resolve().parent
    seg = _find_segment(script, segment_id=segment_id)
    if not seg:
        raise ValueError(f"segment {segment_id} not found")
    sid = seg["id"]
    txt = seg["text"]
    wc = word_count(txt)
    pid = script["project_id"]
    out = ROOT / "Videos" / "QA" / "audio_compare" / pid / sid
    out.mkdir(parents=True, exist_ok=True)
    voice = script.get("voice", {})
    settings = {**DEFAULT_VOICE_SETTINGS, **voice.get("settings", {})}
    model = voice.get("model_id", DEFAULT_MODEL)
    # script text
    (out / "script_text.txt").write_text(txt)
    # redacted payload
    payload = {"text": txt, "model_id": model, "voice_settings": {**settings, "speed": "<calibrating>"},
               "voice_id": "<REDACTED>", "api_key": "<REDACTED>"}
    (out / "tts_payload.json").write_text(json.dumps(payload, indent=2))
    # reference + instructions
    (out / "INSTRUCTIONS.txt").write_text(
        f"Manual ElevenLabs comparison for segment {sid}\n\n"
        f"Voice: James Harrington\nModel: {model}\n"
        f"Stability: {settings['stability']} | Similarity: {settings['similarity_boost']} | "
        f"Style: {settings['style']} | Speaker Boost: {settings['use_speaker_boost']}\n"
        f"Try Speed values: {', '.join(str(s) for s in speeds)}\n\n"
        f"Paste this text:\n{txt}\n\n"
        f"Compare against the cal_spXXX.mp3 files in this folder. Tell me which speed sounds right.\n"
        f"Reference clip you liked: Videos/Input_audio/20260608_trailer/"
        f"ElevenLabs_2026-06-08T03_39_17_James Harrington_gen_sp105_s50_sb75_se12_b_m2.mp3\n")
    # copy current production mp3 if exists
    proj = resolve(base, script.get("output_dir", f"Videos/Projects/{pid}"))
    cur = proj / "narration" / f"{sid}.mp3"
    candidates = []
    if cur.exists():
        import shutil
        shutil.copy(cur, out / "current_production.mp3")
    # calibration candidates
    ref_wps = 24 / 11.964
    api_key = get_api_key()
    voice_id = get_voice_id(script.get("voice", {}))
    for sp in speeds:
        audio = synthesize_segment(txt, voice_id, model, settings, api_key, speed=sp)
        p = out / f"cal_sp{int(sp*100)}.mp3"
        p.write_bytes(audio)
        d = probe_dur(p)
        candidates.append({"speed": sp, "path": str(p), "duration": round(d, 2),
                           "word_count": wc, "wps": round(wc/d, 3),
                           "ref_wps_delta": round(wc/d - ref_wps, 3),
                           "subjective_review_pending": True})
        print(f"  speed={sp}: {d:.2f}s, {wc/d:.2f} wps")
    report = {"segment_id": sid, "script_text": txt, "reference_wps": round(ref_wps, 3),
              "settings": settings, "model": model, "candidates": candidates,
              "production_mp3": str(cur) if cur.exists() else None,
              "compare_dir": str(out)}
    (out / "audio_calibration_report.json").write_text(json.dumps(report, indent=2))
    print(f"\n  Comparison pack: {out}")
    print(f"  Report: {out / 'audio_calibration_report.json'}")


def main():
    ap = argparse.ArgumentParser(description="Generate TTS narration + assembly manifest from script.")
    ap.add_argument("script", help="Path to reviewed script JSON")
    ap.add_argument("--force", action="store_true", help="Regenerate all narration (skip cache)")
    ap.add_argument("--assemble", action="store_true", help="Run assemble.py after manifest creation")
    ap.add_argument("--validate-only", action="store_true", help="Validate script without API calls")
    ap.add_argument("--show-segment-audio", action="store_true", help="Inspect one segment, no regeneration")
    ap.add_argument("--segment-text-contains", default=None, help="Find segment by text substring")
    ap.add_argument("--segment", default=None, help="Segment id (with --show-segment-audio or --compare-pack)")
    ap.add_argument("--compare-pack", action="store_true", help="Build manual-comparison + calibration pack")
    args = ap.parse_args()

    try:
        if args.show_segment_audio or args.segment_text_contains:
            show_segment_audio(args.script, text_contains=args.segment_text_contains, segment_id=args.segment)
            return
        if args.compare_pack:
            if not args.segment:
                ap.error("--compare-pack requires --segment")
            make_audio_compare_pack(args.script, args.segment)
            return
        run_tts(args.script, force=args.force, do_assemble=args.assemble, validate_only=args.validate_only)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
