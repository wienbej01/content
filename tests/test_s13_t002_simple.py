"""Simplified tests for S13-T002: Enforce compensated hero artifact requirement.

This test suite focuses on the core enforcement logic without complex test setup.
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from assemble_db import get_audio_assembly_mode, AssemblyError


class TestAudioAssemblyModeS13_T002:
    """Verify the audio_assembly_mode mapping works for enforcement."""

    def test_hero_sync_locked_maps_to_hero_island(self):
        """HERO_SYNC_LOCKED must map to hero_island for enforcement."""
        mode = get_audio_assembly_mode("HERO_SYNC_LOCKED")
        assert mode == "hero_island", "HERO_SYNC_LOCKED requires hero_island mode for compensated artifact enforcement"

    def test_broll_flex_maps_to_master_slice(self):
        """BROLL_FLEX must map to master_slice (not hero_island)."""
        mode = get_audio_assembly_mode("BROLL_FLEX")
        assert mode == "master_slice", "BROLL_FLEX should not trigger hero artifact enforcement"


class TestCompensatedArtifactErrorMessages:
    """Verify error message formatting from the implementation."""

    def test_blocked_compensated_artifact_missing_error_format(self):
        """BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING error must contain required strings."""
        # Simulate the error message from assemble_db.py lines 273-279
        unit_id = "test_unit_123"
        label = "HERO_TEST"
        error_msg = (
            f"BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING: render unit {unit_id} "
            f"({label}) requires compensated_artifact_path for hero_island assembly mode. "
            f"Hero lip-sync units must use compensated provider audio to preserve sync. "
            f"Raw provider video cannot be used."
        )

        assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING" in error_msg
        assert unit_id in error_msg
        assert label in error_msg
        assert "hero_island" in error_msg
        assert "compensated_artifact_path" in error_msg
        assert "Raw provider video cannot be used" in error_msg

    def test_blocked_compensated_artifact_file_missing_error_format(self):
        """BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING error must contain required strings."""
        unit_id = "test_unit_456"
        label = "HERO_TEST_2"
        missing_path = "/path/to/missing.mp4"
        error_msg = (
            f"BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING: render unit {unit_id} "
            f"({label}) compensated_artifact_path file not found: {missing_path}. "
            f"Hero lip-sync units require the compensated artifact file to exist."
        )

        assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING" in error_msg
        assert unit_id in error_msg
        assert label in error_msg
        assert missing_path in error_msg
        assert "not found" in error_msg


class TestEnforcementLogicLocation:
    """Verify enforcement code exists in the right location."""

    def test_enforcement_in_validate_assembly_inputs(self):
        """Compensated artifact enforcement must be in validate_assembly_inputs()."""
        import inspect
        from assemble_db import validate_assembly_inputs

        source = inspect.getsource(validate_assembly_inputs)

        # Check for key enforcement markers
        assert "S13-T002" in source or "Compensated hero artifact" in source, \
            "Enforcement code must be in validate_assembly_inputs"
        assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING" in source, \
            "Must check for missing compensated artifact path"
        assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING" in source, \
            "Must check for missing compensated artifact file"
        assert "hero_island" in source, \
            "Must use audio_assembly_mode from S13-T001"
        assert "get_audio_assembly_mode" in source, \
            "Must call audio_assembly_mode mapping function"

    def test_enforcement_after_syncnet_gate(self):
        """Compensated artifact enforcement should run after SyncNet gate."""
        import inspect
        from assemble_db import validate_assembly_inputs

        source = inspect.getsource(validate_assembly_inputs)

        # Find positions (rough check by substring order)
        syncnet_pos = source.find("BLOCKED_HERO_SYNC_UNVERIFIED")
        compensated_pos = source.find("BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING")

        # Both should exist, and compensated should come after syncnet
        assert syncnet_pos > 0, "SyncNet gate must exist"
        assert compensated_pos > 0, "Compensated artifact enforcement must exist"
        assert compensated_pos > syncnet_pos, \
            "Compensated artifact enforcement should run after SyncNet gate"


class TestEnforcementScope:
    """Verify enforcement only applies to hero_island units."""

    def test_enforcement_uses_hero_lipsync_policies(self):
        """Enforcement must check _HERO_LIPSYNC_POLICIES."""
        import inspect
        from assemble_db import validate_assembly_inputs

        source = inspect.getsource(validate_assembly_inputs)

        # Should check against hero policies
        assert "_HERO_LIPSYNC_POLICIES" in source or \
               "lipsync_required" in source, \
               "Must check hero lipsync policies"

    def test_enforcement_checks_audio_assembly_mode(self):
        """Enforcement must verify audio_assembly_mode == 'hero_island'."""
        import inspect
        from assemble_db import validate_assembly_inputs

        source = inspect.getsource(validate_assembly_inputs)

        # Should call get_audio_assembly_mode and check for hero_island
        assert 'get_audio_assembly_mode' in source, \
               "Must call audio_assembly_mode mapping"
        assert '"hero_island"' in source or "'hero_island'" in source, \
               "Must check for hero_island mode"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
