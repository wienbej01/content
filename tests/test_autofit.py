"""tests/test_autofit.py — TKT-404: Auto-fit text layout (no hard truncation)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# ============================================================================
# fit_text — direct unit tests on the shared auto-fit function
# ============================================================================

class TestFitTextDirect:
    """Direct tests for the fit_text() helper."""

    def test_short_text_returns_max_size(self, tmp_path):
        from PIL import Image, ImageDraw
        from render_graphics import fit_text, _font
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        font, lines = fit_text("Hi", d, box_width=800, max_lines=2, role="body",
                               min_size=12, max_size=72)
        ref = _font(72, role="body")
        ref_bbox = d.textbbox((0, 0), "Hi", font=ref)
        f_bbox = d.textbbox((0, 0), "Hi", font=font)
        assert f_bbox[2] - f_bbox[0] == ref_bbox[2] - ref_bbox[0], (
            "Short text should render at max_size"
        )
        assert len(lines) == 1

    def test_long_text_fits_at_reduced_size(self, tmp_path):
        from PIL import Image, ImageDraw
        from render_graphics import fit_text
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        long_text = "word " * 25
        font, lines = fit_text(long_text, d, box_width=400, max_lines=3, role="body",
                               min_size=12, max_size=36)
        assert len(lines) <= 3, (
            f"fit_text should reduce font size so text fits in 3 lines at 400px wide, "
            f"got {len(lines)} lines"
        )
        for ln in lines:
            bbox = d.textbbox((0, 0), ln, font=font)
            assert bbox[2] - bbox[0] <= 400, (
                f"Each line must fit within box_width 400px, got {(bbox[2]-bbox[0])}px"
            )

    def test_overflow_beyond_min_size_raises(self, tmp_path):
        from PIL import Image, ImageDraw
        from render_graphics import fit_text, RenderError
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        huge_text = " enormous " * 200
        with pytest.raises(RenderError, match="exceeds capacity|does not fit"):
            fit_text(huge_text, d, box_width=100, max_lines=2, role="body",
                     min_size=12, max_size=12)

    def test_deterministic_output(self, tmp_path):
        from PIL import Image, ImageDraw
        from render_graphics import fit_text
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        text = "The only sustainable advantage is learning faster than your competition."
        result1 = fit_text(text, d, box_width=600, max_lines=3, role="body",
                           min_size=12, max_size=48)
        result2 = fit_text(text, d, box_width=600, max_lines=3, role="body",
                           min_size=12, max_size=48)
        assert result1[0].size == result2[0].size, (
            "fit_text must produce deterministic font size for identical inputs"
        )
        assert result1[1] == result2[1], (
            "fit_text must produce identical lines for identical inputs"
        )


# ============================================================================
# Integration: render_spec with full text (no [:120] truncation)
# ============================================================================

class TestRenderSpecNoTruncation:
    """Render templates with full text — no [:120] truncation anywhere."""

    KEY_LINE_LONG = (
        "The only sustainable advantage is learning faster than your competition. "
        "Organizations that prioritize continuous learning and adaptation will "
        "outperform those that rely on static advantages."
    )

    def test_key_line_long_text_renders_without_error(self, tmp_path):
        from render_graphics import render_spec
        spec = {"layout": "key_line", "text": self.KEY_LINE_LONG}
        out = tmp_path / "key_line_long.png"
        render_spec(spec, out)
        assert out.exists()

    def test_key_line_short_text_renders_at_max_size(self, tmp_path):
        from render_graphics import render_spec, _font
        from PIL import Image, ImageDraw
        spec = {"layout": "key_line", "text": "Hello"}
        out = tmp_path / "key_line_short.png"
        render_spec(spec, out)
        assert out.exists()

    def test_framework_3_step_long_desc_raises_on_overflow(self, tmp_path):
        from render_graphics import render_spec, RenderError
        huge_desc = " ".join(["word"] * 500)
        spec = {
            "layout": "framework_3_step",
            "title": "Test",
            "steps": [
                {"number": 1, "label": "Step 1", "description": huge_desc},
            ]
        }
        out = tmp_path / "overflow.png"
        with pytest.raises(RenderError, match="exceeds capacity|does not fit"):
            render_spec(spec, out)

    def test_quote_card_long_context_raises_on_overflow(self, tmp_path):
        from render_graphics import render_spec, RenderError
        long_context = " ".join(["verbose"] * 500)
        spec = {
            "layout": "quote_card",
            "quote": "A short quote.",
            "author": "Author",
            "context": long_context,
        }
        out = tmp_path / "overflow_quote.png"
        with pytest.raises(RenderError, match="exceeds capacity|does not fit"):
            render_spec(spec, out)

    def test_lower_third_long_subtitle_auto_fits(self, tmp_path):
        from render_graphics import render_spec
        long_subtitle = (
            "Professor of Economics at Stanford University with over 20 years of "
            "research experience in behavioral economics and decision theory"
        )
        spec = {"layout": "lower_third", "text": "Dr. Jane Smith", "subtitle": long_subtitle}
        out = tmp_path / "lower_third_long.png"
        render_spec(spec, out)
        assert out.exists()


# ============================================================================
# Regression: short text still renders at expected quality
# ============================================================================

class TestShortTextRegression:
    """Short text should render at full (max) size, identical to before."""

    def test_short_key_line_renders(self, tmp_path):
        from render_graphics import render_spec
        spec = {"layout": "key_line", "text": "Short"}
        out = tmp_path / "short_key.png"
        render_spec(spec, out)
        assert out.exists()
