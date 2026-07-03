#!/usr/bin/env python3
"""tests/test_storyboard_v2_schema.py — Schema and validation tests for S22_T003.

Tests the canonical LLM-authored storyboard schema defined in
schemas/storyboard_v2.schema.json:
  - Positive semantic fixture passes
  - Negative fixtures fail on required fields
  - Sonnet-5 authority checks
  - Legacy compatibility path
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from storyboard_v2_validator import (
    validate_against_schema,
    validate_sonnet5_authority,
    validate_all,
    is_canonical,
    compatibility_path_for_legacy,
    NON_CANONICAL_FALLBACK_STR,
)

FIXTURE = ROOT / "tests" / "fixtures" / "storyboard_v2"


def _load(name):
    return json.loads((FIXTURE / name).read_text())


def _error_text(errors):
    """Extract searchable text from jsonschema errors (messages + paths)."""
    texts = []
    for e in errors:
        texts.append(e.message)
        texts.append("/".join(str(p) for p in e.absolute_path))
    return "\n".join(texts)


class TestValidSemanticStoryboard:
    def test_valid_fixture_passes_schema(self):
        data = _load("valid_semantic_storyboard.json")
        errors = validate_against_schema(data)
        assert errors == [], f"Expected 0 errors, got {len(errors)}: {[e.message for e in errors]}"

    def test_valid_fixture_passes_sonnet5_authority(self):
        data = _load("valid_semantic_storyboard.json")
        errors = validate_sonnet5_authority(data)
        assert errors == [], f"Expected 0 author errors, got: {errors}"


class TestMissingSegmentWorkOrders:
    def test_missing_segment_work_orders_fails(self):
        data = _load("missing_segment_work_orders.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when segment_work_orders is missing"
        assert "segment_work_orders" in text, \
            f"Error should reference segment_work_orders, got: {text}"


class TestShotMissingWhyThisVisual:
    def test_shot_missing_why_this_visual_fails(self):
        data = _load("shot_missing_why_this_visual.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when shot is missing why_this_visual"
        assert "why_this_visual" in text, \
            f"Error should reference why_this_visual, got: {text}"


class TestBrollMissingNarrativeAlignment:
    def test_broll_missing_narrative_alignment_fails(self):
        data = _load("broll_missing_narrative_alignment.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when B-roll shot is missing narrative_alignment"
        assert "narrative_alignment" in text, \
            f"Error should reference narrative_alignment, got: {text}"


class TestOverlayMissingSemanticPurpose:
    def test_overlay_missing_semantic_purpose_fails(self):
        data = _load("overlay_missing_semantic_purpose.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when overlay is missing semantic_purpose"
        assert "semantic_purpose" in text, \
            f"Error should reference semantic_purpose, got: {text}"


class TestShotMissingDriftPolicy:
    def test_shot_missing_drift_policy_fails(self):
        data = _load("shot_missing_drift_policy.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when shot is missing duration_drift_policy"
        assert "duration_drift_policy" in text, \
            f"Error should reference duration_drift_policy, got: {text}"


class TestMissingModelProfile:
    def test_missing_model_profile_fails(self):
        data = _load("missing_model_profile.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when authoring_model_profile is missing"
        assert "authoring_model_profile" in text, \
            f"Error should reference authoring_model_profile, got: {text}"


class TestNonSonnetAuthor:
    def test_non_sonnet_author_fails_validation_helper(self):
        data = _load("non_sonnet_author.json")
        errors = validate_sonnet5_authority(data)
        assert len(errors) > 0, "Should fail when author is not Sonnet 5"
        assert any(NON_CANONICAL_FALLBACK_STR in e["message"] for e in errors), \
            f"Error should contain {NON_CANONICAL_FALLBACK_STR}"

    def test_non_sonnet_author_passes_schema(self):
        data = _load("non_sonnet_author.json")
        errors = validate_against_schema(data)
        assert errors == [], (
            f"Schema should not block non-Sonnet (validation helper handles that), "
            f"got: {[e.message for e in errors]}"
        )


class TestMissingScriptHash:
    def test_missing_script_hash_fails(self):
        data = _load("missing_script_hash.json")
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when approved_script_sha256 is missing"
        assert "approved_script_sha256" in text, \
            f"Error should reference approved_script_sha256, got: {text}"


class TestLegacyCompatibility:
    def test_legacy_v2_fixture_passes_legacy_branch(self):
        data = _load("legacy_v2_fixture.json")
        assert not is_canonical(data), "Legacy fixture should not be canonical"
        compat = compatibility_path_for_legacy(data)
        assert compat is not None, "Legacy doc should have a compatibility path"
        assert compat["action"] == "accept_as_legacy", \
            f"Legacy v2 should be accepted, got: {compat}"

    def test_legacy_v2_fixture_passes_schema(self):
        data = _load("legacy_v2_fixture.json")
        errors = validate_against_schema(data)
        assert errors == [], (
            f"Legacy v2 fixture should pass its own (else-branch) schema requirements. "
            f"Errors: {[e.message for e in errors]}"
        )

    def test_legacy_v2_not_rejected_outright(self):
        data = _load("legacy_v2_fixture.json")
        schema_errs, author_errs = validate_all(data)
        assert not author_errs, "Legacy docs should not trigger Sonnet-5 authority check"


class TestSchemaDocumentation:
    def test_schema_exists_and_contains_canonical_definitions(self):
        assert (ROOT / "schemas" / "storyboard_v2.schema.json").exists(), \
            "Schema file must exist"
        schema = json.loads((ROOT / "schemas" / "storyboard_v2.schema.json").read_text())
        defs = schema.get("definitions", {})
        required_defs = ["shot", "overlay", "segment_work_order", "claim",
                         "narrative_beat", "feedback_policy", "timing_policy"]
        for d in required_defs:
            assert d in defs, f"Schema must define {d}"


class TestRequiredTopLevelFields:
    def test_missing_claim_inventory_fails(self):
        data = _load("valid_semantic_storyboard.json")
        del data["claim_inventory"]
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert "claim_inventory" in text, \
            f"Error should reference claim_inventory, got: {text}"

    def test_missing_narrative_beats_fails(self):
        data = _load("valid_semantic_storyboard.json")
        del data["narrative_beats"]
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert "narrative_beats" in text, f"Should require narrative_beats, got: {text}"

    def test_missing_shots_fails(self):
        data = _load("valid_semantic_storyboard.json")
        del data["shots"]
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert "shots" in text, f"Should require shots, got: {text}"

    def test_missing_approval_fails(self):
        data = _load("valid_semantic_storyboard.json")
        del data["approval"]
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert "approval" in text, f"Should require approval, got: {text}"

    def test_missing_feedback_policy_fails(self):
        data = _load("valid_semantic_storyboard.json")
        del data["feedback_policy"]
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert "feedback_policy" in text, f"Should require feedback_policy, got: {text}"

    def test_missing_timing_policy_fails(self):
        data = _load("valid_semantic_storyboard.json")
        del data["timing_policy"]
        errors = validate_against_schema(data)
        text = _error_text(errors)
        assert "timing_policy" in text, f"Should require timing_policy, got: {text}"
