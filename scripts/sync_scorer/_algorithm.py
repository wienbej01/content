"""TKT-102: Shared algorithmic primitives for the face-tracked AV-sync scorer.

These functions implement the scorer selected by TKT-101 discovery:
face-landmark mouth-envelope x cross-correlation with audio envelope.

Consumed by both:
  - scripts/sync_scorer/scorer.py (production RealSyncBackend)
  - scripts/evals/spike_sync_scorer.py (TKT-101 discovery spike)

All ML-import-heavy functions use lazy imports inside function bodies so the
module remains importable without mediapipe/opencv installed.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

# Landmark indices for the 478-point MediaPipe FaceLandmarker model.
_LIP_UPPER_INNER = 13
_LIP_LOWER_INNER = 14
_LIP_LEFT = 78
_LIP_RIGHT = 308

# Correlation window / search bounds (ms).
_SEARCH_WINDOW_MS = 600

# Audio envelope hop (ms) — 50 Hz; fine enough for 40 ms tolerance.
_AUDIO_HOP_MS = 20

# Shift tolerance for the differential proof matrix (per TKT-101 G2).
_SHIFT_TOLERANCE_MS = 40

# Scorer identity constants.
REAL_METHOD = "face_landmarker_mouth_xcorr"
REAL_MODEL_NAME = "mediapipe_face_landmarker_float16"
DEFAULT_MODEL_PATH = "/tmp/kilo/tkt101_venv/models/face_landmarker.task"


def _check_real_deps() -> tuple[bool, dict]:
    """Check whether mediapipe, cv2, numpy, ffmpeg, ffprobe are available."""
    deps = {}
    try:
        import mediapipe
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        deps["mediapipe"] = getattr(mediapipe, "__version__", "ok")
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
    import shutil

    deps["ffmpeg"] = shutil.which("ffmpeg") is not None
    deps["ffprobe"] = shutil.which("ffprobe") is not None
    ok = all(
        v is True or (isinstance(v, str) and not v.startswith("err:"))
        for v in deps.values()
    )
    return ok, deps


def _audio_envelope(path: Path, hop_ms: int | None = None) -> tuple[list[float], float]:
    """Return (envelope_samples, sample_rate_hz) for the file's mono audio."""
    import numpy as np

    if hop_ms is None:
        hop_ms = _AUDIO_HOP_MS
    audio_rate = 8000
    hop_samples = int(audio_rate * hop_ms / 1000)
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as tf:
        raw = Path(tf.name)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(path),
                "-ac", "1", "-ar", str(audio_rate), "-f", "f32le", str(raw),
            ],
            check=True,
        )
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
    """Return (mouth_open_ratio_per_frame, fps, face_track_fraction, n_frames, face_hits)."""
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
    """Linear-interpolate resample `values` from src_rate to dst_rate."""
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
    """Z-score normalize (zero mean, unit std)."""
    import numpy as np

    arr = np.asarray(values, dtype=float)
    arr = arr - arr.mean()
    std = arr.std()
    if std < 1e-9:
        return [0.0] * len(arr)
    return (arr / std).tolist()


def _cross_correlate(visual: list[float], audio: list[float], rate: float,
                     search_ms: int) -> tuple[int, float]:
    """Return (best_lag_samples, peak_confidence) where lag>0 means audio leads."""
    import numpy as np

    vis = np.asarray(visual, dtype=float)
    aud = np.asarray(audio, dtype=float)
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
        denom = np.linalg.norm(v) * np.linalg.norm(a)
        if denom < 1e-12:
            continue
        corr = float(np.dot(v, a) / denom)
        if corr > best:
            best = corr
            best_lag = lag
    return best_lag, best
