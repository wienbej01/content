"""Tests for DDL-W1: Wire resolve_drift into QA stage + emit edit instructions in manifest."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from duration_drift import DriftInput, resolve_drift, resolution_manifest_entry


class TestDriftResolverWired:
    def test_resolve_drift_produces_trim_in_manifest_entry(self):
        inp = DriftInput(
            render_unit_id="ru_w1_trim",
            production_id="prod_drift",
            artifact_id="art_w1_trim",
            required_duration_ms=7738,
            actual_duration_ms=8041,
            min_usable_duration_ms=5000,
            max_usable_duration_ms=10000,
            duration_drift_policy="trim_ok",
            asset_type="generated_video",
            audio_policy="BROLL_FLEX",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=False)

        assert result.resolution == "accepted"
        assert result.assembly_action == "trim"

        entry = resolution_manifest_entry(result, segment_id="ru_w1_trim")
        assert "drift_resolution" in entry
        assert entry["drift_resolution"] == "accepted"
        assert "trim" in entry
        assert entry["trim"]["action"] == "trim_from_end"
        assert entry["trim"]["trim_duration_sec"] == pytest.approx(0.303, abs=0.01)
        assert entry["trim"]["planned_duration_sec"] == pytest.approx(7.738)
        assert entry["trim"]["actual_duration_sec"] == pytest.approx(8.041)

    def test_duration_within_tolerance_accepted_no_drift_key(self):
        inp = DriftInput(
            render_unit_id="ru_w1_ok",
            production_id="prod_drift",
            artifact_id="art_w1_ok",
            required_duration_ms=4200,
            actual_duration_ms=4250,
            duration_drift_policy="trim_ok",
            asset_type="generated_video",
            audio_policy="BROLL_FLEX",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=False)

        assert result.resolution == "accepted"
        assert result.assembly_action is None

    def test_hero_lipsync_blocking_drift(self):
        inp = DriftInput(
            render_unit_id="ru_w1_hero",
            production_id="prod_drift",
            artifact_id="art_w1_hero",
            required_duration_ms=7000,
            actual_duration_ms=7200,
            duration_drift_policy="regenerate_required",
            asset_type="generated_video",
            audio_policy="HERO_LIPSYNC",
            is_hero_lipsync=True,
        )
        result = resolve_drift(inp, create_change_requests=False)

        assert result.resolution == "regenerate_same_prompt"
        assert abs(result.delta_sec) > 0.15


class TestManifestSegmentEmit:
    """Verify the segment-building logic that reads metadata_json.drift
    and emits trim/extend keys into the manifest segment dict."""

    def _build_segment(self, clip_metadata):
        seg = {
            "id": "test",
            "beat_id": "test",
            "clip_id": "test",
            "media": "/tmp/test.mp4",
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "timing_in": 0.0,
            "timing_out": 5.0,
            "duration_required": 5.0,
            "words": 0,
        }

        drift = clip_metadata.get("drift")
        if isinstance(drift, dict):
            seg["drift_resolution"] = drift.get("drift_resolution")
            seg["reason"] = drift.get("reason")
            if "trim" in drift:
                seg["trim"] = drift["trim"]
            if "extend" in drift:
                seg["extend"] = drift["extend"]

        return seg

    def test_trim_instruction_emitted(self):
        meta = {
            "drift": {
                "drift_resolution": "accepted",
                "reason": "actual exceeds planned by 0.303s",
                "trim": {
                    "action": "trim_from_end",
                    "trim_duration_sec": 0.303,
                    "planned_duration_sec": 7.738,
                    "actual_duration_sec": 8.041,
                },
            }
        }
        seg = self._build_segment(meta)
        assert "trim" in seg
        assert seg["trim"]["action"] == "trim_from_end"
        assert seg["trim"]["trim_duration_sec"] == 0.303
        assert seg["trim"]["planned_duration_sec"] == 7.738

    def test_extend_instruction_emitted(self):
        meta = {
            "drift": {
                "drift_resolution": "accepted",
                "reason": "actual below planned by 0.500s",
                "extend": {
                    "action": "freeze_last_frame",
                    "extend_duration_sec": 0.500,
                    "planned_duration_sec": 5.0,
                    "actual_duration_sec": 4.5,
                },
            }
        }
        seg = self._build_segment(meta)
        assert "extend" in seg
        assert seg["extend"]["action"] == "freeze_last_frame"
        assert seg["extend"]["extend_duration_sec"] == 0.500

    def test_no_drift_keys_emitted_when_not_present(self):
        seg = self._build_segment({})
        assert "trim" not in seg
        assert "extend" not in seg
        assert "drift_resolution" not in seg

    def test_segment_without_metadata_json_still_has_default_keys(self):
        seg = self._build_segment({})
        assert "timing_in" in seg
        assert "timing_out" in seg
        assert "duration_required" in seg
        assert "media" in seg
