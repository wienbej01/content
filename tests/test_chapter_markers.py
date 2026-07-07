"""Tests for TKT-503 chapter marker audio cues."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chapter_markers import (
    is_chapter_marker_enabled,
    get_cue_for_act_boundary,
    get_cue_library,
    CUE_TYPES,
)


class TestChapterMarkerMode:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("CHAPTER_MARKERS_MODE", raising=False)
        assert is_chapter_marker_enabled() is False

    def test_on_mode(self, monkeypatch):
        monkeypatch.setenv("CHAPTER_MARKERS_MODE", "on")
        assert is_chapter_marker_enabled() is True


class TestCueLibrary:
    def test_cue_library_has_required_types(self):
        library = get_cue_library()
        assert "act_open" in library
        assert "act_close" in library
        assert "chapter_reveal" in library
        assert "transition_whoosh" in library

    def test_cue_types_have_duration(self):
        for cue_type, info in CUE_TYPES.items():
            assert "duration_sec" in info
            assert info["duration_sec"] > 0


class TestActBoundaryCues:
    def test_act_open_cue(self):
        cue = get_cue_for_act_boundary(1, is_open=True)
        assert cue["type"] == "act_open"
        assert cue["act"] == 1

    def test_act_close_cue(self):
        cue = get_cue_for_act_boundary(3, is_open=False)
        assert cue["type"] == "act_close"
        assert cue["act"] == 3
