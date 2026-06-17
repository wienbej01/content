"""Tests for safe-boundary validation (Ticket LB-602)."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.safe_boundary_qa import validate_safe_boundaries, record_safe_boundary_evidence


class TestSafeBoundaryValidation:
    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_safe_pause_passes(self, mock_subprocess):
        """Verify that a cut point during a safe pause (low audio energy) passes."""
        # Mock ffprobe for duration
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="5.0",
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            # Mock _estimate_audio_energy_at to return low energy (safe pause)
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.01):
                result = validate_safe_boundaries(
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[2.0]  # Cut in the middle, safe pause
                )
                
                assert result["status"] == "pass"
                assert not result["issues"]

    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_cut_mid_word_fails(self, mock_subprocess):
        """Verify that a cut point during active speech (high audio energy) fails."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="5.0",
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            # Mock _estimate_audio_energy_at to return high energy (active speech)
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.5):
                result = validate_safe_boundaries(
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[2.0]
                )
                
                assert result["status"] == "fail"
                assert any("cuts through active speech" in issue for issue in result["issues"])

    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_unstable_first_frames_fail(self, mock_subprocess):
        """Verify that a cut point in the unstable startup region fails."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="5.0",
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.01):
                result = validate_safe_boundaries(
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[0.2]  # < 0.5s unstable startup
                )
                
                assert result["status"] == "fail"
                assert any("unstable startup region" in issue for issue in result["issues"])

    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_unstable_terminal_frames_fail(self, mock_subprocess):
        """Verify that a cut point in the unstable terminal region fails."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="5.0",
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.01):
                result = validate_safe_boundaries(
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[4.8]  # > 4.5s unstable terminal (5.0 - 0.5)
                )
                
                assert result["status"] == "fail"
                assert any("unstable terminal region" in issue for issue in result["issues"])

    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_approved_return_interval_passes(self, mock_subprocess):
        """Verify that a cut within an approved return-to-hero interval passes."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="10.0",
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            approved_intervals = [
                {"start_sec": 4.0, "end_sec": 6.0}
            ]
            
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.01):
                result = validate_safe_boundaries(
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[5.0],  # Within approved interval
                    approved_return_intervals=approved_intervals
                )
                
                assert result["status"] == "pass"
                assert not result["issues"]

    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_unapproved_return_interval_fails(self, mock_subprocess):
        """Verify that a cut outside approved return-to-hero intervals fails."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="10.0",
            stderr=""
        )
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            approved_intervals = [
                {"start_sec": 4.0, "end_sec": 6.0}
            ]
            
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.01):
                result = validate_safe_boundaries(
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[8.0],  # Outside approved interval
                    approved_return_intervals=approved_intervals
                )
                
                assert result["status"] == "fail"
                assert any("not within any approved return-to-hero interval" in issue for issue in result["issues"])

    def test_missing_artifacts_fails(self):
        """Verify that missing input artifacts result in immediate failure."""
        result = validate_safe_boundaries(
            video_path=Path("/nonexistent/video.mp4"),
            audio_path=Path("/nonexistent/audio.wav"),
            cut_points_sec=[1.0]
        )
        
        assert result["status"] == "fail"
        assert "Input artifacts missing" in result["issues"]

    @patch('scripts.safe_boundary_qa._db.transaction')
    @patch('scripts.safe_boundary_qa._db._now')
    @patch('scripts.safe_boundary_qa.subprocess.run')
    def test_record_safe_boundary_evidence_saves_to_db(self, mock_subprocess, mock_now, mock_transaction):
        """Verify that safe boundary evidence is correctly formatted and saved to the DB."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="5.0",
            stderr=""
        )
        mock_now.return_value = "2026-01-01T00:00:00Z"
        
        mock_conn = MagicMock()
        mock_transaction.return_value.__enter__.return_value = mock_conn
        
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            audio_path = Path(td) / "audio.wav"
            video_path.write_bytes(b"fake video")
            audio_path.write_bytes(b"fake audio")
            
            with patch('scripts.safe_boundary_qa._estimate_audio_energy_at', return_value=0.01):
                evidence = record_safe_boundary_evidence(
                    production_id="prod_1",
                    render_unit_id="ru_1",
                    video_path=video_path,
                    audio_path=audio_path,
                    cut_points_sec=[2.0],
                    db_path="test.db"
                )
                
                # Verify the INSERT statement was called with correct structure
                assert mock_conn.execute.called
                call_args = mock_conn.execute.call_args[0]
                sql = call_args[0]
                params = call_args[1]
                
                assert "safe_boundary" in sql
                assert params[1] == "prod_1"
                assert params[2] == "ru_1"
                assert params[3] == "safe_boundary_v1"
                
                # Verify evidence JSON is valid (it's at index 6)
                evidence_json = json.loads(params[6])
                assert evidence_json["status"] == evidence["status"]
