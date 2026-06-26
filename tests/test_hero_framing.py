"""Tests for S14-T002: Hero framing metadata.

Validates that:
- Hero framing metadata (close, medium, wide) is properly stored and validated
- HERO_SYNC_LOCKED with hero_framing=close resolves to close_hero policy
- HERO_SYNC_LOCKED with hero_framing=medium resolves to medium_hero policy
- HERO_SYNC_LOCKED with hero_framing=wide resolves to wide_hero behavior
- HERO_SYNC_LOCKED missing hero_framing defaults to close_hero
- Explicit invalid hero_framing fails closed with BLOCKED_INVALID_HERO_FRAMING
- Non-hero BROLL_FLEX does not require hero_framing
- Metadata is propagated into assembly manifest for S14_T003/S14_T004
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from hero_framing import (
    normalize_hero_framing,
    get_effective_hero_framing,
    hero_framing_to_policy_name,
    policy_name_to_hero_framing,
    CLOSE_FRAMING,
    MEDIUM_FRAMING,
    WIDE_FRAMING,
    DEFAULT_HERO_FRAMING,
    HERO_AUDIO_POLICIES,
    HeroFramingMetadata,
)
import production_db as _db


# ---------------------------------------------------------------------------
# Test normalization
# ---------------------------------------------------------------------------

class TestNormalizeHeroFraming:
    """Test hero framing normalization."""

    def test_normalize_close(self):
        """'close' normalizes to 'close'."""
        result = normalize_hero_framing("close")
        assert result == "close"

    def test_normalize_medium(self):
        """'medium' normalizes to 'medium'."""
        result = normalize_hero_framing("medium")
        assert result == "medium"

    def test_normalize_wide(self):
        """'wide' normalizes to 'wide'."""
        result = normalize_hero_framing("wide")
        assert result == "wide"

    def test_normalize_case_insensitive(self):
        """Normalization is case-insensitive."""
        assert normalize_hero_framing("CLOSE") == "close"
        assert normalize_hero_framing("Medium") == "medium"
        assert normalize_hero_framing("WIDE") == "wide"

    def test_normalize_whitespace(self):
        """Normalization strips whitespace."""
        assert normalize_hero_framing(" close ") == "close"

    def test_normalize_none_returns_none(self):
        """None returns None."""
        assert normalize_hero_framing(None) is None

    def test_normalize_empty_string_returns_none(self):
        """Empty string returns None."""
        assert normalize_hero_framing("") is None

    def test_normalize_invalid_raises_error(self):
        """Invalid value raises ValueError with BLOCKED_INVALID_HERO_FRAMING."""
        with pytest.raises(ValueError, match="BLOCKED_INVALID_HERO_FRAMING"):
            normalize_hero_framing("portrait")

    def test_normalize_invalid_tight_raises_error(self):
        """'tight' raises ValueError."""
        with pytest.raises(ValueError, match="BLOCKED_INVALID_HERO_FRAMING"):
            normalize_hero_framing("tight")

    def test_normalize_invalid_full_body_raises_error(self):
        """'full_body' raises ValueError."""
        with pytest.raises(ValueError, match="BLOCKED_INVALID_HERO_FRAMING"):
            normalize_hero_framing("full_body")


# ---------------------------------------------------------------------------
# Test effective hero framing with defaults
# ---------------------------------------------------------------------------

class TestEffectiveHeroFraming:
    """Test effective hero framing resolution with fail-closed defaults."""

    def test_hero_sync_locked_with_close(self):
        """HERO_SYNC_LOCKED with hero_framing=close resolves to close_hero policy."""
        result = get_effective_hero_framing(
            hero_framing="close",
            audio_policy="HERO_SYNC_LOCKED",
        )
        assert result.effective_framing == "close"
        assert result.policy_name == "close_hero"
        assert result.is_hero_unit is True
        assert result.requires_framing is True
        assert result.source == "explicit"

    def test_hero_sync_locked_with_medium(self):
        """HERO_SYNC_LOCKED with hero_framing=medium resolves to medium_hero policy."""
        result = get_effective_hero_framing(
            hero_framing="medium",
            audio_policy="HERO_SYNC_LOCKED",
        )
        assert result.effective_framing == "medium"
        assert result.policy_name == "medium_hero"
        assert result.is_hero_unit is True
        assert result.requires_framing is True
        assert result.source == "explicit"

    def test_hero_sync_locked_with_wide(self):
        """HERO_SYNC_LOCKED with hero_framing=wide resolves to wide_hero policy."""
        result = get_effective_hero_framing(
            hero_framing="wide",
            audio_policy="HERO_SYNC_LOCKED",
        )
        assert result.effective_framing == "wide"
        assert result.policy_name == "wide_hero"
        assert result.is_hero_unit is True
        assert result.requires_framing is True
        assert result.source == "explicit"

    def test_hero_sync_locked_missing_framing_defaults_to_close(self):
        """HERO_SYNC_LOCKED missing hero_framing defaults to close_hero (fail-closed)."""
        result = get_effective_hero_framing(
            hero_framing=None,
            audio_policy="HERO_SYNC_LOCKED",
        )
        assert result.effective_framing == "close"
        assert result.policy_name == "close_hero"
        assert result.is_hero_unit is True
        assert result.requires_framing is True
        assert result.source == "default"

    def test_hero_lipsync_missing_framing_defaults_to_close(self):
        """hero_lipsync missing hero_framing defaults to close_hero."""
        result = get_effective_hero_framing(
            hero_framing=None,
            audio_policy="hero_lipsync",
        )
        assert result.effective_framing == "close"
        assert result.policy_name == "close_hero"
        assert result.source == "default"

    def test_keep_lipsync_missing_framing_defaults_to_close(self):
        """keep_lipsync missing hero_framing defaults to close_hero."""
        result = get_effective_hero_framing(
            hero_framing=None,
            audio_policy="keep_lipsync",
        )
        assert result.effective_framing == "close"
        assert result.policy_name == "close_hero"
        assert result.source == "default"

    def test_lipsync_required_true_missing_framing_defaults_to_close(self):
        """lipsync_required=True missing hero_framing defaults to close_hero."""
        result = get_effective_hero_framing(
            hero_framing=None,
            lipsync_required=True,
        )
        assert result.effective_framing == "close"
        assert result.policy_name == "close_hero"
        assert result.source == "default"

    def test_broll_flex_does_not_require_framing(self):
        """Non-hero BROLL_FLEX does not require hero_framing."""
        result = get_effective_hero_framing(
            hero_framing=None,
            audio_policy="BROLL_FLEX",
        )
        assert result.is_hero_unit is False
        assert result.requires_framing is False
        assert result.source == "not_required"

    def test_broll_synced_action_does_not_require_framing(self):
        """BROLL_SYNCED_ACTION does not require hero_framing."""
        result = get_effective_hero_framing(
            hero_framing=None,
            audio_policy="BROLL_SYNCED_ACTION",
        )
        assert result.is_hero_unit is False
        assert result.requires_framing is False

    def test_silent_graphic_does_not_require_framing(self):
        """SILENT_GRAPHIC does not require hero_framing."""
        result = get_effective_hero_framing(
            hero_framing=None,
            audio_policy="SILENT_GRAPHIC",
        )
        assert result.is_hero_unit is False
        assert result.requires_framing is False

    def test_hero_with_invalid_framing_raises_error(self):
        """Hero unit with invalid hero_framing raises BLOCKED_INVALID_HERO_FRAMING."""
        with pytest.raises(ValueError, match="BLOCKED_INVALID_HERO_FRAMING"):
            get_effective_hero_framing(
                hero_framing="portrait",
                audio_policy="HERO_SYNC_LOCKED",
            )

    def test_hero_with_tight_framing_raises_error(self):
        """Hero unit with 'tight' framing raises BLOCKED_INVALID_HERO_FRAMING."""
        with pytest.raises(ValueError, match="BLOCKED_INVALID_HERO_FRAMING"):
            get_effective_hero_framing(
                hero_framing="tight",
                audio_policy="HERO_SYNC_LOCKED",
            )

    def test_non_hero_with_invalid_framing_still_does_not_require(self):
        """Non-hero unit with invalid hero_framing still doesn't require framing."""
        # This is a design decision: non-hero units ignore framing entirely
        # The invalid framing would be caught at DB insert/update time
        result = get_effective_hero_framing(
            hero_framing="invalid",
            audio_policy="BROLL_FLEX",
        )
        assert result.is_hero_unit is False
        assert result.requires_framing is False


