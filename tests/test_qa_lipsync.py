"""Tests for QA lipsync guardrails (Ticket LB-203)."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.qa_lipsync import (
    detect_lipsync_drift_ms,
    detect_freeze_frames,
    detect_black_frames,
    validate_audio_presence,
    run_lipsync_qa,
    MAX_LIPSYNC_DRIFT_MS,
    MAX_FREEZE_DURATION_SEC,
)


class TestLipsyncDriftDetection:
    @patch("subprocess.run")
    def test_lipsync_drift_detected_and_rejected(self, mock_run):
        """Verify that drift exceeding MAX_LIPSYNC_DRIFT_MS is detected."""
        # Mock ffprobe to return video and audio durations with >50ms drift
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [
                    {"codec_type": "video", "duration": "5.0"},
                    {"codec_type": "audio", "duration": "5.2"}  # 200ms drift
                ]
            }),
            stderr=""
        )
        
        video_path = Path("/tmp/test.mp4")
        has_drift, drift_ms, msg = detect_lipsync_drift_ms(video_path, expected_duration_ms=5000)
        
        assert has_drift is True
        assert drift_ms == 200
        assert "exceeds max" in msg

    @patch("subprocess.run")
    def test_valid_lipsync_clip_passes_qa(self, mock_run):
        """Verify that drift within tolerance passes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [
                    {"codec_type": "video", "duration": "5.0"},
                    {"codec_type": "audio", "duration": "5.02"}  # 20ms drift, within 50ms tolerance
                ]
            }),
            stderr=""
        )
        
        video_path = Path("/tmp/test.mp4")
        has_drift, drift_ms, msg = detect_lipsync_drift_ms(video_path, expected_duration_ms=5000)
        
        assert has_drift is False
        assert drift_ms == 20
        assert msg == "OK"


class TestFreezeFrameDetection:
    @patch("scripts.qa_lipsync._run_ffmpeg_filter")
    def test_freeze_frame_detected_and_rejected(self, mock_filter):
        """Verify that freeze frames exceeding threshold are detected."""
        mock_filter.return_value = """
        [Parsed_freezedetect_0 @ 0x...] freeze_start: 1.0
        [Parsed_freezedetect_0 @ 0x...] freeze_end: 2.0
        """
        
        video_path = Path("/tmp/test.mp4")
        has_freeze, freezes, msg = detect_freeze_frames(video_path, threshold_sec=0.5)
        
        assert has_freeze is True
        assert len(freezes) == 1
        assert freezes[0]["duration"] == 1.0
        assert "Detected 1 freeze segments" in msg

    @patch("scripts.qa_lipsync._run_ffmpeg_filter")
    def test_no_freeze_frame_passes(self, mock_filter):
        """Verify that short freezes below threshold are ignored (ffmpeg returns nothing)."""
        # If ffmpeg finds no freezes above threshold, it returns no freeze_start/end lines
        mock_filter.return_value = ""
        
        video_path = Path("/tmp/test.mp4")
        has_freeze, freezes, msg = detect_freeze_frames(video_path, threshold_sec=0.5)
        
        assert has_freeze is False
        assert len(freezes) == 0
        assert msg == "OK"


class TestBlackFrameDetection:
    @patch("scripts.qa_lipsync._run_ffmpeg_filter")
    def test_black_frame_detected_and_rejected(self, mock_filter):
        """Verify that black frames exceeding threshold are detected."""
        mock_filter.return_value = """
        [Parsed_blackdetect_0 @ 0x...] black_start: 2.0
        [Parsed_blackdetect_0 @ 0x...] black_end: 3.0
        """
        
        video_path = Path("/tmp/test.mp4")
        has_black, blacks, msg = detect_black_frames(video_path, threshold_sec=0.5)
        
        assert has_black is True
        assert len(blacks) == 1
        assert blacks[0]["duration"] == 1.0


class TestAudioPresenceValidation:
    @patch("subprocess.run")
    def test_silent_audio_detected_and_rejected(self, mock_run):
        """Verify that silent audio is detected and rejected."""
        def side_effect(cmd, *args, **kwargs):
            if "ffprobe" in cmd[0]:
                return MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "audio"}]}), stderr="")
            else:
                # ffmpeg ebur128 output with very low volume
                return MagicMock(returncode=0, stdout="", stderr="I: -50.0 LUFS")
        
        mock_run.side_effect = side_effect
        
        video_path = Path("/tmp/test.mp4")
        is_valid, avg_db, msg = validate_audio_presence(video_path, min_db=-40.0)
        
        assert is_valid is False
        assert avg_db == -50.0
        assert "too silent" in msg

    @patch("subprocess.run")
    def test_valid_audio_passes(self, mock_run):
        """Verify that audio with sufficient volume passes."""
        def side_effect(cmd, *args, **kwargs):
            if "ffprobe" in cmd[0]:
                return MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "audio"}]}), stderr="")
            else:
                return MagicMock(returncode=0, stdout="", stderr="I: -20.0 LUFS")
        
        mock_run.side_effect = side_effect
        
        video_path = Path("/tmp/test.mp4")
        is_valid, avg_db, msg = validate_audio_presence(video_path, min_db=-40.0)
        
        assert is_valid is True
        assert avg_db == -20.0
        assert msg == "OK"


class TestIntegratedLipsyncQA:
    @patch("pathlib.Path.exists", return_value=True)
    @patch("scripts.qa_lipsync.detect_lipsync_drift_ms")
    @patch("scripts.qa_lipsync.detect_freeze_frames")
    @patch("scripts.qa_lipsync.detect_black_frames")
    @patch("scripts.qa_lipsync.validate_audio_presence")
    def test_run_lipsync_qa_fails_on_drift(self, mock_audio, mock_black, mock_freeze, mock_drift, mock_exists):
        """Verify that run_lipsync_qa fails when drift is detected."""
        mock_drift.return_value = (True, 100, "Drift too high")
        mock_freeze.return_value = (False, [], "OK")
        mock_black.return_value = (False, [], "OK")
        mock_audio.return_value = (True, -20.0, "OK")
        
        video_path = Path("/tmp/test.mp4")
        results = run_lipsync_qa(video_path, expected_duration_ms=5000, is_hero_lipsync=True)
        
        assert results["status"] == "fail"
        assert "Drift too high" in results["issues"]
        assert results["checks"]["lipsync_drift"]["passed"] is False
