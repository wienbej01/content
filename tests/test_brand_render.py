"""tests/test_brand_render.py — TKT-401: Brand typography, supersampling, 9x16."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# ============================================================================
# Fixtures
# ============================================================================

ALL_TEMPLATES_16X9 = [
    {"layout": "lower_third", "text": "Dr. Jane Smith", "subtitle": "Professor of Economics"},
    {"layout": "key_line", "text": "The only sustainable advantage is learning faster"},
    {"layout": "stat_callout", "stat": "73%", "label": "of professionals agree"},
    {"layout": "side_by_side", "left_title": "Old Way", "left_items": ["Manual", "Slow"],
     "right_title": "New Way", "right_items": ["Automated", "Fast"]},
    {"layout": "comparison_card", "left_column": {"title": "Option A", "items": ["Speed", "Cost"]},
     "right_column": {"title": "Option B", "items": ["Efficiency", "Value"]}},
    {"layout": "framework_3_step", "title": "Three-Step Framework",
     "steps": [{"number": 1, "label": "Plan"}, {"number": 2, "label": "Do"}, {"number": 3, "label": "Review"}]},
    {"layout": "decision_tree", "root": {"question": "Which path?"},
     "branches": [{"condition": "A", "outcome": "Result A"}, {"condition": "B", "outcome": "Result B"}]},
    {"layout": "cost_stack", "title": "Costs",
     "segments": [{"label": "Rent", "value": "$1200"}, {"label": "Food", "value": "$400"}]},
    {"layout": "before_after", "before": {"label": "Before", "description": "Old process"},
     "after": {"label": "After", "description": "New process"}, "change_highlight": "50% faster"},
    {"layout": "timeline", "title": "Timeline",
     "events": [{"time_label": "Q1", "label": "Research"}, {"time_label": "Q2", "label": "Build"}]},
    {"layout": "annotated_ui_mock", "ui_title": "Dashboard",
     "annotations": [{"element_name": "Chart", "callout_text": "Revenue", "position_hint": "center"}]},
    {"layout": "quote_card", "quote": "Innovation distinguishes between a leader and a follower.",
     "author": "Steve Jobs", "author_title": "Entrepreneur"},
]


# ============================================================================
# Helper
# ============================================================================

def _img_size(img_path):
    from PIL import Image
    return Image.open(img_path).size


# ============================================================================
# Font — Glyph width metrics test (brand font detectable, not DejaVu)
# ============================================================================

class TestBrandFontGlyphWidths:
    """Render uses brand fonts, verifiable via known-glyph-width metrics."""

    def test_body_font_is_inter_not_dejavu(self, tmp_path):
        from render_graphics import _font
        from PIL import Image, ImageDraw, ImageFont

        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        size = 36

        rendered_font = _font(size, bold=False)

        brand_path = ROOT / "brand" / "fonts" / "Inter.ttf"
        brand_font = ImageFont.truetype(str(brand_path), size)

        img = Image.new("RGBA", (200, 50), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r_bbox = d.textbbox((0, 0), text, font=rendered_font)
        b_bbox = d.textbbox((0, 0), text, font=brand_font)
        r_w = r_bbox[2] - r_bbox[0]
        b_w = b_bbox[2] - b_bbox[0]

        assert r_w == b_w, (
            f"Body font width mismatch: brand Inter={b_w}, rendered={r_w}. "
            f"This indicates DejaVu/fallback font is being used instead of brand fonts."
        )


# ============================================================================
# 16x9 rendering
# ============================================================================

class TestRender16x9:
    """Each template renders at 1920x1080 with brand fonts."""

    @pytest.mark.parametrize("spec", ALL_TEMPLATES_16X9,
                             ids=[s["layout"] for s in ALL_TEMPLATES_16X9])
    def test_renders_1920x1080(self, spec, tmp_path):
        from render_graphics import render_spec
        out = tmp_path / f"{spec['layout']}.png"
        render_spec(spec, out)
        assert out.exists()
        w, h = _img_size(out)
        assert w == 1920 and h == 1080, f"{spec['layout']}: expected 1920x1080, got {w}x{h}"

    @pytest.mark.parametrize("spec", ALL_TEMPLATES_16X9,
                             ids=[s["layout"] for s in ALL_TEMPLATES_16X9])
    def test_has_visible_content(self, spec, tmp_path):
        from render_graphics import render_spec
        out = tmp_path / f"{spec['layout']}.png"
        render_spec(spec, out)
        from PIL import Image
        img = Image.open(out)
        data = img.getdata()
        assert any(px[3] > 0 for px in data), f"{spec['layout']} has no visible content"


# ============================================================================
# 9x16 rendering — aspect variant
# ============================================================================

class TestRender9x16:
    """Each template renders at 1080x1920 with recomputed safe margins."""

    @pytest.mark.parametrize("spec", ALL_TEMPLATES_16X9,
                             ids=[s["layout"] for s in ALL_TEMPLATES_16X9])
    def test_renders_1080x1920(self, spec, tmp_path):
        from render_graphics import render_spec
        spec = {**spec, "aspect": "9x16"}
        out = tmp_path / f"{spec['layout']}_9x16.png"
        render_spec(spec, out)
        assert out.exists()
        w, h = _img_size(out)
        assert w == 1080 and h == 1920, f"{spec['layout']} 9x16: expected 1080x1920, got {w}x{h}"

    @pytest.mark.parametrize("spec", ALL_TEMPLATES_16X9,
                             ids=[s["layout"] for s in ALL_TEMPLATES_16X9])
    def test_has_visible_content(self, spec, tmp_path):
        from render_graphics import render_spec
        spec = {**spec, "aspect": "9x16"}
        out = tmp_path / f"{spec['layout']}_9x16.png"
        render_spec(spec, out)
        from PIL import Image
        img = Image.open(out)
        data = img.getdata()
        assert any(px[3] > 0 for px in data), f"{spec['layout']} 9x16 has no visible content"


# ============================================================================
# Negative: missing brand fonts
# ============================================================================

class TestMissingBrandFonts:
    """When brand fonts directory is hidden, render raises a loud error."""

    def test_missing_font_raises_render_error(self, tmp_path, monkeypatch):
        from render_graphics import render_spec, RenderError
        monkeypatch.setattr("render_graphics.FONT_DIR", tmp_path / "empty_fonts")
        spec = {"layout": "key_line", "text": "Test"}
        out = tmp_path / "missing_font.png"
        with pytest.raises(RenderError, match="Brand font"):
            render_spec(spec, out)
        assert not out.exists(), "No PNG should be written when brand fonts are missing"
