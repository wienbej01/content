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
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gates import require_gates  # noqa: E402

# Gates that must pass before ANY Higgsfield spend (blueprint §2/§6/§10).
SPEND_GATES = ["storyboard_review", "media_plan_review", "budget", "render_approval"]

HF_BIN = ROOT / "node_modules" / "@higgsfield" / "cli" / "bin" / "higgsfield.js"
DEFAULT_LIPSYNC_MODEL = "seedance_2_0"    # lipsync: only CLI model with --audio
DEFAULT_BROLL_MODEL = "kling3_0"           # b-roll: kling (wan NOT authorized)
HUMAN_CLOSEUP_MODEL = "kling3_0"           # hero face, hands, body, human background
BANNED_MODELS = {"minimax_hailuo", "seedance_2_0_fast", "seedance1_5",
                 "wan2_7", "wan2_6"}        # wan models NOT authorized
LIPSYNC_MAX_DUR = 10    # seedance_2_0 max duration per clip (seconds)


def _seedance_min_duration():
    """Seedance 2.0 minimum clip duration (constraints.json lipsync_render_rules),
    default 4s. Seedance rejects duration < this."""
    try:
        c = json.loads((ROOT / "docs" / "channel_universe" / "constraints.json").read_text())
        return int(c.get("lipsync_render_rules", {}).get("min_clip_duration_sec", 4))
    except Exception:
        return 4


SEEDANCE_MIN_DURATION_SEC = _seedance_min_duration()  # hero_lipsync clips must be >= this
WAIT_TIMEOUT = "15m"
WAIT_INTERVAL = "10s"
MAX_FREEZE = 0.5        # PHASE 5: no held frame longer than this
CLIP_MAX_DUR = 5.0      # assume model produces ~5s clips; plan multiple shots beyond this

# PHASE 3: text-surface risk terms — these scenes tend to produce AI-gibberish text
TEXT_SURFACE_TERMS = {
    "screen_risk": ["laptop screen", "monitor", "computer screen", "screen", "display", "tablet"],
    "document_risk": ["document", "report", "paper", "papers", "page", "book", "printout", "spreadsheet"],
    "whiteboard_risk": ["whiteboard", "blackboard", "flip chart", "flipchart", "writing on"],
    "slide_risk": ["powerpoint", "slide", "presentation", "deck", "projector"],
    "text_risk": ["sign", "signage", "logo", "label", "chart with", "dashboard", "graph with", "interface"],
}
# PHASE 4: close-human risk terms — must route to seedance, not wan2_7
HUMAN_CLOSEUP_TERMS = {
    "contains_hands": ["hand", "hands", "typing", "writing", "gesture", "fingers", "holding"],
    "contains_face": ["face", "facial", "expression", "smiling", "eyes", "portrait", "close-up of"],
    "contains_close_human": ["close-up", "closeup", "headshot", "person speaking", "speaking to camera"],
}

# Realism constraints injected into every b-roll prompt
BROLL_REALISM_PREFIX = (
    "Premium business cinematography, realistic scale and proportions, "
    "modern office or finance setting, natural lighting, "
    "cinematic quality, believable architecture and interiors. "
    "Construct the scene WITHOUT any text-bearing surfaces: no screens, no laptops, no monitors, "
    "no whiteboards, no documents, no papers, no slides, no signage, no logos. "
    "Prefer wide shots, architecture, city views, and ambient motion. "
    "Any surface that could carry text must be blank or out of focus. "
)
BROLL_NEGATIVE = (
    "readable text, letters, numbers, symbols, fake writing, gibberish text, AI text, "
    "logos, watermark, UI text, whiteboard text, slide deck text, PowerPoint text, "
    "document text, chart labels, subtitles, captions, screens with text, "
    "portrait laptop screens, miniature or toy-like interiors, warped architecture, "
    "fisheye distortion, surreal proportions, fake celebrities, "
    "neon, cyberpunk, sci-fi, futuristic holograms"
)


def classify_prompt_risk(text):
    """PHASE 3+4: classify a visual brief for text-surface and close-human risk.
    Negation-aware: 'no screens', 'without documents' etc. do not count as risk."""
    t = (text or "").lower()

    def present_unnegated(term):
        start = 0
        while True:
            i = t.find(term, start)
            if i == -1:
                return False
            # look back ~12 chars for a negation cue
            window = t[max(0, i - 14):i]
            if not any(neg in window for neg in ["no ", "without ", "absent", "free of", "not "]):
                return True
            start = i + len(term)

    text_flags = {}
    for risk, terms in TEXT_SURFACE_TERMS.items():
        if any(present_unnegated(term) for term in terms):
            text_flags[risk] = True
    human_flags = {}
    for flag, terms in HUMAN_CLOSEUP_TERMS.items():
        if any(present_unnegated(term) for term in terms):
            human_flags[flag] = True
    return {"text_surface_risk": bool(text_flags), "text_flags": sorted(text_flags),
            "close_human_risk": bool(human_flags), "human_flags": sorted(human_flags)}


def route_model(seg_or_shot, audio_mode, default_broll=DEFAULT_BROLL_MODEL):
    """Return model string. Banned models are replaced with the default."""
    return route_model_with_reason(seg_or_shot, audio_mode, default_broll)[0]


def route_model_with_reason(seg_or_shot, audio_mode, default_broll=DEFAULT_BROLL_MODEL):
    """Return (model, reason) for dry-run reporting."""
    if audio_mode == "baked_in":
        return DEFAULT_LIPSYNC_MODEL, "lipsync/talking-head"
    explicit = seg_or_shot.get("model")
    if explicit:
        if explicit in BANNED_MODELS:
            return default_broll, f"banned model {explicit!r} → replaced with {default_broll}"
        return explicit, "explicit override"
    risk = classify_prompt_risk(seg_or_shot.get("visual_brief", "")
                                or seg_or_shot.get("visual_prompt_override", ""))
    if risk["close_human_risk"]:
        return HUMAN_CLOSEUP_MODEL, f"close-human ({', '.join(risk['human_flags'])})"
    return default_broll, "environment/abstract b-roll"


# Credit cost estimates per clip (Higgsfield bills a 10-second minimum)
_CREDITS = {
    "seedance_2_0": (2.0, 2.0),
    "kling3_0":   (10.0, 10.0),
    "wan2_7":      (1.0, 1.0),
    "wan2_6":      (1.0, 1.0),
    "cinematic_studio_3_0": (25.0, 25.0),
    "seedance_2_0":      (2.0, 2.0),
}


def credit_estimate(model, duration=None):
    """Return (prorated_cr, worst_case_cr) estimate."""
    p, w = _CREDITS.get(model, (1.0, 1.0))
    return p, w




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


