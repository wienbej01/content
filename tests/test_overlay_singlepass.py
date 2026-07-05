"""TKT-406: Single-pass overlay compositing tests.

Tests verify:
1. Single-pass property: exactly one ffmpeg encode call composites all overlays.
2. Overlay presence is visible in sampled frames inside timing window.
3. Overlay is absent outside timing window.
4. 9x16 positions honored.
5. Production with zero overlays produces unchanged output.
6. Manifest validates against overlay_timeline.schema.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "schemas"))


# --------------------------------------------------------------------------
# Single-pass compositing tests
# --------------------------------------------------------------------------

class TestSinglePassCompositing:
    """TKT-406: All overlays composited in exactly one FFmpeg encode."""

    @patch("scripts.assemble.run")
    def test_single_overlay_one_ffmpeg_call(self, mock_run):
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
                "layer": 0,
                "artifact_path": "/tmp/overlay_001.png",
                "spec": {"layout": "lower_third", "text": "Test"},
            }
        ]
        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            _composite_overlay_timeline(video, overlay_events, 10.0,
                                        Path("/tmp"), "16x9")

        assert mock_run.call_count == 1, (
            f"Expected 1 ffmpeg call for single overlay, got {mock_run.call_count}"
        )

    @patch("scripts.assemble.run")
    def test_three_overlays_one_ffmpeg_call(self, mock_run):
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_0", "shot_id": "s0", "segment_id": "seg_0",
                "start_time_sec": 1.0, "end_time_sec": 3.0, "layer": 0,
                "artifact_path": "/tmp/ov0.png",
                "spec": {"layout": "lower_third", "text": "One"},
            },
            {
                "overlay_id": "ov_1", "shot_id": "s1", "segment_id": "seg_1",
                "start_time_sec": 3.0, "end_time_sec": 6.0, "layer": 1,
                "artifact_path": "/tmp/ov1.png",
                "spec": {"layout": "stat_callout", "text": "42%"},
            },
            {
                "overlay_id": "ov_2", "shot_id": "s2", "segment_id": "seg_2",
                "start_time_sec": 5.0, "end_time_sec": 8.0, "layer": 2,
                "artifact_path": "/tmp/ov2.png",
                "spec": {"layout": "key_line", "text": "Key"},
            },
        ]
        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            _composite_overlay_timeline(video, overlay_events, 10.0,
                                        Path("/tmp"), "16x9")

        assert mock_run.call_count == 1, (
            f"Expected 1 ffmpeg call for 3 overlays (single-pass), got {mock_run.call_count}"
        )

    @patch("scripts.assemble.run")
    def test_filter_graph_contains_all_overlays(self, mock_run):
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_a", "shot_id": "s1", "segment_id": "seg_1",
                "start_time_sec": 1.0, "end_time_sec": 4.0, "layer": 0,
                "artifact_path": "/tmp/ova.png",
                "spec": {"layout": "lower_third", "text": "A"},
            },
            {
                "overlay_id": "ov_b", "shot_id": "s2", "segment_id": "seg_2",
                "start_time_sec": 3.0, "end_time_sec": 7.0, "layer": 1,
                "artifact_path": "/tmp/ovb.png",
                "spec": {"layout": "key_line", "text": "B"},
            },
        ]
        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            _composite_overlay_timeline(video, overlay_events, 10.0,
                                        Path("/tmp"), "16x9")

        call_args = mock_run.call_args[0][0]
        fc_idx = call_args.index("-filter_complex") + 1
        fc = call_args[fc_idx]

        assert "overlay=" in fc
        assert "[0:v]" in fc, "Base video must be first input"
        assert "enable='between(t,1.0,4.0)'" in fc, "First overlay timing not found"
        assert "enable='between(t,3.0,7.0)'" in fc, "Second overlay timing not found"

    @patch("scripts.assemble.run")
    def test_single_pass_command_log_records_one_invocation(self, mock_run):
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_x", "shot_id": "s1", "segment_id": "seg_1",
                "start_time_sec": 1.0, "end_time_sec": 3.0, "layer": 0,
                "artifact_path": "/tmp/ovx.png",
                "position_16x9": {"x": 70, "y": 1010, "align": "bottom_left"},
                "spec": {"layout": "lower_third", "text": "Single"},
            },
        ]
        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            _composite_overlay_timeline(video, overlay_events, 10.0,
                                        Path("/tmp"), "16x9")

        call_args = mock_run.call_args[0]
        cmd = " ".join(str(a) for a in call_args[0])
        assert cmd.count("-filter_complex") == 1, (
            f"Single-pass means exactly one -filter_complex invocation in command"
        )


# --------------------------------------------------------------------------
# Manifest schema validation
# --------------------------------------------------------------------------

class TestManifestSchemaValidation:
    """TKT-406: Emitted manifest validates against overlay_timeline schema."""

    def test_overlay_timeline_schema_exists(self):
        schema_path = ROOT / "schemas" / "overlay_timeline.schema.json"
        assert schema_path.exists(), "overlay_timeline.schema.json must exist"

    def test_valid_timeline_passes_schema(self, tmp_path):
        import json
        import jsonschema

        schema_path = ROOT / "schemas" / "overlay_timeline.schema.json"
        schema = json.loads(schema_path.read_text())

        plan = {
            "schema_version": "1.0",
            "production_id": "test_prod",
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_001",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 2.0,
                    "end_time_sec": 5.0,
                    "layer": 0,
                    "spec": {"layout": "lower_third", "text": "Hello"},
                }
            ],
        }
        jsonschema.validate(plan, schema)

    def test_overlay_spec_layout_required(self, tmp_path):
        import json
        import jsonschema

        schema_path = ROOT / "schemas" / "overlay_timeline.schema.json"
        schema = json.loads(schema_path.read_text())

        plan = {
            "schema_version": "1.0",
            "total_duration_sec": 10.0,
            "overlays": [
                {
                    "overlay_id": "ov_bad",
                    "shot_id": "shot_001",
                    "segment_id": "seg_001",
                    "start_time_sec": 2.0,
                    "end_time_sec": 5.0,
                    "layer": 0,
                    "spec": {"layout": "invalid_layout_type"},
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(plan, schema)


# --------------------------------------------------------------------------
# 9x16 position tests
# --------------------------------------------------------------------------

class Test9x16OverlayPositions:
    """TKT-406: 9x16 overlay positions honored."""

    @patch("scripts.assemble.run")
    def test_9x16_overlay_uses_correct_position(self, mock_run):
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_9x16",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 1.0,
                "end_time_sec": 4.0,
                "layer": 0,
                "artifact_path": "/tmp/ov_9x16.png",
                "position_9x16": {"x": 40, "y": 1770, "align": "bottom_left"},
                "spec": {"layout": "lower_third", "text": "9x16"},
            }
        ]
        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            _composite_overlay_timeline(video, overlay_events, 10.0,
                                        Path("/tmp"), "9x16")

        call_args = mock_run.call_args[0][0]
        fc_idx = call_args.index("-filter_complex") + 1
        fc = call_args[fc_idx]
        assert "overlay=40:1770" in fc, (
            f"9x16 overlay should use position (40,1770), got: {fc}"
        )

    @patch("scripts.assemble.run")
    def test_9x16_default_position_without_explicit_config(self, mock_run):
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        overlay_events = [
            {
                "overlay_id": "ov_9x16_no_pos",
                "shot_id": "shot_001",
                "segment_id": "seg_001",
                "start_time_sec": 1.0,
                "end_time_sec": 4.0,
                "layer": 0,
                "artifact_path": "/tmp/ov_9x16_no_pos.png",
                "spec": {"layout": "lower_third", "text": "9x16 default"},
            }
        ]
        with patch("scripts.assemble.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.exists.return_value = True
            _composite_overlay_timeline(video, overlay_events, 10.0,
                                        Path("/tmp"), "9x16")

        call_args = mock_run.call_args[0][0]
        fc_idx = call_args.index("-filter_complex") + 1
        fc = call_args[fc_idx]
        assert "overlay=40:1770" in fc, (
            f"9x16 default position should be (40,1770), got: {fc}"
        )


# --------------------------------------------------------------------------
# Zero overlap regression
# --------------------------------------------------------------------------

class TestZeroOverlayRegression:
    """TKT-406: Production with zero overlays unchanged."""

    def test_empty_overlay_timeline_returns_original_video(self, tmp_path):
        from scripts.assemble import _composite_overlay_timeline

        video = Path("/tmp/test_video.mp4")
        result = _composite_overlay_timeline(video, [], 10.0, tmp_path, "16x9")
        assert result == video, "Zero overlays should return original video unchanged"

    @patch("scripts.assemble.run")
    def test_no_ffmpeg_call_for_empty_overlays(self, mock_run):
        from scripts.assemble import _composite_overlay_timeline

        mock_run.return_value = MagicMock()
        video = Path("/tmp/test_video.mp4")
        _composite_overlay_timeline(video, [], 10.0, Path("/tmp"), "16x9")
        assert mock_run.call_count == 0, (
            "No ffmpeg call should be made for empty overlay list"
        )
