"""Tests for TKT-202 frame-gap + visual-fatigue validator."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from review_storyboard import _visual_variation_check, _bands_check, review


def _mk_beats(beats: list[dict]) -> list[dict]:
    return beats


class TestFrameGap:
    def _mk_hero_beats(self, frames: list[str | None], act: int = 1) -> list[dict]:
        return [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": act,
             "canonical_ref_frame": f, "visual_brief": "Valid brief",
             "narrative_function": "thesis_statement"}
            for i, f in enumerate(frames)
        ]

    def test_same_frame_consecutive_triggers_gap(self):
        beats = self._mk_hero_beats(["frame_a", "frame_a"])
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert any("frame_gap_violation" in b for b in blocking)

    def test_gap_above_threshold_no_violation(self):
        beats = self._mk_hero_beats(["frame_a", "frame_b", "frame_c", "frame_a"])
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert not any("frame_gap_violation" in b for b in blocking)

    def test_no_frames_no_violation(self):
        beats = [
            {"beat_id": "b_0", "shot_type": "hero_lipsync", "act": 1,
             "canonical_ref_frame": None, "visual_brief": "Brief A",
             "narrative_function": "hook"},
            {"beat_id": "b_1", "shot_type": "hero_lipsync", "act": 1,
             "canonical_ref_frame": None, "visual_brief": "Brief B",
             "narrative_function": "thesis_statement"},
        ]
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert not blocking


class TestVisualFatigue:
    def test_all_same_frame_triggers_fatigue(self):
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": 1,
             "canonical_ref_frame": "frame_a"}
            for i in range(10)
        ]
        beats[5]["shot_type"] = "broll_environment"  # one non-hero
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert any("visual_fatigue_violation" in b for b in blocking)

    def test_good_diversity_no_fatigue(self):
        acts = {0: "frame_a", 1: "frame_b", 2: "frame_c"}
        beats = []
        for i in range(12):
            beats.append({
                "beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": (i % 3) + 1,
                "canonical_ref_frame": acts[i % 3],
            })
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert not any("visual_fatigue_violation" in b for b in blocking)


class TestWithShotMix:
    def test_too_many_hero_beats_with_same_frame_blocked(self):
        m = {"hero_lipsync_pct": 90, "hero_cutaway_pct": 0, "broll_specific_pct": 5,
             "graphics_ui_pct": 5, "broll_metaphorical_pct": 0, "kinetic_text_pct": 0,
             "distinct_visual_setups": 1}
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": 1,
             "canonical_ref_frame": "single_frame", "est_duration_sec": 5}
            for i in range(10)
        ]
        blocking, warnings = [], []
        _bands_check(m, blocking, warnings, beats=beats)
        _visual_variation_check(beats, blocking, warnings)
        assert any("frame_gap_violation" in b for b in blocking or [
            any("visual_fatigue" in x for x in blocking)
        ])


class TestEdgeCases:
    def test_acts_outside_range_no_crash(self):
        beats = [
            {"beat_id": "b1", "shot_type": "hero_lipsync", "act": 99,
             "canonical_ref_frame": "frame_a"},
            {"beat_id": "b2", "shot_type": "hero_lipsync", "act": 99,
             "canonical_ref_frame": "frame_a"},
        ]
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert any("frame_gap_violation" in b for b in blocking)

    def test_non_hero_beats_ignored(self):
        beats = [
            {"beat_id": "b1", "shot_type": "broll_environment", "act": 1,
             "visual_brief": "City skyline", "narrative_function": "tonal_reset"},
            {"beat_id": "b2", "shot_type": "broll_environment", "act": 1,
             "visual_brief": "Office interior", "narrative_function": "visual_pause"},
        ]
        blocking, warnings = [], []
        _visual_variation_check(beats, blocking, warnings)
        assert not blocking