def audio_duration(path: Path) -> float:
    """Return duration of an audio file in seconds (0.0 on error)."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def split_audio(audio_path: Path, chunk_dur: float, tmp_dir: Path) -> list[Path]:
    """Split audio into ≤chunk_dur second segments using ffmpeg segment muxer.
    Returns list of chunk paths in order. Cleans up existing chunks first."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(tmp_dir / "chunk_%03d.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path),
         "-f", "segment", "-segment_time", str(int(chunk_dur)),
         "-c", "copy", pattern],
        check=True, capture_output=True)
    return sorted(tmp_dir.glob("chunk_*.mp3"))


def concat_videos(clips: list[Path], out: Path) -> None:
    """Concatenate MP4 clips with ffmpeg, then remove the source clips."""
    lst = out.with_suffix(".concat.txt")
    lst.write_text("\n".join(f"file '{c.resolve()}'" for c in clips))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(out)],
        check=True, capture_output=True)
    lst.unlink(missing_ok=True)
    for c in clips:
        c.unlink(missing_ok=True)


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

def build_prompt(spec, audio_mode):
    """Build the effective positive+negative prompt for a segment or shot spec."""
    if spec.get("visual_prompt_override"):
        positive = spec["visual_prompt_override"]
    elif audio_mode == "generated_tts":
        positive = BROLL_REALISM_PREFIX + spec.get("visual_brief", "")
    else:
        positive = spec.get("visual_brief", "")
    negative = spec.get("negative_prompt") or (BROLL_NEGATIVE if audio_mode == "generated_tts" else "")
    prompt = positive + (f". Avoid: {negative}" if negative else "")
    return prompt, negative


def generate_segment(seg, media_path, model, dry_run=False, audio_mode=None, spec=None,
                     duration=None, audio_path=None):
    """Generate one video clip (segment OR shot). Returns job result dict or None for dry_run.

    spec defaults to seg; for per-shot generation pass the shot dict as spec.
    """
    if audio_mode is None:
        audio_mode = seg.get("audio_mode", "generated_tts")
    if spec is None:
        spec = seg
    prompt, negative = build_prompt(spec, audio_mode)
    seg_id = spec.get("id", seg.get("id"))
    ref_image = spec.get("reference_image") or seg.get("reference_image")

    if dry_run:
        risk = classify_prompt_risk(spec.get("visual_brief", "") or spec.get("visual_prompt_override", ""))
        flags = []
        if risk["text_surface_risk"]: flags += [f"text:{','.join(risk['text_flags'])}"]
        if risk["close_human_risk"]:  flags += [f"human:{','.join(risk['human_flags'])}"]
        _, reason = route_model_with_reason(spec, audio_mode)
        pro, worst = credit_estimate(model, duration)
        print(f"  [{seg_id}] DRY RUN:")
        print(f"    model:    {model}  (reason: {reason})")
        print(f"    credits:  ~{pro}cr prorated / ~{worst}cr worst-case (10s min billing)")
        print(f"    duration: {duration if duration else 'segment-level'}")
        print(f"    prompt:   {prompt[:140]}")
        if negative:
            print(f"    negative: {negative[:80]}...")
        if ref_image:
            print(f"    ref img:  {ref_image}")
        if audio_path:
            print(f"    audio:    {audio_path}")
        print(f"    output:   {media_path}")
        print(f"    risk:     {', '.join(flags) if flags else 'none ✓'}")
        print(f"    action:   would {'reuse' if media_path.exists() else 'generate'} | blocked: no")
        return None

    print(f"  [{seg_id}] generating ({model})...", end=" ", flush=True)

    cmd = ["node", str(HF_BIN), "generate", "create", model, "--prompt", prompt]
    if duration:
        cmd += ["--duration", str(int(round(duration)))]

    # Reference image — required for lipsync (seedance_2_0 needs --image + --audio together)
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

    # Lipsync: pass narration audio to Higgsfield
    if audio_path and Path(audio_path).exists():
        cmd += ["--audio", str(audio_path)]
    elif audio_path:
        raise RuntimeError(f"[{seg_id}] audio_path not found: {audio_path}")

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
    print(f"done ({info['width']}x{info['height']}, {info['duration']:.1f}s)")
    return {"segment_id": seg_id, "media_path": str(media_path), "model": model,
            "duration": round(info["duration"], 2)}


def plan_shots(seg, narration_dur, base):
    """PHASE 5: plan shot coverage for a segment's narration duration.
    Returns list of planned shots (uses seg['shots'] if present, else derives count)."""
    sid = seg["id"]
    tail = 0.25
    needed = narration_dur + tail
    audio_mode = seg.get("audio_mode", "generated_tts")
    if seg.get("shots"):
        # Fill in routed model per shot if not explicitly set
        for s in seg["shots"]:
            if not s.get("model"):
                s["_routed_model"] = route_model(s, audio_mode)
        return seg["shots"], needed
    n = max(1, math.ceil(needed / CLIP_MAX_DUR)) if narration_dur else 1
    if audio_mode == "baked_in":
        n = 1  # lipsync is a single continuous take
    shots = []
    for i in range(n):
        dur = min(CLIP_MAX_DUR, needed - i * CLIP_MAX_DUR) if n > 1 else needed
        shots.append({
            "id": f"{sid}_shot{i+1:02d}" if n > 1 else sid,
            "duration": round(dur, 2),
            "media": seg["media"] if n == 1 else f"../../assets/media/james_teaser_02/{sid}_shot{i+1:02d}.mp4",
            "visual_brief": seg.get("visual_brief", ""),
            "model": route_model(seg, audio_mode),
        })
    return shots, needed


