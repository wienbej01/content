"""Tests for R6-001 fail-closed lipsync scoring."""
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lipsync_scoring import (
    score_lipsync, record_lipsync_evidence,
    register_sync_model, get_sync_model, SyncModelAdapter, NoModelLoaded,
    PASS_THRESHOLD, REVIEW_THRESHOLD,
)


class FakeSyncedModel(SyncModelAdapter):
    """A test model that returns a high sync score for testing."""
    def __init__(self, score=0.90, confidence=0.95, offset=0):
        self._score = score
        self._confidence = confidence
        self._offset = offset

    def load(self) -> bool:
        return True

    def score(self, video_path, audio_path):
        return {
            "score": self._score,
            "offset_estimate_ms": self._offset,
            "confidence": self._confidence,
            "per_window_scores": [self._score],
            "progressive_drift_ms": 0,
            "visible_face_confidence": 1.0,
            "multiple_faces_detected": False,
            "occlusion_confidence": 0.0,
        }

    @property
    def model_info(self):
        return {"name": "fake_synced", "version": "test_1.0", "checksum": "abc", "environment": {}}


class TestLipsyncScoring:
    @pytest.fixture(autouse=True)
    def reset_model(self):
        """Reset registered model between tests."""
        from lipsync_scoring import _registered_model
        import lipsync_scoring
        _registered_model = None
        lipsync_scoring._sync_scorer_adapter = None
        yield
        _registered_model = None
        lipsync_scoring._sync_scorer_adapter = None

    def test_no_model_returns_review_required(self, tmp_path):
        """Without a real model, score returns REVIEW_REQUIRED."""
        video = tmp_path / "test.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       capture_output=True, check=True)
        audio = tmp_path / "test.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100",
                        "-q:a", "9", str(audio)], capture_output=True, check=True)

        result = score_lipsync(video, audio)
        assert result["result_state"] == "REVIEW_REQUIRED"
        assert "NO_REAL_MODEL_LOADED" in result["failure_reason"]

    def test_with_synced_model_returns_pass(self, tmp_path):
        """A loaded synced model returns PASS for aligned input."""
        register_sync_model(FakeSyncedModel(score=0.90, confidence=0.95))

        video = tmp_path / "test.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       capture_output=True, check=True)
        audio = tmp_path / "test.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100",
                        "-q:a", "9", str(audio)], capture_output=True, check=True)

        result = score_lipsync(video, audio)
        assert result["result_state"] == "PASS"
        assert result["score"] >= PASS_THRESHOLD

    def test_with_model_low_score_blocks(self, tmp_path):
        """A loaded model that scores below threshold returns BLOCKED."""
        register_sync_model(FakeSyncedModel(score=0.20, confidence=0.95))

        video = tmp_path / "test.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       capture_output=True, check=True)
        audio = tmp_path / "test.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100",
                        "-q:a", "9", str(audio)], capture_output=True, check=True)

        result = score_lipsync(video, audio)
        assert result["result_state"] == "BLOCKED"

    def test_no_visible_face_requires_review(self, tmp_path):
        """Short video returns REVIEW_REQUIRED."""
        video = tmp_path / "short.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=0.3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       capture_output=True, check=True)
        audio = tmp_path / "short.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100:duration=0.3",
                        "-q:a", "9", str(audio)], capture_output=True, check=True)

        result = score_lipsync(video, audio)
        assert result["result_state"] == "REVIEW_REQUIRED"

    def test_missing_artifacts_returns_blocked(self, tmp_path):
        """Missing files return BLOCKED."""
        result = score_lipsync(tmp_path / "nonexistent.mp4", tmp_path / "nonexistent.mp3")
        assert result["result_state"] == "BLOCKED"

    def test_result_includes_model_info(self, tmp_path):
        """Result includes model checksum/version metadata."""
        register_sync_model(FakeSyncedModel())

        video = tmp_path / "test.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       capture_output=True, check=True)
        audio = tmp_path / "test.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100",
                        "-q:a", "9", str(audio)], capture_output=True, check=True)

        result = score_lipsync(video, audio)
        assert "model_info" in result
        assert result["model_info"]["name"] == "fake_synced"
        assert "input_artifact_hashes" in result
