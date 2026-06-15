"""Tests for PST-02: Calibrated Pre-TTS Duration Estimates."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import yaml
from estimate_beat_durations import estimate_duration_sec

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "voice_pacing.yaml"


def test_calibrated_config_loads():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    assert cfg["calibrated_wpm"] > 0
    assert cfg["calibrated_wps"] > 0
    assert len(cfg["measured_wpm"]) >= 1


def test_estimate_uses_calibration():
    # 10 words at ~1.8077 WPS should be ~5.53s
    result = estimate_duration_sec("A ten word sentence here with exactly ten words now")
    expected = 10 / 1.8077
    assert abs(result["estimate_sec"] - expected) < 0.5


def test_estimate_labeled_nonauthoritative():
    result = estimate_duration_sec("Some text here")
    assert result["authoritative"] is False


def test_uncertainty_recorded():
    result = estimate_duration_sec("Some text here")
    assert "uncertainty_pct" in result
    assert result["uncertainty_pct"] > 0


def test_estimate_never_authoritative():
    result = estimate_duration_sec("Testing that output key is estimate_sec")
    assert "estimate_sec" in result
    assert "audio_duration_sec" not in result
