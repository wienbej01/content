#!/usr/bin/env python3
"""TKT-703 tests for thumbnail generator."""
import tempfile
from pathlib import Path

import pytest

from scripts.thumbnail_generator import (
    generate_thumbnails,
    validate_readability,
    contrast_ratio,
    BRAND_BG,
    BRAND_TEXT,
)


def test_contrast_ratio():
    """Contrast ratio calculation."""
    ratio = contrast_ratio((255, 255, 255), (0, 0, 0))
    assert ratio > 20.0  # white vs black = 21:1

    ratio2 = contrast_ratio(BRAND_TEXT, BRAND_BG)
    assert ratio2 >= 4.5  # brand combo meets WCAG


def test_generate_three_variants():
    """Generate 3 thumbnail variants."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "thumbs"
        results = generate_thumbnails(None, "How AI Thinks in 2024", out)
        assert len(results) == 3
        for r in results:
            assert Path(r["path"]).exists()
        # All distinct layouts
        layouts = {r["layout"] for r in results}
        assert len(layouts) == 3


def test_readability_validation():
    """validate_readability returns expected keys."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "thumbs"
        results = generate_thumbnails(None, "Test Title", out)
        v = results[0]["validation"]
        assert "text_height_ok" in v
        assert "contrast_ok" in v
        assert "issues" in v
        assert len(v["issues"]) == 0  # no issues with brand default colors