def duration_report(script, base):
    """PHASE 5: per-segment narration vs media duration, freeze/loop risk, shots needed."""
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    fmt = script.get("defaults", {}).get("format", "mp3")
    tail = 0.25
    entries = []
    for seg in script["segments"]:
        sid = seg["id"]
        media = resolve(base, seg["media"])
        nar = output_dir / "narration" / f"{sid}.{fmt}"
        md = probe_video(media)["duration"] if media.exists() else None
        nd = None
        if nar.exists():
            r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","default=noprint_wrappers=1:nokey=1",str(nar)],capture_output=True,text=True)
            try: nd = float(r.stdout.strip())
            except ValueError: pass
        mode = seg.get("audio_mode", "generated_tts")
        eff = (nd + tail) if (nd and mode != "baked_in") else (md if md else None)
        freeze = 0.0
        loops = False
        shots_needed = 1
        if nd and md and mode != "baked_in":
            if md < nd + tail:
                freeze = round((nd + tail) - md, 2)
                shots_needed = max(1, math.ceil((nd + tail) / CLIP_MAX_DUR))
        # PHASE 1/5: shots[] coverage
        shots = seg.get("shots")
        required_visual = round(nd + tail, 2) if (nd and mode != "baked_in") else None
        total_shot_dur = round(sum(s.get("duration", 0) for s in shots), 2) if shots else None
        coverage_pass = None
        if shots and required_visual:
            coverage_pass = total_shot_dur >= required_visual - 0.05
        # If shots exist, no freeze/loop expected (they cover narration)
        if shots:
            freeze = 0.0
            shots_needed = len(shots)
        entries.append({
            "segment_id": sid, "audio_mode": mode,
            "narration_duration": round(nd, 2) if nd else None,
            "tail_pad": tail,
            "required_visual_duration": required_visual,
            "media_duration": round(md, 2) if md else None,
            "effective_segment_duration": round(eff, 2) if eff else None,
            "has_shots": bool(shots),
            "total_planned_shot_duration": total_shot_dur,
            "coverage_pass": coverage_pass,
            "freeze_duration_if_single_clip": freeze,
            "freeze_risk": (freeze > MAX_FREEZE) if not shots else False,
            "loop_risk": False,
            "shots_needed": shots_needed,
        })
    out = output_dir / "duration_mismatch_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"project_id": script["project_id"], "max_freeze": MAX_FREEZE,
                   "clip_max_dur": CLIP_MAX_DUR, "segments": entries}, f, indent=2)
    for e in entries:
        if e["has_shots"]:
            cov = "✓" if e["coverage_pass"] else "✗ INSUFFICIENT"
            print(f"  [{e['segment_id']}] nar={e['narration_duration']} need={e['required_visual_duration']} "
                  f"shots={e['shots_needed']} cover={e['total_planned_shot_duration']}s {cov}")
        else:
            fr = f" FREEZE={e['freeze_duration_if_single_clip']}s" if e["freeze_risk"] else ""
            sh = f" shots_needed={e['shots_needed']}" if e["shots_needed"] > 1 else ""
            print(f"  [{e['segment_id']}] nar={e['narration_duration']} media={e['media_duration']}{fr}{sh}")
    print(f"  report: {out}")
    return entries


def risk_report(script, base):
    """PHASE 3/4: per-segment text-surface + close-human risk + model routing."""
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    entries = []
    for seg in script["segments"]:
        sid = seg["id"]
        mode = seg.get("audio_mode", "generated_tts")
        brief = seg.get("visual_brief", "")
        risk = classify_prompt_risk(brief)
        model = route_model(seg, mode)
        warnings = []
        if risk["text_surface_risk"] and mode != "baked_in":
            warnings.append("text_surface_risk:" + ",".join(risk["text_flags"]))
        if risk["close_human_risk"] and mode != "baked_in" and model != HUMAN_CLOSEUP_MODEL:
            warnings.append("close_human_requires_seedance")
        entries.append({
            "segment_id": sid, "audio_mode": mode, "model_routed": model,
            "text_surface_risk": risk["text_surface_risk"], "text_flags": risk["text_flags"],
            "close_human_risk": risk["close_human_risk"], "human_flags": risk["human_flags"],
            "warnings": warnings,
        })
    out = output_dir / "media_risk_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"project_id": script["project_id"], "segments": entries}, f, indent=2)
    for e in entries:
        w = f" ⚠ {'; '.join(e['warnings'])}" if e["warnings"] else " ✓"
        print(f"  [{e['segment_id']}] {e['audio_mode']} → {e['model_routed']}{w}")
    print(f"  report: {out}")
    return entries


def file_sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_lipsync_provenance(script, base):
    """PHASE 2: verify each baked_in (lipsync) clip's embedded audio matches the
    narration it was generated from, using media_generation_log.json provenance."""
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    log_path = output_dir / "media_generation_log.json"
    log = json.load(open(log_path)) if log_path.exists() else {"segments": {}}
    seglog = log.get("segments", {}) if isinstance(log, dict) else log
    if isinstance(seglog, list):
        seglog = {r.get("segment_id"): r for r in seglog if isinstance(r, dict)}
    fmt = script.get("defaults", {}).get("format", "mp3")
    issues = []
    for seg in script["segments"]:
        if seg.get("audio_mode") != "baked_in":
            continue
        sid = seg["id"]
        media = resolve(base, seg["media"])
        nar = output_dir / "narration" / f"{sid}.{fmt}"
        rec = seglog.get(sid)
        media_dur = probe_video(media)["duration"] if media.exists() else None
        nar_dur = None
        if nar.exists():
            r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","default=noprint_wrappers=1:nokey=1",str(nar)],capture_output=True,text=True)
            try: nar_dur = float(r.stdout.strip())
            except ValueError: pass
        if not rec:
            issues.append(f"{sid}: NO PROVENANCE — cannot verify lipsync audio source "
                          f"(media={round(media_dur,2) if media_dur else None}s, "
                          f"narration={round(nar_dur,2) if nar_dur else None}s)")
            continue
        cur_hash = file_sha256(nar) if nar.exists() else None
        if rec.get("audio_source_sha256") != cur_hash:
            issues.append(f"BLOCKED: {sid} lipsync media audio does not match current narration "
                          f"(generated from {rec.get('audio_source_sha256','?')[:12]}, "
                          f"current {cur_hash[:12] if cur_hash else 'missing'})")
    return issues


def record_lipsync_provenance(script, base, sid, audio_path, model, media_path):
    """PHASE 2: write provenance for a generated lipsync clip."""
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    log_path = output_dir / "media_generation_log.json"
    log = json.load(open(log_path)) if log_path.exists() else {"project_id": script["project_id"], "segments": {}}
    # normalise: older runs wrote segments as a list; convert to dict keyed by segment_id
    if isinstance(log.get("segments"), list):
        log["segments"] = {r["segment_id"]: r for r in log["segments"] if isinstance(r, dict)}
    import datetime
    info = probe_video(media_path) if Path(media_path).exists() else {}
    log["segments"][sid] = {
        "segment_id": sid,
        "media_path": str(media_path),
        "audio_source_path_used_for_generation": str(audio_path),
        "audio_source_sha256": file_sha256(audio_path) if Path(audio_path).exists() else None,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "duration": round(info.get("duration", 0), 2),
        "has_embedded_audio": info.get("has_audio"),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)


