"""Tests for audiovisual lipsync scoring (Ticket LB-601)."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.lipsync_scoring import score_lipsync, record_lipsync_evidence, PASS_THRESHOLD, REVIEW_THRESHOLD


class TestLipsyncScoring:
    @patch('scripts.lipsync_scoring.subprocess.run')
    @patch('scripts.lipsync_scoring._estimate_audio_energy')
    def test_aligned_talking_head_passes(self, mock_energy, mock_subprocess):
        """Verify that a standard video with audio passes the heuristic check."""
        mock_energy.return_value = 0.5  # Simulate healthy audio energy
        
        # Mock ffprobe to return valid video metadata
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "video", "width": 1280, "height": 720, "duration": "2.0"}]
            }),
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            result = score_lipsync(video_path, audio_path)
            
            assert result["result_state"] == "PASS"
            assert result["score"] >= PASS_THRESHOLD
            assert result["failure_reason"] is None

    @patch('scripts.lipsync_scoring.subprocess.run')
    @patch('scripts.lipsync_scoring._estimate_audio_energy')
    def test_frozen_mouth_fails(self, mock_energy, mock_subprocess):
        """Verify that a video with silent audio (simulating frozen mouth/no speech) fails."""
        mock_energy.return_value = 0.001  # Simulate very low/no audio energy
        
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "video", "width": 1280, "height": 720, "duration": "2.0"}]
            }),
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            result = score_lipsync(video_path, audio_path)
            
            assert result["result_state"] == "FAIL_REGENERATE"
            assert result["score"] < PASS_THRESHOLD
            assert "Low audio energy or frozen mouth" in result["failure_reason"]

    @patch('scripts.lipsync_scoring.subprocess.run')
    def test_no_visible_face_requires_review(self, mock_subprocess):
        """Verify that a video too short for analysis requires review."""
        # Mock ffprobe to return a very short duration
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "video", "width": 1280, "height": 720, "duration": "0.2"}]
            }),
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            result = score_lipsync(video_path, audio_path)
            
            assert result["result_state"] == "REVIEW_REQUIRED"
            assert result["confidence"] < 0.5
            assert "too short" in result["failure_reason"]

    def test_missing_artifacts_fails(self):
        """Verify that missing input artifacts result in FAIL_REGENERATE."""
        result = score_lipsync(Path("/nonexistent/video.mp4"), Path("/nonexistent/audio.wav"))
        
        assert result["result_state"] == "FAIL_REGENERATE"
        assert result["failure_reason"] == "Input artifacts missing"

    @patch('scripts.lipsync_scoring.subprocess.run')
    @patch('scripts.lipsync_scoring._estimate_audio_energy')
    def test_evidence_recording_includes_required_fields(self, mock_energy, mock_subprocess):
        """Verify that the scored evidence contains all required fields."""
        mock_energy.return_value = 0.5
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "video", "width": 1280, "height": 720, "duration": "2.0"}]
            }),
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            result = score_lipsync(video_path, audio_path)
            
            # Check all required fields from the plan
            assert "score" in result
            assert "offset_estimate_ms" in result
            assert "confidence" in result
            assert "algorithm_version" in result
            assert "input_artifact_hashes" in result
            assert "video" in result["input_artifact_hashes"]
            assert "audio" in result["input_artifact_hashes"]
            assert "pass_threshold" in result
            assert "review_threshold" in result
            assert "failure_reason" in result
            assert "result_state" in result

    @patch('scripts.lipsync_scoring._db._now')
    @patch('scripts.lipsync_scoring._db.transaction')
    @patch('scripts.lipsync_scoring.subprocess.run')
    @patch('scripts.lipsync_scoring._estimate_audio_energy')
    def test_record_lipsync_evidence_saves_to_db(self, mock_energy, mock_subprocess, mock_transaction, mock_now):
        """Verify that lipsync evidence is correctly formatted and saved to the DB."""
        mock_energy.return_value = 0.5
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"codec_type": "video", "width": 1280, "height": 720, "duration": "2.0"}]
            }),
            stderr=""
        )
        mock_now.return_value = "2026-01-01T00:00:00Z"
        
        mock_conn = MagicMock()
        # Mock the context manager for transaction
        mock_transaction.return_value.__enter__.return_value = mock_conn
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            evidence = record_lipsync_evidence(
                production_id="prod_1",
                render_unit_id="ru_1",
                video_path=video_path,
                audio_path=audio_path,
                db_path="test.db"
            )
            
            # Verify the INSERT statement was called with correct structure
            assert mock_conn.execute.called
            call_args = mock_conn.execute.call_args[0]
            sql = call_args[0]
            params = call_args[1]
            
            assert "lipsync_score" in sql
            assert params[1] == "prod_1"
            assert params[2] == "ru_1"
            assert params[3] == "lipsync_scoring_v1"
            
            # Verify evidence JSON is valid (it's at index 6)
            evidence_json = json.loads(params[6])
            assert evidence_json["result_state"] == evidence["result_state"]
