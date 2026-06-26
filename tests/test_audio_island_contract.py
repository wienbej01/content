"""Tests for S13-T001: Audio-island contract mapping.

This test suite proves:
1. Core invariant: each audio_policy maps to correct audio_assembly_mode
2. Regression: old global-overlay behavior cannot occur for HERO_SYNC_LOCKED
3. Existing tests still pass
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from assemble_db import get_audio_assembly_mode, _AUDIO_ASSEMBLY_MODE_MAP, _HERO_LIPSYNC_POLICIES


class TestAudioAssemblyModeCoreInvariant:
    """Prove the core invariant: correct mapping for all audio_policy values."""

    def test_hero_sync_locked_maps_to_hero_island(self):
        """HERO_SYNC_LOCKED must map to hero_island to preserve compensated provider audio."""
        assert get_audio_assembly_mode("HERO_SYNC_LOCKED") == "hero_island"

    def test_broll_flex_maps_to_master_slice(self):
        """BROLL_FLEX must map to master_slice to use narration slices."""
        assert get_audio_assembly_mode("BROLL_FLEX") == "master_slice"

    def test_silent_graphic_maps_to_silent_under_music(self):
        """SILENT_GRAPHIC must map to silent_under_music for music bed only."""
        assert get_audio_assembly_mode("SILENT_GRAPHIC") == "silent_under_music"

    def test_all_hero_lipsync_policies_map_to_hero_island(self):
        """All hero lipsync policies must preserve provider audio."""
        for policy in _HERO_LIPSYNC_POLICIES:
            assert get_audio_assembly_mode(policy) == "hero_island", \
                f"Hero lipsync policy {policy} must map to hero_island"

    def test_all_valid_audio_policies_have_mapping(self):
        """Every valid audio_policy from schema must map to an assembly mode."""
        # All valid values from migration 004 trigger + application layer
        valid_policies = [
            "HERO_SYNC_LOCKED", "BROLL_FLEX", "BROLL_SYNCED_ACTION",
            "AMBIENCE_OR_SFX", "MUSIC_BED", "SILENT_GRAPHIC",
            "narration_overlay", "silent", "baked_in", "generated_tts",
            "strip", "ambient",
        ]
        for policy in valid_policies:
            mode = get_audio_assembly_mode(policy)
            assert mode in ("hero_island", "master_slice", "silent_under_music"), \
                f"Policy {policy} must map to valid mode, got {mode}"


class TestAudioAssemblyModeRegression:
    """Prove old global-overlay behavior cannot occur for hero segments."""

    def test_hero_sync_locked_is_not_master_slice(self):
        """HERO_SYNC_LOCKED must NOT use master_slice (would lose provider audio)."""
        assert get_audio_assembly_mode("HERO_SYNC_LOCKED") != "master_slice"

    def test_hero_sync_locked_is_not_silent(self):
        """HERO_SYNC_LOCKED must NOT be silent (requires provider audio track)."""
        assert get_audio_assembly_mode("HERO_SYNC_LOCKED") != "silent_under_music"

    def test_broll_flex_is_not_hero_island(self):
        """BROLL_FLEX must NOT use hero_island (no provider audio to preserve)."""
        assert get_audio_assembly_mode("BROLL_FLEX") != "hero_island"

    def test_compensated_hero_artifact_implies_hero_island(self):
        """Hero units with compensated artifacts require hero_island mode.

        This invariant ensures that when S13-T002 enforces compensated artifact
        requirements, the assembly mode will be compatible.
        """
        for policy in _HERO_LIPSYNC_POLICIES:
            mode = get_audio_assembly_mode(policy)
            assert mode == "hero_island", \
                f"Hero lipsync policy {policy} requires hero_island for compensated audio"


class TestAudioAssemblyModeErrors:
    """Prove invalid audio_policy values are blocked explicitly."""

    def test_unknown_audio_policy_raises_value_error(self):
        """Unknown audio_policy must raise ValueError with BLOCKED_ prefix."""
        with pytest.raises(ValueError, match="BLOCKED_AUDIO_ASSEMBLY_MODE_UNKNOWN"):
            get_audio_assembly_mode("INVALID_POLICY")

    def test_empty_string_audio_policy_raises_value_error(self):
        """Empty audio_policy must raise ValueError."""
        with pytest.raises(ValueError, match="BLOCKED_AUDIO_ASSEMBLY_MODE_UNKNOWN"):
            get_audio_assembly_mode("")

    def test_none_audio_policy_raises_value_error(self):
        """None audio_policy must raise ValueError."""
        with pytest.raises(ValueError, match="BLOCKED_AUDIO_ASSEMBLY_MODE_UNKNOWN"):
            get_audio_assembly_mode(None)  # type: ignore


class TestAudioAssemblyModeMappingCompleteness:
    """Prove the mapping covers all required values and nothing else."""

    def test_mapping_contains_all_hero_policies(self):
        """Mapping must include all policies from _HERO_LIPSYNC_POLICIES."""
        for policy in _HERO_LIPSYNC_POLICIES:
            assert policy in _AUDIO_ASSEMBLY_MODE_MAP, \
                f"Missing hero policy in mapping: {policy}"

    def test_mapping_outputs_are_valid_modes(self):
        """All mapping values must be valid assembly modes."""
        valid_modes = {"hero_island", "master_slice", "silent_under_music"}
        for policy, mode in _AUDIO_ASSEMBLY_MODE_MAP.items():
            assert mode in valid_modes, \
                f"Invalid mode for {policy}: {mode}"

    def test_mapping_is_exhaustive_for_schema(self):
        """Mapping must cover all audio_policy values from DB schema (migration 004).

        Application layer extends the DB trigger values with legacy aliases
        'keep_lipsync' and 'hero_lipsync' which are valid in _HERO_LIPSYNC_POLICIES.
        """
        # All values enforced by trg_ru_audio_policy trigger
        schema_policies = {
            "HERO_SYNC_LOCKED", "BROLL_FLEX", "BROLL_SYNCED_ACTION",
            "AMBIENCE_OR_SFX", "MUSIC_BED", "SILENT_GRAPHIC",
            "narration_overlay", "silent", "baked_in", "generated_tts",
            "strip", "ambient",
        }
        # Application layer adds legacy aliases
        app_layer_policies = schema_policies | {"keep_lipsync", "hero_lipsync"}
        mapping_keys = set(_AUDIO_ASSEMBLY_MODE_MAP.keys())
        assert mapping_keys == app_layer_policies, \
            f"Mapping keys {mapping_keys} != expected {app_layer_policies}"


class TestAudioAssemblyModeContractPreservation:
    """Prove existing manifest fields are preserved (no breaking changes)."""

    def test_hero_sync_locked_constant_unchanged(self):
        """_HERO_LIPSYNC_POLICIES must still contain HERO_SYNC_LOCKED."""
        assert "HERO_SYNC_LOCKED" in _HERO_LIPSYNC_POLICIES
        assert "keep_lipsync" in _HERO_LIPSYNC_POLICIES
        assert "hero_lipsync" in _HERO_LIPSYNC_POLICIES

    def test_mapping_does_not_remove_existing_policies(self):
        """New mapping must not remove any policy values that existing code uses."""
        # Check that policies referenced in existing tests are still mapped
        legacy_policies = ["HERO_SYNC_LOCKED", "BROLL_FLEX", "SILENT_GRAPHIC"]
        for policy in legacy_policies:
            assert policy in _AUDIO_ASSEMBLY_MODE_MAP, \
                f"Legacy policy {policy} removed from mapping"
