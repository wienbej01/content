#!/usr/bin/env python3
"""Deterministic audio design fixtures for TKT-004.

Generates three fixture types for testing audio scoring and silence rules:
1. Flat music bed — 60s WAV, single RMS level (-20 dBFS), no act distinctions.
2. Act-scored stems — 4 WAV stems with distinct RMS levels per act.
3. Paradigm-shift silence — 60s WAV, silent window at 30-35s.

All outputs use the stdlib `wave` module — no external audio deps.
"""
import math
import struct
import wave
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rms_db(samples: list[float]) -> float:
    """Compute RMS in dBFS from a list of float samples (-1.0 to 1.0).

    Returns -inf for silence (all zeros).
    """
    if not samples:
        return -float("inf")
    sum_squares = sum(s * s for s in samples)
    rms = math.sqrt(sum_squares / len(samples))
    if rms <= 0.0:
        return -float("inf")
    return 20.0 * math.log10(rms)


def _generate_sine_wave(
    duration_sec: float,
    freq_hz: float = 440.0,
    sample_rate: int = 44100,
    amplitude: float = 0.5,
    silent_start: float | None = None,
    silent_end: float | None = None,
) -> list[float]:
    """Generate a list of float samples (-1.0 to 1.0).

    If silent_start and silent_end are provided, samples in that window are 0.0.
    """
    n_samples = int(duration_sec * sample_rate)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        if silent_start is not None and silent_end is not None:
            if silent_start <= t <= silent_end:
                samples.append(0.0)
                continue
        sample = amplitude * math.sin(2.0 * math.pi * freq_hz * t)
        samples.append(sample)
    return samples


def _write_wav(path: Path, samples: list[float], sample_rate: int = 44100) -> None:
    """Write a mono 16-bit WAV file from float samples."""
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        # Convert float (-1.0..1.0) to 16-bit signed int
        frames = b""
        for s in samples:
            # Clamp
            s = max(-1.0, min(1.0, s))
            frames += struct.pack("<h", int(s * 32767))
        w.writeframes(frames)


def _read_wav(path: Path) -> tuple[list[float], int]:
    """Read a WAV file and return (float_samples, sample_rate)."""
    with wave.open(str(path), "r") as w:
        n_channels = w.getnchannels()
        sample_width = w.getsampwidth()
        sample_rate = w.getframerate()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames * n_channels)
        # Parse based on sample width
        if sample_width == 2:
            fmt = f"<{n_frames * n_channels}h"
            ints = struct.unpack(fmt, raw)
        elif sample_width == 1:
            ints = list(raw)
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")
        # Take first channel if stereo
        if n_channels > 1:
            ints = ints[::n_channels]
        # Convert to float (-1.0..1.0)
        if sample_width == 2:
            samples = [s / 32767.0 for s in ints]
        else:
            samples = [(s - 128) / 128.0 for s in ints]
        return samples, sample_rate


# ---------------------------------------------------------------------------
# Fixture 1: Flat music bed
# ---------------------------------------------------------------------------

def generate_flat_music_bed(
    tmp_path: Path,
    duration_sec: float = 3.0,
    target_db: float = -20.0,
    sample_rate: int = 8000,
) -> dict[str, Any]:
    """Generate a flat music bed at the target dB level.

    Note: RMS of a sine wave = amplitude / sqrt(2), so we scale up
    by sqrt(2) to hit the target RMS.
    """
    tmp_path.mkdir(exist_ok=True, parents=True)
    # Scale amplitude so RMS hits target: RMS = amp/sqrt(2) => amp = 10^(db/20) * sqrt(2)
    amplitude = 10.0 ** (target_db / 20.0) * math.sqrt(2)
    n_samples = int(duration_sec * sample_rate)
    samples = [amplitude * math.sin(2.0 * math.pi * 440.0 * i / sample_rate) for i in range(n_samples)]
    out = tmp_path / "flat_music_bed.wav"
    _write_wav(out, samples, sample_rate=sample_rate)
    return {
        "path": str(out),
        "duration_sec": duration_sec,
        "target_db": target_db,
        "sample_rate": sample_rate,
        "amplitude": amplitude,
        "is_flat": True,
        "fixture_type": "flat",
    }


