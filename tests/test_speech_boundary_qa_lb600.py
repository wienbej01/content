"""Tests for speech-boundary and overlap validation (Ticket LB-600)."""
import subprocess
import tempfile
from pathlib import Path

import pytest

from scripts.speech_boundary_qa import (
    validate_speech_boundaries,
    validate_no_slice_overlap,
    _detect_speech_regions
)


def _make_silent_audio(path: Path, duration_sec: float):
    """Generate a silent audio file."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000",
         "-t", str(duration_sec), "-c:a", "pcm_s16le", str(path)],
        capture_output=True, check=True
    )


def _make_tone_audio(path: Path, freq: float, duration_sec: float, start_delay: float = 0.0):
    """Generate an audio file with a tone, optionally delayed."""
    if start_delay > 0:
        silent_path = path.with_suffix(".silent.wav")
        _make_silent_audio(silent_path, start_delay)
        tone_path = path.with_suffix(".tone.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration_sec}",
             "-c:a", "pcm_s16le", str(tone_path)],
            capture_output=True, check=True
        )
        concat_file = path.with_suffix(".txt")
        concat_file.write_text(f"file '{silent_path}'\nfile '{tone_path}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
             "-c:a", "pcm_s16le", str(path)],
            capture_output=True, check=True
        )
        silent_path.unlink()
        tone_path.unlink()
        concat_file.unlink()
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration_sec}",
             "-c:a", "pcm_s16le", str(path)],
            capture_output=True, check=True
        )


class TestSpeechBoundaryValidation:
    def test_silence_only_pad_passes(self):
        """Verify that a slice with only silence in the pad passes validation."""
        with tempfile.TemporaryDirectory() as td:
            slice_path = Path(td) / "slice.wav"
            # 1.0s silence, 1.0s tone, 1.0s silence
            _make_tone_audio(slice_path, freq=1000, duration_sec=1.0, start_delay=1.0)
            
            # Assigned interval is exactly the tone (1.0s to 2.0s)
            result = validate_speech_boundaries(
                slice_path=slice_path,
                assigned_start_sec=1.0,
                assigned_end_sec=2.0,
                visible_trim_end_sec=2.0
            )
            
            assert result["status"] == "pass"
            assert not result["issues"]

    def test_speech_in_pad_fails(self):
        """Verify that speech extending into the silence pad fails validation."""
        with tempfile.TemporaryDirectory() as td:
            slice_path = Path(td) / "slice.wav"
            # 0.5s silence, 2.0s tone, 0.5s silence
            _make_tone_audio(slice_path, freq=1000, duration_sec=2.0, start_delay=0.5)
            
            # Assigned interval is too short, cutting into the tone
            result = validate_speech_boundaries(
                slice_path=slice_path,
                assigned_start_sec=1.0,
                assigned_end_sec=1.5,  # Cuts through the 2.0s tone
                visible_trim_end_sec=1.5
            )
            
            assert result["status"] == "fail"
            assert any("after assigned interval end" in issue for issue in result["issues"])

    def test_trim_through_active_speech_fails(self):
        """Verify that a visible trim cutting through active speech fails."""
        with tempfile.TemporaryDirectory() as td:
            slice_path = Path(td) / "slice.wav"
            # 0.5s silence, 2.0s tone
            _make_tone_audio(slice_path, freq=1000, duration_sec=2.0, start_delay=0.5)
            
            result = validate_speech_boundaries(
                slice_path=slice_path,
                assigned_start_sec=0.5,
                assigned_end_sec=2.5,
                visible_trim_end_sec=1.5  # Cuts through the 2.0s tone
            )
            
            assert result["status"] == "fail"
            assert any("cuts through active speech region" in issue for issue in result["issues"])

    def test_overlapping_source_slices_fail(self):
        """Verify that overlapping speech regions across slices are detected."""
        with tempfile.TemporaryDirectory() as td:
            slice1_path = Path(td) / "slice1.wav"
            slice2_path = Path(td) / "slice2.wav"
            
            # Slice 1: tone from 0.0 to 2.0
            _make_tone_audio(slice1_path, freq=1000, duration_sec=2.0, start_delay=0.0)
            # Slice 2: tone from 1.0 to 3.0 (overlaps with slice 1)
            _make_tone_audio(slice2_path, freq=1000, duration_sec=2.0, start_delay=1.0)
            
            slices = [
                {"path": str(slice1_path), "assigned_start_sec": 0.0, "assigned_end_sec": 2.0},
                {"path": str(slice2_path), "assigned_start_sec": 1.0, "assigned_end_sec": 3.0}
            ]
            
            result = validate_no_slice_overlap(slices)
            
            assert result["status"] == "fail"
            assert any("Speech overlap detected" in issue for issue in result["issues"])

    def test_provider_timing_difference_creates_evidence(self):
        """Verify that the validation captures speech regions for evidence."""
        with tempfile.TemporaryDirectory() as td:
            slice_path = Path(td) / "slice.wav"
            _make_tone_audio(slice_path, freq=1000, duration_sec=1.0, start_delay=0.5)
            
            result = validate_speech_boundaries(
                slice_path=slice_path,
                assigned_start_sec=0.5,
                assigned_end_sec=1.5,
                visible_trim_end_sec=1.5
            )
            
            assert result["status"] == "pass"
            # The speech regions should be recorded as evidence
            assert len(result["speech_regions"]) > 0
            assert result["speech_regions"][0][0] >= 0.4  # Allow small tolerance
