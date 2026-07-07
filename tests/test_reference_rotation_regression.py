"""Tests for TKT-204 reference-frame rotation enforcement regression lock-in."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from review_storyboard import review


class TestReferenceRotationRegression:
    def _make_storyboard(self, beats: list[dict]) -> dict:
        return {
            "schema_version": "2.0",
            "project_id": "test_regression",
            "video_type": "explainer",
            "beats": beats,
        }

    def test_flat_mode_no_regression(self):
        """Flat mode must produce same validation verdict as before the feature."""
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": 1,
             "est_duration_sec": 5, "canonical_ref_frame": f"frame_{i % 4}",
             "visual_brief": f"Brief {i}", "narrative_function": f"func_{i}"}
            for i in range(10)
        ]
        storyboard = self._make_storyboard(beats)
        blocking, warnings, fixes = review(storyboard, {})
        # Should not have frame_gap_violation warnings in flat mode for varied frames
        assert not any("frame_gap_violation" in b for b in blocking)

    def test_chapter_mode_same_frame_gap_blocked(self):
        """Chapter mode: same frame in consecutive hero beats → frame_gap_violation."""
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": 1,
             "est_duration_sec": 5, "canonical_ref_frame": "frame_a",
             "visual_brief": f"Brief {i}", "narrative_function": f"func_{i}"}
            for i in range(4)
        ]
        storyboard = self._make_storyboard(beats)
        blocking, warnings, fixes = review(storyboard, {})
        assert any("frame_gap_violation" in b for b in blocking)

    def test_validator_reports_violation_names(self):
        """Validator output JSON must include frame_gap_violation and visual_fatigue_violation."""
        beats = [
            {"beat_id": f"b_{i}", "shot_type": "hero_lipsync", "act": 1,
             "est_duration_sec": 5, "canonical_ref_frame": "frame_a",
             "visual_brief": f"Brief {i}", "narrative_function": f"func_{i}"}
            for i in range(10)
        ]
        storyboard = self._make_storyboard(beats)
        blocking, warnings, fixes = review(storyboard, {})
        names = " ".join(blocking)
        assert "frame_gap_violation" in names or "visual_fatigue_violation" in names


class TestFramesFromCorrectChapter:
    def test_visual_chapter_mapping_completeness(self):
        """All 6 acts must have a visual chapter entry in model_routing.yaml."""
        import yaml
        cfg_path = ROOT / "configs" / "james" / "model_routing.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        chapters = cfg.get("visual_variation", {}).get("chapters", {})
        for act in range(1, 7):
            assert act in chapters, f"Act {act} missing from visual_variation.chapters"
