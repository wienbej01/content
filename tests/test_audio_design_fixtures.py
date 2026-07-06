import math
import wave
from pathlib import Path

import pytest

from tests.fixtures.audio_design_fixtures import (
    SAMPLE_RATE,
    AudioFixture,
    _rms,
    _rms_db,
    build_all_audio_fixtures,
    make_act_scored_stems,
    make_flat_bed,
    make_paradigm_shift_silence,
)


def read_wav_samples(path: Path) -> tuple[int, list[float]]:
    with wave.open(str(path), "r") as wf:
        rate = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
    samples = []
    for i in range(0, len(raw), 2):
        val = int.from_bytes(raw[i:i+2], "little", signed=True)
        samples.append(val / 32767.0)
    return rate, samples


def read_duration(path: Path) -> float:
    with wave.open(str(path), "r") as wf:
        return wf.getnframes() / wf.getframerate()


def test_flat_bed(tmp_path: Path):
    fixtures = make_flat_bed(tmp_path / "flat_dur")
    assert len(fixtures) == 1
    fx = fixtures[0]
    dur = read_duration(fx.path)
    assert 50 <= dur <= 70, f"flat bed duration {dur} out of range"
    rate, samples = read_wav_samples(fx.path)
    assert rate == SAMPLE_RATE
    assert len(samples) == int(rate * dur)
    rms_val = _rms_db(_rms(samples))
    assert abs(rms_val - fx.rms_db) < 1.0, f"RMS mismatch: measured {rms_val:.2f} vs expected {fx.rms_db}"
    # flat means RMS variance across windows should be negligible
    windows = [samples[i:i+4410] for i in range(0, len(samples), 4410)][:10]
    rms_per_window = [_rms_db(_rms(w)) for w in windows]
    assert max(rms_per_window) - min(rms_per_window) < 0.5, "flat bed RMS variance too high"


def test_act_scored_stems(tmp_path: Path):
    fixtures = make_act_scored_stems(tmp_path / "scored_stems_dir")
    assert len(fixtures) == 4
    rms_values = []
    for fx in fixtures:
        rms_values.append(fx.rms_db)
        dur = read_duration(fx.path)
        assert 30 <= dur <= 60, f"act stem duration {dur} out of range"
        rate, samples = read_wav_samples(fx.path)
        assert rate == SAMPLE_RATE
    # each act stem must have a different RMS
    assert len(set(round(r, 0) for r in rms_values)) == 4


def test_paradigm_shift_silence(tmp_path: Path):
    fixtures = make_paradigm_shift_silence(tmp_path / "silence_dir")
    assert len(fixtures) == 1
    fx = fixtures[0]
    rate, samples = read_wav_samples(fx.path)
    dur = len(samples) / rate
    assert 50 <= dur <= 70, f"duration {dur} out of range"
    # locate 5s silent window
    silence_start_i = int(rate * 30.0)
    silence_end_i = int(rate * 35.0)
    silence_window = samples[silence_start_i:silence_end_i]
    leading_window = samples[0:int(rate * 5.0)]
    trailing_window = samples[int(rate * 55.0):int(rate * 60.0)]
    silence_rms = _rms(silence_window)
    lead_rms = _rms(leading_window)
    trail_rms = _rms(trailing_window)
    assert silence_rms < 0.001, f"silent window has RMS {silence_rms}"
    assert lead_rms > 0.05, f"leading window is too quiet: {lead_rms}"
    assert trail_rms > 0.05, f"trailing window is too quiet: {trail_rms}"


def test_determinism_audio(tmp_path: Path):
    for name, builder in [
        ("flat", make_flat_bed),
        ("scored", make_act_scored_stems),
        ("silence", make_paradigm_shift_silence),
    ]:
        if name == "scored":
            [p1] = [p for p in [builder(tmp_path / f"{name}_a")]]
            [p2] = [p for p in [builder(tmp_path / f"{name}_b")]]
        else:
            fx1 = builder(tmp_path / f"{name}_a")[0]
            fx2 = builder(tmp_path / f"{name}_b")[0]
            assert fx1.path.read_bytes() == fx2.path.read_bytes(), f"{name}: not deterministic"


def test_hermetic_no_network_audio(monkeypatch, tmp_path: Path):
    import socket
    noop = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network disabled"))
    monkeypatch.setattr(socket, "gethostbyname", noop)
    fixtures = make_flat_bed(tmp_path / "hermetic")
    assert len(fixtures) == 1
    dur = read_duration(fixtures[0].path)
    assert dur > 0


def test_audio_fixture_metadata_fields(tmp_path: Path):
    all_fx = build_all_audio_fixtures(tmp_path / "meta")
    assert "flat_bed" in all_fx
    assert "act_scored" in all_fx
    assert "silence" in all_fx
    for name, fixtures in all_fx.items():
        assert len(fixtures) >= 1
        for fx in fixtures:
            assert isinstance(fx, AudioFixture)
            assert fx.path.exists()
            assert fx.duration_sec > 0
            assert isinstance(fx.rms_db, float)
            assert isinstance(fx.label, str) and fx.label
