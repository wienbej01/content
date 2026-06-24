"""Tests for failure class → repair action map (S04-T001)."""
import pytest

from scripts.repair_map import (
    REPAIR_MAP, get_repair, change_type_for, target_stage_for,
)

# All known failure classes from 02_FAILURE_TAXONOMY.md
EXPECTED_CLASSES = {
    "F-LIP-001", "F-LIP-002", "F-LIP-003", "F-LIP-004",
    "F-ASM-001", "F-ASM-002", "F-ASM-003",
    "F-GFX-001", "F-GFX-002", "F-GFX-003",
    "F-TEXT-001",
    "F-QA-001", "F-QA-002",
    "F-PROV-001", "F-PROV-002",
    "F-SPEND-001", "F-SPEND-002",
}

VALID_CHANGE_TYPES = {
    "re_generate", "re_slice", "re_assemble", "re_plan",
    "re_render_local", "add_gate", "block_pipeline",
    "fix_provenance", "fix_column", "unlock_render", "add_idempotency",
}

VALID_STAGES = {
    "render_media", "audio_timing", "assemble", "graphics_compositing",
    "qa_final", "audio_slicing", "production_db",
}


class TestRepairMapCompleteness:
    """Every known failure class has a repair mapping."""

    def test_all_classes_mapped(self):
        """Every failure class from taxonomy has an entry."""
        mapped = set(REPAIR_MAP.keys())
        missing = EXPECTED_CLASSES - mapped
        assert len(missing) == 0, f"Unmapped failure classes: {missing}"

    def test_no_extra_classes(self):
        """No extra classes beyond taxonomy."""
        mapped = set(REPAIR_MAP.keys())
        extra = mapped - EXPECTED_CLASSES
        assert len(extra) == 0, f"Extra failure classes: {extra}"

    def test_each_entry_has_required_fields(self):
        """Each mapping has target_stage, change_type, description."""
        for fc, entry in REPAIR_MAP.items():
            assert "target_stage" in entry, f"{fc} missing target_stage"
            assert "change_type" in entry, f"{fc} missing change_type"
            assert "description" in entry, f"{fc} missing description"

    def test_all_target_stages_valid(self):
        """All target_stages are from the known set."""
        for fc, entry in REPAIR_MAP.items():
            assert entry["target_stage"] in VALID_STAGES, (
                f"{fc} has invalid target_stage: {entry['target_stage']}"
            )

    def test_all_change_types_valid(self):
        """All change_types are from the known set."""
        for fc, entry in REPAIR_MAP.items():
            assert entry["change_type"] in VALID_CHANGE_TYPES, (
                f"{fc} has invalid change_type: {entry['change_type']}"
            )


class TestGetRepair:
    """Lookup functions work correctly."""

    def test_get_repair_returns_entry(self):
        entry = get_repair("F-LIP-001")
        assert entry is not None
        assert entry["target_stage"] == "render_media"

    def test_get_repair_unknown_returns_none(self):
        assert get_repair("F-UNKNOWN-999") is None

    def test_change_type_for(self):
        assert change_type_for("F-LIP-004") == "re_slice"
        assert change_type_for("F-GFX-001") == "re_plan"
        assert change_type_for("F-QA-002") == "block_pipeline"

    def test_target_stage_for(self):
        assert target_stage_for("F-LIP-001") == "render_media"
        assert target_stage_for("F-LIP-004") == "audio_timing"
        assert target_stage_for("F-TEXT-001") == "render_media"

    def test_unknown_returns_none(self):
        assert change_type_for("F-FOO") is None
        assert target_stage_for("F-FOO") is None

    def test_lip_003_does_not_render_first(self):
        """F-LIP-004 repair does NOT trigger provider render (audio_timing stage)."""
        assert target_stage_for("F-LIP-004") != "render_media"
        assert target_stage_for("F-LIP-004") == "audio_timing"

    def test_qa_002_blocks_pipeline(self):
        """F-QA-002 blocks pipeline, does not repair media."""
        assert change_type_for("F-QA-002") == "block_pipeline"
