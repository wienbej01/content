"""TKT-406: Overlay projection classification tests.

Tests verify:
1. Projection of lower-third intent yields overlay entry, not full-frame unit.
2. Stat callout and key line intents are classified as overlay.
3. Full-frame layouts (framework, comparison, timeline) remain full-frame.
4. Unknown layout defaults to full-frame.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


class TestOverlayClassification:
    """Unit tests for classify_overlay_intent and classify_graphic_kind."""

    def test_lower_third_is_overlay(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("lower_third") == "overlay"

    def test_key_line_is_overlay(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("key_line") == "overlay"

    def test_stat_callout_is_overlay(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("stat_callout") == "overlay"

    def test_framework_3_step_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("framework_3_step") == "full_frame"

    def test_comparison_card_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("comparison_card") == "full_frame"

    def test_timeline_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("timeline") == "full_frame"

    def test_quote_card_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("quote_card") == "full_frame"

    def test_side_by_side_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("side_by_side") == "full_frame"

    def test_context_switch_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("context_switch") == "full_frame"

    def test_before_after_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("before_after") == "full_frame"

    def test_annotated_ui_mock_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("annotated_ui_mock") == "full_frame"

    def test_decision_tree_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("decision_tree") == "full_frame"

    def test_cost_stack_is_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("cost_stack") == "full_frame"

    def test_unknown_layout_defaults_to_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("nonexistent_layout") == "full_frame"

    def test_empty_layout_defaults_to_full_frame(self):
        from storyboard_projection import classify_overlay_intent
        assert classify_overlay_intent("") == "full_frame"


class TestClassifyGraphicKind:
    """Unit tests for classify_graphic_kind with full spec dicts."""

    def test_lower_third_graphic_is_overlay(self):
        from storyboard_projection import classify_graphic_kind
        gfx = {"layout": "lower_third", "text": "Hello"}
        assert classify_graphic_kind(gfx) == "overlay"

    def test_stat_callout_graphic_is_overlay(self):
        from storyboard_projection import classify_graphic_kind
        gfx = {"layout": "stat_callout", "text": "42%"}
        assert classify_graphic_kind(gfx) == "overlay"

    def test_framework_graphic_is_full_frame(self):
        from storyboard_projection import classify_graphic_kind
        gfx = {"layout": "framework_3_step", "text": "Step 1"}
        assert classify_graphic_kind(gfx) == "full_frame"

    def test_none_graphics_is_full_frame(self):
        from storyboard_projection import classify_graphic_kind
        assert classify_graphic_kind(None) == "full_frame"

    def test_empty_dict_is_full_frame(self):
        from storyboard_projection import classify_graphic_kind
        assert classify_graphic_kind({}) == "full_frame"


class TestOverlayPositionFor:
    """Unit tests for overlay_position_for."""

    def test_lower_third_16x9_default(self):
        from storyboard_projection import overlay_position_for
        pos = overlay_position_for("lower_third", "16x9")
        assert pos == {"x": 70, "y": 1010, "align": "bottom_left"}

    def test_lower_third_9x16_default(self):
        from storyboard_projection import overlay_position_for
        pos = overlay_position_for("lower_third", "9x16")
        assert pos == {"x": 40, "y": 1770, "align": "bottom_left"}

    def test_key_line_16x9_default(self):
        from storyboard_projection import overlay_position_for
        pos = overlay_position_for("key_line", "16x9")
        assert pos == {"x": 70, "y": 1010, "align": "bottom_left"}

    def test_unknown_layout_uses_lower_third_default(self):
        from storyboard_projection import overlay_position_for
        pos = overlay_position_for("nonexistent", "16x9")
        assert pos == {"x": 70, "y": 1010, "align": "bottom_left"}
