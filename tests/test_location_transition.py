"""Tests for TKT-203 location_transition beat type + minimum-gap rule."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from review_storyboard import _location_transition_check, VALID_SHOT_TYPES


class TestLocationTransitionType:
    def test_location_transition_in_valid_shot_types(self):
        assert "location_transition" in VALID_SHOT_TYPES


class TestLocationTransitionGap:
    def test_no_transition_in_90s_triggers_warning(self):
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "est_duration_sec": 10}
            for i in range(10)
        ]
        warnings = []
        _location_transition_check(beats, warnings)
        assert any("location_transition_gap" in w for w in warnings)

    def test_transition_every_45s_no_warning(self):
        beats = []
        for i in range(10):
            if i > 0 and i % 2 == 0:
                beats.append({
                    "beat_id": f"lt_{i}", "shot_type": "location_transition",
                    "est_duration_sec": 3
                })
            beats.append({
                "beat_id": f"b_{i}", "shot_type": "hero_lipsync",
                "est_duration_sec": 20
            })
        warnings = []
        _location_transition_check(beats, warnings)
        assert not any("location_transition_gap" in w for w in warnings)

    def test_empty_beats_no_warning(self):
        warnings = []
        _location_transition_check([], warnings)
        assert not warnings

    def test_transition_at_60s_boundary(self):
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "est_duration_sec": 15}
            for i in range(4)
        ]
        beats.append({
            "beat_id": "lt_1", "shot_type": "location_transition", "est_duration_sec": 3
        })
        warnings = []
        _location_transition_check(beats, warnings)
        assert not warnings
