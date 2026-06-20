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
import hashlib
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path

# LB-501 & LB-502: Policy validation and B-roll cutaway integration
try:
    from ffmpeg_validator import validate_hero_ffmpeg_command
    from broll_cutaway import assemble_hero_with_broll_cutaways, validate_cutaway_policy
    from assembly_dto import HeroAssemblyDTO, AssemblyDTOValidationError
except ImportError:
    # Fallback if modules are not available (e.g., during certain test setups)
    validate_hero_ffmpeg_command = None
    assemble_hero_with_broll_cutaways = None
    validate_cutaway_policy = None
    HeroAssemblyDTO = None
    AssemblyDTOValidationError = ValueError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrative_speed import measure as measure_pace
from generate_music import generate as gen_music, write_wav
from gates import require_gates  # noqa: E402
import clip_db  # noqa: E402


def run(cmd, label=""):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = r.stderr[-2000:] if r.stderr else ""
        raise RuntimeError(f"ffmpeg failed ({label}): {err}")
    return r


TAIL_PAD = 0.25
MAX_FREEZE = 0.5
LIPSYNC_TIMING_TOL = 0.25


def file_sha256(path):
    """SHA-256 of a file's bytes (None if missing)."""
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def audio_stream_sha256(path):
    """SHA-256 of a media file's decoded-then-reencoded *audio* payload only.

    We hash the extracted audio (copied, container-stripped) so the check is
    stable across video re-encodes. Returns None if the file has no audio.
    """
    p = Path(path)
    if not p.exists():
        return None
    # Probe for an audio stream first
    ra = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True)
    if "audio" not in ra.stdout:
        return None
    # Extract raw PCM and hash it (re-encode-stable representation of the audio)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p),
         "-vn", "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return hashlib.sha256(r.stdout).hexdigest()


def validate_lipsync_provenance(seg, base):
    """Re-verify a hero_lipsync segment's baked-audio provenance against the
    media plan's recorded slice hashes. Returns a list of problem strings
    (empty == clean). Assembly MUST fail if this returns problems.

    The media plan records, per hero beat/render-group:
      audio_slice.slice_sha256       — sha256 of narration/slices/{beat}.mp3 bytes
      audio_slice.parent_mp3_sha256  — sha256 of the parent segment narration mp3
    We re-hash the live slice file and parent file and compare.
    """
    prov = seg.get("lipsync_provenance")
    if not prov:
        # Old manifests without provenance: warn but don't block
        import sys
        print(f"WARNING: hero_lipsync segment {seg.get('id','?')!r} has no "
              f"lipsync_provenance — skipping provenance check.", file=sys.stderr)
        return []
    problems = []
    slice_file = resolve(base, prov.get("slice_file") or prov.get("file") or prov.get("path"))
    expected_slice = prov.get("slice_sha256") or prov.get("sha256")
    if expected_slice:
        if not slice_file or not slice_file.exists():
            problems.append(
                f"hero_lipsync segment {seg.get('id','?')!r}: slice file missing "
                f"({prov.get('slice_file') or prov.get('file')}) — provenance unverifiable.")
        else:
            live = file_sha256(slice_file)
            if live != expected_slice:
                raise RuntimeError(
                    f"Lipsync provenance BLOCKED: segment {seg.get('id','?')!r} slice hash mismatch "
                    f"(expected {expected_slice[:12]}, live {live[:12] if live else 'missing'}). "
                    f"Audio slice was modified after generation.")
    parent_file = resolve(base, prov.get("parent_mp3"))
    expected_parent = prov.get("parent_mp3_sha256") or prov.get("master_sha256")
    if expected_parent and parent_file is not None:
        if parent_file.exists():
            livep = file_sha256(parent_file)
            if livep != expected_parent:
                raise RuntimeError(
                    f"Lipsync provenance BLOCKED: segment {seg.get('id','?')!r} parent narration hash "
                    f"mismatch (expected {expected_parent[:12]}, live "
                    f"{livep[:12] if livep else 'missing'}). Master narration changed.")
    return problems


def probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def resolve(base, p):
    """Resolve a path relative to manifest directory, falling back to repo ROOT."""
    if p is None:
        return None
    path = Path(p)
    if path.is_absolute():
        return path
    local = (base / path).resolve()
    if local.exists():
        return local
    root_rel = (ROOT / path).resolve()
    if root_rel.exists():
        return root_rel
    return local  # return intended path even if missing (caller checks exists())


