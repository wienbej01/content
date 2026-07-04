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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL_ENV = "TKT101_FACE_LANDMARKER_MODEL"
DEFAULT_MODEL = "/tmp/kilo/tkt101_venv/models/face_landmarker.task"

# Landmark indices for the 478-point MediaPipe FaceLandmarker model.
_LIP_UPPER_INNER = 13
_LIP_LOWER_INNER = 14
_LIP_LEFT = 78
_LIP_RIGHT = 308

# Correlation window / search bounds (ms). The injected shift in the proof
# matrix is 200 ms, so a +/- 600 ms search band comfortably brackets it while
# avoiding spurious large-lag peaks.
SEARCH_WINDOW_MS = 600
AUDIO_HOP_MS = 20  # audio envelope hop -> 50 Hz; fine enough for 40 ms tol
SHIFT_TOLERANCE_MS = 40  # per TKT-101 acceptance gate G2


def _check_deps() -> dict:
    deps = {}
    try:
        import mediapipe
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        deps["mediapipe"] = mediapipe.__version__
        deps["vision_ok"] = hasattr(mp_vision, "FaceLandmarker")
    except Exception as exc:
        deps["mediapipe"] = f"err:{exc}"
        deps["vision_ok"] = False
    for mod in ("cv2", "numpy"):
        try:
            m = __import__(mod)
            deps[mod] = getattr(m, "__version__", "ok")
        except Exception as exc:
            deps[mod] = f"err:{exc}"
    deps["ffmpeg"] = shutil.which("ffmpeg") is not None
    deps["ffprobe"] = shutil.which("ffprobe") is not None
    return deps


def _ffprobe_float(path: Path, stream: str, key: str) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", f"stream={key}", "-of", "default=nw=1:nk=1", str(path)],
        text=True,
    ).strip()
    return float(out.split("/")[0]) if out else 0.0


def _audio_envelope(path: Path, hop_ms: int = AUDIO_HOP_MS) -> tuple[list[float], float]:
    """Return (envelope_samples, sample_rate_hz) for the file's mono audio.

    Uses ffmpeg to decode to mono f32le; envelopes are RMS per hop window.
    """
    audio_rate = 8000  # decode rate; plenty of bandwidth for an envelope
    hop_samples = int(audio_rate * hop_ms / 1000)
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as tf:
        raw = Path(tf.name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path),
             "-ac", "1", "-ar", str(audio_rate), "-f", "f32le", str(raw)],
            check=True,
        )
        import numpy as np
        data = np.fromfile(raw, dtype="<f4")
        if data.size == 0:
            return [], float(audio_rate) / hop_samples
        n_hops = max(1, data.size // hop_samples)
        trimmed = data[: n_hops * hop_samples].reshape(n_hops, hop_samples)
        rms = np.sqrt(np.mean(trimmed ** 2, axis=1)).astype(float)
        envelope_rate = 1000.0 / hop_ms
        return rms.tolist(), envelope_rate
    finally:
        raw.unlink(missing_ok=True)


def _mouth_envelope(path: Path, model_path: Path) -> tuple[list[float], float, float, int, int]:
    """Return (mouth_open_ratio_per_frame, fps, face_track_fraction, frames, face_hits).

    The per-frame mouth-open ratio is the visual envelope source; it is
    face-tracked (zero when no face is detected, which also lowers the
    correlation peak / face_track_fraction).
    """
    import cv2
    import mediapipe
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    opts = mp_vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
        min_face_detection_confidence=0.3,
        min_face_presence_confidence=0.3,
        min_tracking_confidence=0.3,
    )
    lm = mp_vision.FaceLandmarker.create_from_options(opts)
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    mouth = []
    face_hits = 0
    n = 0
    try:
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            mp_img = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=fr)
            ts_ms = int(round(n / fps * 1000))
            res = lm.detect_for_video(mp_img, ts_ms)
            if res.face_landmarks:
                lms = res.face_landmarks[0]
                top = lms[_LIP_UPPER_INNER]
                bot = lms[_LIP_LOWER_INNER]
                left = lms[_LIP_LEFT]
                right = lms[_LIP_RIGHT]
                v = ((top.x - bot.x) ** 2 + (top.y - bot.y) ** 2) ** 0.5
                h = ((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5
                mouth.append(float(v / max(h, 1e-6)))
                face_hits += 1
            else:
                mouth.append(0.0)
            n += 1
    finally:
        cap.release()
        lm.close()
    frac = (face_hits / n) if n else 0.0
    return mouth, float(fps), frac, n, face_hits


def _resample(values: list[float], src_rate: float, dst_rate: float) -> list[float]:
    import numpy as np
    if src_rate == dst_rate or len(values) < 2:
        return list(values)
    n_out = max(2, int(round(len(values) * dst_rate / src_rate)))
    idx = np.linspace(0, len(values) - 1, n_out)
    lo = idx.astype(int)
    hi = np.clip(lo + 1, 0, len(values) - 1)
    frac = idx - lo
    out = np.asarray(values)[lo] * (1 - frac) + np.asarray(values)[hi] * frac
    return out.tolist()


def _normalize(values: list[float]) -> list[float]:
    import numpy as np
    arr = np.asarray(values, dtype=float)
    arr = arr - arr.mean()
    std = arr.std()
    if std < 1e-9:
        return [0.0] * len(arr)
    return (arr / std).tolist()


def _cross_correlate(visual: list[float], audio: list[float], rate: float,
                     search_ms: int) -> tuple[int, float]:
    """Return (best_lag_samples, peak_confidence) where lag>0 means audio leads.

    visual[lag] aligns with audio[0] when audio is `lag` hops ahead of the
    visual; i.e. a positive injected adelay (audio delayed) should produce a
    positive estimated offset (audio arrives later than the mouth motion).
    Cross-correlation: r[lag] = sum_k visual[k] * audio[k + lag].
    """
    import numpy as np
    vis = np.asarray(visual, dtype=float)
    aud = np.asarray(audio, dtype=float)
    # pad shorter series to equal length
    m = min(vis.size, aud.size)
    if m < 4:
        return 0, 0.0
    vis = vis[:m]
    aud = aud[:m]
    max_lag = int(search_ms / 1000.0 * rate)
    best_lag = 0
    best = -1.0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a = aud[lag:]
            v = vis[: a.size]
            if v.size < 4:
                continue
            a = a[: v.size]
        else:
            v = vis[-lag:]
            a = aud[: v.size]
        if v.size < 4:
            continue
        denom = (np.linalg.norm(v) * np.linalg.norm(a))
        if denom < 1e-12:
            continue
        corr = float(np.dot(v, a) / denom)
        if corr > best:
            best = corr
            best_lag = lag
    # offset_ms: positive injected audio delay -> positive offset.
    # If audio is delayed by D, the audio envelope lags the visual envelope,
    # so the alignment that maximizes correlation is visual[k] vs audio[k+lag]
    # with lag = D*rate (audio index must advance to catch up). best_lag>0.
    return best_lag, best


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
