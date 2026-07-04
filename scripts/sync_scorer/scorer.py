"""TKT-102: Sync scorer backends and the SyncScore result type.

Provides:
  - SyncScore: structured result from a sync scorer
  - FixtureSyncBackend: deterministic fixture for tests (no mediapipe dep)
  - RealSyncBackend: MediaPipe face-landmark mouth-envelope cross-correlation
  - get_sync_scorer_backend(): reads SYNC_SCORER_BACKEND env and returns
    the appropriate backend instance, or None when unavailable
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ._algorithm import (
    DEFAULT_MODEL_PATH,
    REAL_METHOD,
    REAL_MODEL_NAME,
    _SEARCH_WINDOW_MS,
    _audio_envelope,
    _check_real_deps,
    _cross_correlate,
    _mouth_envelope,
    _normalize,
    _resample,
)


@dataclass
class SyncScore:
    """Structured result from a face-tracked AV-sync scorer."""

    offset_ms: float
    confidence: float
    face_track_found: bool
    face_track_fraction: float = 0.0
    method: str = ""
    model_version: str = ""
    video_sha: str = ""
    audio_sha: str = ""
    frames_processed: int = 0
    face_hits: int = 0
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fixture backend (test-only, deterministic)
# ---------------------------------------------------------------------------


class FixtureSyncBackend:
    """Deterministic sync scorer for tests.

    Configured via constructor parameters to simulate various outcomes:
      - Default: offset_ms=10, confidence=0.8, face_track_found=True
      - Low confidence: offset_ms=50, confidence=0.05, face_track_found=False
      - Unavailable: availability() returns False
    """

    def __init__(
        self,
        offset_ms: float = 10.0,
        confidence: float = 0.8,
        face_track_found: bool = True,
        face_track_fraction: float = 1.0,
        available: bool = True,
        method: str = "fixture_sync_scorer",
        model_version: str = "fixture_v1",
    ):
        self._offset_ms = offset_ms
        self._confidence = confidence
        self._face_track_found = face_track_found
        self._face_track_fraction = face_track_fraction
        self._available = available
        self._method = method
        self._model_version = model_version

    def availability(self) -> bool:
        return self._available

    def score(self, video_path: Path, audio_path: Path) -> SyncScore:
        if not self._available:
            raise RuntimeError("fixture backend not available")
        return SyncScore(
            offset_ms=self._offset_ms,
            confidence=self._confidence,
            face_track_found=self._face_track_found,
            face_track_fraction=self._face_track_fraction,
            method=self._method,
            model_version=self._model_version,
            video_sha="fixture",
            audio_sha="fixture",
        )


# ---------------------------------------------------------------------------
# Real backend — MediaPipe face-landmark mouth-envelope xcorr
# ---------------------------------------------------------------------------


class RealSyncBackend:
    """Production sync scorer using MediaPipe FaceLandmarker + audio xcorr.

    Implements the scorer selected by TKT-101 discovery:
    face-landmark mouth-envelope x audio-envelope cross-correlation.
    Requires mediapipe, opencv-contrib-python, numpy, and the
    FaceLandmarker .task model file.

    Algorithmic primitives are shared with the TKT-101 discovery spike
    via scripts/sync_scorer/_algorithm.py.
    """

    def __init__(self, model_path: Optional[Path] = None):
        self._model_path = model_path or Path(
            os.environ.get("TKT101_FACE_LANDMARKER_MODEL", DEFAULT_MODEL_PATH)
        )
        self._deps = None

    def availability(self) -> bool:
        deps_ok, self._deps = _check_real_deps()
        return deps_ok and self._model_path.exists()

    def score(self, video_path: Path, audio_path: Path) -> SyncScore:
        deps_ok, deps = _check_real_deps()
        if not deps_ok:
            raise RuntimeError(
                f"RealSyncBackend dependencies missing: {deps}"
            )
        if not self._model_path.exists():
            raise RuntimeError(
                f"FaceLandmarker model not found: {self._model_path}"
            )

        mouth, vfps, face_frac, frames, face_hits = _mouth_envelope(
            video_path, self._model_path
        )
        if face_hits == 0:
            return SyncScore(
                offset_ms=0.0,
                confidence=0.0,
                face_track_found=False,
                face_track_fraction=0.0,
                method=REAL_METHOD,
                model_version=REAL_MODEL_NAME,
                frames_processed=frames,
                face_hits=0,
            )

        audio_env, arate = _audio_envelope(audio_path)
        if not audio_env:
            return SyncScore(
                offset_ms=0.0,
                confidence=0.0,
                face_track_found=face_frac >= 0.5,
                face_track_fraction=round(face_frac, 4),
                method=REAL_METHOD,
                model_version=REAL_MODEL_NAME,
                frames_processed=frames,
                face_hits=face_hits,
            )

        vis_resampled = _resample(mouth, vfps, arate)
        vis_norm = _normalize(vis_resampled)
        aud_norm = _normalize(audio_env)

        best_lag, peak = _cross_correlate(vis_norm, aud_norm, arate, _SEARCH_WINDOW_MS)
        offset_ms = round(best_lag * (1000.0 / arate), 1)

        return SyncScore(
            offset_ms=offset_ms,
            confidence=round(peak, 4),
            face_track_found=face_frac >= 0.5,
            face_track_fraction=round(face_frac, 4),
            method=REAL_METHOD,
            model_version=REAL_MODEL_NAME,
            frames_processed=frames,
            face_hits=face_hits,
            extra={
                "audio_envelope_rate_hz": round(arate, 2),
                "search_window_ms": _SEARCH_WINDOW_MS,
                "video_fps": vfps,
            },
        )


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

_registered_backend: Optional[FixtureSyncBackend | RealSyncBackend] = None


def _set_sync_scorer_backend(backend: Optional[FixtureSyncBackend | RealSyncBackend]) -> None:
    """Override backend selection (for tests)."""
    global _registered_backend
    _registered_backend = backend


def get_sync_scorer_backend() -> Optional[FixtureSyncBackend | RealSyncBackend]:
    """Return the configured sync scorer backend, or None if unavailable.

    Selection order:
      1. If a backend was registered via _set_sync_scorer_backend(), use it.
      2. Read SYNC_SCORER_BACKEND env var:
         - "fixture" -> FixtureSyncBackend()
         - "real"    -> RealSyncBackend()
         - otherwise -> None (fail-closed)
    """
    global _registered_backend
    if _registered_backend is not None:
        return _registered_backend

    backend_name = os.environ.get("SYNC_SCORER_BACKEND", "none")
    if backend_name == "fixture":
        return FixtureSyncBackend()
    elif backend_name == "real":
        return RealSyncBackend()
    return None