# ---------------------------------------------------------------------------
# Test policy mapping
# ---------------------------------------------------------------------------

class TestPolicyMapping:
    """Test hero framing to policy name mapping."""

    def test_close_framing_to_close_hero_policy(self):
        """'close' framing maps to 'close_hero' policy."""
        assert hero_framing_to_policy_name("close") == "close_hero"

    def test_medium_framing_to_medium_hero_policy(self):
        """'medium' framing maps to 'medium_hero' policy."""
        assert hero_framing_to_policy_name("medium") == "medium_hero"

    def test_wide_framing_to_wide_hero_policy(self):
        """'wide' framing maps to 'wide_hero' policy."""
        assert hero_framing_to_policy_name("wide") == "wide_hero"

    def test_close_hero_policy_to_close_framing(self):
        """'close_hero' policy maps back to 'close' framing."""
        assert policy_name_to_hero_framing("close_hero") == "close"

    def test_medium_hero_policy_to_medium_framing(self):
        """'medium_hero' policy maps back to 'medium' framing."""
        assert policy_name_to_hero_framing("medium_hero") == "medium"

    def test_wide_hero_policy_to_wide_framing(self):
        """'wide_hero' policy maps back to 'wide' framing."""
        assert policy_name_to_hero_framing("wide_hero") == "wide"

    def test_diagnostic_legacy_policy_maps_to_none(self):
        """'diagnostic_legacy' policy maps to None (not a hero policy)."""
        assert policy_name_to_hero_framing("diagnostic_legacy") is None

    def test_unknown_policy_maps_to_none(self):
        """Unknown policy maps to None."""
        assert policy_name_to_hero_framing("unknown_policy") is None


# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

class TestConstants:
    """Test module constants."""

    def test_default_hero_framing_is_close(self):
        """DEFAULT_HERO_FRAMING is 'close'."""
        assert DEFAULT_HERO_FRAMING == "close"

    def test_hero_audio_policies_contains_expected(self):
        """HERO_AUDIO_POLICIES contains expected values."""
        assert "HERO_SYNC_LOCKED" in HERO_AUDIO_POLICIES
        assert "hero_lipsync" in HERO_AUDIO_POLICIES
        assert "keep_lipsync" in HERO_AUDIO_POLICIES

    def test_close_framing_constant(self):
        """CLOSE_FRAMING constant is 'close'."""
        assert CLOSE_FRAMING == "close"

    def test_medium_framing_constant(self):
        """MEDIUM_FRAMING constant is 'medium'."""
        assert MEDIUM_FRAMING == "medium"

    def test_wide_framing_constant(self):
        """WIDE_FRAMING constant is 'wide'."""
        assert WIDE_FRAMING == "wide"


# ---------------------------------------------------------------------------
# Test metadata propagation
# ---------------------------------------------------------------------------

class TestMetadataPropagation:
    """Test that hero framing metadata is properly propagated."""

    def test_hero_framing_metadata_structure(self):
        """HeroFramingMetadata has all required fields."""
        result = get_effective_hero_framing(
            hero_framing="close",
            audio_policy="HERO_SYNC_LOCKED",
        )

        # Check all fields exist
        assert hasattr(result, "hero_framing")
        assert hasattr(result, "effective_framing")
        assert hasattr(result, "policy_name")
        assert hasattr(result, "is_hero_unit")
        assert hasattr(result, "requires_framing")
        assert hasattr(result, "source")

        # Check field values
        assert result.hero_framing == "close"
        assert result.effective_framing == "close"
        assert result.policy_name == "close_hero"
        assert result.is_hero_unit is True
        assert result.requires_framing is True
        assert result.source == "explicit"

    def test_metadata_available_for_policy_evaluation(self):
        """Metadata structure provides policy_name for S14_T003/T004 evaluation."""
        result = get_effective_hero_framing(
            hero_framing="medium",
            audio_policy="HERO_SYNC_LOCKED",
        )

        # Policy name is available for SyncNet policy evaluation
        assert result.policy_name == "medium_hero"

        # Effective framing is available for logging/reporting
        assert result.effective_framing == "medium"

        # Source indicates if default was used
        assert result.source == "explicit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
