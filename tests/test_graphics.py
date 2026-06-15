#!/usr/bin/env python3
"""tests/test_graphics.py — TKT-11: Deterministic graphics overlay renderer tests."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from render_graphics import render_spec, render_batch, RENDERERS


def _has_nontransparent(img):
    """Check if image has any non-fully-transparent pixels."""
    data = img.getdata()
    return any(px[3] > 0 for px in data)


def test_lower_third_renders(tmp_path):
    """lower_third layout -> PNG exists, correct size, non-transparent pixels."""
    from PIL import Image
    out = tmp_path / "lt.png"
    render_spec({"layout": "lower_third", "text": "HELLO"}, out)
    assert out.exists()
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"
    assert _has_nontransparent(img)


def test_key_line_renders(tmp_path):
    """key_line layout -> PNG exists."""
    out = tmp_path / "kl.png"
    render_spec({"layout": "key_line", "text": "Big idea here"}, out)
    assert out.exists()
    from PIL import Image
    img = Image.open(out)
    assert img.size == (1920, 1080)


def test_unknown_layout_fails():
    """unknown layout -> RuntimeError."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "bad.png"
        with pytest.raises(RuntimeError, match="Unknown graphics layout"):
            render_spec({"layout": "nonexistent_layout"}, out)


def test_text_overflow_handled(tmp_path):
    """Very long text doesn't crash (word-wrap or truncate)."""
    long_text = "superlongword " * 200
    for layout in RENDERERS:
        out = tmp_path / f"{layout}_overflow.png"
        spec = {"layout": layout, "text": long_text, "stat": long_text,
                "label": long_text, "left_title": "A", "right_title": "B",
                "left_items": [long_text], "right_items": [long_text]}
        render_spec(spec, out)  # must not raise
        assert out.exists()


def test_batch_renders_all_required(tmp_path):
    """2 required graphics in media plan -> 2 PNGs created."""
    plan = {
        "beats": [
            {"beat_id": "beat_01", "graphic": {"required": True, "layout": "lower_third", "text": "A"}},
            {"beat_id": "beat_02", "graphic": {"required": True, "layout": "stat_callout", "stat": "42%", "label": "X"}},
            {"beat_id": "beat_03", "graphic": {"required": False, "layout": "key_line", "text": "skip"}},
        ]
    }
    plan_path = tmp_path / "media_plan.json"
    plan_path.write_text(json.dumps(plan))
    render_batch(str(plan_path), str(tmp_path))
    overlays_dir = tmp_path / "assets" / "overlays"
    assert (overlays_dir / "beat_01_overlay.png").exists()
    assert (overlays_dir / "beat_02_overlay.png").exists()
    assert not (overlays_dir / "beat_03_overlay.png").exists()


def test_required_overlay_missing_fails_assembly(tmp_path):
    """Required overlay in manifest but PNG missing -> RuntimeError in validate_manifest."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from assemble import validate_manifest
    manifest = {
        "id": "test",
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "segments": [{
            "id": "seg_0",
            "beat_id": "beat_missing",
            "media": "fake.mp4",
            "words": 10,
            "overlay": {"required": True, "layout": "lower_third", "text": "X"},
        }],
    }
    # Create a fake media file so validation doesn't fail on media check
    (tmp_path / "fake.mp4").write_bytes(b"\x00" * 100)
    errors = validate_manifest(manifest, tmp_path)
    overlay_errors = [e for e in errors if "overlay" in e.lower()]
    assert len(overlay_errors) > 0, f"Expected overlay error, got: {errors}"
