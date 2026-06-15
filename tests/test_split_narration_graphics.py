"""PTC-05: Split narration concatenation and graphics required-field validation."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from review_production_storyboard import structural_review


def _beat(beat_id, start, end, source=None, treatment="broll", narration=None,
          model="kling3_0", graphic=None, split_index=None):
    b = {
        "beat_id": beat_id,
        "source_beat_id": source or beat_id,
        "audio_start_sec": start,
        "audio_end_sec": end,
        "audio_duration_sec": round(end - start, 3),
        "treatment": treatment,
        "shot_type": "broll_environment",
        "segment_id": "001_test",
        "coverage_plan": [
            {"asset_role": "primary", "asset_type": "generated_video",
             "required_start_sec": start, "required_end_sec": end,
             "required_duration_sec": round(end - start, 3)}
        ],
    }
    if narration is not None:
        b["narration_text"] = narration
    if model is not None:
        b["model"] = model
    if graphic is not None:
        b["graphic"] = graphic
    if split_index is not None:
        b["split_index"] = split_index
    return b


def _prod(beats):
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


def _creative(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _cbeat(beat_id, narration=None, graphic=None):
    b = {"beat_id": beat_id, "shot_type": "broll_environment"}
    if narration is not None:
        b["narration_text"] = narration
    if graphic is not None:
        b["graphic"] = graphic
    return b


class TestSplitChildrenNarrationConcatenatesPass:
    def test_split_children_narration_concatenates_pass(self):
        """Parent 'A. B. C.' split into 3 children → group concat == parent → PASS."""
        prod = _prod([
            _beat("B001a", 0.0, 3.0, source="B001", narration="A.", split_index=0),
            _beat("B001b", 3.0, 6.0, source="B001", narration="B.", split_index=1),
            _beat("B001c", 6.0, 9.0, source="B001", narration="C.", split_index=2),
        ])
        creative = _creative([_cbeat("B001", narration="A. B. C.")])
        errors, _ = structural_review(prod, creative)
        narration_errors = [e for e in errors if "NARRATION_MUTATION" in e]
        assert narration_errors == []


class TestWordDroppedFails:
    def test_word_dropped_fails(self):
        """Children concat missing a word → NARRATION_MUTATION fail."""
        prod = _prod([
            _beat("B001a", 0.0, 3.0, source="B001", narration="A.", split_index=0),
            _beat("B001b", 3.0, 6.0, source="B001", narration="C.", split_index=1),
        ])
        creative = _creative([_cbeat("B001", narration="A. B. C.")])
        errors, _ = structural_review(prod, creative)
        assert any("NARRATION_MUTATION" in e for e in errors)


class TestWordReorderedFails:
    def test_word_reordered_fails(self):
        """Children in wrong order → fail."""
        prod = _prod([
            _beat("B001a", 0.0, 3.0, source="B001", narration="B.", split_index=0),
            _beat("B001b", 3.0, 6.0, source="B001", narration="A.", split_index=1),
            _beat("B001c", 6.0, 9.0, source="B001", narration="C.", split_index=2),
        ])
        creative = _creative([_cbeat("B001", narration="A. B. C.")])
        errors, _ = structural_review(prod, creative)
        assert any("NARRATION_MUTATION" in e for e in errors)


class TestSingleBeatNarrationUnchangedPass:
    def test_single_beat_narration_unchanged_pass(self):
        """Non-split beat with same narration as creative → PASS."""
        prod = _prod([
            _beat("B001", 0.0, 5.0, source="B001", narration="Hello world."),
        ])
        creative = _creative([_cbeat("B001", narration="Hello world.")])
        errors, _ = structural_review(prod, creative)
        narration_errors = [e for e in errors if "NARRATION_MUTATION" in e]
        assert narration_errors == []


class TestRequiredFalseGraphicNotFlagged:
    def test_required_false_graphic_not_flagged(self):
        """Graphic with required:false → not flagged as missing."""
        prod = _prod([
            _beat("B001", 0.0, 5.0, source="B001"),  # no graphic on production beat
        ])
        creative = _creative([
            _cbeat("B001", graphic={"type": "overlay", "label": "X", "required": False}),
        ])
        errors, _ = structural_review(prod, creative)
        graphic_errors = [e for e in errors if "MISSING_GRAPHIC" in e]
        assert graphic_errors == []


class TestRequiredGraphicSurvivesSplit:
    def test_required_graphic_survives_split(self):
        """Parent required graphic; production has it on a child → PASS."""
        prod = _prod([
            _beat("B001a", 0.0, 3.0, source="B001", narration="A.", split_index=0),
            _beat("B001b", 3.0, 6.0, source="B001", narration="B.", split_index=1,
                  graphic={"type": "progress_bar", "label": "Step 1", "required": True,
                           "display_slot": "B001b"}),
        ])
        creative = _creative([
            _cbeat("B001", narration="A. B.",
                   graphic={"type": "progress_bar", "label": "Step 1", "required": True}),
        ])
        errors, _ = structural_review(prod, creative)
        graphic_errors = [e for e in errors if "MISSING_GRAPHIC" in e]
        assert graphic_errors == []


class TestRequiredGraphicLostFails:
    def test_required_graphic_lost_fails(self):
        """Parent required graphic; production omits it entirely → fail."""
        prod = _prod([
            _beat("B001a", 0.0, 3.0, source="B001", narration="A.", split_index=0),
            _beat("B001b", 3.0, 6.0, source="B001", narration="B.", split_index=1),
        ])
        creative = _creative([
            _cbeat("B001", narration="A. B.",
                   graphic={"type": "progress_bar", "label": "Step 1", "required": True}),
        ])
        errors, _ = structural_review(prod, creative)
        assert any("MISSING_GRAPHIC" in e for e in errors)


class TestWhitespaceCanonicalMatch:
    def test_whitespace_canonical_match(self):
        """Children with extra whitespace at boundaries still match canonically."""
        prod = _prod([
            _beat("B001a", 0.0, 3.0, source="B001", narration="A. ", split_index=0),
            _beat("B001b", 3.0, 6.0, source="B001", narration=" B.", split_index=1),
        ])
        creative = _creative([_cbeat("B001", narration="A.  B.")])
        errors, _ = structural_review(prod, creative)
        narration_errors = [e for e in errors if "NARRATION_MUTATION" in e]
        assert narration_errors == []
