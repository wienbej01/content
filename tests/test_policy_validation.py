"""Tests for policy-aware repository validation (Ticket LB-102)."""
import pytest
from scripts.production_repo import (
    validate_audio_policy,
    validate_text_policy,
    validate_temporal_edit_policy,
    validate_render_unit,
    PolicyValidationError,
)


class TestAudioPolicyValidation:
    def test_valid_hero_sync_locked(self):
        ru = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only",
        }
        validate_audio_policy(ru)  # Should not raise

    def test_invalid_audio_policy_rejected(self):
        ru = {"audio_policy": "INVALID_POLICY"}
        with pytest.raises(PolicyValidationError, match="Invalid or missing audio_policy"):
            validate_audio_policy(ru)

    def test_hero_requires_master_narration(self):
        ru = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "provider_audio",  # Invalid for HERO
            "provider_audio_usage": "diagnostic_only",
        }
        with pytest.raises(PolicyValidationError, match="requires final_audio_source='master_narration'"):
            validate_audio_policy(ru)

    def test_hero_requires_diagnostic_only(self):
        ru = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "master_narration",
            "provider_audio_usage": "final_mix",  # Invalid for HERO
        }
        with pytest.raises(PolicyValidationError, match="requires provider_audio_usage='diagnostic_only'"):
            validate_audio_policy(ru)

    def test_broll_flex_valid(self):
        ru = {
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
        }
        validate_audio_policy(ru)  # Should not raise


class TestTextPolicyValidation:
    def test_valid_no_visible_text(self):
        ru = {"text_policy": "NO_VISIBLE_TEXT"}
        validate_text_policy(ru)  # Should not raise

    def test_invalid_text_policy_rejected(self):
        ru = {"text_policy": "GENERATE_READABLE_TEXT"}
        with pytest.raises(PolicyValidationError, match="Invalid text_policy"):
            validate_text_policy(ru)

    def test_post_composite_requires_replacement_spec(self):
        ru = {"text_policy": "POST_COMPOSITE"}
        with pytest.raises(PolicyValidationError, match="requires a replacement_asset_spec"):
            validate_text_policy(ru)

    def test_real_screen_capture_requires_source(self):
        ru = {"text_policy": "REAL_SCREEN_CAPTURE"}
        with pytest.raises(PolicyValidationError, match="requires a source_artifact_id"):
            validate_text_policy(ru)


class TestTemporalEditPolicyValidation:
    def test_hero_forbids_speed_change(self):
        ru = {"id": "ru_001", "audio_policy": "HERO_SYNC_LOCKED"}
        with pytest.raises(PolicyValidationError, match="HERO_TEMPORAL_EDIT_FORBIDDEN"):
            validate_temporal_edit_policy(ru, "speed_change")

    def test_hero_forbids_loop(self):
        ru = {"id": "ru_002", "audio_policy": "HERO_SYNC_LOCKED"}
        with pytest.raises(PolicyValidationError, match="HERO_TEMPORAL_EDIT_FORBIDDEN"):
            validate_temporal_edit_policy(ru, "loop")

    def test_broll_allows_flex_edits(self):
        ru = {"id": "ru_003", "audio_policy": "BROLL_FLEX"}
        # Should not raise for B-roll
        validate_temporal_edit_policy(ru, "speed_change")


class TestMasterValidation:
    def test_validate_render_unit_passes_valid(self):
        ru = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "text_policy": "NO_VISIBLE_TEXT",
        }
        validate_render_unit(ru)  # Should not raise

    def test_validate_render_unit_fails_on_audio(self):
        ru = {"audio_policy": "INVALID"}
        with pytest.raises(PolicyValidationError):
            validate_render_unit(ru)
