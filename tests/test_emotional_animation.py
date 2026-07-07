"""Tests for TKT-505 emotional animation."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from emotional_animation import (
    is_emotional_animation_enabled,
    should_animate_graphic,
    get_animation_metadata,
)


class TestEmotionalAnimationMode:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("EMOTIONAL_ANIMATION_MODE", raising=False)
        assert is_emotional_animation_enabled() is False

    def test_on_mode(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "on")
        assert is_emotional_animation_enabled() is True


class TestShouldAnimate:
    def test_qualifying_beat(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "on")
        beat = {
            "shot_type": "graphic_progressive",
            "est_duration_sec": 5.0,
            "narrative_function": "thesis_close",
        }
        assert should_animate_graphic(beat) is True

    def test_short_graphic_not_animated(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "on")
        beat = {
            "shot_type": "graphic_progressive",
            "est_duration_sec": 1.5,
            "narrative_function": "thesis_close",
        }
        assert should_animate_graphic(beat) is False

    def test_non_emotional_function_not_animated(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "on")
        beat = {
            "shot_type": "graphic_progressive",
            "est_duration_sec": 5.0,
            "narrative_function": "factual_data",
        }
        assert should_animate_graphic(beat) is False

    def test_off_mode_never_animates(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "off")
        beat = {
            "shot_type": "graphic_progressive",
            "est_duration_sec": 5.0,
            "narrative_function": "thesis_close",
        }
        assert should_animate_graphic(beat) is False


class TestAnimationMetadata:
    def test_metadata_for_qualifying_beat(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "on")
        beat = {
            "shot_type": "graphic_progressive",
            "est_duration_sec": 5.0,
            "narrative_function": "thesis_close",
        }
        meta = get_animation_metadata(beat)
        assert meta is not None
        assert "animation" in meta
        assert meta["animation"]["type"] == "alpha_reveal"

    def test_none_for_non_qualifying(self, monkeypatch):
        monkeypatch.setenv("EMOTIONAL_ANIMATION_MODE", "on")
        beat = {
            "shot_type": "graphic_progressive",
            "est_duration_sec": 1.0,
            "narrative_function": "thesis_close",
        }
        assert get_animation_metadata(beat) is None
