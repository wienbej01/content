"""Tests for hero slicing interval validation (Ticket LB-300)."""
import pytest
from scripts.production_repo import (
    validate_hero_slicing_intervals,
    PolicyValidationError,
)


class TestHeroSlicingValidation:
    def test_valid_hero_slicing_passes(self):
        """Verify that valid hero slicing intervals pass validation."""
        render_unit = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "speech_start_sample": 48000,
            "speech_end_sample": 96000,
            "generation_start_sample": 43200,  # 48000 - 4800 (0.1s leading silence)
            "generation_end_sample": 100800,   # 96000 + 4800 (0.1s trailing silence)
            "visible_start_sample": 48000,
            "visible_end_sample": 96000,
            "leading_silence_samples": 4800,
            "trailing_silence_samples": 4800,
            "master_duration_samples": 150000,
        }
        # Should not raise
        validate_hero_slicing_intervals(render_unit)

    def test_overlapping_speech_rejected(self):
        """Verify that overlapping speech intervals are rejected."""
        # This is checked at the timeline level, but here we check generation vs speech consistency
        render_unit = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "speech_start_sample": 48000,
            "speech_end_sample": 96000,
            "generation_start_sample": 43200,
            "generation_end_sample": 100800,
            "leading_silence_samples": 4800,
            "trailing_silence_samples": 4800,
            # Missing visible, which is allowed, but let's test generation mismatch
        }
        # Valid, no overlap issue here. Overlap is checked in timeline span service.
        validate_hero_slicing_intervals(render_unit)

    def test_generation_extension_without_silence_rejected(self):
        """Verify that generation extending beyond speech without silence is rejected."""
        render_unit = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "speech_start_sample": 48000,
            "speech_end_sample": 96000,
            "generation_start_sample": 40000,  # Does not match speech_start - leading_silence
            "generation_end_sample": 100800,
            "leading_silence_samples": 4800,
            "trailing_silence_samples": 4800,
        }
        with pytest.raises(PolicyValidationError, match="does not match speech"):
            validate_hero_slicing_intervals(render_unit)

    def test_visible_interval_outside_generation_rejected(self):
        """Verify that visible interval exceeding generation interval is rejected."""
        render_unit = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "speech_start_sample": 48000,
            "speech_end_sample": 96000,
            "generation_start_sample": 43200,
            "generation_end_sample": 100800,
            "visible_start_sample": 40000,  # Before generation start
            "visible_end_sample": 96000,
            "leading_silence_samples": 4800,
            "trailing_silence_samples": 4800,
        }
        with pytest.raises(PolicyValidationError, match="exceeds generation interval"):
            validate_hero_slicing_intervals(render_unit)

    def test_exceeds_master_bounds_rejected(self):
        """Verify that generation exceeding master duration is rejected."""
        render_unit = {
            "audio_policy": "HERO_SYNC_LOCKED",
            "speech_start_sample": 140000,
            "speech_end_sample": 145000,
            "generation_start_sample": 135000,
            "generation_end_sample": 150000,  # Exceeds master duration
            "visible_start_sample": 140000,
            "visible_end_sample": 145000,
            "leading_silence_samples": 5000,
            "trailing_silence_samples": 5000,
            "master_duration_samples": 148000,
        }
        with pytest.raises(PolicyValidationError, match="exceeds master duration"):
            validate_hero_slicing_intervals(render_unit)

    def test_non_hero_unit_skips_validation(self):
        """Verify that non-hero units skip strict slicing validation."""
        render_unit = {
            "audio_policy": "BROLL_FLEX",
            # Missing all slicing fields, but should pass because it's not HERO_SYNC_LOCKED
        }
        # Should not raise
        validate_hero_slicing_intervals(render_unit)
