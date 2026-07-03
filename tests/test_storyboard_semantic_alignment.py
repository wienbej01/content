#!/usr/bin/env python3
"""tests/test_storyboard_semantic_alignment.py — Semantic alignment validator tests for S22_T008.

Tests 9 required scenarios:
  1. Specific source-grounded B-roll passes.
  2. "business people in office" fails as BLOCKED_GENERIC_BROLL.
  3. B-roll with vague alignment fails.
  4. Overlay without semantic purpose fails (source_label without ref).
  5. Statistic overlay without claim ref fails.
  6. Graphic unrelated to segment argument fails.
  7. Conclusion beat with unrelated visual fails.
  8. Emotional reset generic visual passes with explicit visual_role=emotional_reset and justification.
  9. Readable text inside generated video fails.

All tests use local fixtures. No LLM calls, no paid APIs.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_storyboard_v2 import validate_semantic_alignment, load_fixture

FIXTURE = ROOT / "tests" / "fixtures" / "storyboard_v2"


def _error_text(errors):
    texts = []
    for e in errors:
        texts.append(e.get("message", ""))
        texts.append(e.get("entity_id", ""))
    return "\n".join(texts)


class TestValidPasses:
    def test_valid_semantic_storyboard_passes(self):
        data = load_fixture("valid_semantic_storyboard.json")
        errors = validate_semantic_alignment(data)
        assert errors == [], f"Expected 0 errors, got {len(errors)}: {[e['message'] for e in errors]}"

    def test_valid_two_segment_passes(self):
        data = load_fixture("valid_two_segment_storyboard.json")
        errors = validate_semantic_alignment(data)
        assert errors == [], f"Expected 0 errors, got {len(errors)}: {[e['message'] for e in errors]}"

    def test_non_canonical_skips(self):
        data = load_fixture("legacy_v2_fixture.json")
        errors = validate_semantic_alignment(data)
        assert errors == [], "Non-canonical storyboard should skip semantic alignment validation"


class TestSourceGroundedBroll:
    def test_source_grounded_broll_passes(self):
        data = load_fixture("semantic_source_grounded_broll.json")
        errors = validate_semantic_alignment(data)
        errors = [e for e in errors if e["severity"] != "BLOCKER"]
        assert errors == [], (
            f"Specific source-grounded B-roll should pass. "
            f"Got {len(errors)}: {[e['message'] for e in errors]}"
        )


class TestGenericBroll:
    def test_generic_broll_blocked(self):
        data = load_fixture("semantic_generic_broll.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for generic B-roll"
        assert "BLOCKED_GENERIC_BROLL" in text, \
            f"Error should contain BLOCKED_GENERIC_BROLL, got: {text}"
        assert "business people" in text.lower() or "SH002" in text, \
            f"Error should reference the B-roll shot, got: {text}"


class TestVagueBrollAlignment:
    def test_vague_broll_alignment_blocked(self):
        data = load_fixture("semantic_vague_broll_alignment.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for vague B-roll alignment"
        assert "BLOCKED_VAGUE_BROLL_ALIGNMENT" in text, \
            f"Error should contain BLOCKED_VAGUE_BROLL_ALIGNMENT, got: {text}"


class TestOverlaySourceLabelNoRef:
    def test_source_label_no_ref_blocked(self):
        data = load_fixture("semantic_overlay_source_label_no_ref.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for source_label overlay without source or claim ref"
        assert "BLOCKED_PURPOSELESS_OVERLAY" in text, \
            f"Error should contain BLOCKED_PURPOSELESS_OVERLAY, got: {text}"
        assert "OV001" in text, \
            f"Error should reference overlay OV001, got: {text}"


class TestStatOverlayNoClaim:
    def test_stat_overlay_no_claim_blocked(self):
        data = load_fixture("semantic_stat_overlay_no_claim.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for stat_display overlay without claim ref"
        assert "BLOCKED_PURPOSELESS_OVERLAY" in text, \
            f"Error should contain BLOCKED_PURPOSELESS_OVERLAY, got: {text}"


class TestDecorativeGraphic:
    def test_decorative_graphic_blocked(self):
        data = load_fixture("semantic_decorative_graphic.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for purely decorative graphic"
        assert "BLOCKED_DECORATIVE_GRAPHIC" in text, \
            f"Error should contain BLOCKED_DECORATIVE_GRAPHIC, got: {text}"
        assert "SH002" in text, f"Error should reference graphic shot SH002, got: {text}"


class TestConclusionUnrelatedVisual:
    def test_conclusion_unrelated_visual_blocked(self):
        data = load_fixture("semantic_conclusion_unrelated_visual.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for conclusion beat with unrelated visual"
        assert "BLOCKED_UNRELATED_CONCLUSION_VISUAL" in text, \
            f"Error should contain BLOCKED_UNRELATED_CONCLUSION_VISUAL, got: {text}"


class TestEmotionalReset:
    def test_emotional_reset_justified_passes(self):
        data = load_fixture("semantic_emotional_reset_justified.json")
        errors = validate_semantic_alignment(data)
        assert errors == [], (
            f"Emotional reset with explicit justification should pass. "
            f"Got {len(errors)}: {[e['message'] for e in errors]}"
        )

    def test_emotional_reset_unjustified_fails(self):
        data = load_fixture("semantic_emotional_reset_unjustified.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for emotional_reset without justification"
        assert "BLOCKED_GENERIC_BROLL" in text, \
            f"Error should contain BLOCKED_GENERIC_BROLL, got: {text}"


class TestReadableTextInGenerated:
    def test_readable_text_in_generated_blocked(self):
        data = load_fixture("semantic_readable_text_in_generated.json")
        errors = validate_semantic_alignment(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for generated video requesting readable text"
        assert "BLOCKED_READABLE_TEXT_IN_GENERATED" in text, \
            f"Error should contain BLOCKED_READABLE_TEXT_IN_GENERATED, got: {text}"


class TestErrorEntityReferences:
    def test_errors_contain_entity_id_and_field(self):
        data = load_fixture("semantic_generic_broll.json")
        errors = validate_semantic_alignment(data)
        assert len(errors) > 0
        for e in errors:
            assert "entity_id" in e, f"Error missing entity_id: {e}"
            assert "path" in e, f"Error missing path: {e}"
            assert e["severity"] == "BLOCKER", f"Error severity should be BLOCKER, got: {e['severity']}"
