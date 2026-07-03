#!/usr/bin/env python3
"""tests/test_claim_inventory_schema.py — Schema and validation tests for S22_T005.

Tests the claim inventory schema and business-rule validator:
  1. Valid source-backed claim passes.
  2. Statistic without source fails.
  3. Study/person/date claim without source fails.
  4. Opinion claim without source passes only if explicitly typed opinion.
  5. Overlay source ref to unknown claim fails.
  6. Duplicate claim IDs fail.
  7. Unsupported visual treatment fails.
  8. Claim linked to nonexistent segment fails.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from claim_inventory_validator import (
    validate_claim_schema,
    validate_claim_business_rules,
    validate_claim_refs_resolve,
    validate_all,
    ALLOWED_SOURCE_BACKED_TYPES,
    OPINION_TYPES,
)

FIXTURE = ROOT / "tests" / "fixtures" / "claim_inventory"


def _load(name):
    return json.loads((FIXTURE / name).read_text())


def _error_text(errors):
    texts = []
    for e in errors:
        if hasattr(e, "message"):
            texts.append(e.message)
            texts.append("/".join(str(p) for p in e.absolute_path))
        else:
            texts.append(e.get("message", str(e)))
            texts.append(e.get("path", ""))
    return "\n".join(texts)


# ---------------------------------------------------------------------------
#  1. Valid source-backed claim passes
# ---------------------------------------------------------------------------

class TestValidSourceBackedClaim:
    def test_valid_fixture_passes_schema(self):
        data = _load("valid_claim_inventory.json")
        errors = validate_claim_schema(data)
        assert errors == [], (
            f"Expected 0 schema errors, got {len(errors)}: "
            f"{[e.message for e in errors]}"
        )

    def test_valid_fixture_passes_business_rules(self):
        data = _load("valid_claim_inventory.json")
        errors = validate_claim_business_rules(data)
        assert errors == [], (
            f"Expected 0 business rule errors, got {len(errors)}: "
            f"{[e['message'] for e in errors]}"
        )

    def test_valid_fixture_passes_all(self):
        data = _load("valid_claim_inventory.json")
        schema_e, biz_e, ref_e = validate_all(data)
        assert schema_e == [], f"Schema errors: {[e.message for e in schema_e]}"
        assert biz_e == [], f"Business errors: {[e['message'] for e in biz_e]}"
        assert ref_e == [], f"Ref errors: {[e['message'] for e in ref_e]}"


# ---------------------------------------------------------------------------
#  2. Statistic without source fails
# ---------------------------------------------------------------------------

class TestStatisticWithoutSource:
    def test_statistic_without_source_fails_business_rules(self):
        data = _load("statistic_without_source.json")
        errors = validate_claim_business_rules(data)
        text = _error_text(errors)
        assert len(errors) > 0, (
            "Statistic without source should produce business rule errors"
        )
        assert "BLOCKED_UNSUPPORTED_CLAIM" in text, (
            f"Error should contain BLOCKED_UNSUPPORTED_CLAIM, got: {text}"
        )
        assert "statistic" in text, (
            f"Error should reference claim_type 'statistic', got: {text}"
        )

    def test_statistic_without_source_passes_schema(self):
        data = _load("statistic_without_source.json")
        errors = validate_claim_schema(data)
        assert errors == [], (
            "Schema should allow missing source_id. "
            "Business rules handle the source requirement."
        )


# ---------------------------------------------------------------------------
#  3. Study/person/date claim without source fails
# ---------------------------------------------------------------------------

class TestStudyPersonDateWithoutSource:
    def test_study_without_source_fails(self):
        data = _load("study_person_date_without_source.json")
        errors = validate_claim_business_rules(data)
        text = _error_text(errors)
        assert len(errors) > 0, (
            "Study/person/date claims without source should produce errors"
        )
        assert "BLOCKED_UNSUPPORTED_CLAIM" in text, (
            f"Error should contain BLOCKED_UNSUPPORTED_CLAIM, got: {text}"
        )
        for ctype in ["study", "person", "date"]:
            assert ctype in text, (
                f"Error should reference claim_type '{ctype}', got: {text}"
            )


# ---------------------------------------------------------------------------
#  4. Opinion claim without source passes
# ---------------------------------------------------------------------------

class TestOpinionWithoutSource:
    def test_opinion_without_source_passes_business_rules(self):
        data = _load("opinion_without_source.json")
        errors = validate_claim_business_rules(data)
        assert errors == [], (
            f"Opinion claims without source should pass, got errors: "
            f"{[e['message'] for e in errors]}"
        )

    def test_original_argument_without_source_passes(self):
        data = _load("opinion_without_source.json")
        errors = validate_claim_business_rules(data)
        assert errors == [], (
            "original_argument claims without source should pass"
        )


# ---------------------------------------------------------------------------
#  5. Overlay source ref to unknown claim fails
# ---------------------------------------------------------------------------

class TestOverlayRefUnknownClaim:
    def test_overlay_ref_unknown_claim_fails(self):
        data = _load("overlay_ref_unknown_claim.json")
        claims = data.get("claims", [])
        all_refs = set()
        for ov in data.get("overlays", []):
            for ref in ov.get("claim_refs", []):
                all_refs.add(ref)
        errors = validate_claim_refs_resolve(claims, all_refs)
        text = _error_text(errors)
        assert len(errors) > 0, (
            "Overlay ref to unknown claim should produce ref errors"
        )
        assert "BLOCKED_UNRESOLVED_CLAIM_REF" in text, (
            f"Error should contain BLOCKED_UNRESOLVED_CLAIM_REF, got: {text}"
        )
        assert "C002" in text, (
            f"Error should reference the unknown claim id C002, got: {text}"
        )
        assert "C003" in text, (
            f"Error should reference the unknown claim id C003, got: {text}"
        )


# ---------------------------------------------------------------------------
#  6. Duplicate claim IDs fail
# ---------------------------------------------------------------------------

class TestDuplicateClaimIDs:
    def test_duplicate_claim_ids_fail(self):
        data = _load("duplicate_claim_ids.json")
        errors = validate_claim_business_rules(data)
        text = _error_text(errors)
        assert len(errors) > 0, (
            "Duplicate claim IDs should produce business rule errors"
        )
        assert "BLOCKED_DUPLICATE_CLAIM_ID" in text, (
            f"Error should contain BLOCKED_DUPLICATE_CLAIM_ID, got: {text}"
        )


# ---------------------------------------------------------------------------
#  7. Unsupported visual treatment fails
# ---------------------------------------------------------------------------

class TestUnsupportedVisualTreatment:
    def test_unsupported_visual_treatment_fails(self):
        data = _load("unsupported_visual_treatment.json")
        errors = validate_claim_business_rules(data)
        text = _error_text(errors)
        assert len(errors) > 0, (
            "Unsupported visual treatment should produce business rule errors"
        )
        assert "BLOCKED_VISUAL_TREATMENT" in text, (
            f"Error should contain BLOCKED_VISUAL_TREATMENT, got: {text}"
        )
        assert "invalid_hologram_future_vision" in text, (
            f"Error should reference the invalid treatment value, got: {text}"
        )


# ---------------------------------------------------------------------------
#  8. Claim linked to nonexistent segment fails
# ---------------------------------------------------------------------------

class TestClaimNonexistentSegment:
    def test_claim_nonexistent_segment_fails_with_known_segments(self):
        data = _load("claim_nonexistent_segment.json")
        known_segments = {"S001", "S002"}
        errors = validate_claim_business_rules(data, known_segment_ids=known_segments)
        text = _error_text(errors)
        assert len(errors) > 0, (
            "Claim referencing nonexistent segment should produce errors"
        )
        assert "BLOCKED_NONEXISTENT_SEGMENT" in text, (
            f"Error should contain BLOCKED_NONEXISTENT_SEGMENT, got: {text}"
        )
        assert "S999" in text or "S_INVALID" in text, (
            f"Error should reference the nonexistent segment ID, got: {text}"
        )

    def test_claim_nonexistent_segment_passes_without_known_segments(self):
        data = _load("claim_nonexistent_segment.json")
        errors = validate_claim_business_rules(data)
        assert errors == [], (
            "Without known_segment_ids, segment ref validation should not apply"
        )


# ---------------------------------------------------------------------------
#  Schema documentation / contract existence
# ---------------------------------------------------------------------------

class TestSchemaDocumentation:
    def test_claim_inventory_schema_exists(self):
        path = ROOT / "schemas" / "claim_inventory.schema.json"
        assert path.exists(), "Claim inventory schema file must exist"
        schema = json.loads(path.read_text())
        defs = schema.get("definitions", {})
        assert "claim" in defs, "Schema must define 'claim'"

    def test_claim_inventory_contract_doc_exists(self):
        path = ROOT / "docs" / "plans" / "storyboard_v2" / "CLAIM_INVENTORY_CONTRACT.md"
        assert path.exists(), "Claim inventory contract doc must exist"
        text = path.read_text()
        assert "claim_id" in text, "Contract doc must describe claim_id"
        assert "Sonnet" in text, "Contract doc must explain how Sonnet links claims to visuals"
        assert "source-backed" in text or "source_backed" in text, (
            "Contract doc must cover source-backed claims"
        )


class TestBusinessRuleConstants:
    def test_allowed_source_backed_types_include_required_types(self):
        for t in ["statistic", "study", "person", "date", "fact"]:
            assert t in ALLOWED_SOURCE_BACKED_TYPES, (
                f"{t} must be in ALLOWED_SOURCE_BACKED_TYPES"
            )

    def test_opinion_types_include_opinion_and_original_argument(self):
        assert "opinion" in OPINION_TYPES
        assert "original_argument" in OPINION_TYPES
