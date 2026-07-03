#!/usr/bin/env python3
"""tests/test_segment_work_orders.py — Segment work-order validator tests for S22_T007.

Tests 9 required scenarios:
  1. Complete work orders pass.
  2. Missing segment work order fails.
  3. Work order with narration text mismatch fails.
  4. Missing B-roll instruction for B-roll segment fails.
  5. Missing graphic instruction for graphic overlay fails.
  6. Empty QA criteria fails.
  7. Work order references unknown shot fails.
  8. Work order references unknown overlay fails.
  9. Conclusion segment with no conclusion alignment fails.

All tests use local fixtures. No LLM calls, no paid APIs.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_segment_work_orders import validate_work_orders, load_fixture

FIXTURE = ROOT / "tests" / "fixtures" / "storyboard_v2"


def _error_text(errors):
    texts = []
    for e in errors:
        texts.append(e.get("path", ""))
        texts.append(e.get("message", ""))
    return "\n".join(texts)


class TestValidWorkOrders:
    """Test 1: Complete work orders pass."""

    def test_valid_two_segment_passes(self):
        data = load_fixture("valid_two_segment_storyboard.json")
        errors = validate_work_orders(data)
        assert errors == [], f"Expected 0 errors, got {len(errors)}: {[e['message'] for e in errors]}"

    def test_valid_semantic_passes(self):
        data = load_fixture("valid_semantic_storyboard.json")
        errors = validate_work_orders(data)
        assert errors == [], f"Expected 0 errors, got {len(errors)}: {[e['message'] for e in errors]}"

    def test_non_canonical_skips(self):
        data = load_fixture("legacy_v2_fixture.json")
        errors = validate_work_orders(data)
        assert errors == [], "Non-canonical storyboard should skip work order validation"


class TestMissingSegmentWorkOrder:
    """Test 2: Missing segment work order fails."""

    def test_missing_work_order_detected(self):
        data = load_fixture("missing_work_order_for_segment.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when segment lacks a work order"
        assert "BLOCKED_MISSING_WORK_ORDER" in text, \
            f"Error should contain BLOCKED_MISSING_WORK_ORDER, got: {text}"
        assert "S001" in text, f"Error should reference missing segment S001, got: {text}"


class TestNarrationMismatch:
    """Test 3: Work order with narration text mismatch fails."""

    def test_narration_mismatch_detected(self):
        data = load_fixture("work_order_narration_mismatch.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when narration text does not match"
        assert "BLOCKED_NARRATION_MISMATCH" in text, \
            f"Error should contain BLOCKED_NARRATION_MISMATCH, got: {text}"
        assert "S001" in text, f"Error should reference segment S001, got: {text}"


class TestMissingBrollInstruction:
    """Test 4: Missing B-roll instruction for B-roll segment fails."""

    def test_missing_broll_instruction_detected(self):
        data = load_fixture("work_order_missing_broll_instruction.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when B-roll segment lacks alignment instruction"
        assert "BLOCKED_MISSING_BROLL_INSTRUCTION" in text, \
            f"Error should contain BLOCKED_MISSING_BROLL_INSTRUCTION, got: {text}"
        assert "S001" in text, f"Error should reference segment S001, got: {text}"


class TestMissingGraphicInstruction:
    """Test 5: Missing graphic instruction for graphic overlay fails."""

    def test_missing_graphic_instruction_detected(self):
        data = load_fixture("work_order_missing_graphic_instruction.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when graphic overlay segment lacks alignment instruction"
        assert "BLOCKED_MISSING_GRAPHIC_INSTRUCTION" in text, \
            f"Error should contain BLOCKED_MISSING_GRAPHIC_INSTRUCTION, got: {text}"
        assert "S001" in text, f"Error should reference segment S001, got: {text}"


class TestEmptyQACriteria:
    """Test 6: Empty QA criteria fails."""

    def test_empty_qa_criteria_detected(self):
        data = load_fixture("work_order_empty_qa_criteria.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when QA acceptance criteria is empty"
        assert "BLOCKED_EMPTY_QA_CRITERIA" in text, \
            f"Error should contain BLOCKED_EMPTY_QA_CRITERIA, got: {text}"
        assert "S001" in text, f"Error should reference segment S001, got: {text}"


class TestUnknownShotRef:
    """Test 7: Work order references unknown shot fails."""

    def test_unknown_shot_detected(self):
        data = load_fixture("work_order_unknown_shot_ref.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when work order references unknown shot"
        assert "BLOCKED_UNKNOWN_SHOT_REF" in text, \
            f"Error should contain BLOCKED_UNKNOWN_SHOT_REF, got: {text}"
        assert "SH999" in text, f"Error should reference unknown shot SH999, got: {text}"


class TestUnknownOverlayRef:
    """Test 8: Work order references unknown overlay fails."""

    def test_unknown_overlay_detected(self):
        data = load_fixture("work_order_unknown_overlay_ref.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when work order references unknown overlay"
        assert "BLOCKED_UNKNOWN_OVERLAY_REF" in text, \
            f"Error should contain BLOCKED_UNKNOWN_OVERLAY_REF, got: {text}"
        assert "OV999" in text, f"Error should reference unknown overlay OV999, got: {text}"


class TestConclusionMissingInstruction:
    """Test 9: Conclusion segment with no conclusion alignment fails."""

    def test_conclusion_missing_instruction_detected(self):
        data = load_fixture("work_order_conclusion_missing_instruction.json")
        errors = validate_work_orders(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when conclusion segment has empty alignment instruction"
        assert "BLOCKED_MISSING_CONCLUSION_INSTRUCTION" in text, \
            f"Error should contain BLOCKED_MISSING_CONCLUSION_INSTRUCTION, got: {text}"
        assert "S001" in text, f"Error should reference segment S001, got: {text}"
