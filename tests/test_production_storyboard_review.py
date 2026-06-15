"""Tests for PST-05: Production Storyboard Review Gate."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from review_production_storyboard import run_review, structural_review


def _beat(beat_id, start, end, source=None, treatment="broll", narration=None,
          model=None, graphic=None, visual_brief=None):
    """Build a minimal valid production beat."""
    dur = round(end - start, 3)
    b = {
        "beat_id": beat_id,
        "source_beat_id": source or beat_id,
        "audio_start_sec": start,
        "audio_end_sec": end,
        "audio_duration_sec": dur,
        "treatment": treatment,
        "shot_type": "broll_environment",
        "segment_id": "001_test",
        "coverage_plan": [
            {"asset_role": "primary", "asset_type": "generated_video",
             "required_start_sec": start, "required_end_sec": end,
             "required_duration_sec": dur}
        ],
    }
    if narration is not None:
        b["narration_text"] = narration
    if model is not None:
        b["model"] = model
    if graphic is not None:
        b["graphic"] = graphic
    if visual_brief is not None:
        b["visual_brief"] = visual_brief
    return b


def _production_sb(beats, master=None):
    if master is None:
        master = beats[-1]["audio_end_sec"] if beats else 0
    return {
        "schema_version": "1.0",
        "project_id": "test",
        "creative_storyboard_sha256": "a" * 64,
        "timing_map_sha256": "b" * 64,
        "master_audio_duration_sec": master,
        "total_beats": len(beats),
        "created_at": "2026-06-14T00:00:00Z",
        "beats": beats,
    }


def _creative_sb(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _creative_beat(beat_id, narration=None, graphic=None):
    b = {"beat_id": beat_id, "shot_type": "broll_environment"}
    if narration is not None:
        b["narration_text"] = narration
    if graphic is not None:
        b["graphic"] = graphic
    return b


class TestValidStoryboardPasses:
    """test_valid_storyboard_passes — valid production storyboard passes structural review."""

    def test_valid_storyboard_passes(self):
        beats = [
            _beat("B001", 0.0, 5.0, narration="Hello world.", model="kling3_0"),
            _beat("B002", 5.0, 10.0, narration="Second beat.", model="seedance_2_0"),
        ]
        prod = _production_sb(beats)
        creative = _creative_sb([
            _creative_beat("B001", narration="Hello world."),
            _creative_beat("B002", narration="Second beat."),
        ])

        report = run_review(prod, creative)
        assert report["status"] == "PASS"
        assert report["structural"]["passed"] is True
        assert report["blocks_production"] is False
        assert report["structural"]["errors"] == []


class TestStructuralFailureBlocksProduction:
    """test_structural_failure_blocks_production — storyboard with gap → blocks_production=True."""

    def test_gap_blocks_production(self):
        # Gap between B001 and B002 (5.0 to 5.5)
        beats = [
            _beat("B001", 0.0, 5.0, model="kling3_0"),
            _beat("B002", 5.5, 10.0, model="kling3_0"),
        ]
        prod = _production_sb(beats)
        creative = _creative_sb([_creative_beat("B001"), _creative_beat("B002")])

        report = run_review(prod, creative)
        assert report["status"] == "FAIL"
        assert report["structural"]["passed"] is False
        assert report["blocks_production"] is True
        assert any("gap" in e.lower() or "Timeline gap" in e for e in report["structural"]["errors"])


class TestNarrationMutationFatal:
    """test_narration_mutation_fatal — narration differs from creative → FAIL."""

    def test_narration_mutation_detected(self):
        beats = [
            _beat("B001", 0.0, 5.0, source="B001", narration="Changed text."),
        ]
        prod = _production_sb(beats)
        creative = _creative_sb([_creative_beat("B001", narration="Original text.")])

        report = run_review(prod, creative)
        assert report["status"] == "FAIL"
        assert report["blocks_production"] is True
        assert any("NARRATION_MUTATION" in e for e in report["structural"]["errors"])


class TestRequiredGraphicsChecked:
    """test_required_graphics_checked — missing graphic from creative → structural error."""

    def test_missing_graphic(self):
        beats = [
            _beat("B001", 0.0, 5.0, source="B001"),  # no graphic
        ]
        prod = _production_sb(beats)
        creative = _creative_sb([
            _creative_beat("B001", graphic={"type": "progress_bar", "label": "Step 1"}),
        ])

        report = run_review(prod, creative)
        assert report["status"] == "FAIL"
        assert report["blocks_production"] is True
        assert any("MISSING_GRAPHIC" in e for e in report["structural"]["errors"])


class TestStructuralFailOverridesCreativePass:
    """test_structural_fail_overrides_creative_pass — structural fail blocks even if creative passes."""

    def test_structural_overrides_creative(self):
        # Gap → structural fail, but creative review passes
        beats = [
            _beat("B001", 0.0, 5.0, model="kling3_0"),
            _beat("B002", 5.5, 10.0, model="kling3_0"),
        ]
        prod = _production_sb(beats)
        creative = _creative_sb([_creative_beat("B001"), _creative_beat("B002")])

        with patch("review_production_storyboard.creative_review",
                   return_value=(True, 9, ["Looks great"])):
            report = run_review(prod, creative, llm_review=True)

        assert report["creative"]["passed"] is True
        assert report["creative"]["score"] == 9
        assert report["structural"]["passed"] is False
        assert report["blocks_production"] is True
        assert report["status"] == "FAIL"


class TestCreativeReviewMocked:
    """test_creative_review_mocked — creative notes don't block production."""

    def test_creative_notes_advisory_only(self):
        beats = [
            _beat("B001", 0.0, 5.0, narration="Hello.", model="kling3_0"),
            _beat("B002", 5.0, 10.0, narration="World.", model="seedance_2_0"),
        ]
        prod = _production_sb(beats)
        creative = _creative_sb([
            _creative_beat("B001", narration="Hello."),
            _creative_beat("B002", narration="World."),
        ])

        with patch("review_production_storyboard.creative_review",
                   return_value=(False, 3, ["Repetitive angles", "Weak transitions"])):
            report = run_review(prod, creative, llm_review=True)

        # Creative failed but structural passed → does NOT block
        assert report["creative"]["passed"] is False
        assert report["creative"]["notes"] == ["Repetitive angles", "Weak transitions"]
        assert report["structural"]["passed"] is True
        assert report["blocks_production"] is False
        assert report["status"] == "PASS"
