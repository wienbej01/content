"""Tests for TKT-502 silence rule."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audio_silence import is_silence_required, compute_music_volume, get_ramp_in_sec


class TestSilenceOff:
    def test_off_mode_never_silences(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "off")
        assert is_silence_required("paradigm_shift") is False
        assert compute_music_volume({"narrative_function": "paradigm_shift"}) == 0.0


class TestSilenceOn:
    def test_paradigm_shift_silenced(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        assert is_silence_required("paradigm_shift") is True

    def test_myth_bust_reveal_silenced(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        assert is_silence_required("myth_bust_reveal") is True

    def test_philosophical_close_silenced(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        assert is_silence_required("philosophical_close") is True

    def test_factual_data_not_silenced(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        assert is_silence_required("factual_data") is False

    def test_none_not_silenced(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        assert is_silence_required(None) is False

    def test_custom_silence_functions(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        assert is_silence_required("hook", silence_functions=["hook", "cta"]) is True


class TestComputeVolume:
    def test_silence_volume(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        vol = compute_music_volume({"narrative_function": "paradigm_shift"})
        assert vol == float("-inf")

    def test_normal_volume(self, monkeypatch):
        monkeypatch.setenv("AUDIO_SILENCE_MODE", "on")
        vol = compute_music_volume({"narrative_function": "factual_data"})
        assert vol == 0.0


class TestRampIn:
    def test_ramp_in_positive(self):
        assert get_ramp_in_sec() > 0