# ---------------------------------------------------------------------------
# Fixture 2: Act-scored stems
# ---------------------------------------------------------------------------

ACT_TARGET_DB = {
    1: -18.0,  # Hook: higher energy (builds tension)
    2: -22.0,  # Myth busting: moderate
    3: -16.0,  # Framework reveal: highest energy (excitement)
    4: -24.0,  # Iteration loop: lower energy (educational)
}


def generate_act_scored_stems(
    tmp_path: Path,
    acts: list[int] | None = None,
    duration_sec: float = 3.0,
    sample_rate: int = 8000,
) -> dict[str, Any]:
    """Generate stems with distinct RMS levels per act."""
    if acts is None:
        acts = [1, 2, 3, 4]
    tmp_path.mkdir(exist_ok=True, parents=True)
    stems = {}
    for act in acts:
        target_db = ACT_TARGET_DB.get(act, -20.0)
        # Scale amplitude so RMS hits target: RMS = amp/sqrt(2) => amp = 10^(db/20) * sqrt(2)
        amplitude = 10.0 ** (target_db / 20.0) * math.sqrt(2)
        n_samples = int(duration_sec * sample_rate)
        samples = [amplitude * math.sin(2.0 * math.pi * 440.0 * i / sample_rate) for i in range(n_samples)]
        out = tmp_path / f"act_{act}_stem.wav"
        _write_wav(out, samples, sample_rate=sample_rate)
        stems[act] = {
            "path": str(out),
            "target_db": target_db,
            "duration_sec": duration_sec,
            "sample_rate": sample_rate,
            "is_flat": False,
            "fixture_type": "act_scored",
        }

    return {
        "stems": stems,
        "acts": acts,
        "is_flat": False,
        "fixture_type": "act_scored",
    }


# ---------------------------------------------------------------------------
# Fixture 3: Paradigm-shift silence
# ---------------------------------------------------------------------------