def record_shot_provenance(script, base, seg_id, shot_id, media_path, model):
    """PHASE 1: write provenance for a generated b-roll shot."""
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    log_path = output_dir / "shot_generation_log.json"
    log = json.load(open(log_path)) if log_path.exists() else {"project_id": script["project_id"], "shots": {}}
    import datetime
    info = probe_video(media_path) if Path(media_path).exists() else {}
    log.setdefault("shots", {})[shot_id] = {
        "segment_id": seg_id, "shot_id": shot_id, "media_path": str(media_path),
        "model": model, "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "duration": round(info.get("duration", 0), 2), "has_embedded_audio": info.get("has_audio"),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)


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
        # Enrich with shot plan + model routing + risk (PHASE 3/4/5)
        output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
        fmt = script.get("defaults", {}).get("format", "mp3")
        nar = output_dir / "narration" / f"{sid}.{fmt}"
        nd = None
        if nar.exists():
            r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","default=noprint_wrappers=1:nokey=1",str(nar)],capture_output=True,text=True)
            try: nd = float(r.stdout.strip())
            except ValueError: pass
        shots, needed = plan_shots(seg, nd, base) if nd else ([{"id": sid, "duration": None,
                         "media": seg["media"], "visual_brief": seg.get("visual_brief",""),
                         "model": route_model(seg, mode)}], None)
        risk = classify_prompt_risk(seg.get("visual_brief", ""))
        seg_warn = []
        if risk["text_surface_risk"] and mode != "baked_in":
            seg_warn.append("text_surface_risk")
        if risk["close_human_risk"] and mode != "baked_in":
            chosen = route_model(seg, mode)
            if chosen != HUMAN_CLOSEUP_MODEL:
                seg_warn.append("close_human_requires_seedance")
        if len(shots) > 1:
            warnings.append(f"{sid}: needs {len(shots)} shots to cover {round(needed,1)}s narration")
        plan[-1].update({
            "narration_duration": round(nd, 2) if nd else None,
            "coverage_needed": round(needed, 2) if needed else None,
            "shots": [{"id": s["id"], "duration": s.get("duration"),
                       "model": s.get("model") or s.get("_routed_model") or route_model(s, mode),
                       "media": s["media"]} for s in shots],
            "model_routed": route_model(seg, mode),
            "risk": seg_warn,
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
        # PHASE 8: expand into per-shot units if shots[] exists
        units = seg.get("shots") if seg.get("shots") else [seg]
        for unit in units:
            uid = unit.get("id", sid)
            media_path = resolve(base, unit["media"])
            ubrief = (unit.get("visual_brief", "") + " " + (unit.get("visual_prompt_override") or ""))
            risk = classify_prompt_risk(ubrief)
            if not media_path.exists():
                entries.append({"segment_id": sid, "shot_id": uid if uid != sid else None,
                                "media_path": str(media_path), "status": "missing",
                                "prompt": ubrief.strip()[:200],
                                "risk": risk["text_flags"] + risk["human_flags"]})
                continue
            info = probe_video(media_path)
            frames = []
            for pct in (0.2, 0.5, 0.8):
                t = info["duration"] * pct
                fp = review_dir / f"{uid}_{int(pct*100)}.jpg"
                subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.1f}", "-i", str(media_path),
                                "-frames:v", "1", "-q:v", "3", str(fp)], capture_output=True)
                if fp.exists():
                    frames.append(str(fp))
            warnings = []
            if risk["text_surface_risk"]:
                warnings.append("text_surface_risk:" + ",".join(risk["text_flags"]))
            if risk["close_human_risk"]:
                warnings.append("close_human:" + ",".join(risk["human_flags"]))
            entries.append({
                "segment_id": sid, "shot_id": uid if uid != sid else None,
                "media_path": str(media_path), "duration": round(info["duration"], 2),
                "resolution": f"{info['width']}x{info['height']}", "has_audio": info["has_audio"],
                "prompt": ubrief.strip()[:200], "frames": frames, "warnings": warnings,
            })
            wstr = f" ⚠ {', '.join(warnings)}" if warnings else " ✓"
            print(f"  [{uid}] {info['duration']:.1f}s {info['width']}x{info['height']}{wstr}")
    out = output_dir / "media_review.json"
    with open(out, "w") as f:
        json.dump({"project_id": script["project_id"], "units": entries}, f, indent=2)
    print(f"  review: {out}")
    return entries


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


LIBRARY_INDEX = ROOT / "assets" / "media" / "library_index.json"


def _load_library_index():
    if LIBRARY_INDEX.exists():
        try:
            return json.loads(LIBRARY_INDEX.read_text())
        except json.JSONDecodeError:
            return {"assets": {}}
    return {"assets": {}}


def _library_lookup(beat, index):
    """Reuse a QA-passed asset keyed by prompt_class if available (≤2× per video,
    enforced by caller). Returns a path string or None (§5.2 #3)."""
    if not beat.get("reuse", {}).get("allowed"):
        return None
    assets = index.get("assets", {})
    pc = beat.get("prompt_class")
    for aid, rec in assets.items():
        if rec.get("prompt_class") == pc and rec.get("qa_status") == "pass":
            p = rec.get("path")
            if p and (ROOT / p).exists():
                return p
    return None


def _still_kenburns(beat, out_path, dry_run=False):
    """Generate a still + slow ffmpeg pan-zoom for a still_kenburns beat.

    Uses an existing reference still if provided; otherwise falls back to a
    solid brand-palette frame so the pipeline never blocks on a missing still.
    Zero Higgsfield cost."""
    dur = max(2.0, float(beat.get("duration_target_sec", 5)))
    refs = beat.get("reference_images") or []
    src = None
    for r in refs:
        if (ROOT / r).exists():
            src = ROOT / r
            break
    if dry_run:
        return {"beat_id": beat["beat_id"], "asset_type": "generated_still",
                "model": "still_kenburns", "cost_usd": 0.0, "action": "kenburns(dry)"}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if src:
        # zoompan over the still
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", f"{dur}",
             "-vf", f"scale=1280:720,zoompan=z='min(zoom+0.0008,1.12)':d={int(dur*25)}:s=1280x720,format=yuv420p",
             "-r", "25", "-an", str(out_path)], capture_output=True)
    else:
        # solid ivory frame (placeholder still; real still comes from reference lib)
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0xF5F0E8:s=1280x720:d={dur}",
             "-r", "25", "-an", str(out_path)], capture_output=True)
    info = probe_video(out_path)
    return {"beat_id": beat["beat_id"], "media_path": str(out_path),
            "model": "still_kenburns", "duration": round(info["duration"], 2) if info else dur,
            "cost_usd": 0.0}