def validate_manifest(manifest, base):
    """Validate manifest structure and file existence. Returns list of error strings."""
    errors = []

    if not isinstance(manifest, dict):
        return ["Manifest must be a JSON object"]

    if "id" not in manifest or not manifest["id"]:
        errors.append("Missing required field: 'id'")

    # In continuous_voiceover mode, narration is ONE master track; per-segment audio is
    # not required and silent graphic/image segments legitimately have words=0.
    is_continuous = manifest.get("narration_mode") == "continuous_voiceover"

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
        is_lipsync = _is_hero_lipsync(seg)
        if "media" not in seg:
            errors.append(f"{prefix}: missing 'media'")
        else:
            media = resolve(base, seg["media"])
            if not media.exists():
                errors.append(f"{prefix}.media: file not found: {media}")

        if is_lipsync:
            # hero_lipsync spans carry their own baked audio; 'words'/'audio' are
            # not required. speech_len_sec is needed to trim to true speech length.
            if "speech_len_sec" not in seg:
                errors.append(f"{prefix}: audio_policy=hero_lipsync requires 'speech_len_sec'")
            elif not isinstance(seg["speech_len_sec"], (int, float)) or seg["speech_len_sec"] <= 0:
                errors.append(f"{prefix}.speech_len_sec: must be > 0, got {seg['speech_len_sec']}")
            if "lipsync_provenance" not in seg:
                errors.append(f"{prefix}: audio_policy=hero_lipsync requires 'lipsync_provenance' "
                              f"(slice_sha256/parent_mp3_sha256 from the media plan)")
            continue

        if "words" not in seg:
            errors.append(f"{prefix}: missing 'words'")
        elif not isinstance(seg["words"], int) or seg["words"] < 0:
            errors.append(f"{prefix}.words: must be a non-negative integer, got {seg['words']}")
        elif seg["words"] == 0 and not is_continuous:
            # Segment-TTS mode: every segment must carry its own narration words.
            # Continuous mode: silent graphic/image segments legitimately have 0 words.
            errors.append(f"{prefix}.words: must be a positive integer, got 0")

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

        # TKT-11: Validate required overlays
        overlay = seg.get("overlay")
        if overlay and overlay.get("required"):
            beat_id = seg.get("beat_id") or seg.get("id", f"seg_{i}")
            overlay_path = base / "assets" / "overlays" / f"{beat_id}_overlay.png"
            if not overlay_path.exists():
                errors.append(
                    f"{prefix}.overlay: required overlay PNG not found: {overlay_path}")

        # Whether a segment needs its OWN audio is determined by the authoritative
        # audio_policy from the DB/plan — NOT re-inferred from the media file extension.
        #   hero_lipsync → handled above (baked audio)
        #   strip / post_overlay (continuous mode) → silent visual under master narration; no per-seg audio
        #   segment_tts (non-continuous) → an image segment needs its own audio
        is_image = seg.get("media", "").lower().split(".")[-1] in ("png", "jpg", "jpeg", "webp")
        policy = seg.get("audio_policy", "strip")
        silent_under_master = is_continuous and policy in ("BROLL_FLEX", "strip", "post_overlay")
        if is_image and not audio and not silent_under_master:
            errors.append(f"{prefix}: image media requires 'audio' field "
                          f"(audio_policy={policy!r}, continuous={is_continuous})")

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

def compute_speeds(segments, pacing, base, narration_mode=None):
    """Measure WPS per segment and compute alignment speeds."""
    if narration_mode == "continuous_voiceover":
        # The master narration has one fixed pace and the visual clips are snapped
        # to authoritative timeline windows. Per-segment media may be silent stills.
        return [1.0] * len(segments), [None] * len(segments), None

    ref_idx = pacing.get("reference", 0)
    baseline = pacing.get("baseline_speed", 1.0)

    wps_list = []
    for seg in segments:
        # hero_lipsync spans run at native speed (lipsync timing is sacred); skip
        # WPS measurement (they may have no 'words'/'audio'). Use a sentinel WPS.
        if _is_hero_lipsync(seg):
            wps_list.append(None)
            continue
        # Measure narration audio for WPS — use separate audio if provided (generated_tts),
        # fall back to media file (baked_in lipsync clips where audio IS the narration).
        audio_file = resolve(base, seg.get("audio"))
        probe_target = audio_file if (audio_file and audio_file.exists()) else resolve(base, seg["media"])
        words = seg["words"]
        pace = measure_pace(probe_target, words)
        wps_list.append(pace.wps)

    # Reference must be a non-lipsync segment with a real WPS.
    if wps_list[ref_idx] is None:
        ref_idx = next((i for i, x in enumerate(wps_list) if x is not None), ref_idx)
    ref_wps = wps_list[ref_idx] if ref_idx < len(wps_list) and wps_list[ref_idx] is not None else None
    # All-lipsync or all-None: everything runs at 1.0 (continuous mode snaps to timing map)
    if ref_wps is None:
        return [1.0] * len(segments), wps_list, 1.0
    # hero_lipsync segments get speed 1.0; others align to the reference WPS.
    speeds = [1.0 if w is None else baseline * ref_wps / w for w in wps_list]
    return speeds, wps_list, ref_wps


def _contract_segment_durations(segments):
    """Return authoritative per-clip durations, or None for legacy manifests."""
    durations = []
    for seg in segments:
        timing_in = seg.get("timing_in")
        timing_out = seg.get("timing_out")
        required = seg.get("duration_required")
        if timing_in is not None and timing_out is not None:
            duration = float(timing_out) - float(timing_in)
            if duration <= 0:
                raise ValueError(
                    f"Segment {seg.get('id', '?')} has non-positive timeline duration: {duration:.3f}s")
            if required is not None and abs(float(required) - duration) > 0.01:
                raise ValueError(
                    f"Segment {seg.get('id', '?')} duration contract mismatch: "
                    f"timing={duration:.3f}s vs duration_required={float(required):.3f}s")
            durations.append(duration)
        elif required is not None:
            duration = float(required)
            if duration <= 0:
                raise ValueError(
                    f"Segment {seg.get('id', '?')} has non-positive duration_required: {duration:.3f}s")
            durations.append(duration)
        else:
            return None
    return durations


def _segment_media_kind(seg, media):
    """Classify media from the authoritative asset_type, with legacy suffix fallback."""
    asset_type = seg.get("asset_type")
    if asset_type in ("local_graphic", "still_image", "generated_still"):
        return "still"
    if asset_type == "generated_video":
        return "video"

    suffix = media.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".webp"):
        return "still"
    if suffix in (".mp4", ".mov", ".mkv", ".webm"):
        return "video"
    raise ValueError(
        f"Segment {seg.get('id', '?')} has unsupported asset_type={asset_type!r} "
        f"and media suffix {suffix!r}")


