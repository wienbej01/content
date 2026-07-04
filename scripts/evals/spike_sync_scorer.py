#!/usr/bin/env python3
"""TKT-101 discovery spike: face-tracked AV-sync scorer.

Proves a face-tracked audio-visual offset estimator that does NOT require the
brittle Oxford SyncNet_v2 weights / syncnet_python (Python 2-era) toolchain.

Method (an "equivalent latent-sync scorer" per TKT-101 candidate list):

  1. Face tracking: MediaPipe Tasks FaceLandmarker runs per video frame and
     returns a mouth-open ratio per frame. The *visual* envelope is this
     per-frame mouth-open ratio resampled to the audio frame rate. Tracking
     is face-gated: frames without a tracked face contribute zero to the
     envelope and are recorded, so `face_track_found` reflects coverage.
  2. Audio envelope: ffmpeg decodes the file's audio to mono PCM at a fixed
     hop rate; the per-hop RMS amplitude is the *audio* envelope.
  3. Offset: normalized cross-correlation of the visual mouth envelope vs the
     audio envelope. The lag of the peak correlation (in ms) is the estimated
     audio-lead/visual-lag offset. Positive offset means the audio leads the
     visible mouth motion (audio early); negative means audio lags.

This is a real face-tracked measurement (the visual side is derived from the
speaker's face, not from whole-frame pixel diff) and is fully reproducible on
CPU with pinned, freely-licensed dependencies and a small Apache-2.0 model.

Proof matrix (per TKT-101). The scorer measures a clip's TRUE audio-vs-face
offset, which includes any intrinsic desync. The controlled proof is therefore
DIFFERENTIAL: the same clip scored unshifted vs with an ffmpeg adelay shift,
where the detected delta must match the injected shift. --shift-ms runs both
and reports `detected_shift_ms = offset_shifted - offset_reference`.

  - unshifted clip              : score completes; face_track_found true
  - +200 ms adelay-shifted       : detected_shift_ms ~= +200 (+/- 40 ms tolerance)
  - --mismatch (other audio)    : low confidence / explicit no-peak signal
                                  (detected_shift_ms not meaningful; confidence
                                   and face_track_found are the verdict)

Usage:
  python3 scripts/evals/spike_sync_scorer.py <clip>
  python3 scripts/evals/spike_sync_scorer.py <clip> --shift-ms 200
  python3 scripts/evals/spike_sync_scorer.py <video.mp4> --mismatch-audio <other.mp4>
  python3 scripts/evals/spike_sync_scorer.py <clip> --json <out.json>

Dependencies (pinned in the decision record and the venv at
/tmp/kilo/tkt101_venv): mediapipe==0.10.35, opencv-python, numpy.
Model: mediapipe FaceLandmarker (float16, Apache-2.0 task bundle).
Exit codes: 0 success; 2 precondition/scorer failure (no face track, deps
missing); 1 argument/IO error.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sync_scorer._algorithm import (
    DEFAULT_MODEL_PATH,
    _LIP_UPPER_INNER,
    _LIP_LOWER_INNER,
    _LIP_LEFT,
    _LIP_RIGHT,
    _SEARCH_WINDOW_MS,
    _AUDIO_HOP_MS,
    _SHIFT_TOLERANCE_MS,
    _check_real_deps,
    _audio_envelope,
    _mouth_envelope,
    _resample,
    _normalize,
    _cross_correlate,
)

MODEL_ENV = "TKT101_FACE_LANDMARKER_MODEL"
DEFAULT_MODEL = DEFAULT_MODEL_PATH

# Backward-compatible aliases for spike-specific code references.
SEARCH_WINDOW_MS = _SEARCH_WINDOW_MS
AUDIO_HOP_MS = _AUDIO_HOP_MS
SHIFT_TOLERANCE_MS = _SHIFT_TOLERANCE_MS


def _check_deps() -> dict:
    _, deps = _check_real_deps()
    return deps


def _ffprobe_float(path: Path, stream: str, key: str) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", f"stream={key}", "-of", "default=nw=1:nk=1", str(path)],
        text=True,
    ).strip()
    return float(out.split("/")[0]) if out else 0.0


def _shift_audio(video: Path, shift_ms: int, out: Path) -> None:
    """Remux video with audio delayed by shift_ms (positive = audio later)."""
    # adelay delays audio by N ms; mono->one channel spec, stereo->two.
    # Use aresample to keep format sane; stream copy video to avoid re-encode.
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-filter:a", f"adelay={shift_ms}|{shift_ms}",
         "-c:v", "copy", str(out)],
        check=True,
    )


def score(video_path: Path, audio_path: Path, model_path: Path) -> dict:
    """Score one (video, audio) pair. Returns the structured result."""
    deps = _check_deps()
    missing = [k for k, v in deps.items() if v is False or (isinstance(v, str) and v.startswith("err:"))]
    if missing:
        return {"status": "deps_missing", "missing": missing, "deps": deps}

    mouth, vfps, face_frac, frames, face_hits = _mouth_envelope(video_path, model_path)
    if face_hits == 0:
        return {
            "status": "no_face_track",
            "method": "face_landmarker_mouth_xcorr",
            "face_track_found": False,
            "confidence": 0.0,
            "offset_ms": None,
            "frames": frames,
            "video_fps": vfps,
            "deps": deps,
        }
    audio_env, arate = _audio_envelope(audio_path)
    if not audio_env:
        return {"status": "audio_decode_failed", "deps": deps}

    # Resample both envelopes to the audio hop rate (audio envelope rate).
    vis_resampled = _resample(mouth, vfps, arate)
    vis_norm = _normalize(vis_resampled)
    aud_norm = _normalize(audio_env)

    best_lag, peak = _cross_correlate(vis_norm, aud_norm, arate, SEARCH_WINDOW_MS)
    offset_ms = round(best_lag * (1000.0 / arate), 1)

    return {
        "status": "ok",
        "method": "face_landmarker_mouth_xcorr",
        "model": "mediapipe_face_landmarker_float16",
        "face_track_found": face_frac >= 0.5,
        "face_track_fraction": round(face_frac, 4),
        "offset_ms": offset_ms,
        "confidence": round(peak, 4),
        "frames": frames,
        "face_hits": face_hits,
        "video_fps": vfps,
        "audio_envelope_rate_hz": round(arate, 2),
        "search_window_ms": SEARCH_WINDOW_MS,
        "video_path": str(video_path),
        "audio_path": str(audio_path),
        "deps": {k: v for k, v in deps.items()},
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("clip", type=Path, help="talking-head video (.mp4)")
    p.add_argument("--shift-ms", type=int, default=None,
                   help="inject an audio delay of N ms before scoring (proof matrix)")
    p.add_argument("--mismatch-audio", type=Path, default=None,
                   help="score the clip's video against a DIFFERENT clip's audio")
    p.add_argument("--json", type=Path, default=None, help="write result JSON here")
    p.add_argument("--model", type=Path, default=None,
                   help=f"FaceLandmarker .task model (default ${MODEL_ENV} or {DEFAULT_MODEL})")
    args = p.parse_args(argv)

    if not args.clip.exists():
        print(f"ERROR: clip not found: {args.clip}", file=sys.stderr)
        return 1
    model = args.model or Path(os.environ.get(MODEL_ENV, DEFAULT_MODEL))
    if not model.exists():
        print(f"ERROR: FaceLandmarker model not found: {model}", file=sys.stderr)
        print(f"  set ${MODEL_ENV} or pass --model <path>", file=sys.stderr)
        return 2

    if args.shift_ms is not None and args.mismatch_audio is not None:
        print("ERROR: --shift-ms and --mismatch-audio are mutually exclusive", file=sys.stderr)
        return 1

    tmp_shifted = None
    if args.shift_ms is not None:
        # Controlled DIFFERENTIAL proof: score the clip unshifted (reference)
        # and with an ffmpeg adelay shift (shifted). The injected shift is the
        # controlled variable; the scorer's detected delta must match it,
        # independent of any intrinsic clip A/V desync.
        tmp_shifted = Path(tempfile.mkstemp(suffix=".mp4", dir="/tmp/kilo")[1])
        try:
            _shift_audio(args.clip, args.shift_ms, tmp_shifted)
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: ffmpeg audio shift failed: {exc}", file=sys.stderr)
            tmp_shifted.unlink(missing_ok=True)
            return 1
        reference = score(args.clip, args.clip, model)
        shifted = score(args.clip, tmp_shifted, model)
        result = {
            "mode": "shift_proof",
            "injected_shift_ms": args.shift_ms,
            "reference": reference,
            "shifted": shifted,
            "deps": reference.get("deps"),
        }
        if reference.get("offset_ms") is not None and shifted.get("offset_ms") is not None:
            result["detected_shift_ms"] = round(
                shifted["offset_ms"] - reference["offset_ms"], 1
            )
            result["detected_shift_error_ms"] = round(
                abs(result["detected_shift_ms"] - args.shift_ms), 1
            )
            result["detected_shift_within_tolerance"] = (
                result["detected_shift_error_ms"] <= SHIFT_TOLERANCE_MS
            )
    elif args.mismatch_audio is not None:
        if not args.mismatch_audio.exists():
            print(f"ERROR: mismatch audio source not found: {args.mismatch_audio}", file=sys.stderr)
            return 1
        result = score(args.clip, args.mismatch_audio, model)
        result["mismatch"] = True
        result["mismatch_audio_source"] = str(args.mismatch_audio)
    else:
        result = score(args.clip, args.clip, model)

    print(json.dumps(result, indent=2, default=str))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, default=str))

    if tmp_shifted is not None:
        tmp_shifted.unlink(missing_ok=True)

    # Exit 2 when no face was tracked (precondition failure), else 0 on a
    # completed score (even low-confidence mismatch results exit 0; the
    # confidence field communicates the quality).
    statuses = []
    if "reference" in result:
        statuses.append(result["reference"].get("status"))
        statuses.append(result["shifted"].get("status"))
    else:
        statuses.append(result.get("status"))
    if any(s in ("no_face_track", "deps_missing", "audio_decode_failed") for s in statuses):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
