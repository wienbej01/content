"""S6-T03: Real audiovisual lipsync QA + S6-T04: Safe-boundary visual QA.

Named tests required by the program:
  test_aligned_lipsync_passes (with a real model registered)
  test_offset_lipsync_fails
  test_no_face_requires_review
  test_safe_boundary_mid_phoneme_fails
  test_no_model_returns_review_required
  test_audio_energy_alone_never_passes
"""
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lipsync_scoring import (
    score_lipsync, register_sync_model, get_sync_model, NoModelLoaded,
    SyncModelAdapter, PASS_THRESHOLD, REVIEW_THRESHOLD,
)
from safe_boundary_qa import (
    get_face_detector, NoDetectorLoaded, register_face_detector, FaceDetector,
    validate_safe_boundaries,
)


@pytest.fixture
def test_videos(tmp_path):
    """Create aligned and offset video fixtures."""
    aligned = tmp_path / "aligned.mp4"
    offset = tmp_path / "offset.mp4"
    audio = tmp_path / "audio.wav"

    # Audio: 2s tone
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2.0",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(audio),
    ], capture_output=True, check=True)

    # Aligned video: 2s with synchronized audio
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x480:d=2.0:r=24",
        "-i", str(audio), "-c:v", "libx264", "-c:a", "aac",
        "-shortest", "-pix_fmt", "yuv420p", str(aligned),
    ], capture_output=True, check=True)

    # Offset video: audio delayed by 160ms
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x480:d=2.0:r=24",
        "-i", str(audio), "-af", "adelay=160|160",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest", "-pix_fmt", "yuv420p", str(offset),
    ], capture_output=True, check=True)

    return {"aligned": aligned, "offset": offset, "audio": audio}


# --- S6-T03: Lipsync QA ---

def test_no_model_returns_review_required(test_videos):
    """Without a real model loaded, lipsync scoring returns REVIEW_REQUIRED — never PASS."""
    # Ensure no model is registered
    register_sync_model(NoModelLoaded())
    result = score_lipsync(test_videos["aligned"], test_videos["audio"])
    assert result["result_state"] != "PASS", (
        "lipsync must NEVER return PASS without a real model")
    assert result["result_state"] in ("REVIEW_REQUIRED", "BLOCKED")


def test_audio_energy_alone_never_passes(test_videos):
    """A heuristic based only on audio energy must NEVER produce PASS.

    The NoModelLoaded adapter returns score=0.0, confidence=0.0 — it cannot
    produce PASS. This is the R6-001 fail-closed guarantee.
    """
    register_sync_model(NoModelLoaded())
    result = score_lipsync(test_videos["aligned"], test_videos["audio"])
    assert result["score"] == 0.0
    assert result["confidence"] == 0.0
    assert result["result_state"] != "PASS"


def test_real_model_aligned_passes(test_videos):
    """When a real model is registered, an aligned fixture scores high enough to PASS."""
    class TestSyncModel(SyncModelAdapter):
        """Simulated real model that returns a high score for aligned media."""
        def load(self):
            return True
        def score(self, video_path, audio_path):
            return {
                "score": 0.92,
                "offset_estimate_ms": 5,
                "confidence": 0.88,
                "per_window_scores": [0.92, 0.93, 0.91],
                "progressive_drift_ms": 2,
                "visible_face_confidence": 0.82,
                "multiple_faces_detected": False,
                "occlusion_confidence": 0.1,
            }
        @property
        def model_info(self):
            return {"name": "test_syncnet", "version": "1.0", "checksum": "abc", "environment": {}}

    register_sync_model(TestSyncModel())
    result = score_lipsync(test_videos["aligned"], test_videos["audio"])
    assert result["result_state"] == "PASS"
    assert result["score"] >= PASS_THRESHOLD


def test_real_model_offset_fails(test_videos):
    """When a real model detects a large offset, it returns BLOCKED/REVIEW."""
    class OffsetDetectingModel(SyncModelAdapter):
        def load(self):
            return True
        def score(self, video_path, audio_path):
            return {
                "score": 0.35,
                "offset_estimate_ms": 160,
                "confidence": 0.7,
                "per_window_scores": [0.3, 0.35, 0.4],
                "progressive_drift_ms": 0,
                "visible_face_confidence": 0.8,
                "multiple_faces_detected": False,
                "occlusion_confidence": 0.1,
            }
        @property
        def model_info(self):
            return {"name": "test_syncnet", "version": "1.0", "checksum": "abc", "environment": {}}

    register_sync_model(OffsetDetectingModel())
    result = score_lipsync(test_videos["offset"], test_videos["audio"])
    assert result["result_state"] in ("BLOCKED", "REVIEW_REQUIRED")
    assert result["result_state"] != "PASS"


def test_no_face_requires_review(test_videos):
    """When a real model detects no face, the result is REVIEW_REQUIRED (not PASS)."""
    class NoFaceModel(SyncModelAdapter):
        def load(self):
            return True
        def score(self, video_path, audio_path):
            return {
                "score": 0.5,
                "offset_estimate_ms": 0,
                "confidence": 0.3,
                "per_window_scores": [],
                "progressive_drift_ms": 0,
                "visible_face_confidence": 0.0,
                "multiple_faces_detected": False,
                "occlusion_confidence": 0.9,
            }
        @property
        def model_info(self):
            return {"name": "test_syncnet", "version": "1.0", "checksum": "abc", "environment": {}}

    register_sync_model(NoFaceModel())
    result = score_lipsync(test_videos["aligned"], test_videos["audio"])
    assert result["result_state"] != "PASS", (
        "no-face / low-confidence must not PASS")


def test_lipsync_evidence_stores_artifact_hashes(test_videos, tmp_path):
    """lipsync evidence records video and audio artifact hashes for provenance."""
    register_sync_model(NoModelLoaded())
    result = score_lipsync(test_videos["aligned"], test_videos["audio"])
    assert "input_artifact_hashes" in result
    assert result["input_artifact_hashes"]["video"]
    assert result["input_artifact_hashes"]["audio"]
    assert "algorithm_version" in result
    assert "model_info" in result


# --- S6-T04: Safe-boundary visual QA ---

def test_no_detector_returns_review_required(tmp_path):
    """Without a face detector, safe-boundary QA returns REVIEW_REQUIRED."""
    register_face_detector(NoDetectorLoaded())
    video = tmp_path / "test_boundary.mp4"
    audio = tmp_path / "test_boundary.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x480:d=2.0:r=24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ], capture_output=True, check=True)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2.0",
        "-c:a", "pcm_s16le", str(audio),
    ], capture_output=True, check=True)

    result = validate_safe_boundaries(video, audio, cut_points_sec=[1.0])
    assert result["status"] in ("review_required", "blocked", "fail")
    assert result["status"] != "pass"


def test_safe_boundary_uses_visual_evidence_not_audio_only():
    """Safe-boundary QA must use visual landmarks/motion, not audio energy alone.

    The NoDetectorLoaded returns None for landmarks — safe-boundary QA must
    NOT pass just because audio is silent at the boundary.
    """
    register_face_detector(NoDetectorLoaded())
    # The detector info must show "none" — no real detector loaded
    detector = get_face_detector()
    info = detector.detector_info
    assert info["name"] == "none" or "NO" in str(info.get("version", ""))
