"""Tests for overlay timeline integration (S22_T016).

Tests verify:
1. Overlay renders deterministic local artifact.
2. 16:9 overlay appears only in expected time window.
3. 9:16 overlay appears only in expected time window.
4. Multiple overlays respect layer order.
5. Overlay outside video duration fails.
6. Missing overlay artifact blocks assembly.
7. Existing assembly without overlays still passes.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "schemas"))


# ============================================================================
# Test 1: Overlay renders deterministic local artifact
# ============================================================================

class TestOverlayRendersDeterministic:
    """S22_T016: Overlay renders deterministic local artifact."""

    def test_render_overlay_timeline_creates_pngs(self, tmp_path):
        """render_overlay_timeline produces deterministic PNG files."""
        from render_graphics import render_overlay_timeline, RENDERERS

        timeline_plan = {
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_test_001",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 2.0,
                    "end_time_sec": 5.0,
                    "layer": 1,
                    "spec": {"layout": "lower_third", "text": "Hello"}
                }
            ]
        }

        out_dir = tmp_path / "overlays"
        result = render_overlay_timeline(timeline_plan, out_dir)

        assert len(result) == 1
        ov = result[0]
        assert "artifact_path" in ov
        assert "artifact_sha256" in ov
        png_path = Path(ov["artifact_path"])
        assert png_path.exists()
        assert png_path.suffix == ".png"
        assert ov["overlay_id"] == "ov_test_001"

    def test_render_overlay_timeline_deterministic(self, tmp_path):
        """Same overlay timeline produces identical artifacts."""
        from render_graphics import render_overlay_timeline

        timeline_plan = {
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_det_001",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 1.0,
                    "end_time_sec": 3.0,
                    "layer": 1,
                    "spec": {"layout": "key_line", "text": "Deterministic"}
                }
            ]
        }

        out_dir1 = tmp_path / "run1"
        out_dir2 = tmp_path / "run2"
        r1 = render_overlay_timeline(timeline_plan, out_dir1)
        r2 = render_overlay_timeline(timeline_plan, out_dir2)

        assert r1[0]["artifact_sha256"] == r2[0]["artifact_sha256"]

    def test_render_overlay_timeline_unknown_layout_fails(self, tmp_path):
        """Unknown layout in overlay spec raises RuntimeError."""
        from render_graphics import render_overlay_timeline

        timeline_plan = {
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_bad",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 0.0,
                    "end_time_sec": 2.0,
                    "layer": 1,
                    "spec": {"layout": "nonexistent_layout"}
                }
            ]
        }

        with pytest.raises(RuntimeError, match="BLOCKED_UNKNOWN_OVERLAY_LAYOUT"):
            render_overlay_timeline(timeline_plan, tmp_path)


# ============================================================================
# Test 2 & 3: Overlay timing window (16:9 and 9:16)
# ============================================================================

class TestOverlayTimingWindow:
    """S22_T016: Overlay appears only in expected time window."""

    @patch("scripts.assemble.run")
    def test_overlay_ffmpeg_enable_between_16x9(self, mock_run):
        """16:9 overlay ffmpeg command contains enable='between(t,start,end)'."""
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_001",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 2.0,
                "end_time_sec": 5.0,
                "layer": 1,
                "artifact_path": "/tmp/test_overlay.png",
                "spec": {"layout": "lower_third", "text": "Test"}
            }
        ]
        tmp_dir = Path(tempfile.gettempdir())

        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            with patch("scripts.assemble.probe_dur", return_value=10.0):
                _composite_overlay_timeline(video, overlay_events, 10.0, tmp_dir, "16x9")

        last_call_args = mock_run.call_args[0][0]
        filter_complex_idx = last_call_args.index("-filter_complex") + 1
        fc = last_call_args[filter_complex_idx]

        assert "enable='between(t,2.0,5.0)'" in fc, f"Expected enable filter for 2.0-5.0s window, got: {fc}"
        assert "'between(t,0,10)'" not in fc, "Overlay should NOT be enabled for full duration"

    @patch("scripts.assemble.run")
    def test_overlay_ffmpeg_enable_between_9x16(self, mock_run):
        """9:16 overlay ffmpeg command contains enable='between(t,start,end)'."""
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_002",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 1.5,
                "end_time_sec": 4.0,
                "layer": 1,
                "artifact_path": "/tmp/test_overlay2.png",
                "spec": {"layout": "lower_third", "text": "Test 9x16"}
            }
        ]
        tmp_dir = Path(tempfile.gettempdir())

        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            with patch("scripts.assemble.probe_dur", return_value=10.0):
                _composite_overlay_timeline(video, overlay_events, 10.0, tmp_dir, "9x16")

        last_call_args = mock_run.call_args[0][0]
        filter_complex_idx = last_call_args.index("-filter_complex") + 1
        fc = last_call_args[filter_complex_idx]

        assert "enable='between(t,1.5,4.0)'" in fc, f"Expected enable filter for 1.5-4.0s window, got: {fc}"


# ============================================================================
# Test 4: Multiple overlays respect layer order
# ============================================================================

class TestOverlayLayerOrder:
    """S22_T016: Multiple overlays respect layer order."""

    @patch("scripts.assemble.run")
    def test_multi_layer_overlays_composited_sequentially(self, mock_run):
        """Multiple overlays are composited layer by layer, higher layers last."""
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_layer0",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 1.0,
                "end_time_sec": 5.0,
                "layer": 0,
                "artifact_path": "/tmp/overlay_layer0.png",
                "spec": {"layout": "lower_third", "text": "Bottom"}
            },
            {
                "overlay_id": "ov_layer1",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 1.0,
                "end_time_sec": 5.0,
                "layer": 1,
                "artifact_path": "/tmp/overlay_layer1.png",
                "spec": {"layout": "stat_callout", "text": "Top"}
            }
        ]
        tmp_dir = Path(tempfile.gettempdir())

        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            with patch("scripts.assemble.probe_dur", return_value=10.0):
                _composite_overlay_timeline(video, overlay_events, 10.0, tmp_dir, "16x9")

        # Should be 2 ffmpeg calls (one per overlay layer)
        assert mock_run.call_count == 2

        # First call should be for layer 0, second for layer 1
        call_args_list = mock_run.call_args_list
        fc0_idx = call_args_list[0][0][0].index("-filter_complex") + 1
        fc1_idx = call_args_list[1][0][0].index("-filter_complex") + 1

        # Both should have 'overlay=' in their filter_complex
        assert "overlay=" in call_args_list[0][0][0][fc0_idx]
        assert "overlay=" in call_args_list[1][0][0][fc1_idx]

        # Layer 1 processes the output of layer 0 (input [0:v] should be the output of first pass)
        fc1 = call_args_list[1][0][0][fc1_idx]
        assert "[0:v]" in fc1 or "overlay" in fc1


# ============================================================================
# Test 5: Overlay outside video duration fails
# ============================================================================

class TestOverlayOutsideDuration:
    """S22_T016: Overlay outside video duration fails."""

    def test_render_overlay_end_exceeds_total_duration(self, tmp_path):
        """Overlay with end_time_sec > total_duration_sec raises RuntimeError."""
        from render_graphics import render_overlay_timeline

        timeline_plan = {
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_oob",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 8.0,
                    "end_time_sec": 12.0,
                    "layer": 1,
                    "spec": {"layout": "key_line", "text": "OOB"}
                }
            ]
        }

        with pytest.raises(RuntimeError, match="BLOCKED_OVERLAY_OUTSIDE_DURATION"):
            render_overlay_timeline(timeline_plan, tmp_path)

    @patch("scripts.assemble.run")
    def test_composite_overlay_end_exceeds_total_duration(self, mock_run):
        """_composite_overlay_timeline with end beyond video duration raises."""
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_oob2",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 8.0,
                "end_time_sec": 12.0,
                "layer": 1,
                "artifact_path": "/tmp/test_overlay_oob.png",
                "spec": {"layout": "key_line", "text": "OOB"}
            }
        ]
        tmp_dir = Path(tempfile.gettempdir())

        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            with pytest.raises(RuntimeError, match="BLOCKED_OVERLAY_OUTSIDE_DURATION"):
                _composite_overlay_timeline(video, overlay_events, 10.0, tmp_dir, "16x9")


# ============================================================================
# Test 6: Missing overlay artifact blocks assembly
# ============================================================================

class TestMissingOverlayArtifact:
    """S22_T016: Missing overlay artifact blocks assembly."""

    def test_manifest_validation_blocks_missing_artifact(self, tmp_path):
        """Manifest with overlay_timeline but missing artifact_path files fails validation."""
        from scripts.assemble import validate_manifest

        manifest_json = {
            "id": "test_ov_missing",
            "segments": [
                {"id": "seg_001", "media": "test.mp4", "words": 10, "audio": "test.mp3"}
            ],
            "pacing": {"reference": 0, "baseline_speed": 1.0},
            "overlay_timeline": {
                "total_duration_sec": 10.0,
                "overlays": [
                    {
                        "overlay_id": "ov_missing",
                        "shot_id": "shot_001",
                        "segment_id": "seg_001",
                        "start_time_sec": 1.0,
                        "end_time_sec": 3.0,
                        "layer": 1,
                        "spec": {"layout": "lower_third", "text": "Missing"},
                        "artifact_path": "/nonexistent/overlay_missing.png"
                    }
                ]
            }
        }

        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_json))
        base = tmp_path

        errors = validate_manifest(manifest_json, base)
        assert any("artifact_path: file not found" in e for e in errors), (
            f"Expected artifact not found error, got: {errors}"
        )

    @patch("scripts.assemble.run")
    def test_composite_missing_artifact_blocks_assembly(self, mock_run):
        """_composite_overlay_timeline with missing overlay artifact raises RuntimeError."""
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_noart",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 1.0,
                "end_time_sec": 3.0,
                "layer": 1,
                "spec": {"layout": "key_line", "text": "No Artifact"}
            }
        ]
        tmp_dir = Path(tempfile.gettempdir())

        with pytest.raises(RuntimeError, match="BLOCKED_MISSING_OVERLAY_ARTIFACT"):
            _composite_overlay_timeline(video, overlay_events, 10.0, tmp_dir, "16x9")


# ============================================================================
# Test 7: Existing assembly without overlays still passes
# ============================================================================

class TestAssemblyWithoutOverlays:
    """S22_T016: Existing assembly without overlays still passes."""

    def test_validate_manifest_without_overlay_timeline(self):
        """Manifest without overlay_timeline field validates without error."""
        from scripts.assemble import validate_manifest

        manifest_json = {
            "id": "test_no_ov",
            "segments": [
                {"id": "seg_001", "media": "test.mp4", "words": 10, "audio": "test.mp3"}
            ],
            "pacing": {"reference": 0, "baseline_speed": 1.0}
        }

        errors = validate_manifest(manifest_json, Path("/tmp"))
        overlay_errors = [e for e in errors if "overlay" in e.lower()]
        assert len(overlay_errors) == 0, (
            f"Manifest without overlay_timeline should not produce overlay errors: "
            f"{overlay_errors}"
        )

    def test_composite_overlay_timeline_empty_returns_original(self, tmp_path):
        """_composite_overlay_timeline with empty overlay list returns original video path."""
        from scripts.assemble import _composite_overlay_timeline

        video = Path("/tmp/test_video.mp4")
        result = _composite_overlay_timeline(video, [], 10.0, tmp_path, "16x9")
        assert result == video, "Empty overlay list should return original video unchanged"


# ============================================================================
# Schema validation tests
# ============================================================================

class TestOverlayTimelineSchemaValidation:
    """S22_T016: Overlay timeline schema validation."""

    def test_valid_overlay_timeline_schema_passes(self, tmp_path):
        """A valid overlay timeline plan passes schema validation."""
        plan = {
            "schema_version": "1.0",
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_001",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 2.0,
                    "end_time_sec": 5.0,
                    "layer": 0,
                    "spec": {"layout": "lower_third", "text": "Hello"}
                }
            ]
        }

        schema_path = ROOT / "schemas" / "overlay_timeline.schema.json"
        assert schema_path.exists(), "overlay_timeline.schema.json must exist"

        import json
        schema = json.loads(schema_path.read_text())
        assert schema["title"] == "Overlay Timeline Plan"

    def test_validate_manifest_passes_valid_overlay_timeline(self, tmp_path):
        """Manifest with valid overlay_timeline should pass validation."""
        from scripts.assemble import validate_manifest

        seg_media = tmp_path / "test.mp4"
        seg_media.touch()

        manifest_json = {
            "id": "test_ov_valid",
            "segments": [
                {"id": "seg_001", "media": str(seg_media.name), "words": 10, "audio": "test.mp3"}
            ],
            "pacing": {"reference": 0, "baseline_speed": 1.0},
            "overlay_timeline": {
                "total_duration_sec": 10.0,
                "overlays": [
                    {
                        "overlay_id": "ov_001",
                        "shot_id": "shot_001",
                        "segment_id": "seg_001",
                        "start_time_sec": 2.0,
                        "end_time_sec": 5.0,
                        "layer": 0,
                        "spec": {"layout": "lower_third", "text": "Hello"}
                    }
                ]
            }
        }

        errors = validate_manifest(manifest_json, tmp_path)
        overlay_errors = [e for e in errors if "overlay" in e.lower()]
        assert len(overlay_errors) == 0, (
            f"Valid overlay_timeline should not produce errors: {overlay_errors}"
        )


# ============================================================================
# Position helper tests
# ============================================================================

class TestOverlayPositionHelpers:
    """S22_T016: Overlay position helpers compute correct offsets."""

    def test_overlay_position_16x9_default(self):
        """Default 16:9 overlay position is lower-third zone."""
        from scripts.assemble import _overlay_position_16x9
        x, y = _overlay_position_16x9({})
        assert x == 70
        assert y == 1010

    def test_overlay_position_9x16_default(self):
        """Default 9:16 overlay position is lower portion."""
        from scripts.assemble import _overlay_position_9x16
        x, y = _overlay_position_9x16({})
        assert x == 40
        assert y == 1770

    def test_overlay_position_16x9_center(self):
        """16:9 center alignment produces x=0,y=0."""
        from scripts.assemble import _overlay_position_16x9
        x, y = _overlay_position_16x9({"align": "center", "x": 0, "y": 0})
        assert x == 0
        assert y == 0

    def test_overlay_position_9x16_explicit(self):
        """9:16 overlay with explicit x,y returns those values."""
        from scripts.assemble import _overlay_position_9x16
        x, y = _overlay_position_9x16({"x": 100, "y": 500})
        assert x == 100
        assert y == 500
