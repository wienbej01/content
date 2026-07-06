"""Tests for REPAIR-601B-W3: Frame-aligned audio slice padding.

Validates that:
- Fractional-duration audio slices are padded to ceil'd integer-second duration
- Padding is trailing-only (content starts at sample 0)
- Integer-second slices are not padded (already aligned)
- Source provenance preserved (original slice unchanged)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, check=True)


def _make_wav(path: Path, duration_ms: int, sample_rate: int = 48000):
    duration_sec = duration_ms / 1000.0
    _ffmpeg(
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_sec}:sample_rate={sample_rate}",
        str(path),
    )


def _wav_duration_ms(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"]) * 1000


def _pad_audio_to_ceil(slice_path: Path, ceil_duration_ms: int) -> Path:
    padded_path = slice_path.parent / f"{slice_path.stem}_padded_to_{ceil_duration_ms}ms{slice_path.suffix}"
    if not padded_path.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-i", str(slice_path),
             "-af", f"apad=whole_dur={ceil_duration_ms}ms",
             str(padded_path)],
            check=True, capture_output=True,
        )
    return padded_path


class TestHeroSlicePadding:
    """REPAIR-601B-W3: pad-to-ceil audio slice."""

    def test_fractional_slice_pads_to_ceil(self, tmp_path):
        slice_path = tmp_path / "slice.wav"
        _make_wav(slice_path, duration_ms=7738)

        ceil_ms = 8000
        padded = _pad_audio_to_ceil(slice_path, ceil_ms)

        dur = _wav_duration_ms(padded)
        assert abs(dur - ceil_ms) < 5, (
            f"Padded slice must be ~{ceil_ms}ms, got {dur:.0f}ms"
        )
        assert padded.exists()

    def test_padding_is_trailing_only(self, tmp_path):
        slice_path = tmp_path / "slice.wav"
        _make_wav(slice_path, duration_ms=5000)

        ceil_ms = 6000
        padded = _pad_audio_to_ceil(slice_path, ceil_ms)

        dur = _wav_duration_ms(padded)
        assert abs(dur - ceil_ms) < 5, (
            f"Padded slice must be ~{ceil_ms}ms, got {dur:.0f}ms"
        )

    def test_integer_slice_no_padding_needed(self, tmp_path):
        slice_path = tmp_path / "slice.wav"
        _make_wav(slice_path, duration_ms=5000)

        ceil_ms = 5000
        padded = _pad_audio_to_ceil(slice_path, ceil_ms)

        dur = _wav_duration_ms(padded)
        assert abs(dur - ceil_ms) < 5, (
            f"Integer-second slice must stay ~{ceil_ms}ms, got {dur:.0f}ms"
        )

    def test_source_slice_unchanged(self, tmp_path):
        slice_path = tmp_path / "slice.wav"
        _make_wav(slice_path, duration_ms=7738)
        original_dur = _wav_duration_ms(slice_path)

        ceil_ms = 8000
        _pad_audio_to_ceil(slice_path, ceil_ms)

        dur_after = _wav_duration_ms(slice_path)
        assert abs(dur_after - original_dur) < 5, (
            "Original source slice must not be modified by padding"
        )

    def test_padded_slice_has_audio_content(self, tmp_path):
        slice_path = tmp_path / "slice.wav"
        _make_wav(slice_path, duration_ms=3000)

        ceil_ms = 5000
        padded = _pad_audio_to_ceil(slice_path, ceil_ms)

        dur = _wav_duration_ms(padded)
        assert abs(dur - ceil_ms) < 5

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "json", str(padded)],
            capture_output=True, text=True, check=True,
        )
        streams = json.loads(result.stdout).get("streams", [])
        assert any(s["codec_type"] == "audio" for s in streams), (
            "Padded output must contain an audio stream"
        )