def _generate_beat_clip(beat, out_path, dry_run=False, audio_path=None):
    """Generate one beat's clip via Higgsfield from the MEDIA PLAN fields only.

    hero_lipsync → seedance --image --audio (narration slice); other generated
    beats → model from the plan with the plan's prompt. Retry once then fallback."""
    model = beat["model"]
    if model in BANNED_MODELS:
        raise RuntimeError(f"{beat['beat_id']}: banned model {model!r} in media plan")
    prompt = beat["positive_prompt"]
    negative = beat.get("negative_prompt", "")
    # The Higgsfield CLI has NO --negative-prompt param (kling3_0/seedance_2_0 accept
    # only prompt/duration/medias/mode/aspect_ratio/sound). Fold the negative
    # constraints into the positive prompt as an "Avoid:" clause, like the legacy path.
    if negative:
        prompt = f"{prompt} Avoid: {negative}"
    # For lipsync beats, duration comes from the padded audio slice (integer seconds),
    # clamped to [SEEDANCE_MIN_DURATION_SEC, LIPSYNC_MAX_DUR] (API hard limits).
    sl = beat.get("audio_slice") or {}
    if beat.get("lipsync_required") and sl.get("padded_len_sec"):
        duration = int(sl["padded_len_sec"])
        if beat.get("shot_type") == "hero_lipsync":
            duration = max(duration, SEEDANCE_MIN_DURATION_SEC)
            duration = min(duration, LIPSYNC_MAX_DUR)   # Seedance rejects > 10s
    else:
        duration = max(1, int(round(beat.get("duration_target_sec", 5))))
    refs = beat.get("reference_images") or []
    ref_image = refs[0] if refs else None
    lipsync = beat.get("lipsync_required") and beat.get("shot_type") == "hero_lipsync"

    if dry_run:
        return {"beat_id": beat["beat_id"], "model": model,
                "cost_usd": beat.get("cost", {}).get("est_usd", 0.0),
                "duration": duration, "ref": ref_image, "lipsync": bool(lipsync),
                "action": "generate"}

    cmd = ["node", str(HF_BIN), "generate", "create", model, "--prompt", prompt]
    cmd += ["--duration", str(duration)]

    if ref_image and (ROOT / ref_image).exists():
        r = subprocess.run(["node", str(HF_BIN), "upload", "create", str(ROOT / ref_image), "--json"],
                           capture_output=True, text=True)
        try:
            uid = json.loads(r.stdout).get("id")
            if uid:
                cmd += ["--image", uid]
        except json.JSONDecodeError:
            pass
    elif lipsync:
        raise RuntimeError(f"{beat['beat_id']}: hero_lipsync requires a reference image")

    # T1 (LIPSYNC_TICKETS): hero_lipsync MUST have audio_path — no degradation.
    if lipsync:
        if not audio_path or not Path(audio_path).exists():
            raise RuntimeError(
                f"{beat['beat_id']}: hero_lipsync requires a narration audio slice "
                f"(audio_path={audio_path!r}). Compile with audio_timing wired (T3).")
        # Trim the slice to the render duration when the audio is longer than the
        # requested clip (e.g. 16s speech → 10s clamped render). Seedance rejects
        # lipsync jobs where audio duration > video duration.
        import subprocess as _sp
        audio_for_api = audio_path
        audio_dur = float(_sp.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True).stdout.strip() or "0")
        if audio_dur > duration + 0.1:
            trimmed = out_path.parent / f"_slice_trim_{out_path.stem}.mp3"
            _sp.run(["ffmpeg", "-y", "-i", str(audio_path),
                     "-t", str(duration), "-c", "copy", str(trimmed)],
                    capture_output=True, check=True)
            audio_for_api = trimmed
        cmd += ["--audio", str(audio_for_api)]

    cmd += ["--wait", "--wait-timeout", WAIT_TIMEOUT, "--wait-interval", WAIT_INTERVAL, "--json"]
    result = hf_cmd(cmd[2:])
    if isinstance(result, list):
        result = result[0] if result else {}
    url = (result.get("result_url") or result.get("output_url")
           or next(iter(result.get("outputs") or result.get("output_urls") or []), None))
    if not url:
        raise RuntimeError(f"{beat['beat_id']}: no result_url: {json.dumps(result)[:200]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request
    raw = out_path.parent / f".raw_{out_path.name}"
    urllib.request.urlretrieve(url, str(raw))
    # Keep embedded audio only for a TRUE lipsync render; otherwise strip.
    if not lipsync:
        subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-an", "-c:v", "copy", str(out_path)],
                       capture_output=True)
        raw.unlink(missing_ok=True)
    else:
        import shutil
        shutil.move(str(raw), str(out_path))
    info = probe_video(out_path)
    return {"beat_id": beat["beat_id"], "media_path": str(out_path), "model": model,
            "duration": round(info["duration"], 2) if info else duration,
            "cost_usd": beat.get("cost", {}).get("est_usd", 0.0),
            "lipsync": bool(lipsync)}


