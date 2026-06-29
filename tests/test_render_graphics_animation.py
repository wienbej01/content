#!/usr/bin/env python3
"""tests/test_render_graphics_animation.py — S16_T003: Progressive reveal animation tests.

Tests verify:
1. >2s graphics without animation fail with BLOCKED_GRAPHICS_ANIMATION_REQUIRED
2. Animated graphics output multi-frame sequences
3. Frame sequences have measurable changes (not all identical)
4. Animation metadata is written correctly
5. Progressive reveal works for key template types
6. Existing graphics tests remain green
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from render_graphics import (
    validate_animation_requirement,
    render_animated_template,
    DEFAULT_FRAME_RATE,
    ANIMATION_THRESHOLD,
    render_spec,
    RENDERERS,
)


def _img_size(img_path):
    """Get image dimensions."""
    from PIL import Image
    img = Image.open(img_path)
    return img.size


def _frame_hash(frame_path):
    """Get SHA-256 hash of a frame for comparison."""
    import hashlib
    return hashlib.sha256(frame_path.read_bytes()).hexdigest()


# ============================================================================
# S16_T003: Animation Requirement Validation Tests
# ============================================================================

class TestAnimationRequirementValidation:
    """Tests for validate_animation_requirement function."""

    def test_graphics_under_2s_pass_without_animation(self):
        """Graphics displayed <2s should pass without animation."""
        spec = {"layout": "key_line", "text": "Short graphic"}
        # Should not raise
        validate_animation_requirement(spec, duration_sec=1.5)
        validate_animation_requirement(spec, duration_sec=0.5)
        validate_animation_requirement(spec, duration_sec=1.999)

    def test_graphics_exactly_2s_pass_without_animation(self):
        """Graphics displayed exactly 2s should pass without animation."""
        spec = {"layout": "key_line", "text": "2-second graphic"}
        # Should not raise (threshold is >2s, not >=2s)
        validate_animation_requirement(spec, duration_sec=2.0)

    def test_graphics_over_2s_fail_without_animation(self):
        """Graphics displayed >2s must have animation enabled."""
        spec = {"layout": "key_line", "text": "Long graphic"}
        with pytest.raises(RuntimeError, match="BLOCKED_GRAPHICS_ANIMATION_REQUIRED"):
            validate_animation_requirement(spec, duration_sec=2.1)

        with pytest.raises(RuntimeError, match="BLOCKED_GRAPHICS_ANIMATION_REQUIRED"):
            validate_animation_requirement(spec, duration_sec=3.0)

        with pytest.raises(RuntimeError, match="BLOCKED_GRAPHICS_ANIMATION_REQUIRED"):
            validate_animation_requirement(spec, duration_sec=10.0)

    def test_graphics_over_2s_pass_with_animation_enabled(self):
        """Graphics >2s with animation enabled should pass validation."""
        spec = {
            "layout": "key_line",
            "text": "Animated graphic",
            "animation": {"enabled": True, "style": "reveal"}
        }
        # Should not raise
        validate_animation_requirement(spec, duration_sec=3.0)
        validate_animation_requirement(spec, duration_sec=5.0)

    def test_validation_with_unknown_duration(self):
        """Unknown duration should skip validation (no error)."""
        spec = {"layout": "key_line", "text": "Unknown duration"}
        # Should not raise when duration is None
        validate_animation_requirement(spec, duration_sec=None)


# ============================================================================
# Animated Rendering Tests
# ============================================================================

class TestAnimatedRendering:
    """Tests for render_animated_template function."""

    def test_animation_disabled_renders_single_frame(self, tmp_path):
        """Animation disabled renders single static frame."""
        spec = {
            "layout": "quote_card",
            "quote": "Test quote",
            "author": "Test Author",
            "animation": {"enabled": False}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=1.0)

        assert len(frames) == 1
        assert frames[0].exists()
        assert frames[0].name == "output_frame000.png"
        assert _img_size(frames[0]) == (1920, 1080)

    def test_animation_enabled_renders_multiple_frames(self, tmp_path):
        """Animation enabled renders multi-frame sequence."""
        spec = {
            "layout": "framework_3_step",
            "title": "Test Framework",
            "steps": [
                {"number": 1, "label": "Plan", "description": "First step"},
                {"number": 2, "label": "Execute", "description": "Second step"},
                {"number": 3, "label": "Review", "description": "Third step"}
            ],
            "animation": {"enabled": True, "style": "reveal", "hold_frames": 2}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Should render multiple frames (3 steps × 2 hold frames = 6 frames)
        assert len(frames) >= 3
        for frame in frames:
            assert frame.exists()
            assert _img_size(frame) == (1920, 1080)

    def test_reveal_animation_creates_different_frames(self, tmp_path):
        """Progressive reveal animation creates visually different frames."""
        spec = {
            "layout": "framework_3_step",
            "title": "Test Framework",
            "steps": [
                {"number": 1, "label": "Step 1", "description": "First"},
                {"number": 2, "label": "Step 2", "description": "Second"}
            ],
            "animation": {"enabled": True, "style": "reveal", "hold_frames": 1}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Verify frames are different (measurable frame changes)
        hashes = [_frame_hash(f) for f in frames]
        unique_hashes = set(hashes)

        # At least first and last frames should be different
        assert len(unique_hashes) > 1, "Animated frames should have measurable changes"

    def test_fade_animation_creates_different_frames(self, tmp_path):
        """Fade animation creates visually different frames."""
        spec = {
            "layout": "quote_card",
            "quote": "Test quote for fade",
            "author": "Test Author",
            "animation": {"enabled": True, "style": "fade", "fade_duration": 0.5}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Fade should create multiple frames
        assert len(frames) > 1

        # Verify frames are different
        hashes = [_frame_hash(f) for f in frames]
        unique_hashes = set(hashes)
        assert len(unique_hashes) > 1, "Fade animation should create different frames"


# ============================================================================
# Animation Metadata Tests
# ============================================================================

class TestAnimationMetadata:
    """Tests for animation metadata file generation."""

    def test_metadata_file_created(self, tmp_path):
        """Animation metadata file is created alongside frames."""
        spec = {
            "layout": "quote_card",
            "quote": "Test",
            "author": "Author",
            "animation": {"enabled": True, "style": "fade", "fade_duration": 0.3}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Metadata file should exist
        metadata_path = tmp_path / "output_metadata.json"
        assert metadata_path.exists()

        # Verify metadata structure
        metadata = json.loads(metadata_path.read_text())
        assert "format" in metadata
        assert "frame_rate" in metadata
        assert "frames" in metadata
        assert "frame_count" in metadata
        assert "duration_sec" in metadata

    def test_metadata_contains_correct_frame_info(self, tmp_path):
        """Metadata contains accurate frame information."""
        spec = {
            "layout": "quote_card",
            "quote": "Test",
            "author": "Author",
            "animation": {"enabled": True, "style": "fade", "fade_duration": 0.3}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)
        metadata_path = tmp_path / "output_metadata.json"
        metadata = json.loads(metadata_path.read_text())

        # Verify frame count matches
        assert metadata["frame_count"] == len(frames)
        assert len(metadata["frames"]) == len(frames)

        # Verify frame rate
        assert metadata["frame_rate"] == DEFAULT_FRAME_RATE

        # Verify duration calculation
        expected_duration = len(frames) / DEFAULT_FRAME_RATE
        assert abs(metadata["duration_sec"] - expected_duration) < 0.1


# ============================================================================
# Progressive Reveal Tests
# ============================================================================

class TestProgressiveReveal:
    """Tests for progressive reveal functionality."""

    def test_framework_3_step_progressive_reveal(self, tmp_path):
        """Framework 3-step template reveals steps progressively."""
        spec = {
            "layout": "framework_3_step",
            "title": "Three Steps",
            "steps": [
                {"number": 1, "label": "First", "description": "Step 1"},
                {"number": 2, "label": "Second", "description": "Step 2"},
                {"number": 3, "label": "Third", "description": "Step 3"}
            ],
            "animation": {"enabled": True, "style": "reveal", "hold_frames": 1}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Should create multiple frames (fade creates 16 frames)
        assert len(frames) > 1

        # Frames should be progressively different
        hashes = [_frame_hash(f) for f in frames]
        assert len(set(hashes)) > 1, "Reveal frames should be different"

    def test_timeline_progressive_reveal(self, tmp_path):
        """Timeline template reveals events progressively."""
        spec = {
            "layout": "timeline",
            "title": "Project Timeline",
            "events": [
                {"time_label": "Week 1", "label": "Planning", "description": "Setup"},
                {"time_label": "Week 2", "label": "Execution", "description": "Work"}
            ],
            "orientation": "horizontal",
            "animation": {"enabled": True, "style": "reveal", "hold_frames": 1}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Should create multiple frames (fade creates 16 frames)
        assert len(frames) > 1

    def test_comparison_card_progressive_reveal(self, tmp_path):
        """Comparison card reveals columns progressively."""
        spec = {
            "layout": "comparison_card",
            "left_column": {"title": "Before", "items": ["A", "B"]},
            "right_column": {"title": "After", "items": ["C", "D"]},
            "animation": {"enabled": True, "style": "reveal", "hold_frames": 1}
        }
        out_path = tmp_path / "output.png"

        frames = render_animated_template(spec, out_path, duration_sec=3.0)

        # Should create multiple frames (fade creates 16 frames)
        assert len(frames) > 1

        # Frames should be different
        hashes = [_frame_hash(f) for f in frames]
        assert len(set(hashes)) > 1


# ============================================================================
# Integration Tests
# ============================================================================

class TestAnimationIntegration:
    """Integration tests for animation with existing graphics."""

    def test_static_rendering_still_works(self, tmp_path):
        """Static rendering (no animation) still works as before."""
        spec = {
            "layout": "key_line",
            "text": "Static graphic"
        }
        out_path = tmp_path / "static.png"

        # render_spec should still work
        render_spec(spec, out_path)
        assert out_path.exists()
        assert _img_size(out_path) == (1920, 1080)

    def test_all_template_types_support_animation(self, tmp_path):
        """All 12 template types support animation field."""
        templates = [
            {"layout": "lower_third", "text": "Test", "animation": {"enabled": True}},
            {"layout": "key_line", "text": "Test", "animation": {"enabled": True}},
            {"layout": "stat_callout", "stat": "99%", "animation": {"enabled": True}},
            {"layout": "side_by_side", "left_title": "A", "right_title": "B", "animation": {"enabled": True}},
            {"layout": "comparison_card", "left_column": {"title": "A", "items": ["X"]}, "right_column": {"title": "B", "items": ["Y"]}, "animation": {"enabled": True}},
            {"layout": "framework_3_step", "title": "Test", "steps": [{"number": 1, "label": "S1", "description": "D1"}], "animation": {"enabled": True}},
            {"layout": "decision_tree", "root": {"question": "Q?"}, "branches": [{"condition": "A", "outcome": "R"}], "animation": {"enabled": True}},
            {"layout": "cost_stack", "title": "Budget", "segments": [{"label": "A", "value": "100"}], "animation": {"enabled": True}},
            {"layout": "before_after", "before": {"label": "Old"}, "after": {"label": "New"}, "animation": {"enabled": True}},
            {"layout": "timeline", "events": [{"time_label": "T1", "label": "E1"}], "animation": {"enabled": True}},
            {"layout": "annotated_ui_mock", "ui_title": "UI", "annotations": [{"element_name": "E", "callout_text": "N"}], "animation": {"enabled": True}},
            {"layout": "quote_card", "quote": "Quote", "author": "Author", "animation": {"enabled": True}},
        ]

        for spec in templates:
            out_path = tmp_path / f"{spec['layout']}_test.png"
            # Should not raise
            try:
                frames = render_animated_template(spec, out_path, duration_sec=1.0)
                assert len(frames) >= 1
            except Exception as e:
                raise AssertionError(f"Template {spec['layout']} failed animation support: {e}")
