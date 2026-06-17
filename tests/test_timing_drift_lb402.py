"""Tests for provider timing-drift evidence (Ticket LB-402)."""
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.timing_drift import analyze_timing_drift, _get_audio_duration, _detect_speech_energy


def _make_silent_audio(path: Path, duration_sec: float):
    """Generate a silent audio file."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000",
         "-t", str(duration_sec), "-c:a", "pcm_s16le", str(path)],
        capture_output=True, check=True
    )


def _make_tone_audio(path: Path, freq: float, duration_sec: float, start_delay: float = 0.0):
    """Generate an audio file with a tone, optionally delayed."""
    # Create silent part
    if start_delay > 0:
        silent_path = path.with_suffix(".silent.wav")
        _make_silent_audio(silent_path, start_delay)
        tone_path = path.with_suffix(".tone.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration_sec}",
             "-c:a", "pcm_s16le", str(tone_path)],
            capture_output=True, check=True
        )
        # Concatenate
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


def _make_dummy_video(path: Path, duration_sec: float, audio_path: Path):
    """Generate a dummy video with the given audio."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=1280x720:d={duration_sec}",
         "-i", str(audio_path), "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)],
        capture_output=True, check=True
    )


class TestTimingDriftAnalysis:
    def test_perfect_alignment_passes(self):
        """Verify that perfectly aligned source and returned media passes validation."""
        with tempfile.TemporaryDirectory() as td:
            source_path = Path(td) / "source.wav"
            video_path = Path(td) / "video.mp4"
            
            _make_tone_audio(source_path, freq=1000, duration_sec=2.0)
            _make_dummy_video(video_path, duration_sec=2.0, audio_path=source_path)
            
            evidence = analyze_timing_drift(video_path, source_path)
            
            assert evidence["pass_fail_result"] == "pass"
            assert evidence["measured_values"]["speech_start_lag_sec"] < 0.15
            assert not evidence["issues"]

    def test_constant_offset_fails_if_exceeds_threshold(self):
        """Verify that a constant offset exceeding the threshold fails validation."""
        with tempfile.TemporaryDirectory() as td:
            source_path = Path(td) / "source.wav"
            returned_audio_path = Path(td) / "returned.wav"
            video_path = Path(td) / "video.mp4"
            
            # Source starts immediately
            _make_tone_audio(source_path, freq=1000, duration_sec=2.0, start_delay=0.0)
            # Returned has a 0.3s delay (exceeds 0.15s threshold)
            _make_tone_audio(returned_audio_path, freq=1000, duration_sec=2.0, start_delay=0.3)
            _make_dummy_video(video_path, duration_sec=2.3, audio_path=returned_audio_path)
            
            evidence = analyze_timing_drift(video_path, source_path, diagnostic_audio_path=returned_audio_path)
            
            assert evidence["pass_fail_result"] == "fail"
            assert any("Speech start lag" in issue for issue in evidence["issues"])

    def test_early_speech_end_detected(self):
        """Verify that early speech end (truncation) is detected."""
        with tempfile.TemporaryDirectory() as td:
            source_path = Path(td) / "source.wav"
            returned_audio_path = Path(td) / "returned.wav"
            video_path = Path(td) / "video.mp4"
            
            _make_tone_audio(source_path, freq=1000, duration_sec=3.0, start_delay=0.0)
            # Returned is truncated to 1.0s
            _make_tone_audio(returned_audio_path, freq=1000, duration_sec=1.0, start_delay=0.0)
            _make_dummy_video(video_path, duration_sec=1.0, audio_path=returned_audio_path)
            
            evidence = analyze_timing_drift(video_path, source_path, diagnostic_audio_path=returned_audio_path)
            
            assert evidence["pass_fail_result"] == "fail"
            assert any("significantly shorter" in issue or "Speech end delta" in issue for issue in evidence["issues"])

    def test_correlation_lag_calculation(self):
        """Verify that the correlation lag is correctly calculated as the average of start and end lags."""
        with tempfile.TemporaryDirectory() as td:
            source_path = Path(td) / "source.wav"
            returned_audio_path = Path(td) / "returned.wav"
            video_path = Path(td) / "video.mp4"
            
            # Source: 0.0s to 2.0s
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2.0",
                 "-c:a", "pcm_s16le", str(source_path)],
                capture_output=True, check=True
            )
            
            # Returned: delayed by 0.2s, and truncated by 0.2s at the end
            # This creates a start lag of 0.2s and an end delta of 0.2s
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1.6",
                 "-af", "adelay=200|200", "-c:a", "pcm_s16le", str(returned_audio_path)],
                capture_output=True, check=True
            )
            
            _make_dummy_video(video_path, duration_sec=1.8, audio_path=returned_audio_path)
            
            evidence = analyze_timing_drift(video_path, source_path, diagnostic_audio_path=returned_audio_path)
            
            # Correlation lag should be approximately the average of start and end lags
            assert evidence["measured_values"]["correlation_lag_sec"] >= 0.15

    def test_missing_provider_audio_fails_gracefully(self):
        """Verify that missing provider audio results in a fail, but doesn't crash."""
        with tempfile.TemporaryDirectory() as td:
            source_path = Path(td) / "source.wav"
            video_path = Path(td) / "video.mp4"
            
            _make_tone_audio(source_path, freq=1000, duration_sec=2.0)
            # Video with NO audio stream
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=2.0",
                 "-c:v", "libx264", str(video_path)],
                capture_output=True, check=True
            )
            
            evidence = analyze_timing_drift(video_path, source_path)
            
            # Should fail due to duration mismatch or missing audio
            assert evidence["pass_fail_result"] == "fail"
            assert any("shorter" in issue or "exist" in issue for issue in evidence["issues"])