def _composite_overlay(seg, clip, base, tmp, idx):
    """TKT-11: If segment has an overlay, composite the PNG over the clip."""
    overlay = seg.get("overlay")
    if not overlay:
        return clip
    beat_id = seg.get("beat_id") or seg.get("id", f"seg_{idx}")
    overlay_path = base / "assets" / "overlays" / f"{beat_id}_overlay.png"
    if not overlay_path.exists():
        if overlay.get("required"):
            raise RuntimeError(
                f"Required overlay missing for {beat_id}: {overlay_path}")
        return clip
    dst = tmp / f"seg_{idx}_overlay.mp4"
    dur = probe_dur(clip)
    fade_in = 0.4
    fade_out = 0.4
    show_end = max(dur - fade_out, fade_in)
    fc = (
        f"[1:v]format=rgba,"
        f"fade=t=in:st=0:d={fade_in}:alpha=1,"
        f"fade=t=out:st={show_end}:d={fade_out}:alpha=1[ov];"
        f"[0:v][ov]overlay=0:0:enable='between(t,0,{dur})'[v]"
    )
    run(["ffmpeg", "-y", "-i", str(clip), "-i", str(overlay_path),
         "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)],
        f"overlay_{idx}")
    return dst


_HERO_LIPSYNC_POLICIES = frozenset({"HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"})


def _is_hero_lipsync(seg):
    """A segment is hero-lipsync when its audio policy locks lip sync, or it is
    explicitly flagged. Recognizes both the DB-native policy (HERO_SYNC_LOCKED)
    and the legacy alias (keep_lipsync) used by manifests/fixtures."""
    policy = seg.get("audio_policy")
    if policy in _HERO_LIPSYNC_POLICIES:
        return True
    return bool(seg.get("lipsync_required"))


def process_segment(seg, speed, w, h, fps, grade, crf, tmp, base, idx, allow_looping=False):
    """Normalize one segment: scale/crop, speed, grade, optional lower-third.
    When narration is longer than the video, hold the last frame (premium 'linger')
    instead of looping — unless allow_looping=True."""
    
    # LB-001: Hero temporal-edit fail-closed guard
    is_hero_lipsync = _is_hero_lipsync(seg)
    if is_hero_lipsync:
        if abs(speed - 1.0) > 1e-3:
            raise ValueError(
                f"BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN\n"
                f"render_unit_id={seg.get('clip_id', 'unknown')}\n"
                f"operation=speed_change (speed={speed})\n"
                f"source=assemble.py:process_segment\n"
                f"reason: Hero lipsync clips must not be retimed.")
        if allow_looping:
            raise ValueError(
                f"BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN\n"
                f"render_unit_id={seg.get('clip_id', 'unknown')}\n"
                f"operation=looping\n"
                f"source=assemble.py:process_segment\n"
                f"reason: Hero lipsync clips must not be looped.")
        if seg.get("trim_end") and seg.get("speech_len_sec"):
            # Prevent arbitrary trim through active speech
            if seg["trim_end"] < seg["speech_len_sec"] - 0.1:
                raise ValueError(
                    f"BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN\n"
                    f"render_unit_id={seg.get('clip_id', 'unknown')}\n"
                    f"operation=trim_through_speech (trim_end={seg['trim_end']}, speech_len={seg['speech_len_sec']})\n"
                    f"source=assemble.py:process_segment\n"
                    f"reason: Hero lipsync clips must not be trimmed through active speech.")

    # LB-502: B-roll cutaway integration
    if validate_cutaway_policy and assemble_hero_with_broll_cutaways:
        broll_intervals = seg.get("broll_cover_intervals", [])
        broll_media = seg.get("broll_media")
        if broll_intervals and broll_media and is_hero_lipsync:
            # Create a minimal mock DTO for validation
            media_dur_ms = int(probe_dur(resolve(base, seg["media"])) * 1000) if resolve(base, seg["media"]) else 0
            mock_dto = type('MockDTO', (), {
                'audio_policy': seg.get("audio_policy"),
                'exact_timeline_placement': {'start_ms': 0, 'end_ms': media_dur_ms},
            })()
            validate_cutaway_policy(mock_dto, broll_intervals)
            
            broll_path = resolve(base, broll_media)
            if broll_path and broll_path.exists():
                assemble_hero_with_broll_cutaways(
                    hero_video_path=resolve(base, seg["media"]),
                    broll_video_path=broll_path,
                    cutaway_intervals=broll_intervals,
                    output_path=dst,
                    fps=fps
                )
                return dst

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

    # --- LB-202: Hero lipsync span: STRIP provider audio, use master spine ---
    # Hero lipsync clips are generated using the master narration. To prevent
    # audio artifacts, drift, or duplication, we MUST strip the provider's baked
    # audio (-an) and rely exclusively on the master narration spine in the final mix.
    if _is_hero_lipsync(seg):
        speech_len = seg.get("speech_len_sec")
        media_dur = probe_dur(media)
        # Trim to true speech length when known; else keep full clip.
        out_dur = float(speech_len) if speech_len else media_dur
        if out_dur > media_dur + 0.05:
            raise ValueError(
                f"hero_lipsync segment {idx}: speech_len_sec={out_dur:.3f}s exceeds clip "
                f"length {media_dur:.3f}s — slice/clip mismatch.")
        
        # 1. Create muted video
        muted = tmp / f"seg_{idx}_muted.mp4"
        run(["ffmpeg", "-y", "-i", str(media),
             "-vf", f"{scale_crop},{grade}",
             "-t", f"{out_dur:.3f}",
             "-map", "0:v", "-an",  # LB-202: Strip provider audio
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
             "-pix_fmt", "yuv420p", str(muted)], f"seg_{idx}_lipsync_muted")
        
        # 2. Overlay master narration spine
        audio_src = seg.get("audio")
        if audio_src:
            audio_path = resolve(base, audio_src)
            run(["ffmpeg", "-y", "-i", str(muted), "-i", str(audio_path),
                 "-af", "aresample=48000", "-t", f"{out_dur:.3f}",
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 str(dst)], f"seg_{idx}_lipsync")
        else:
            # Fallback: if no audio source is provided, just use the muted video
            # (This shouldn't happen in a correct LB-202 manifest)
            run(["ffmpeg", "-y", "-i", str(muted), "-c", "copy", str(dst)], f"seg_{idx}_lipsync_fallback")
            
        return dst

    # PHASE 5: multi-shot visual bed — concatenate distinct shots to cover narration,
    # then overlay continuous narration once (no audio pause, no loop, no long freeze).
    shots = seg.get("shots")
    audio_src = seg.get("audio")
    if shots and audio_src:
        # If ANY shot is hero_lipsync, we cannot use a single narration overlay for
        # the whole bed — lipsync shots must keep their baked audio. Instead, process
        # each shot individually: lipsync shots via the hero_lipsync path (baked audio,
        # trimmed to speech_len_sec); voiceover shots via a proportional narration slice.
        has_lipsync = any(
            isinstance(sh, dict) and _is_hero_lipsync(sh)
            for sh in shots)

        audio_path = resolve(base, audio_src)
        total_nar_dur = probe_dur(audio_path)
        out_dur = total_nar_dur + TAIL_PAD

        if has_lipsync:
            # Per-shot processing: build individual clips with correct audio, then concat.
            shot_clips = []
            # Compute actual lipsync duration from the real clip files (not speech_len_sec)
            # — clips clamped to LIPSYNC_MAX_DUR are shorter than speech_len_sec, so using
            # speech_len_sec would under-allocate narration time to the voiceover shots.
            actual_lipsync_dur = 0.0
            for sh in shots:
                if isinstance(sh, dict) and _is_hero_lipsync(sh):
                    sp = resolve(base, sh["media"] if isinstance(sh, dict) else sh)
                    speech_len = float(sh.get("speech_len_sec") or 0)
                    clip_dur = probe_dur(sp) or speech_len
                    actual_lipsync_dur += min(speech_len, clip_dur) if speech_len else clip_dur
            vo_shots = [sh for sh in shots
                        if not (isinstance(sh, dict) and _is_hero_lipsync(sh))]
            n_vo = len(vo_shots)
            vo_nar_dur = max(0.0, total_nar_dur - actual_lipsync_dur)
            per_vo = (vo_nar_dur / n_vo) if n_vo else 0.0
            nar_offset = 0.0  # current position in narration mp3

            for j, sh in enumerate(shots):
                is_lip = isinstance(sh, dict) and _is_hero_lipsync(sh)
                sp = resolve(base, sh["media"] if isinstance(sh, dict) else sh)
                sdst = tmp / f"seg_{idx}_shot{j}.mp4"

                if is_lip:
                    speech_len = float(sh.get("speech_len_sec") or 0) or probe_dur(sp)
                    clip_dur = min(speech_len, probe_dur(sp))
                    # LB-202: Keep visual, STRIP baked provider audio. Master narration will be mixed globally.
                    run(["ffmpeg", "-y", "-i", str(sp),
                         "-vf", f"{scale_crop},{grade}", "-t", f"{clip_dur:.3f}",
                         "-map", "0:v", "-an",  # LB-202: Strip provider audio
                         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                         "-pix_fmt", "yuv420p", str(sdst)], f"seg_{idx}_shot{j}_lip")
                    nar_offset += clip_dur
                else:
                    # Voiceover shot: muted visual + a narration slice overlay
                    slot = per_vo if n_vo else (probe_dur(sp) or 4.0)
                    shot_src_dur = probe_dur(sp) or slot
                    vf_shot = f"{scale_crop},{grade}"
                    if shot_src_dur < slot - 0.05:
                        pad = min(slot - shot_src_dur, MAX_FREEZE)
                        vf_shot = f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={pad:.3f}"
                    # Extract narration slice for this voiceover shot
                    nar_slice = tmp / f"seg_{idx}_narslice{j}.mp3"
                    run(["ffmpeg", "-y", "-i", str(audio_path),
                         "-ss", f"{nar_offset:.3f}", "-t", f"{slot:.3f}",
                         "-c", "copy", str(nar_slice)], f"seg_{idx}_narslice{j}")
                    # Build muted visual then overlay the narration slice
                    muted = tmp / f"seg_{idx}_muted{j}.mp4"
                    run(["ffmpeg", "-y", "-i", str(sp), "-an", "-vf", vf_shot,
                         "-t", f"{slot:.3f}", "-c:v", "libx264", "-preset", "medium",
                         "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps),
                         str(muted)], f"seg_{idx}_shot{j}_mute")
                    run(["ffmpeg", "-y", "-i", str(muted), "-i", str(nar_slice),
                         "-af", "aresample=48000", "-t", f"{slot + TAIL_PAD/n_vo:.3f}",
                         "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                         str(sdst)], f"seg_{idx}_shot{j}_vo")
                    nar_offset += slot

                shot_clips.append(sdst)

            # Concat all per-shot clips
            concat_list = tmp / f"seg_{idx}_shots.txt"
            concat_list.write_text("".join(f"file '{p}'\n" for p in shot_clips))
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                 "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 "-pix_fmt", "yuv420p", str(dst)], f"seg_{idx}_concat_mixed")
            return dst

        # Pure voiceover segment: build muted visual bed + overlay narration (original path)
        norm_shots = []
        per = out_dur / len(shots)
        for j, sh in enumerate(shots):
            sp = resolve(base, sh["media"] if isinstance(sh, dict) else sh)
            seg_dur = (sh.get("duration") if isinstance(sh, dict) and sh.get("duration") else per)
            seg_dur = min(seg_dur, per) if len(shots) > 1 else per
            ndst = tmp / f"seg_{idx}_shot{j}.mp4"
            shot_src_dur = probe_dur(sp)
            vf_shot = f"{scale_crop},{grade}"
            if shot_src_dur < per - 0.05:
                pad = per - shot_src_dur
                if pad > MAX_FREEZE:
                    pad = MAX_FREEZE
                vf_shot = f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={pad:.3f}"
            run(["ffmpeg", "-y", "-i", str(sp), "-an", "-vf", vf_shot,
                 "-t", f"{per:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-r", str(fps), str(ndst)], f"seg_{idx}_shot{j}")
            norm_shots.append(ndst)
        concat_list = tmp / f"seg_{idx}_shots.txt"
        concat_list.write_text("".join(f"file '{p}'\n" for p in norm_shots))
        bed = tmp / f"seg_{idx}_bed.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(bed)], f"seg_{idx}_concat")
        run(["ffmpeg", "-y", "-i", str(bed), "-i", str(audio_path),
             "-af", "aresample=48000", "-t", f"{out_dur:.3f}",
             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(dst)],
            f"seg_{idx}_bed_audio")
        return dst

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
                # Default: hold last frame, but only up to MAX_FREEZE; beyond that it's
                # unacceptable filler — require a shots bed or explicit --allow-looping.
                pad_dur = out_dur - media_dur
                if pad_dur > MAX_FREEZE:
                    raise ValueError(
                        f"segment {idx} ({seg.get('media')}): media is {media_dur:.1f}s but narration "
                        f"needs {out_dur:.1f}s — a {pad_dur:.1f}s freeze-frame exceeds the {MAX_FREEZE}s limit. "
                        f"Provide multiple shots to cover the narration, regenerate a longer clip, "
                        f"or pass --allow-looping.")
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
    """Load a music file, loop/trim to video duration, apply level + fades.

    Returns path to the prepared music track, or None if music is disabled.
    S9-C07: If no path is provided but mood/seed are present, generates a
    deterministic music bed using local synthesis (tools/generate_music).
    Fails loudly if enabled=True but neither path nor generation config is available.
    """
    if not music_cfg.get("enabled", False):
        return None

    rel = music_cfg.get("path") or music_cfg.get("file")  # accept both keys
    if not rel:
        # S9-C07: Generate deterministic music bed if mood/seed are provided
        mood = music_cfg.get("mood")
        seed = music_cfg.get("seed")
        if mood is not None and seed is not None:
            try:
                sys.path.insert(0, str(ROOT / "tools"))
                from generate_music import generate as gen_music, write_wav
            except ImportError:
                raise ValueError("music.enabled=true but generate_music not available")
            raw_wav = tmp / "music_raw.wav"
            stereo = gen_music(duration, mood, seed)
            write_wav(stereo, raw_wav)
            rel = str(raw_wav)
        else:
            raise ValueError("music.enabled=true but no music.path or mood/seed specified")
    music_file = resolve(base, rel)
    if not music_file.exists():
        raise FileNotFoundError(f"music file not found: {music_file}")
    src_dur = probe_dur(music_file)
    if src_dur is None or src_dur <= 0:
        raise RuntimeError(f"music file is unreadable or has zero duration: {music_file}")

    volume_db = music_cfg.get("volume_db", -24)
    fade_in   = music_cfg.get("fade_in", 1.5)
    fade_out  = music_cfg.get("fade_out", 2.0)
    do_loop   = music_cfg.get("loop", True)
    fo_start  = max(duration - fade_out, 0)

    # Loop input so it covers full video duration (ffmpeg -stream_loop -1)
    loop_flag = ["-stream_loop", "-1"] if do_loop and src_dur < duration else []

    bed = tmp / "music_bed.m4a"
    run(["ffmpeg", "-y", *loop_flag, "-i", str(music_file),
         "-t", f"{duration:.3f}",
         "-af", (f"volume={volume_db}dB,"
                 f"afade=t=in:st=0:d={fade_in:.2f},"
                 f"afade=t=out:st={fo_start:.3f}:d={fade_out:.2f},"
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


def _composite_graphics_overlays(video, graphics_layers, segments, total_dur,
                                  tmp, w, h, fps):
    """S9-C07: Composite deterministic text overlays for graphic beats.

    For each graphic layer, generates a text overlay PNG using ffmpeg's drawtext
    filter and composites it over the video at the correct timing window.
    Returns the path to the composited video.
    """
    current = video
    for i, gfx in enumerate(graphics_layers):
        beat_id = gfx.get("beat_id", f"gfx_{i}")
        text = gfx.get("text", "")
        if not text:
            continue

        seg_timing_in = 0.0
        seg_timing_out = total_dur
        for seg in segments:
            if seg.get("beat_id") == beat_id or seg.get("id") == beat_id:
                seg_timing_in = seg.get("timing_in", 0.0)
                seg_timing_out = seg.get("timing_out", total_dur)
                break

        overlay_dur = seg_timing_out - seg_timing_in
        if overlay_dur <= 0:
            continue

        escaped_text = text.replace("'", "'\\''").replace(":", "\\:")
        dst = tmp / f"gfx_overlay_{i}.mp4"
        vf = (
            f"drawtext=text='{escaped_text}'"
            f":fontsize=48:fontcolor=white:borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=(h-text_h)/2"
            f":enable='between(t,{seg_timing_in:.3f},{seg_timing_out:.3f})'"
        )
        run(["ffmpeg", "-y", "-i", str(current),
             "-vf", vf,
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "copy",
             str(dst)], f"gfx_overlay_{i}")
        current = dst

    return current


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

    # --- Continuous voiceover path ---
    if manifest.get("narration_mode") == "continuous_voiceover":
        continuous_audio = resolve(base, manifest["continuous_audio"])
        if not continuous_audio.exists():
            raise FileNotFoundError(f"Continuous narration not found: {continuous_audio}")
        total_nar_dur = probe_dur(continuous_audio)

        # Beat-level timing map: each beat has [start, end] in the master
        beat_timing = None
        if manifest.get("beat_timing_map"):
            bt_path = resolve(base, manifest["beat_timing_map"])
            if bt_path.exists():
                beat_timing = json.load(open(bt_path))

        # Segment-level timing map (fallback)
        timing = None
        timing_map_field = manifest.get("timing_map")
        if timing_map_field:
            timing_map_path = resolve(base, timing_map_field)
            if timing_map_path.exists() and timing_map_path.is_file():
                timing = json.load(open(timing_map_path))

        # In continuous mode ALL clips are muted visuals — baked lipsync audio is
        # IGNORED. The single master narration is the sole audio source. Mouth sync
        # is preserved because lipsync clips were rendered to the same audio slice
        # that occupies that [start,end] span in the master.

        # Build per-segment visual durations. Modern manifests carry the exact
        # clip-level timeline contract; timing maps are legacy fallbacks only.
        seg_durations = _contract_segment_durations(segments)
        if seg_durations is not None:
            contract_total = sum(seg_durations)
            if abs(contract_total - total_nar_dur) > 0.25:
                raise RuntimeError(
                    f"Clip timeline duration mismatch: clips={contract_total:.3f}s vs "
                    f"audio={total_nar_dur:.3f}s (delta={contract_total - total_nar_dur:.3f}s).")
        elif beat_timing and beat_timing.get("beats"):
            # Group beat durations by segment
            from collections import OrderedDict
            seg_windows = OrderedDict()
            for bt in beat_timing["beats"]:
                # Match beat to segment by iterating segments' shots
                for seg in segments:
                    shots = seg.get("shots", [])
                    media_name = Path(seg.get("media", "")).stem if seg.get("media") else ""
                    # Check if this beat belongs to this segment
                    beat_in_seg = any(
                        bt["beat_id"] in (sh.get("beat_id", "") or Path(sh.get("media", "")).stem)
                        for sh in shots
                    ) if shots else bt["beat_id"].startswith(media_name)
                    if beat_in_seg:
                        sid = seg.get("id") or seg.get("segment_id") or f"seg_{segments.index(seg)}"
                        if sid not in seg_windows:
                            seg_windows[sid] = {"start": bt["start"], "end": bt["end"]}
                        else:
                            seg_windows[sid]["start"] = min(seg_windows[sid]["start"], bt["start"])
                            seg_windows[sid]["end"] = max(seg_windows[sid]["end"], bt["end"])
                        break
            seg_durations = []
            for i, seg in enumerate(segments):
                sid = seg.get("id") or seg.get("segment_id") or f"seg_{i}"
                if sid in seg_windows:
                    seg_durations.append(seg_windows[sid]["end"] - seg_windows[sid]["start"])
                else:
                    seg_durations.append(total_nar_dur / len(segments))
        elif timing and timing.get("beats"):
            # Group beats by segment_id to get per-segment duration
            from collections import OrderedDict
            seg_durs = OrderedDict()
            for beat in timing["beats"]:
                sid = beat.get("segment_id", "unknown")
                if sid not in seg_durs:
                    seg_durs[sid] = {"start": beat["start"], "end": beat["end"]}
                else:
                    if beat["start"] is not None:
                        seg_durs[sid]["start"] = min(seg_durs[sid]["start"], beat["start"])
                    if beat["end"] is not None:
                        seg_durs[sid]["end"] = max(seg_durs[sid]["end"], beat["end"])
            seg_durations = [seg_durs[s["segment_id"]]["end"] - seg_durs[s["segment_id"]]["start"]
                            if s.get("segment_id") and s["segment_id"] in seg_durs else total_nar_dur / len(segments)
                            for s in timing["beats"][:len(segments)]]
            if len(seg_durations) != len(segments):
                seg_durations = [total_nar_dur / len(segments)] * len(segments)
        else:
            seg_durations = [total_nar_dur / len(segments)] * len(segments)

        # Normalize each visual segment to its narration duration (muted)
        norm_clips = []
        for i, seg in enumerate(segments):
            media = resolve(base, seg["media"])
            target_dur = seg_durations[i] if i < len(seg_durations) else total_nar_dur / len(segments)
            dst = fmt_tmp / f"cont_seg_{i}.mp4"
            scale_crop = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"

            media_kind = _segment_media_kind(seg, media)

            if media_kind == "video":
                # Generated-video b-roll. The clip length is non-deterministic
                # (kling3_0 returns ~4/5/6s buckets), so small shortfalls are
                # expected. Freeze-pad the tail up to MAX_FREEZE (imperceptible,
                # and well under qa_final's 1.5s freeze limit) rather than hard-
                # failing and forcing a regeneration. Only error if the shortfall
                # exceeds what a tail freeze can cover. Overshoot is trimmed by -t.
                clip_dur = probe_dur(media)
                shortfall = target_dur - clip_dur
                if shortfall > MAX_FREEZE:
                    raise RuntimeError(
                        f"Beat {seg.get('id', i)} clip too short: clip={clip_dur:.3f}s, "
                        f"required={target_dur:.3f}s (shortfall={shortfall:.3f}s exceeds "
                        f"the {MAX_FREEZE}s freeze-pad limit). "
                        f"Regenerate a longer clip or split into multiple shots.")
                pad = max(0.0, shortfall)
                vf = (f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={pad:.3f}"
                      if pad > 0.0 else f"{scale_crop},{grade}")
                run(["ffmpeg", "-y", "-i", str(media), "-an",
                     "-vf", vf,
                     "-t", f"{target_dur:.3f}",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-pix_fmt", "yuv420p", "-r", str(fps), str(dst)], f"cont_seg_{i}")
            else:
                # A still has no intrinsic duration. Its timeline duration comes
                # exclusively from the clip contract above.
                run(["ffmpeg", "-y", "-i", str(media), "-an",
                     "-vf", f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={target_dur:.3f}",
                     "-t", f"{target_dur:.3f}",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-pix_fmt", "yuv420p", "-r", str(fps), str(dst)], f"cont_seg_{i}")
            norm_clips.append(dst)

        # Concat all visual segments
        concat_list = fmt_tmp / "cont_concat.txt"
        concat_list.write_text("".join(f"file '{p}'\n" for p in norm_clips))
        visual_bed = fmt_tmp / "cont_visual.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(visual_bed)], "cont_concat")

        # Change 2: Pre-mux visual bed duration check
        visual_bed_dur = probe_dur(visual_bed)
        if abs(visual_bed_dur - total_nar_dur) > 0.25:
            raise RuntimeError(
                f"Visual bed duration mismatch: visual={visual_bed_dur:.3f}s vs "
                f"audio={total_nar_dur:.3f}s (delta={visual_bed_dur - total_nar_dur:.3f}s). "
                f"Cannot mux — fix short clips first.")

        # Overlay continuous narration onto visual bed
        joined = fmt_tmp / "cont_joined.mp4"
        run(["ffmpeg", "-y", "-i", str(visual_bed), "-i", str(continuous_audio),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-t", f"{total_nar_dur:.3f}", str(joined)], "cont_overlay")

        # S9-C07: Generate deterministic music bed and mix under narration
        music_cfg = manifest.get("music", {})
        if music_cfg.get("enabled"):
            music_bed = make_music_bed(total_nar_dur, music_cfg, fmt_tmp, base)
            if music_bed:
                mixed = fmt_tmp / "cont_mixed.mp4"
                run(["ffmpeg", "-y", "-i", str(joined), "-i", str(music_bed),
                     "-filter_complex",
                     "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
                     "-map", "0:v", "-map", "[a]",
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                     str(mixed)], "cont_mix_music")
                joined = mixed

        # S9-C07: Composite graphics overlays for graphic beats
        graphics_layers = manifest.get("graphics", [])
        if graphics_layers:
            joined = _composite_graphics_overlays(
                joined, graphics_layers, segments, total_nar_dur,
                fmt_tmp, w, h, fps)

        # Change 3: Post-mux stream integrity check
        joined_vid_dur = probe_dur(joined)
        if abs(joined_vid_dur - total_nar_dur) > 0.25:
            Path(joined).unlink(missing_ok=True)
            raise RuntimeError(
                f"Post-mux integrity failure: output={joined_vid_dur:.3f}s vs "
                f"expected={total_nar_dur:.3f}s. Broken output deleted.")

    else:
        # --- Segment-by-segment path (default) ---
        # 1. Process segments
        norm_clips = []
        for i, seg in enumerate(segments):
            # hero_lipsync spans: verify baked-audio provenance BEFORE assembling.
            # A tampered slice hash (or missing provenance) must kill assembly.
            if _is_hero_lipsync(seg):
                prov_problems = validate_lipsync_provenance(seg, base)
                if prov_problems:
                    raise ValueError(
                        "Lipsync provenance check failed — refusing to assemble:\n  "
                        + "\n  ".join(prov_problems))
            clip = process_segment(seg, speeds[i], w, h, fps, grade, crf, fmt_tmp, base, i, allow_looping=allow_looping)
            if _is_hero_lipsync(seg):
                # Baked-audio span: assert the assembled clip's audio matches the
                # clip's own baked audio and the true speech length within ±0.25s.
                seg_dur = probe_dur(clip)
                speech_len = seg.get("speech_len_sec")
                if speech_len is not None:
                    if abs(seg_dur - float(speech_len)) > LIPSYNC_TIMING_TOL:
                        raise ValueError(
                            f"hero_lipsync segment {seg.get('id','?')}: assembled span "
                            f"{seg_dur:.3f}s vs true speech_len {float(speech_len):.3f}s "
                            f"exceeds ±{LIPSYNC_TIMING_TOL}s.")
                norm_clips.append(clip)
                continue
            # ENG-04: assert assembled segment audio aligns with narration (within 0.3s)
            audio_src = seg.get("audio")
            if audio_src:
                narr_dur = probe_dur(resolve(base, audio_src))
                seg_dur  = probe_dur(clip)
                seg_audio = probe_dur(clip)  # audio stream duration ≈ container duration for trimmed segs
                # container duration of clip should be narration + TAIL_PAD ± tolerance
                expected = narr_dur / speeds[i] + TAIL_PAD  # plain branch is speed-adjusted
                if seg.get("shots"):
                    expected = narr_dur + TAIL_PAD  # shots branch: no speed applied (ENG-01 fix)
                if abs(seg_dur - expected) > 0.5:
                    raise ValueError(
                        f"ENG-04 QA gate: segment {seg.get('id','?')} duration={seg_dur:.2f}s "
                        f"expected≈{expected:.2f}s (narration={narr_dur:.2f}s). "
                        f"Audio/video mis-alignment detected."
                    )
            # TKT-11: Composite overlay PNG if present
            clip = _composite_overlay(seg, clip, base, fmt_tmp, i)
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

    # 4. Music (None if disabled)
    music_cfg = manifest.get("music", {})

    # TKT-10: Validate music requirements against constraints
    video_format = manifest.get("format", manifest.get("episode_type", ""))
    constraints_path = ROOT / "docs" / "channel_universe" / "constraints.json"
    if constraints_path.exists():
        with open(constraints_path) as cf:
            constraints = json.load(cf)
        required_formats = constraints.get("music", {}).get("required_for_formats", [])
    else:
        required_formats = []

    if music_cfg.get("enabled"):
        rel = music_cfg.get("path") or music_cfg.get("file")
        if rel:
            music_file = resolve(base, rel)
            if not music_file.exists():
                raise RuntimeError(f"Music enabled but file not found: {music_file}")
    elif video_format in required_formats:
        raise RuntimeError(
            f"Music is required for format '{video_format}' but music.enabled=false. "
            f"Enable music in the manifest or change the format.")

    total_dur = probe_dur(joined)
    bed = make_music_bed(total_dur, music_cfg, fmt_tmp, base)
    mixed = mix_music(joined, bed, fmt_tmp) if bed else joined

    # TKT-10: Volume detection after mix
    volume_meta = {}
    if bed:
        vd = subprocess.run(
            ["ffmpeg", "-i", str(mixed), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        import re
        mean_m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", vd.stderr)
        max_m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", vd.stderr)
        volume_meta = {
            "mean_volume": float(mean_m.group(1)) if mean_m else None,
            "max_volume": float(max_m.group(1)) if max_m else None,
        }

    # 5. Loudnorm → final
    out_dir = resolve(base, manifest.get("output", {}).get("directory", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = manifest.get("output", {}).get("prefix", manifest.get("id", "output"))
    final = out_dir / f"{prefix}_{fmt}.mp4"
    loudnorm(mixed, final)

    return final, volume_meta


def assemble(manifest_path, formats=None, tmp_base=None, allow_looping=False,
             music_override=None, music_volume_db=None, no_music=False):
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

    # --- UCI-04: resolve clip paths from DB and assert all valid ---
    segments = manifest.get("segments", [])
    has_clip_ids = any(seg.get("clip_id") for seg in segments)
    if has_clip_ids:
        clip_db.init_db()
        project_id = manifest.get("id") or manifest_path.parent.name
        # Check if DB has clips for this project (skip gate if none registered)
        db_clips = clip_db.list_clips(project_id)
        if db_clips:
            # Resolve media paths from the clip DB (golden truth)
            for seg in segments:
                cid = seg.get("clip_id")
                if cid:
                    db_clip = clip_db.get_clip(cid)
                    if db_clip:
                        seg["media"] = db_clip["output_path"]
                        seg["asset_type"] = db_clip["asset_type"]
                        seg["audio_policy"] = db_clip["audio_policy"]
                        seg["timing_in"] = db_clip["required_start_sec"]
                        seg["timing_out"] = db_clip["required_end_sec"]
                        seg["duration_required"] = db_clip["required_dur_sec"]
            # Gate: all clips must be valid + files exist on disk before muxing
            ok, problems = clip_db.assert_all_valid(project_id)
            if not ok:
                lines = [f"  {p['clip_id']}: status={p.get('status','?')} reason={p.get('status_reason') or p.get('reason','')}"
                         for p in problems]
                raise RuntimeError(
                    "UCI-04 assembly gate FAILED — clips not valid:\n" + "\n".join(lines))
        else:
            import warnings
            warnings.warn("UCI-04: clip_ids present but no clips registered in DB — skipping gate (transitional)")
    else:
        import warnings
        warnings.warn("UCI-04: no clip_ids in manifest — skipping DB path resolution (legacy mode)")

    # Apply CLI music overrides (after validation, before assembly)
    if no_music:
        manifest.setdefault("music", {})["enabled"] = False
    if music_override:
        manifest.setdefault("music", {}).update({"enabled": True, "path": music_override})
    if music_volume_db is not None:
        manifest.setdefault("music", {})["volume_db"] = music_volume_db

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
        manifest["segments"], manifest.get("pacing", {}), base,
        narration_mode=manifest.get("narration_mode"))

    log["pacing"] = {
        "wps_per_segment": [round(w, 3) if w is not None else None for w in wps_list],
        "speeds": [round(s, 4) for s in speeds],
        "target_wps": (round(ref_wps * manifest.get("pacing", {}).get("baseline_speed", 1.0), 3)
                       if ref_wps is not None else None),
    }

    # Build each format
    for fmt in formats:
        t0 = time.time()
        final, volume_meta = assemble_format(manifest, fmt, speeds, base, tmp, allow_looping=allow_looping)
        dur = probe_dur(final)
        fmt_log = {
            "path": str(final),
            "duration_s": round(dur, 2),
            "build_time_s": round(time.time() - t0, 1),
        }
        if volume_meta:
            fmt_log["volume"] = volume_meta
        log["formats"][fmt] = fmt_log

    log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    # Music provenance in log
    music_cfg = manifest.get("music", {})
    if music_cfg.get("enabled"):
        rel = music_cfg.get("path") or music_cfg.get("file", "")
        mf = resolve(base, rel) if rel else None
        src_dur = probe_dur(mf) if mf and mf.exists() else None
        vid_dur = log["formats"].get(formats[0], {}).get("duration_s") if log["formats"] else None
        log["music"] = {
            "enabled": True,
            "path": str(mf) if mf else rel,
            "filename": mf.name if mf else rel,
            "source_duration": round(src_dur, 2) if src_dur else None,
            "final_video_duration": vid_dur,
            "volume_db": music_cfg.get("volume_db", -24),
            "fade_in": music_cfg.get("fade_in", 1.5),
            "fade_out": music_cfg.get("fade_out", 2.0),
            "loop": music_cfg.get("loop", True),
            "looped": (src_dur < vid_dur) if (src_dur and vid_dur) else None,
        }
    else:
        log["music"] = {"enabled": False}

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
    ap.add_argument("--music", default=None, metavar="FILE", help="Background music file (overrides manifest)")
    ap.add_argument("--music-volume-db", type=float, default=None, metavar="DB", help="Music volume in dB (default -24)")
    ap.add_argument("--no-music", action="store_true", help="Disable music even if manifest enables it")
    ap.add_argument("--require-gates", action="store_true",
                    help="Enforce the G8 media_qa gate before assembling")
    ap.add_argument("--project-id", default=None,
                    help="Project id for gate lookup (defaults to manifest 'id')")
    ap.add_argument("--force-unsafe", action="store_true",
                    help="EMERGENCY: bypass the media_qa gate (logged)")
    args = ap.parse_args()

    # G8 media QA gate (blueprint §6): assembly refuses to run on un-QA'd clips.
    if args.require_gates and not args.force_unsafe:
        pid = args.project_id
        if not pid:
            try:
                pid = json.loads(Path(args.manifest).read_text()).get("id")
            except (OSError, json.JSONDecodeError):
                pid = None
        if not pid:
            print("ERROR: --require-gates needs a project id (manifest 'id' or --project-id)",
                  file=sys.stderr)
            sys.exit(1)
        require_gates(pid, ["media_qa"])
    elif args.require_gates and args.force_unsafe:
        sys.stderr.write("\033[31m⚠ FORCE-UNSAFE: bypassing media_qa gate before assembly.\033[0m\n")

    formats = [f.strip() for f in args.formats.split(",")]
    try:
        log = assemble(args.manifest, formats, args.tmp, allow_looping=args.allow_looping,
                       music_override=args.music, music_volume_db=args.music_volume_db,
                       no_music=args.no_music)
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
