"""Deterministic, hermetic audio design fixtures.

Three fixture generators for music/audio scoring tests (TKT-501..505):
  1. flat_bed         — 60s WAV at constant RMS with no act distinctions.
  2. act_scored_stems — 4 WAV stems (Act 1-4) each with distinct RMS envelope.
  3. paradigm_shift_silence — 60s WAV with a 5s silent window simulating a paradigm-shift beat.

All outputs use the standard library + wave module — no external dependencies,
no network. Synthesized using math.sin for tonal content and zeros for silence.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import NamedTuple


SAMPLE_RATE = 44100
BIT_DEPTH = 16
CHANNELS = 1


class AudioFixture(NamedTuple):
    path: Path
    duration_sec: float
    rms_db: float
    label: str


def _write_wav(path: Path, samples: list[float], rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BIT_DEPTH // 8)
        wf.setframerate(rate)
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            int_val = int(clamped * 32767)
            wf.writeframes(int_val.to_bytes(2, "little", signed=True))


def _rms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    mean_sq = sum(s * s for s in samples) / len(samples)
    return math.sqrt(mean_sq)


def _rms_db(samples: float | list[float]) -> float:
    if isinstance(samples, float):
        return -96.0 if samples <= 0 else 20 * math.log10(samples)
    r = _rms(samples)
    return -96.0 if r <= 0 else 20 * math.log10(r)


def _sine_wave(freq: float, duration_sec: float, rms_db: float, rate: int = SAMPLE_RATE) -> list[float]:
    """Synthesize a sine wave whose RMS matches the target dB value.

    RMS of a pure sine with amplitude A is A / sqrt(2), so to hit a target
    dB we solve A = sqrt(2) * 10^(rms_db/20).
    """
    target_linear = 10 ** (rms_db / 20)
    amplitude = math.sqrt(2) * target_linear
    n = int(rate * duration_sec)
    return [amplitude * math.sin(2 * math.pi * freq * i / rate) for i in range(n)]


def make_flat_bed(tmp_path: Path, duration: float = 60.0, target_db: float = -20.0) -> list[AudioFixture]:
    """60s flat music bed with no act distinctions. """
    samples = _sine_wave(440.0, duration, target_db)
    out = tmp_path / "flat_bed.wav"
    _write_wav(out, samples)
    actual_db = 20 * math.log10(_rms(samples))
    return [AudioFixture(out, duration, round(actual_db, 2), "flat_bed")]


def make_act_scored_stems(tmp_path: Path, duration: float = 45.0) -> list[AudioFixture]:
    """4 act stems with distinct RMS envelopes matching MITmonk narrative energy. """
    act_configs = [
        (1, -18.0, 220.0),  # Act 1: gentle intro, low tempo
        (2, -22.0, 330.0),  # Act 2: building tension
        (3, -16.0, 440.0),  # Act 3: peak energy, thesis
        (4, -24.0, 262.0),  # Act 4: philosophical close
    ]
    stems_dir = tmp_path / "act_scored"
    stems_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for act_num, target_db, freq in act_configs:
        samples = _sine_wave(freq, duration, target_db)
        out = stems_dir / f"act_{act_num}.wav"
        _write_wav(out, samples)
        actual_db = 20 * math.log10(_rms(samples))
        fixtures.append(AudioFixture(out, duration, round(actual_db, 2), f"act_{act_num}"))
    return fixtures


def make_paradigm_shift_silence(tmp_path: Path, duration: float = 60.0, silence_start: float = 30.0, silence_duration: float = 5.0) -> list[AudioFixture]:
    """60s bed with one 5s silent window at the specified position. """
    music_db = -20.0
    n = int(SAMPLE_RATE * duration)
    silence_start_i = int(SAMPLE_RATE * silence_start)
    silence_end_i = int(SAMPLE_RATE * (silence_start + silence_duration))
    # synthesize non-silent segments at the target dB
    non_silent_samples = _sine_wave(440.0, duration, music_db)
    samples = []
    for i in range(n):
        if silence_start_i <= i < silence_end_i:
            samples.append(0.0)
        else:
            samples.append(non_silent_samples[i] if i < len(non_silent_samples) else 0.0)
    out = tmp_path / "paradigm_shift_silence.wav"
    _write_wav(out, samples)
    return [AudioFixture(out, duration, round(20 * math.log10(_rms(samples)), 2), "paradigm_shift_silence")]


def build_all_audio_fixtures(tmp_path: Path) -> dict[str, list[AudioFixture]]:
    return {
        "flat_bed": make_flat_bed(tmp_path),
        "act_scored": make_act_scored_stems(tmp_path),
        "silence": make_paradigm_shift_silence(tmp_path),
    }
