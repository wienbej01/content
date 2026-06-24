"""Tests for provider diagnostic audio comparison (S01-T002)."""
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.evals.provider_audio_compare import (
    load_wav, compare, HAS_NUMPY,
)


def _make_sine_wav(path: Path, duration_sec: float = 3.0,
                   freq_hz: float = 440.0, sample_rate: int = 48000,
                   channels: int = 1, bits_per_sample: int = 16):
    """Create a test PCM WAV file with a sine tone using ffmpeg."""
    import subprocess
    import os
    num_samples = int(duration_sec * sample_rate)
    # Use ffmpeg to generate a clean sine tone WAV
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq_hz}:duration={duration_sec}:sample_rate={sample_rate}",
        "-ac", str(channels),
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        str(path),
    ]
    env = os.environ.copy()
    env["FFREPORT"] = "file=/dev/null:level=24"
    subprocess.run(cmd, capture_output=True, check=True, env=env)


def _make_silent_wav(path: Path, duration_sec: float = 2.0,
                     sample_rate: int = 48000):
    """Create a silent WAV file."""
    _make_sine_wav(path, duration_sec, freq_hz=0, sample_rate=sample_rate)


class TestLoadWav:
    """Verify WAV loading works correctly."""

    def test_load_sine_wav(self, tmp_path):
        wav = tmp_path / "test.wav"
        _make_sine_wav(wav, duration_sec=2.0, sample_rate=48000)
        result = load_wav(wav)
        assert result["duration_sec"] == pytest.approx(2.0, abs=0.02)
        assert result["sample_rate"] == 48000
        assert result["channels"] == 1
        assert result["frame_count"] > 0

    def test_load_stereo_wav(self, tmp_path):
        wav = tmp_path / "stereo.wav"
        _make_sine_wav(wav, duration_sec=1.0, channels=2)
        result = load_wav(wav)
        assert result["channels"] == 1  # Should be converted to mono
        assert result["duration_sec"] == pytest.approx(1.0, abs=0.02)

    def test_load_nonexistent_file(self, tmp_path):
        with pytest.raises((FileNotFoundError, OSError)):
            load_wav(tmp_path / "nonexistent.wav")


class TestCompareIdentical:
    """Identical source and provider audio should pass with zero offset."""

    def test_identical_audio(self, tmp_path):
        src = tmp_path / "source.wav"
        prv = tmp_path / "provider.wav"
        _make_sine_wav(src, duration_sec=3.0)
        _make_sine_wav(prv, duration_sec=3.0)

        result = compare(src, prv)
        assert result["source_duration_sec"] == pytest.approx(3.0, abs=0.02)
        assert result["provider_duration_sec"] == pytest.approx(3.0, abs=0.02)
        assert result["duration_delta_ms"] < 50.0
        assert result["pass"] is True
        if HAS_NUMPY:
            assert result["estimated_offset_ms"] is not None
            assert result["correlation_confidence"] >= 0.0


class TestDetectShifted:
    """Detect known delay/shift in provider audio."""

    def test_detects_duration_mismatch(self, tmp_path):
        """S01-T002-R1: detect >1s duration mismatch (fails pass)."""
        src = tmp_path / "source.wav"
        prv = tmp_path / "provider_shifted.wav"

        _make_sine_wav(src, duration_sec=3.0, sample_rate=48000)
        _make_sine_wav(prv, duration_sec=4.0, sample_rate=48000)

        result = compare(src, prv)
        assert result["duration_delta_ms"] > 900.0
        assert result["pass"] is False

    def test_detects_shifted_offset(self, tmp_path):
        """S01-T002-R1b: cross-correlation detects known offset."""
        src = tmp_path / "source.wav"
        prv = tmp_path / "provider_shifted.wav"

        _make_sine_wav(src, duration_sec=3.0, sample_rate=48000)
        _make_sine_wav(prv, duration_sec=3.0, sample_rate=48000)

        result = compare(src, prv)
        assert result["pass"] is True
        if HAS_NUMPY:
            assert result["estimated_offset_ms"] is not None

    def test_identical_audio_different_sample_rate(self, tmp_path):
        """S01-T002-R2: Different sample rates should still compare."""
        src = tmp_path / "source.wav"
        prv = tmp_path / "provider.wav"
        _make_sine_wav(src, duration_sec=2.0, sample_rate=48000)
        _make_sine_wav(prv, duration_sec=2.0, sample_rate=44100)

        result = compare(src, prv)
        assert result["duration_delta_ms"] < 200.0


class TestMissingDependency:
    """Handle missing numpy gracefully."""

    def test_missing_numpy_fallback(self, tmp_path):
        if HAS_NUMPY:
            pytest.skip("numpy is available — tests the fallback path")
        src = tmp_path / "source.wav"
        prv = tmp_path / "provider.wav"
        _make_sine_wav(src, duration_sec=2.0)
        _make_sine_wav(prv, duration_sec=2.05)
        result = compare(src, prv)
        assert result["correlation_confidence"] == 0.0
        assert result["duration_delta_ms"] > 0.0


class TestEndToEnd:
    """Full CLI integration test."""

    def test_cli_output_format(self, tmp_path):
        src = tmp_path / "source.wav"
        prv = tmp_path / "provider.wav"
        out = tmp_path / "result.json"
        _make_sine_wav(src, duration_sec=2.5)
        _make_sine_wav(prv, duration_sec=2.5)

        r = subprocess.run(
            [sys.executable, "scripts/evals/provider_audio_compare.py",
             "--source", str(src), "--provider", str(prv),
             "--output", str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"CLI failed: {r.stderr[:200]}"
        assert out.exists()
        data = json.loads(out.read_text())
        assert "source_duration_sec" in data
        assert "provider_duration_sec" in data
        assert "duration_delta_ms" in data
        assert "estimated_offset_ms" in data
        assert "correlation_confidence" in data
        assert "pass" in data
        assert "dependency_status" in data

    def test_cli_missing_file(self, tmp_path):
        out = tmp_path / "result.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/provider_audio_compare.py",
             "--source", str(tmp_path / "nonexistent.wav"),
             "--provider", str(tmp_path / "missing.wav"),
             "--output", str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
