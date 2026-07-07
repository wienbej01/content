"""Tests for visual chapter mapping (TKT-201)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from produce_db import _select_hero_reference_image


@pytest.fixture
def routing() -> dict:
    return {
        "lipsync_references": {
            "active_set": "navy_sweater_library",
            "sets": {
                "navy_sweater_library": {
                    "frames": [
                        {"angle": "front", "path": "/refs/front.png"},
                        {"angle": "front_speaking", "path": "/refs/front_speaking.png"},
                        {"angle": "three_quarter", "path": "/refs/three_quarter.png"},
                        {"angle": "side_profile", "path": "/refs/side_profile.png"},
                    ]
                },
                "dark_jacket_library": {
                    "frames": [
                        {"angle": "front", "path": "/refs/dark_front.png"},
                        {"angle": "medium_wide", "path": "/refs/dark_medium_wide.png"},
                        {"angle": "three_quarter", "path": "/refs/dark_three_quarter.png"},
                        {"angle": "side_profile", "path": "/refs/dark_side_profile.png"},
                    ]
                },
            }
        },
        "visual_variation": {
            "mode": "flat",
            "min_hero_frame_gap": 3,
            "max_visual_fatigue_score": 0.75,
            "chapters": {
                1: {"set": "navy_sweater_library", "allowed_angles": ["front", "front_speaking"]},
                2: {"set": "navy_sweater_library", "allowed_angles": ["three_quarter", "side_profile"]},
                3: {"set": "dark_jacket_library", "allowed_angles": ["front", "three_quarter"]},
            }
        }
    }


class TestFlatMode:
    def test_flat_returns_active_set_frame(self, routing):
        routing["visual_variation"]["mode"] = "flat"
        result = _select_hero_reference_image(routing, hero_beat_index=0)
        assert result == "/refs/front.png"

    def test_flat_round_robin(self, routing):
        routing["visual_variation"]["mode"] = "flat"
        results = [_select_hero_reference_image(routing, i) for i in range(8)]
        assert results[0] == "/refs/front.png"
        assert results[4] == "/refs/front.png"  # wraps around

    def test_flat_ignores_act(self, routing):
        routing["visual_variation"]["mode"] = "flat"
        r1 = _select_hero_reference_image(routing, hero_beat_index=0, act=1)
        r3 = _select_hero_reference_image(routing, hero_beat_index=0, act=3)
        assert r1 == r3  # act ignored in flat mode


class TestChapterMode:
    def test_chapter_1_frames(self, routing):
        routing["visual_variation"]["mode"] = "chapter"
        results = set()
        for i in range(10):
            results.add(_select_hero_reference_image(routing, hero_beat_index=i, act=1))
        # chapter 1 uses navy_sweater_library with front, front_speaking only
        assert results == {"/refs/front.png", "/refs/front_speaking.png"}

    def test_chapter_2_frames(self, routing):
        routing["visual_variation"]["mode"] = "chapter"
        results = set()
        for i in range(10):
            results.add(_select_hero_reference_image(routing, hero_beat_index=i, act=2))
        assert results == {"/refs/three_quarter.png", "/refs/side_profile.png"}

    def test_chapter_3_uses_dark_jacket(self, routing):
        routing["visual_variation"]["mode"] = "chapter"
        results = set()
        for i in range(10):
            results.add(_select_hero_reference_image(routing, hero_beat_index=i, act=3))
        assert "/refs/dark_front.png" in results
        assert "/refs/dark_three_quarter.png" in results

    def test_chapter_missing_act_falls_back_to_flat(self, routing):
        routing["visual_variation"]["mode"] = "chapter"
        result = _select_hero_reference_image(routing, hero_beat_index=0, act=99)
        # act 99 not in chapters → falls back to flat (active_set = navy_sweater_library)
        assert result == "/refs/front.png"


class TestEdgeCases:
    def test_empty_frames_returns_none(self):
        routing = {
            "lipsync_references": {
                "active_set": "empty_set",
                "sets": {"empty_set": {"frames": []}}
            },
            "visual_variation": {"mode": "flat"}
        }
        assert _select_hero_reference_image(routing, 0) is None

    def test_no_visual_variation_defaults_to_flat(self):
        routing = {
            "lipsync_references": {
                "active_set": "navy_sweater_library",
                "sets": {
                    "navy_sweater_library": {
                        "frames": [{"angle": "front", "path": "/refs/front.png"}]
                    }
                }
            }
        }
        result = _select_hero_reference_image(routing, 0)
        assert result == "/refs/front.png"
