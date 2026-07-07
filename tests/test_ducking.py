"""Tests for TKT-504 frequency-selective dynamic ducking."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audio_ducking import (
    is_selective_ducking_enabled,
    get_duck_db,
    build_duck_args,
)


class TestDuckingMode:
    def test_default_simple(self, monkeypatch):
        monkeypatch.delenv("DUCKING_MODE", raising=False)
        assert is_selective_ducking_enabled() is False

    def test_selective_mode(self, monkeypatch):
        monkeypatch.setenv("DUCKING_MODE", "selective")
        assert is_selective_ducking_enabled() is True

    def test_simple_mode_explicit(self, monkeypatch):
        monkeypatch.setenv("DUCKING_MODE", "simple")
        assert is_selective_ducking_enabled() is False


class TestDuckDb:
    def test_duck_db_negative(self):
        assert get_duck_db() < 0


class TestBuildDuckArgs:
    def test_selective_with_narration(self, monkeypatch):
        monkeypatch.setenv("DUCKING_MODE", "selective")
        args = build_duck_args({"narrative_function": "thesis"}, "/tmp/narration.wav")
        assert len(args) > 0
        assert any("sidechaincompress" in a for a in args)

    def test_selective_without_narration(self, monkeypatch):
        monkeypatch.setenv("DUCKING_MODE", "selective")
        args = build_duck_args({"narrative_function": "thesis"}, None)
        assert args == []

    def test_simple_mode_returns_empty(self, monkeypatch):
        monkeypatch.setenv("DUCKING_MODE", "simple")
        args = build_duck_args({"narrative_function": "thesis"}, "/tmp/narration.wav")
        assert args == []