def run_from_media_plan(plan_path, dry_run=False, force=False, force_unsafe=False, selected=None):
    """PRIMARY generation path (blueprint §10 #2): media_plan.json is the ONLY
    prompt source. Generates per-beat, with hero lipsync, still_kenburns, reuse
    lookup, provenance, and a dry-run report. Local-graphic beats are skipped
    here (rendered by graphics.py / T10)."""
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text())
    project_id = plan["project_id"]
    project_dir = ROOT / "Videos" / "Projects" / project_id
    # Fallback base only used if a beat lacks an explicit output_path. The media
    # plan's per-beat output_path is the single source of truth (QA, assembly, and
    # reuse all read output_path), so generation MUST write there too.
    out_base = ROOT / "assets" / "media" / project_id / "shots"

    def _beat_out_path(beat):
        """Resolve a beat's clip path from its output_path (ROOT-relative),
        falling back to the shots/ convention only if output_path is absent."""
        op = beat.get("output_path")
        if op:
            p = Path(op)
            return p if p.is_absolute() else (ROOT / p)
        return out_base / f"{beat['beat_id']}.mp4"

    # HARD SPEND GATE before any Higgsfield call (§10 #1).
    if not dry_run and not force_unsafe:
        require_gates(project_id, SPEND_GATES)
    elif not dry_run and force_unsafe:
        sys.stderr.write(f"\033[31m⚠ FORCE-UNSAFE: bypassing spend gates for {project_id}.\033[0m\n")

    if not dry_run:
        available, msg = check_hf_available()
        if not available:
            raise RuntimeError(f"BLOCKED: {msg}")

    index = _load_library_index()
    reuse_counts = {}
    report_beats = []
    total_cost = 0.0
    generated = reused = local_skipped = 0

    LOCAL = {"graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"}

    for beat in plan["beats"]:
        bid = beat["beat_id"]
        shot_type = beat["shot_type"]
        out_path = _beat_out_path(beat)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Honour --segment / --segments filter (beat_id or render_group).
        if selected and bid not in selected and (beat.get("render_group") or "") not in selected:
            report_beats.append({"beat_id": bid, "shot_type": shot_type, "model": beat.get("model",""),
                                 "clips": 0, "cost_usd": 0.0, "reuse": False, "action": "skipped_not_selected"})
            continue

        # Local graphics are not Higgsfield work — handled by graphics.py (T10).
        if shot_type in LOCAL or beat["model"] == "local_graphic":
            report_beats.append({"beat_id": bid, "shot_type": shot_type, "model": "local_graphic",
                                 "clips": 0, "cost_usd": 0.0, "reuse": False, "action": "local_graphic"})
            local_skipped += 1
            continue

        # T4: merged follower beats — rendered as part of the group leader's clip.
        if beat.get("render_group") and beat.get("render_group_index", 0) > 0:
            report_beats.append({"beat_id": bid, "shot_type": shot_type, "model": beat["model"],
                                 "clips": 0, "cost_usd": 0.0, "reuse": False,
                                 "render_group": beat["render_group"],
                                 "action": "merged_follower"})
            continue

        # Reuse lookup (≤2× per video).
        reused_path = _library_lookup(beat, index)
        if reused_path and reuse_counts.get(reused_path, 0) < 2:
            reuse_counts[reused_path] = reuse_counts.get(reused_path, 0) + 1
            report_beats.append({"beat_id": bid, "shot_type": shot_type, "model": beat["model"],
                                 "clips": 0, "cost_usd": 0.0, "reuse": True,
                                 "reused_asset": reused_path, "action": "reuse"})
            reused += 1
            continue

        # Existing on-disk clip (skip unless --force).
        if out_path.exists() and not force and not dry_run:
            report_beats.append({"beat_id": bid, "shot_type": shot_type, "model": beat["model"],
                                 "clips": 1, "cost_usd": 0.0, "reuse": True, "action": "exists"})
            reused += 1
            continue

        cost = beat.get("cost", {}).get("est_usd", 0.0)
        total_cost += cost
        report_beats.append({"beat_id": bid, "shot_type": shot_type, "model": beat["model"],
                             "clips": beat.get("cost", {}).get("est_clips", 1),
                             "cost_usd": cost, "reuse": False,
                             "ref": (beat.get("reference_images") or [None])[0],
                             "lipsync": bool(beat.get("lipsync_required")),
                             "action": "generate"})

        if dry_run:
            generated += 1
            continue

        # Resolve narration audio slice for lipsync beats.
        audio_path = None
        if beat.get("lipsync_required"):
            sl = beat.get("audio_slice")
            if sl and sl.get("file"):
                # Slice path is relative to project_dir.
                src = project_dir / sl["file"]
                if src.exists():
                    audio_path = src
                else:
                    raise RuntimeError(
                        f"{bid}: audio_slice references {sl['file']} but file missing at {src}. "
                        "Re-compile the media plan.")
            else:
                # T1: hard-fail, no degradation. Compile must populate audio_slice.
                raise RuntimeError(
                    f"{bid}: hero_lipsync beat has no audio_slice in the media plan. "
                    "Re-compile with scripts/compile_media_prompts.py (T3 wires audio_timing).")

        # Generate with retry-once-then-fallback (§2 S6 / G8).
        try:
            if shot_type == "still_kenburns" or beat.get("model") == "still_kenburns":
                res = _still_kenburns(beat, out_path)
            else:
                try:
                    res = _generate_beat_clip(beat, out_path, audio_path=audio_path)
                except RuntimeError as e:
                    print(f"  [{bid}] generation failed ({e}); retrying once…", file=sys.stderr)
                    time.sleep(30)
                    try:
                        res = _generate_beat_clip(beat, out_path, audio_path=audio_path)
                    except RuntimeError:
                        fb = beat.get("fallback", {}).get("on_generation_fail", "still_kenburns")
                        print(f"  [{bid}] retry failed; falling back to {fb}", file=sys.stderr)
                        res = _still_kenburns(beat, out_path)
            _record_beat_provenance(project_dir, beat, res, audio_path)
            generated += 1
            print(f"  [{bid}] {shot_type} → {res.get('model')} (${cost:.2f})")
        except RuntimeError as e:
            print(f"  [{bid}] FATAL: {e}", file=sys.stderr)
            raise

    summary = {
        "project_id": project_id, "media_plan": str(plan_path),
        "generated_at": datetime_now(),
        "beats_total": len(plan["beats"]),
        "beats_generated": generated, "beats_reused": reused,
        "beats_local_graphic": local_skipped,
        "est_spend_usd": round(total_cost, 2),
        "beats": report_beats,
    }

    if dry_run:
        report_path = project_dir / "dryrun_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, indent=2))
        print(f"DRY RUN: {generated} beats to generate, {reused} reused, "
              f"{local_skipped} local — est ${round(total_cost,2)} (ZERO API calls)")
        print(f"  report: {report_path}")
    else:
        print(f"\n  generated {generated}, reused {reused}, local {local_skipped} — "
              f"spent ~${round(total_cost,2)}")
    return summary


def datetime_now():
    import datetime as _dt
    return _dt.datetime.now().isoformat(timespec="seconds")


def _record_beat_provenance(project_dir, beat, res, audio_path):
    log_path = project_dir / "media_generation_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"beats": {}}
    log.setdefault("beats", {})
    entry = {
        "beat_id": beat["beat_id"], "shot_type": beat["shot_type"],
        "model": res.get("model"), "media_path": res.get("media_path"),
        "duration": res.get("duration"), "generated_at": datetime_now(),
        "lipsync": bool(beat.get("lipsync_required")),
    }
    if audio_path and Path(audio_path).exists():
        entry["audio_source_sha256"] = file_sha256(audio_path)
        entry["audio_source_path"] = str(audio_path)
    log["beats"][beat["beat_id"]] = entry
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2))


