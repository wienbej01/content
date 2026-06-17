"""Tests for R6-003 visual safe boundary QA."""
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from safe_boundary_qa import (
    validate_safe_boundaries, register_face_detector, FaceDetector,
    NoDetectorLoaded,
)


def _make_test_video(path: Path, duration: float):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={duration}:r=24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], capture_output=True, check=True)


def _make_test_audio(path: Path, duration: float):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={duration}",
        "-c:a", "pcm_s16le", str(path),
    ], capture_output=True, check=True)


class TestSafeBoundaryValidation:
    @pytest.fixture(autouse=True)
    def reset_detector(self):
        from safe_boundary_qa import _registered_detector
        _registered_detector = None
        yield
        _registered_detector = None

    def test_no_detector_returns_review_required(self, tmp_path):
        """Without real detector, returns review_required."""
        video = tmp_path / "test.mp4"
        audio = tmp_path / "test.wav"
        _make_test_video(video, 5.0)
        _make_test_audio(audio, 5.0)

        result = validate_safe_boundaries(video, audio, [1.0, 3.0])
        assert result["status"] == "review_required"
        assert any("NO_REAL_DETECTOR_LOADED" in i for i in result["issues"])

    def test_unstable_startup_fails_with_detector(self, tmp_path):
        """Cut in startup region fails."""
        video = tmp_path / "test.mp4"
        audio = tmp_path / "test.wav"
        _make_test_video(video, 5.0)
        _make_test_audio(audio, 5.0)

        fake = MagicMock(spec=FaceDetector)
        fake.load.return_value = True
        fake.detect_landmarks.return_value = {"face_bbox": [10, 10, 100, 100], "mouth_aperture": 0.3}
        fake.detector_info = {"name": "fake", "version": "1.0"}
        register_face_detector(fake)

        result = validate_safe_boundaries(video, audio, [0.2])
        assert result["status"] == "fail"

    def test_unstable_terminal_fails_with_detector(self, tmp_path):
        """Cut in terminal region fails."""
        video = tmp_path / "test.mp4"
        audio = tmp_path / "test.wav"
        _make_test_video(video, 5.0)
        _make_test_audio(audio, 5.0)

        fake = MagicMock(spec=FaceDetector)
        fake.load.return_value = True
        fake.detect_landmarks.return_value = {"face_bbox": [10, 10, 100, 100], "mouth_aperture": 0.3}
        fake.detector_info = {"name": "fake", "version": "1.0"}
        register_face_detector(fake)

        result = validate_safe_boundaries(video, audio, [4.8])
        assert result["status"] == "fail"

    def test_missing_artifacts_fails(self, tmp_path):
        """Missing files fail regardless of detector."""
        result = validate_safe_boundaries(tmp_path / "nonexistent.mp4", tmp_path / "nonexistent.wav", [1.0])
        assert result["status"] == "fail"

    def test_zero_duration_fails(self, tmp_path):
        """Zero-duration video fails."""
        video = tmp_path / "empty.mp4"
        video.write_bytes(b"not a video")
        audio = tmp_path / "test.wav"
        _make_test_audio(audio, 5.0)

        result = validate_safe_boundaries(video, audio, [1.0])
        assert result["status"] == "fail"

    def test_result_includes_detector_info(self, tmp_path):
        """Detector info is included in result."""
        video = tmp_path / "test.mp4"
        audio = tmp_path / "test.wav"
        _make_test_video(video, 5.0)
        _make_test_audio(audio, 5.0)

        result = validate_safe_boundaries(video, audio, [2.0])
        assert "detector_info" in result
        assert "has_real_detector" in result
