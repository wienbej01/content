"""Unit tests for hero temporal-edit fail-closed guard (Ticket LB-001)."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# We need to import the function or test it via the module
# Since process_segment is in assemble.py, we can test the guard logic directly
# or by mocking the dependencies.

def test_rejects_hero_speed_change():
    """Verify that speed changes are rejected for hero lipsync clips."""
    from scripts.assemble import process_segment
    
    seg = {
        "media": "test.mp4",
        "audio_policy": "keep_lipsync",
        "clip_id": "test_clip_001",
        "speech_len_sec": 5.0
    }
    
    with pytest.raises(ValueError) as exc_info:
        # Mock resolve to return a dummy path
        with patch("scripts.assemble.resolve", return_value=Path("/tmp/test.mp4")):
            process_segment(seg, speed=1.5, w=1920, h=1080, fps=30, grade="", crf=23, tmp=Path("/tmp"), base=Path("/tmp"), idx=0)
            
    assert "BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN" in str(exc_info.value)
    assert "operation=speed_change" in str(exc_info.value)


def test_rejects_hero_looping():
    """Verify that looping is rejected for hero lipsync clips."""
    from scripts.assemble import process_segment
    
    seg = {
        "media": "test.mp4",
        "lipsync_required": True,
        "clip_id": "test_clip_002",
        "speech_len_sec": 5.0
    }
    
    with pytest.raises(ValueError) as exc_info:
        with patch("scripts.assemble.resolve", return_value=Path("/tmp/test.mp4")):
            process_segment(seg, speed=1.0, w=1920, h=1080, fps=30, grade="", crf=23, tmp=Path("/tmp"), base=Path("/tmp"), idx=0, allow_looping=True)
            
    assert "BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN" in str(exc_info.value)
    assert "operation=looping" in str(exc_info.value)


def test_rejects_trim_inside_active_speech():
    """Verify that trimming through active speech is rejected for hero lipsync clips."""
    from scripts.assemble import process_segment
    
    seg = {
        "media": "test.mp4",
        "audio_policy": "keep_lipsync",
        "clip_id": "test_clip_003",
        "speech_len_sec": 5.0,
        "trim_end": 3.0  # Trims 2 seconds of active speech
    }
    
    with pytest.raises(ValueError) as exc_info:
        with patch("scripts.assemble.resolve", return_value=Path("/tmp/test.mp4")):
            process_segment(seg, speed=1.0, w=1920, h=1080, fps=30, grade="", crf=23, tmp=Path("/tmp"), base=Path("/tmp"), idx=0)
            
    assert "BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN" in str(exc_info.value)
    assert "operation=trim_through_speech" in str(exc_info.value)


def test_allows_crop_scale_and_overlay():
    """Verify that non-temporal operations (crop, scale, grade) are allowed for hero clips."""
    from scripts.assemble import process_segment
    
    seg = {
        "media": "test.mp4",
        "audio_policy": "keep_lipsync",
        "clip_id": "test_clip_004",
        "speech_len_sec": 5.0
    }
    
    # This should NOT raise a ValueError for the guard.
    # It will fail later due to missing ffmpeg/file, but the guard should pass.
    with patch("scripts.assemble.resolve", return_value=Path("/tmp/test.mp4")):
        with patch("scripts.assemble.probe_dur", return_value=5.0):
            with patch("scripts.assemble.run") as mock_run:
                try:
                    process_segment(seg, speed=1.0, w=1920, h=1080, fps=30, grade="format=yuv420p", crf=23, tmp=Path("/tmp"), base=Path("/tmp"), idx=0)
                except Exception as e:
                    # We expect it to potentially fail on ffmpeg execution in this mock, 
                    # but NOT on the HERO_TEMPORAL_EDIT_FORBIDDEN guard.
                    assert "HERO_TEMPORAL_EDIT_FORBIDDEN" not in str(e)
                
                # Verify run was called (meaning guard passed)
                assert mock_run.called