def generate_paradigm_shift_silence(
    tmp_path: Path,
    duration_sec: float = 10.0,
    target_db: float = -20.0,
    silent_start: float = 3.0,
    silent_end: float = 6.0,
    sample_rate: int = 8000,
) -> dict[str, Any]:
    """Generate a music bed with a silent window (paradigm-shift moment)."""
    tmp_path.mkdir(exist_ok=True, parents=True)
    # Scale amplitude so RMS hits target: RMS = amp/sqrt(2) => amp = 10^(db/20) * sqrt(2)
    amplitude = 10.0 ** (target_db / 20.0) * math.sqrt(2)
    n_samples = int(duration_sec * sample_rate)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        if silent_start <= t <= silent_end:
            samples.append(0.0)
            continue
        samples.append(amplitude * math.sin(2.0 * math.pi * 440.0 * t))
    out = tmp_path / "paradigm_shift_silence.wav"
    _write_wav(out, samples, sample_rate=sample_rate)
    return {
        "path": str(out),
        "duration_sec": duration_sec,
        "target_db": target_db,
        "silent_start": silent_start,
        "silent_end": silent_end,
        "sample_rate": sample_rate,
        "is_flat": False,
        "is_silence": True,
        "fixture_type": "paradigm_shift_silence",
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flat_music_bed(tmp_path):
    yield generate_flat_music_bed(tmp_path)


@pytest.fixture
def act_scored_stems(tmp_path):
    yield generate_act_scored_stems(tmp_path)


@pytest.fixture
def paradigm_shift_silence(tmp_path):
    yield generate_paradigm_shift_silence(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_flat_fixture(flat_music_bed):
    """Flat music bed: RMS matches target within ±1 dB."""
    p = Path(flat_music_bed["path"])
    assert p.exists(), "flat music bed WAV not created"
    samples, sr = _read_wav(p)
    measured_db = _rms_db(samples)
    target_db = flat_music_bed["target_db"]
    assert abs(measured_db - target_db) < 1.0, (
        f"Flat fixture RMS {measured_db:.1f} dBFS, expected {target_db:.1f} dBFS"
    )
    assert flat_music_bed["is_flat"] is True


def test_act_scored_fixture(act_scored_stems):
    """Act-scored stems: each act has distinct RMS."""
    stems = act_scored_stems["stems"]
    measured_dbs = {}
    for act in [1, 2, 3, 4]:
        samples, sr = _read_wav(Path(stems[act]["path"]))
        measured_dbs[act] = _rms_db(samples)

    # Each act should be within ±1 dB of its target
    for act in [1, 2, 3, 4]:
        target = ACT_TARGET_DB[act]
        measured = measured_dbs[act]
        assert abs(measured - target) < 1.0, (
            f"Act {act}: RMS {measured:.1f} dBFS, expected {target:.1f} dBFS"
        )

    # All acts should have distinct RMS values
    unique_dbs = set(round(db, 1) for db in measured_dbs.values())
    assert len(unique_dbs) == 4, f"Expected 4 distinct RMS values, got {unique_dbs}"


def test_paradigm_shift_silence(paradigm_shift_silence):
    """Paradigm-shift silence: silent window has RMS < -60 dBFS."""
    p = Path(paradigm_shift_silence["path"])
    assert p.exists(), "paradigm shift WAV not created"
    samples, sr = _read_wav(p)

    # Extract the silent window
    start_sample = int(paradigm_shift_silence["silent_start"] * sr)
    end_sample = int(paradigm_shift_silence["silent_end"] * sr)
    silent_samples = samples[start_sample:end_sample]
    silent_rms = _rms_db(silent_samples)
    assert silent_rms < -60.0, (
        f"Silent window RMS {silent_rms:.1f} dBFS, expected < -60 dBFS"
    )

    # Extract a non-silent window (before the silent window)
    non_silent_start = int(0.5 * sr)
    non_silent_end = int(min(paradigm_shift_silence["silent_start"] - 0.1, 2.0) * sr)
    if non_silent_end > non_silent_start:
        non_silent_samples = samples[non_silent_start:non_silent_end]
    else:
        non_silent_samples = samples[:int(0.5 * sr)]
    non_silent_rms = _rms_db(non_silent_samples)
    assert non_silent_rms > -30.0, (
        f"Non-silent window RMS {non_silent_rms:.1f} dBFS, expected > -30 dBFS"
    )


def test_fixture_determinism_flat(tmp_path):
    """Same inputs produce same WAV output (hash match across runs)."""
    m1 = generate_flat_music_bed(tmp_path / "run1")
    m2 = generate_flat_music_bed(tmp_path / "run2")
    assert Path(m1["path"]).read_bytes() == Path(m2["path"]).read_bytes(), \
        "flat music bed generation is not deterministic"


def test_fixture_determinism_silence(tmp_path):
    """Paradigm-shift silence is deterministic."""
    m1 = generate_paradigm_shift_silence(tmp_path / "run1")
    m2 = generate_paradigm_shift_silence(tmp_path / "run2")
    assert Path(m1["path"]).read_bytes() == Path(m2["path"]).read_bytes(), \
        "paradigm shift generation is not deterministic"


def test_wav_format_valid(flat_music_bed):
    """Generated WAV is valid and well-formed."""
    samples, sr = _read_wav(Path(flat_music_bed["path"]))
    assert sr == flat_music_bed["sample_rate"], f"Expected {flat_music_bed['sample_rate']} Hz, got {sr} Hz"
    duration = len(samples) / sr
    assert abs(duration - flat_music_bed["duration_sec"]) < 0.5, (
        f"Duration {duration:.1f}s, expected ~{flat_music_bed['duration_sec']}s"
    )
