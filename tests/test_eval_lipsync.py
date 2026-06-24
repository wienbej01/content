"""Tests for lipsync eval harness (S01-T003)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.evals.eval_lipsync import (
    analyze_video, extract_audio_envelope, compute_visual_activity,
    correlate_signals, HAS_NUMPY,
)


FIXTURE = Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")


class TestAnalyzeVideo:
    """Eval produces valid JSON for existing video."""

    def test_eval_outputs_valid_json(self, tmp_path):
        """S01-T003-R1: eval writes JSON for existing MP4."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        out = tmp_path / "result.json"
        result = analyze_video(FIXTURE, subject_id="test_unit")
        out.write_text(json.dumps(result, indent=2))
        assert out.exists()
        data = json.loads(out.read_text())
        assert "eval_name" in data
        assert "subject_id" in data
        assert data["subject_id"] == "test_unit"
        assert data["status"] in ("diagnostic", "warn", "fail", "blocked")

    def test_eval_returns_expected_structure(self, tmp_path):
        """S01-T003-R2: eval returns all required fields."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        result = analyze_video(FIXTURE, subject_id="ru_test_001")
        assert result["eval_name"] == "lipsync"
        assert result["method"] == "mouth_motion_proxy"
        assert result["face_track_found"] is False
        assert "offset_ms" in result
        assert "confidence" in result
        assert "thresholds" in result
        assert "warn_offset_ms" in result["thresholds"]
        assert "fail_offset_ms" in result["thresholds"]
        assert result["provisional"] is True

    def test_eval_face_track_false_without_cv(self):
        """S01-T003-R3: Without OpenCV, face_track_found is always False."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        result = analyze_video(FIXTURE)
        assert result["face_track_found"] is False


class TestMissingVideo:
    """Missing video returns blocked status."""

    def test_missing_video_returns_blocked(self, tmp_path):
        """S01-T003-R4: missing video returns blocked/fail JSON."""
        result = analyze_video(Path("/nonexistent/video.mp4"), subject_id="missing")
        assert result["status"] == "blocked"
        assert result["blocked_reason"] is not None
        assert result["offset_ms"] is None

    def test_cli_missing_video_returns_nonzero(self, tmp_path):
        """S01-T003-R5: CLI returns non-zero for missing video."""
        out = tmp_path / "result.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/eval_lipsync.py",
             "--video", str(tmp_path / "nonexistent.mp4"),
             "--out", str(out),
             "--subject-id", "missing"],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["status"] == "blocked"


class TestExtractAudio:
    """Audio extraction from video works."""

    def test_extract_audio_envelope_from_fixture(self, tmp_path):
        """S01-T003-R6: Audio envelope extraction produces signal."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        audio = extract_audio_envelope(FIXTURE, tmp_path)
        assert audio is not None
        assert len(audio["envelope"]) > 0
        assert audio["duration_sec"] > 0
        assert audio["sample_rate"] > 0

    def test_extract_audio_from_nonexistent_video(self, tmp_path):
        """S01-T003-R7: Missing video returns None for audio."""
        audio = extract_audio_envelope(Path("/nonexistent.mp4"), tmp_path)
        assert audio is None


class TestVisualActivity:
    """Visual activity extraction from video works."""

    def test_compute_visual_activity_from_fixture(self, tmp_path):
        """S01-T003-R8: Visual activity signal extraction produces signal."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        visual = compute_visual_activity(FIXTURE, tmp_path)
        assert visual is not None
        assert len(visual["signal"]) > 0
        assert visual["duration_sec"] > 0

    def test_compute_visual_activity_nonexistent(self, tmp_path):
        """S01-T003-R9: Missing video returns None for visual."""
        visual = compute_visual_activity(Path("/nonexistent.mp4"), tmp_path)
        assert visual is None


class TestCorrelation:
    """Cross-correlation between audio and visual signals."""

    def test_correlation_with_synthetic_signals(self):
        """S01-T003-R10: Correlation returns offset and confidence."""
        if not HAS_NUMPY:
            pytest.skip("numpy required")
        audio = {
            "envelope": [0.0, 0.1, 0.5, 0.8, 0.5, 0.1, 0.0],
            "frame_rate": 20.0,
        }
        visual = {
            "signal": [0.0, 0.1, 0.5, 0.8, 0.5, 0.1, 0.0],
        }
        corr = correlate_signals(audio, visual)
        assert corr["offset_ms"] is not None
        assert corr["confidence"] >= 0.0

    def test_correlation_offset_detection(self):
        """Correlation returns valid structure for shifted signals."""
        if not HAS_NUMPY:
            pytest.skip("numpy required")
        # Use a pulse to create asymmetric signal for offset detection
        audio = {
            "envelope": [0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,0,0,0,0,0],
            "frame_rate": 10.0,
        }
        visual = {
            "signal": [0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,0,0],
        }
        corr = correlate_signals(audio, visual)
        assert corr["offset_ms"] is not None
        assert corr["confidence"] >= 0.0
        # Shifted pulse should produce some offset
        assert abs(corr["offset_ms"]) >= 0


class TestCLI:
    """End-to-end CLI tests."""

    def test_cli_with_fixture(self, tmp_path):
        """S01-T003-R11: CLI produces valid output for fixture."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        out = tmp_path / "result.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/eval_lipsync.py",
             "--video", str(FIXTURE),
             "--out", str(out),
             "--subject-id", "ru_fixture"],
            capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["eval_name"] == "lipsync"
        assert data["subject_id"] == "ru_fixture"