def run(script_path, dry_run=False, force=False, validate_only=False,
        do_assemble=False, selected_segments=None, allow_text_surfaces=False,
        force_unsafe=False):
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

    # HARD SPEND GATE (blueprint §10 rule 1): no Higgsfield call without the full
    # gate chain. Skipped for dry-run / validate-only (no spend) and for an
    # explicit, logged --force-unsafe emergency override.
    if not dry_run and not force_unsafe:
        require_gates(script["project_id"], SPEND_GATES)
    elif not dry_run and force_unsafe:
        sys.stderr.write(
            "\033[31m⚠ FORCE-UNSAFE: bypassing spend gates "
            f"({', '.join(SPEND_GATES)}) for {script['project_id']}. "
            "This spends real credits without approval.\033[0m\n")

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
        mode = seg.get("audio_mode", "generated_tts")

        # Compute narration duration + coverage requirement for generated_tts
        output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
        fmt = script.get("defaults", {}).get("format", "mp3")
        nar = output_dir / "narration" / f"{seg_id}.{fmt}"
        nar_dur = None
        if nar.exists():
            rp = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                 "-of","default=noprint_wrappers=1:nokey=1",str(nar)],capture_output=True,text=True)
            try: nar_dur = float(rp.stdout.strip())
            except ValueError: pass
        required_visual = (nar_dur + 0.25) if nar_dur else None

        # --- Per-shot generation path (PHASE 1/3/4) ---
        shots = seg.get("shots")
        if shots and mode != "baked_in":
            # Coverage validation BEFORE spending credits (PHASE 3)
            total_dur = sum(s.get("duration", 0) for s in shots)
            if required_visual and total_dur < required_visual - 0.05:
                raise RuntimeError(
                    f"{seg_id}: BLOCKED — planned shots cover {total_dur:.1f}s but narration needs "
                    f"{required_visual:.1f}s. Add shots or increase durations.")
            print(f"  [{seg_id}] {len(shots)} shots, coverage {total_dur:.1f}s / need "
                  f"{required_visual:.1f}s" if required_visual else f"  [{seg_id}] {len(shots)} shots")
            for sh in shots:
                shot_id = sh["id"]
                shot_media = resolve(base, sh["media"])
                shot_model = model or route_model(sh, mode)
                # PHASE 3: block text-surface shots
                if not allow_text_surfaces:
                    srisk = classify_prompt_risk(sh.get("visual_brief", "") or sh.get("visual_prompt_override", ""))
                    if srisk["text_surface_risk"]:
                        raise RuntimeError(
                            f"{shot_id}: BLOCKED — shot brief requests text-bearing surfaces "
                            f"({', '.join(srisk['text_flags'])}). Rewrite or pass --allow-text-surfaces.")
                    # Block banned models even if explicitly set on a shot
                    if shot_model in BANNED_MODELS:
                        raise RuntimeError(
                            f"{shot_id}: BLOCKED — model {shot_model!r} is not allowed. "
                            f"Use seedance_2_0_fast or seedance_2_0.")
                    # PHASE 4: block close-human shot if model doesn't meet the bar
                    if srisk["close_human_risk"] and shot_model == DEFAULT_BROLL_MODEL \
                            and DEFAULT_BROLL_MODEL != HUMAN_CLOSEUP_MODEL:
                        raise RuntimeError(
                            f"{shot_id}: BLOCKED — close-human shot ({','.join(srisk['human_flags'])}) "
                            f"requires {HUMAN_CLOSEUP_MODEL}.")
                if shot_media.exists() and not force:
                    info = probe_video(shot_media)
                    if info:
                        print(f"    [{shot_id}] reused ({info['duration']:.1f}s)")
                        skipped += 1
                        continue
                try:
                    result = generate_segment(seg, shot_media, shot_model, dry_run=dry_run,
                                              audio_mode=mode, spec=sh, duration=sh.get("duration"))
                    if result:
                        results.append(result)
                        generated += 1
                        review_dir = output_dir / "review_frames"
                        review_dir.mkdir(parents=True, exist_ok=True)
                        extract_review_frame(shot_media, review_dir)
                        # per-shot provenance
                        record_shot_provenance(script, base, seg_id, shot_id, shot_media, shot_model)
                except RuntimeError as e:
                    print(f"  [{shot_id}] FAILED: {e}", file=sys.stderr)
                    raise
            continue  # done with this segment's shots

        # --- Segment-level path (backward compatible, no shots[]) ---
        # Model selection: explicit segment model > shot_router > route_model fallback
        seg_shot_type = seg.get("shot_type")
        explicit_model = seg.get("model")
        if explicit_model and explicit_model not in BANNED_MODELS:
            seg_model = explicit_model
        elif seg_shot_type and not model:
            try:
                import sys as _sys
                _sys.path.insert(0, str(ROOT / "scripts"))
                from shot_router import ShotRouter
                _router = ShotRouter()
                seg_model, _, _ = _router.resolve(seg_shot_type, allow_alternate=True)
            except Exception:
                seg_model = route_model(seg, mode)
        else:
            seg_model = model or route_model(seg, mode)

        # Lipsync audio: for baked_in, pass narration mp3 to Higgsfield
        nar_audio = None
        if mode == "baked_in":
            fmt = script.get("defaults", {}).get("format", "mp3")
            nar_path = output_dir / "narration" / f"{seg_id}.{fmt}"
            if nar_path.exists():
                nar_audio = nar_path
            else:
                raise RuntimeError(
                    f"BLOCKED: {seg_id} is baked_in lipsync but narration not found: {nar_path}. "
                    f"Run tts.py first.")

        # PHASE 3: block text-surface b-roll prompts unless explicitly allowed
        if mode != "baked_in" and not allow_text_surfaces:
            risk = classify_prompt_risk(seg.get("visual_brief", ""))
            if risk["text_surface_risk"]:
                raise RuntimeError(
                    f"{seg_id}: BLOCKED — visual brief requests text-bearing surfaces "
                    f"({', '.join(risk['text_flags'])}). Rewrite the brief to a text-free concept "
                    f"or pass --allow-text-surfaces. (AI renders these as gibberish text.)")

        if media_path.exists() and not force:
            info = probe_video(media_path)
            if info:
                print(f"  [{seg_id}] reused ({info['width']}x{info['height']}, {info['duration']:.1f}s)")
                skipped += 1
                continue

        try:
            # --- Baked_in lipsync: chunk long narration into ≤LIPSYNC_MAX_DUR clips ---
            if mode == "baked_in" and nar_audio:
                nar_dur = audio_duration(nar_audio)
                if nar_dur > LIPSYNC_MAX_DUR:
                    tmp_dir = media_path.parent / f"_chunks_{seg_id}"
                    print(f"  [{seg_id}] narration {nar_dur:.1f}s > {LIPSYNC_MAX_DUR}s — splitting into chunks")
                    chunks = split_audio(nar_audio, LIPSYNC_MAX_DUR, tmp_dir)
                    print(f"  [{seg_id}] {len(chunks)} chunk(s)")
                    chunk_videos: list[Path] = []
                    for ci, chunk_path in enumerate(chunks):
                        chunk_video = tmp_dir / f"video_{ci:03d}.mp4"
                        chunk_dur = audio_duration(chunk_path)
                        clip_dur = 10 if chunk_dur > 5 else 5
                        print(f"    chunk {ci+1}/{len(chunks)} ({chunk_dur:.1f}s) → duration={clip_dur}s")
                        for attempt in range(3):
                            try:
                                result = generate_segment(seg, chunk_video, seg_model,
                                                          dry_run=dry_run, audio_mode=mode,
                                                          audio_path=chunk_path, duration=clip_dur)
                                break
                            except RuntimeError as e:
                                if attempt < 2 and "no result_url" in str(e):
                                    print(f"    chunk {ci+1} retry {attempt+1}/2 in 60s…")
                                    time.sleep(60)
                                else:
                                    raise
                        if not dry_run:
                            chunk_videos.append(chunk_video)
                    if not dry_run and chunk_videos:
                        print(f"  [{seg_id}] concatenating {len(chunk_videos)} clips…")
                        concat_videos(chunk_videos, media_path)
                        # clean tmp dir
                        for f in tmp_dir.iterdir(): f.unlink(missing_ok=True)
                        tmp_dir.rmdir()
                        result = {"segment_id": seg_id}
                else:
                    clip_dur = 10 if nar_dur > 5 else 5
                    for attempt in range(3):
                        try:
                            result = generate_segment(seg, media_path, seg_model, dry_run=dry_run,
                                                      audio_mode=mode, audio_path=nar_audio,
                                                      duration=clip_dur)
                            break
                        except RuntimeError as e:
                            if attempt < 2 and "no result_url" in str(e):
                                print(f"  [{seg_id}] retry {attempt+1}/2 in 60s…")
                                time.sleep(60)
                            else:
                                raise
            else:
                # Non-lipsync segment: original retry logic
                max_retries = 3
                result = None
                for attempt in range(max_retries):
                    try:
                        result = generate_segment(seg, media_path, seg_model, dry_run=dry_run,
                                                  audio_mode=mode, audio_path=nar_audio)
                        break
                    except RuntimeError as e:
                        if attempt < max_retries - 1 and ("no result_url" in str(e) or "nsfw" in str(e).lower()):
                            wait = 60 * (attempt + 1)
                            print(f"  [{seg_id}] retry {attempt+1}/{max_retries-1} in {wait}s (rate-limit suspected)...")
                            time.sleep(wait)
                        else:
                            raise
            if result:
                results.append(result)
                generated += 1
                output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
                review_dir = output_dir / "review_frames"
                review_dir.mkdir(parents=True, exist_ok=True)
                frame = extract_review_frame(media_path, review_dir)
                if frame:
                    print(f"    frame: {frame}")
                # PHASE 2: record provenance for lipsync clips (audio hash for sync validation)
                if mode == "baked_in" and not dry_run:
                    fmt = script.get("defaults", {}).get("format", "mp3")
                    nar = output_dir / "narration" / f"{seg_id}.{fmt}"
                    if nar.exists():
                        record_lipsync_provenance(script, base, seg_id, nar, seg_model, media_path)
                        print(f"    provenance recorded (audio hash)")
            # Throttle between segments to avoid rate-limit triggers (seedance_2_0 needs ~60s)
            if not dry_run and generated > 0:
                time.sleep(60)
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
            matched = [r for r in results if r.get("segment_id") == seg["id"]]
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
    ap = argparse.ArgumentParser(description="Generate video clips from a media plan (or legacy script) via Higgsfield.")
    ap.add_argument("input", help="Path to media_plan.json (preferred) or legacy script JSON")
    ap.add_argument("--validate-only", action="store_true", help="Check schema and existing media")
    ap.add_argument("--dry-run", action="store_true", help="Print prompts/paths, no API calls")
    ap.add_argument("--force", action="store_true", help="Regenerate all media (overwrite existing)")
    ap.add_argument("--segment", action="append", dest="segments", metavar="SEG_ID",
                    help="Regenerate only this segment (repeat for multiple)")
    ap.add_argument("--segments", dest="segments_csv", default=None,
                    help="Comma-separated segment IDs to regenerate")
    ap.add_argument("--storyboard-only", action="store_true", help="Output storyboard plan, no generation")
    ap.add_argument("--duration-report", action="store_true", help="Output duration_mismatch_report.json")
    ap.add_argument("--risk-report", action="store_true", help="Output media_risk_report.json")
    ap.add_argument("--allow-text-surfaces", action="store_true", help="Permit text-surface b-roll prompts")
    ap.add_argument("--avoid-human-closeups", action="store_true", default=True,
                    help="Route/flag close-human shots (default on)")
    ap.add_argument("--review", action="store_true", help="Generate review frames + media_review.json")
    ap.add_argument("--assemble", action="store_true", help="Run tts.py --assemble after generation")
    ap.add_argument("--force-unsafe", action="store_true",
                    help="EMERGENCY: bypass the spend gate chain (logged, spends real credits)")
    ap.add_argument("--model", default=None, help="Override video model")
    args = ap.parse_args()

    selected = set(args.segments) if args.segments else set()
    if args.segments_csv:
        selected |= {s.strip() for s in args.segments_csv.split(",")}
    selected = selected or None

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    doc = json.load(open(input_path))

    # PRIMARY PATH (blueprint §10 #2): media_plan.json is the sole prompt source.
    is_media_plan = isinstance(doc, dict) and "beats" in doc and \
        str(doc.get("schema_version", "")).startswith("media_plan")
    if is_media_plan:
        try:
            run_from_media_plan(input_path, dry_run=args.dry_run, force=args.force,
                                force_unsafe=args.force_unsafe, selected=selected)
        except (ValueError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # LEGACY script path (visual_brief). Hard-deprecated as a generation source.
    script = doc
    script_path = input_path
    base = script_path.parent

    try:
        if args.duration_report:
            duration_report(script, base)
            return
        if args.risk_report:
            risk_report(script, base)
            return

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

        # Reporting / validation on the legacy script is allowed (no spend).
        # Actual generation from a raw script visual_brief is FORBIDDEN
        # (constraints.json automatic_fail: media_prompt_from_raw_visual_brief_after_m5_m8).
        if not (args.validate_only or args.dry_run) and not args.force_unsafe:
            print("ERROR: generating from a raw script visual_brief is deprecated and forbidden.\n"
                  "  Route it first:  storyboard.py → review_storyboard.py → compile_media_prompts.py\n"
                  "  then run generate_media.py on the resulting media_plan.json.\n"
                  "  (Emergency override: --force-unsafe, logged.)", file=sys.stderr)
            sys.exit(1)
        if args.force_unsafe and not (args.validate_only or args.dry_run):
            sys.stderr.write("\033[31m⚠ FORCE-UNSAFE: generating from raw script visual_brief "
                             "(deprecated path).\033[0m\n")

        run(args.input, dry_run=args.dry_run, force=args.force,
            validate_only=args.validate_only, do_assemble=args.assemble,
            selected_segments=selected, allow_text_surfaces=args.allow_text_surfaces,
            force_unsafe=args.force_unsafe)
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
