"""Tests for minimal affected stage routing (S04-T003)."""
import pytest

from media_service import route_minimal_stage, _CHANGE_TYPE_TO_STAGE
from repair_map import REPAIR_MAP


class TestMinimalStageFromRepairMap:
    """route_minimal_stage returns the correct minimal stage."""

    def test_lip_001_routes_to_render_media(self):
        """F-LIP-001 (mouth offset) → render_media (regenerate)."""
        stage = route_minimal_stage("F-LIP-001", "re_generate")
        assert stage == "render_media"

    def test_lip_004_routes_to_audio_timing_not_render(self):
        """F-LIP-004 (master window) → audio_timing, NOT render_media."""
        stage = route_minimal_stage("F-LIP-004", "re_slice")
        assert stage == "audio_timing"
        assert stage != "render_media"

    def test_gfx_001_routes_to_graphics(self):
        """F-GFX-001 (static hold) → graphics_compositing without provider video."""
        stage = route_minimal_stage("F-GFX-001", "re_plan")
        assert stage == "graphics_compositing"
        assert stage != "render_media"

    def test_text_001_routes_to_render_media(self):
        """F-TEXT-001 (provider text risk) → render_media (one b-roll unit)."""
        stage = route_minimal_stage("F-TEXT-001", "re_generate")
        assert stage == "render_media"

    def test_qa_002_routes_to_qa_final(self):
        """F-QA-002 (missing eval) → qa_final, blocks pipeline."""
        stage = route_minimal_stage("F-QA-002", "block_pipeline")
        assert stage == "qa_final"

    def test_prov_001_routes_to_audio_slicing(self):
        """F-PROV-001 (broken provenance) → audio_slicing (fix before regenerate)."""
        stage = route_minimal_stage("F-PROV-001", "fix_provenance")
        assert stage == "audio_slicing"

    def test_asm_002_routes_to_assemble(self):
        """F-ASM-002 (visual bed mismatch) → assemble."""
        stage = route_minimal_stage("F-ASM-002", "re_assemble")
        assert stage == "assemble"


class TestChangeTypeToStage:
    """Fallback _CHANGE_TYPE_TO_STAGE has all repair_map change types."""

    def test_all_repair_map_change_types_have_stage(self):
        """Every change_type from REPAIR_MAP has a routing in _CHANGE_TYPE_TO_STAGE."""
        repair_change_types = set(
            entry["change_type"] for entry in REPAIR_MAP.values()
        )
        routed_types = set(_CHANGE_TYPE_TO_STAGE.keys())
        missing = repair_change_types - routed_types
        assert len(missing) == 0, f"Missing stage routing for change types: {missing}"

    def test_all_stage_routes_known(self):
        """All target stages in _CHANGE_TYPE_TO_STAGE are recognized."""
        known_stages = {"render_media", "audio_timing", "assemble",
                        "graphics_compositing", "qa_final", "audio_slicing",
                        "production_db"}
        for ct, stage in _CHANGE_TYPE_TO_STAGE.items():
            assert stage in known_stages, f"{ct} routes to unknown stage: {stage}"


class TestSpecificConstraints:
    """Ticket-specific routing constraints."""

    def test_timing_failure_no_provider_render(self):
        """Timing failure (F-ASM-002) → assemble, not provider render."""
        assert route_minimal_stage("F-ASM-002", "re_assemble") != "render_media"

    def test_source_slice_mismatch_re_slice_before_regenerate(self):
        """Source-slice issue (F-PROV-001) → audio_slicing, not render_media first."""
        stage = route_minimal_stage("F-PROV-001", "fix_provenance")
        assert stage != "render_media"
        assert stage in ("audio_slicing", "production_db")

    def test_static_graphic_hold_no_provider(self):
        """Static graphic hold (F-GFX-001) → graphics_compositing, no provider video."""
        stage = route_minimal_stage("F-GFX-001", "re_plan")
        assert stage != "render_media"
        assert stage == "graphics_compositing"
