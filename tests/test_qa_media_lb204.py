"""Integration tests for qa_media lipsync fail-closed behavior (Ticket LB-204)."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestQAMediaLipsyncFailClosed:
    @patch("scripts.qa_media.audio_duration")
    @patch("scripts.qa_media.run_lipsync_qa")
    @patch("scripts.qa_media.probe")
    @patch("scripts.qa_media.check_blank_screen")
    @patch("scripts.qa_media.check_frozen_video")
    def test_qa_media_fails_on_lipsync_drift(self, mock_frozen, mock_blank, mock_probe, mock_lipsync_qa, mock_audio_dur):
        """Verify that qa_media fails when run_lipsync_qa detects drift."""
        from scripts.qa_media import run_qa
        
        # Mock probe to return valid media info
        mock_probe.return_value = {
            "width": 1920,
            "height": 1080,
            "duration": 5.0,
            "has_audio": True
        }
        mock_audio_dur.return_value = 5.0
        mock_blank.return_value = []
        mock_frozen.return_value = []
        
        # Mock run_lipsync_qa to return a failure
        mock_lipsync_qa.return_value = {
            "status": "fail",
            "issues": ["Lipsync drift 100ms exceeds max 50ms"]
        }
        
        # Create a temporary script file with a hero lipsync segment
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.json"
            media_path = Path(tmpdir) / "test.mp4"
            media_path.write_bytes(b"fake video")
            
            # Create fake audio slice and get its real hash
            audio_slice_path = Path(tmpdir) / "test.mp3"
            audio_slice_path.write_bytes(b"fake audio")
            real_hash = hashlib.sha256(b"fake audio").hexdigest()
            
            script_data = {
                "project_id": "test_proj",
                "segments": [
                    {
                        "id": "001",
                        "media": "test.mp4",
                        "audio_policy": "keep_lipsync",
                        "shot_type": "hero_lipsync",
                        "speech_len_sec": 5.0,
                        "audio_slice": {
                            "file": "test.mp3",
                            "slice_sha256": real_hash,
                            "parent_mp3_sha256": "def456",
                            "start_sec": 0.0,
                            "end_sec": 5.0,
                            "speech_len_sec": 5.0,
                            "padded_len_sec": 5.0
                        }
                    }
                ]
            }
            script_path.write_text(json.dumps(script_data))
            
            # Run QA
            results, all_pass = run_qa(str(script_path), scope="source", project_id="test_proj")
            
            # Verify it failed
            assert all_pass is False
            assert len(results) == 1
            assert results[0]["status"] == "FAIL"
            assert any("QA_LIPSYNC_FAIL" in issue for issue in results[0]["issues"])
            assert "Lipsync drift 100ms exceeds max 50ms" in " ".join(results[0]["issues"])

    @patch("scripts.qa_media.audio_duration")
    @patch("scripts.qa_media.run_lipsync_qa")
    @patch("scripts.qa_media.probe")
    @patch("scripts.qa_media.check_blank_screen")
    @patch("scripts.qa_media.check_frozen_video")
    def test_qa_media_passes_valid_lipsync(self, mock_frozen, mock_blank, mock_probe, mock_lipsync_qa, mock_audio_dur):
        """Verify that qa_media passes when run_lipsync_qa returns OK."""
        from scripts.qa_media import run_qa
        
        mock_probe.return_value = {
            "width": 1920,
            "height": 1080,
            "duration": 5.0,
            "has_audio": True
        }
        mock_audio_dur.return_value = 5.0
        mock_blank.return_value = []
        mock_frozen.return_value = []
        
        # Mock run_lipsync_qa to return success
        mock_lipsync_qa.return_value = {
            "status": "pass",
            "issues": []
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.json"
            media_path = Path(tmpdir) / "test.mp4"
            media_path.write_bytes(b"fake video")
            
            # Create fake audio slice and get its real hash
            audio_slice_path = Path(tmpdir) / "test.mp3"
            audio_slice_path.write_bytes(b"fake audio")
            real_hash = hashlib.sha256(b"fake audio").hexdigest()
            
            script_data = {
                "project_id": "test_proj",
                "segments": [
                    {
                        "id": "001",
                        "media": "test.mp4",
                        "audio_policy": "keep_lipsync",
                        "shot_type": "hero_lipsync",
                        "speech_len_sec": 5.0,
                        "audio_slice": {
                            "file": "test.mp3",
                            "slice_sha256": real_hash,
                            "parent_mp3_sha256": "def456",
                            "start_sec": 0.0,
                            "end_sec": 5.0,
                            "speech_len_sec": 5.0,
                            "padded_len_sec": 5.0
                        }
                    }
                ]
            }
            script_path.write_text(json.dumps(script_data))
            
            # Run QA
            results, all_pass = run_qa(str(script_path), scope="source", project_id="test_proj")
            
            # Verify it passed
            assert all_pass is True, f"Expected all_pass to be True. Issues: {results[0].get('issues', [])}"
            assert len(results) == 1
            assert results[0]["status"] == "PASS"
            assert not any("QA_LIPSYNC_FAIL" in issue for issue in results[0].get("issues", []))
