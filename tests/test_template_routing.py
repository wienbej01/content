"""tests/test_template_routing.py — TKT-402: All 12 templates reachable via layout_map."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _all_spec_types():
    return [
        "title_card",
        "source_card",
        "quote_card",
        "framework_card",
        "stat_card",
        "comparison_card",
        "before_after_card",
        "timeline_card",
        "cost_card",
        "decision_card",
        "ui_annotation_card",
        "side_by_side_card",
    ]


class TestLayoutMapCoversAll12Templates:
    """Verifies render_local_graphic_render_unit maps all 12 spec types."""

    def test_all_spec_types_mapped(self):
        from render_graphics import RENDERERS

        expected_layouts = {
            "title_card": "key_line",
            "source_card": "lower_third",
            "quote_card": "quote_card",
            "framework_card": "framework_3_step",
            "stat_card": "stat_callout",
            "comparison_card": "comparison_card",
            "before_after_card": "before_after",
            "timeline_card": "timeline",
            "cost_card": "cost_stack",
            "decision_card": "decision_tree",
            "ui_annotation_card": "annotated_ui_mock",
            "side_by_side_card": "side_by_side",
        }

        for spec_type in _all_spec_types():
            layout = expected_layouts[spec_type]
            assert layout in RENDERERS, (
                f"Layout '{layout}' for spec type '{spec_type}' not found in RENDERERS. "
                f"Available: {sorted(RENDERERS.keys())}"
            )

    @pytest.mark.parametrize("spec_type", _all_spec_types())
    def test_spec_type_renders(self, spec_type, tmp_path):
        from render_graphics import render_spec, RENDERERS

        expected_layouts = {
            "title_card": "key_line",
            "source_card": "lower_third",
            "quote_card": "quote_card",
            "framework_card": "framework_3_step",
            "stat_card": "stat_callout",
            "comparison_card": "comparison_card",
            "before_after_card": "before_after",
            "timeline_card": "timeline",
            "cost_card": "cost_stack",
            "decision_card": "decision_tree",
            "ui_annotation_card": "annotated_ui_mock",
            "side_by_side_card": "side_by_side",
        }

        layout = expected_layouts[spec_type]
        spec_data = {"layout": layout, "text": "Test content for " + spec_type}
        out = tmp_path / f"{spec_type}.png"
        render_spec(spec_data, out)
        assert out.exists()
        from PIL import Image
        img = Image.open(out)
        assert img.size == (1920, 1080), f"{spec_type}: expected 1920x1080, got {img.size}"


class TestUnknownLayoutRaisesError:
    """Unknown deterministic_text_spec type raises loud error."""

    def test_unknown_type_raises(self, tmp_path):
        from render_graphics import render_spec

        spec = {"layout": "nonexistent_bogus_type", "text": "Test"}
        with pytest.raises(RuntimeError, match="Unknown graphics layout"):
            render_spec(spec, tmp_path / "should_not_exist.png")
