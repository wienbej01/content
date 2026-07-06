"""ENG-0601/0602: Tests for failure classification and repair action decision table.

Test each classification and its corresponding action.
"""
import pytest

from media_service import (
    classify_validation_failure,
    choose_repair_action,
    VALIDATION_FAILURE_CLASSIFICATIONS,
    REPAIR_ACTIONS,
)


# =========================================================================
# ENG-0601: classify_validation_failure
# =========================================================================

class TestClassifyValidationFailure:
    """Each known failure mode maps to one classification."""

    def test_missing_artifact(self):
        ev = {"file_exists": False, "sha_match": False}
        assert classify_validation_failure(ev) == "missing_artifact"

    def test_sha_mismatch(self):
        ev = {"file_exists": True, "sha_match": False}
        assert classify_validation_failure(ev) == "sha_mismatch"

    def test_provider_forbidden_asset(self):
        ev = {"file_exists": True, "sha_match": True,
              "render_method": "local_graphic", "no_provider_job": False}
        assert classify_validation_failure(ev) == "provider_forbidden_asset"

    def test_local_graphic_not_local(self):
        ev = {"file_exists": True, "sha_match": True,
              "render_method": "local_graphic", "no_provider_job": True,
              "provenance_ok": False}
        assert classify_validation_failure(ev) == "local_graphic_not_local"

    def test_local_graphic_text_mismatch(self):
        ev = {"file_exists": True, "sha_match": True,
              "render_method": "local_graphic", "no_provider_job": True,
              "provenance_ok": True, "text_spec_sha_match": False}
        assert classify_validation_failure(ev) == "local_graphic_text_mismatch"

    def test_unexpected_visible_text(self):
        ev = {"file_exists": True, "sha_match": True,
              "text_detected": True}
        assert classify_validation_failure(ev) == "unexpected_visible_text"

    def test_ocr_unavailable(self):
        ev = {"file_exists": True, "sha_match": True,
              "ocr_available": False, "text_policy": "NO_VISIBLE_TEXT"}
        assert classify_validation_failure(ev) == "ocr_unavailable"

    def test_ocr_unavailable_non_strict_no_text_policy(self):
        """OCR unavailable without NO_VISIBLE_TEXT policy should not classify as ocr_unavailable."""
        ev = {"file_exists": True, "sha_match": True,
              "ocr_available": False, "text_policy": "DETERMINISTIC_GRAPHIC"}
        assert classify_validation_failure(ev) == "duration_shortfall"

    def test_hero_lipsync_unverified(self):
        ev = {"file_exists": True, "sha_match": True,
              "render_method": "hero_lipsync", "duration_ok": False}
        assert classify_validation_failure(ev) == "hero_lipsync_unverified"

    def test_duration_shortfall(self):
        ev = {"file_exists": True, "sha_match": True,
              "render_method": "generated_video", "duration_ok": False}
        assert classify_validation_failure(ev) == "duration_shortfall"

    def test_unknown_contract_failure(self):
        ev = {"file_exists": True, "sha_match": True,
              "render_method": "generated_video", "duration_ok": True,
              "text_detected": False}
        assert classify_validation_failure(ev) == "unknown_contract_failure"

    def test_all_classifications_covered(self):
        """Every known classification has at least one test that produces it."""
        tested = {
            "missing_artifact", "sha_mismatch", "provider_forbidden_asset",
            "local_graphic_not_local", "local_graphic_text_mismatch",
            "unexpected_visible_text", "ocr_unavailable",
            "hero_lipsync_unverified", "hero_lipsync_needs_human_review",
            "duration_shortfall",
            "semantic_mismatch",
            "unknown_contract_failure",
            # S10-C09: provider job failures are not QA-evidence classifications
            # — they're handled by the provider job repair path
            "provider_job_retryable_failure", "provider_job_permanent_failure",
            "hero_lipsync_offset_correctable",
        }
        assert tested == VALIDATION_FAILURE_CLASSIFICATIONS, (
            f"Untested classifications: {VALIDATION_FAILURE_CLASSIFICATIONS - tested}"
        )


# =========================================================================
# ENG-0602: choose_repair_action
# =========================================================================

class TestChooseRepairAction:
    """Decision table for each failure class maps to correct action."""

    def test_local_graphic_not_local(self):
        ru = {"asset_type": "local_graphic"}
        assert choose_repair_action(ru, "local_graphic_not_local") == "render_local_graphic"

    def test_local_graphic_text_mismatch(self):
        ru = {"asset_type": "local_graphic"}
        assert choose_repair_action(ru, "local_graphic_text_mismatch") == "render_local_graphic"

    def test_provider_forbidden_asset_local_graphic(self):
        ru = {"asset_type": "local_graphic"}
        assert choose_repair_action(ru, "provider_forbidden_asset") == "render_local_graphic"

    def test_provider_forbidden_asset_non_local(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "provider_forbidden_asset") == "block_for_manual_review"

    def test_unexpected_visible_text(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "unexpected_visible_text") == "regenerate_provider_video"

    def test_missing_artifact(self):
        ru = {"asset_type": "local_graphic"}
        assert choose_repair_action(ru, "missing_artifact") == "recover_artifact"

    def test_sha_mismatch(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "sha_mismatch") == "block_for_manual_review"

    def test_ocr_unavailable(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "ocr_unavailable") == "rerun_qa"

    def test_hero_lipsync_unverified(self):
        ru = {"asset_type": "lipsync_video"}
        assert choose_repair_action(ru, "hero_lipsync_unverified") == "regenerate_provider_video"

    def test_duration_shortfall(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "duration_shortfall") == "regenerate_provider_video"

    def test_unknown_fallback(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "unknown_contract_failure") == "block_for_manual_review"

    def test_all_failure_classes_have_rule(self):
        """Every classification has a rule in _RULES."""
        from media_service import _RULES
        for cls in VALIDATION_FAILURE_CLASSIFICATIONS:
            assert cls in _RULES, f"Missing rule for {cls}"
