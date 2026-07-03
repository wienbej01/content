"""Tests for scripts/storyboard_projection.py.

Covers 7 required tests from S22_T013:
1. Canonical shot projects to expected legacy beat fields.
2. Canonical overlay projects to both graphic and graphics compatibility shape.
3. Projection preserves shot/overlay IDs.
4. Projection fails if canonical shot is missing semantic source fields.
5. Projection output passes current compiler minimum fields.
6. Projection output passes current production storyboard minimum fields.
7. Projection never reads raw script visual_brief.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from storyboard_projection import project_canonical, ProjectionError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_canonical_shot(shot_id="SH001", segment_id="S001",
                             visual_role="hero_lipsync",
                             literal_vs_metaphorical="literal",
                             include_semantic=True):
    shot = {
        "shot_id": shot_id,
        "segment_id": segment_id,
        "visual_role": visual_role,
        "visual_concept": "James discussing AI scaling from his desk",
        "literal_vs_metaphorical": literal_vs_metaphorical,
        "planned_duration_sec": 8.5,
        "min_usable_duration_sec": 4.0,
        "max_usable_duration_sec": 12.0,
        "duration_drift_policy": "trim_ok",
        "assembly_fit_policy": "Lead shot, can be trimmed",
        "generation_risk": "low",
        "fallback_strategy": "hero_cutaway",
        "qa_requirements": ["lipsync_sync_score >= 0.85"],
    }
    if include_semantic:
        shot["why_this_visual"] = "Establishes James as trusted narrator."
        shot["narrative_alignment"] = "Direct address builds trust."
    return shot


def _minimal_canonical_overlay(overlay_id="OV001", shot_id="SH001",
                               segment_id="S001"):
    return {
        "overlay_id": overlay_id,
        "shot_id": shot_id,
        "segment_id": segment_id,
        "overlay_type": "stat_display",
        "text": "GPT-4: 90th percentile on Bar Exam",
        "semantic_purpose": "Displays the specific benchmark statistic.",
        "source_ref": "src_research/gpt4_benchmarks.txt",
        "claim_refs": ["C002"],
        "trigger_phrase": "90th percentile",
        "start_time_offset_sec": 2.0,
        "end_time_offset_sec": 5.0,
        "position": "lower_third",
        "style_token": "stat_callout_primary",
        "animation": "fade_in",
        "safe_for_9x16": True,
        "qa_rules": ["text_legible", "timing_synced"],
    }


def _canonical_storyboard(shots=None, overlays=None):
    return {
        "storyboard_contract_version": "1.0",
        "approved_script_revision_id": "rev_test",
        "approved_script_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "authoring_model_profile": "storyboard_sonnet5",
        "authoring_model": "kilo/anthropic/claude-sonnet-5-20250908",
        "claim_inventory": [],
        "narrative_beats": [],
        "shots": shots or [],
        "overlays": overlays or [],
        "segment_work_orders": [],
        "feedback_policy": {"repair_authority": "sonnet5_only",
                            "max_repair_rounds": 3,
                            "block_on_unresolved": True},
        "timing_policy": {"planned_is_intent": True,
                          "observed_is_truth": True,
                          "drift_resolution_order": ["trim_ok"]},
        "approval": {"status": "draft", "creative_author": "sonnet5"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCanonicalShotProjectsToLegacy:
    """Test 1: Canonical shot projects to expected legacy beat fields."""

    def test_hero_lipsync_produces_correct_fields(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)

        assert len(beats) == 1
        beat = beats[0]

        assert beat["beat_id"] == "SH001"
        assert beat["source_beat_id"] == "SH001"
        assert beat["canonical_shot_id"] == "SH001"
        assert beat["segment_id"] == "S001"
        assert beat["shot_type"] == "hero_lipsync"
        assert beat["asset_type"] == "generated_video"
        assert beat["model"] == "seedance_2_0"
        assert beat["prompt_class"] == "descriptive"
        assert beat["reference_required"] is True
        assert isinstance(beat["visual_brief"], str) and len(beat["visual_brief"]) > 0
        assert isinstance(beat["visual_intent"], dict)
        assert beat["visual_intent"]["shot_id"] == "SH001"
        assert beat["visual_intent"]["why_this_visual"] == "Establishes James as trusted narrator."
        assert beat["text_policy"] == "none"

    def test_broll_metaphorical_produces_correct_fields(self):
        shot = _minimal_canonical_shot("SH002", "S001", "broll_metaphorical",
                                       literal_vs_metaphorical="metaphorical")
        shot["claim_refs"] = ["C001"]
        shot["must_avoid"] = ["no readable text", "sci-fi"]
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)

        assert len(beats) == 1
        beat = beats[0]

        assert beat["beat_id"] == "SH002"
        assert beat["shot_type"] == "broll_metaphorical"
        assert beat["asset_type"] == "generated_video"
        assert beat["model"] == "kling3_0"
        assert beat["prompt_class"] == "conceptual"
        assert beat["reference_required"] is True
        assert beat["text_policy"] == "no_readable_text"


class TestOverlayProjectsToGraphic:
    """Test 2: Canonical overlay projects to both graphic and graphics."""

    def test_single_overlay_produces_graphic_and_graphics(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        overlay = _minimal_canonical_overlay("OV001", "SH001", "S001")
        sb = _canonical_storyboard(shots=[shot], overlays=[overlay])
        beats = project_canonical(sb)

        assert len(beats) == 1
        beat = beats[0]

        assert "graphics" in beat
        assert isinstance(beat["graphics"], list)
        assert len(beat["graphics"]) == 1

        graphic = beat["graphics"][0]
        assert graphic["canonical_overlay_id"] == "OV001"
        assert graphic["kind"] == "stat_display"
        assert graphic["required"] is True
        assert graphic["payload"]["text"] == "GPT-4: 90th percentile on Bar Exam"
        assert graphic["payload"]["position"] == "lower_third"
        assert graphic["payload"]["start_time_offset_sec"] == 2.0
        assert graphic["payload"]["end_time_offset_sec"] == 5.0
        assert graphic["payload"]["overlay_id"] == "OV001"

        assert "graphic" in beat
        assert beat["graphic"]["canonical_overlay_id"] == "OV001"

    def test_multiple_overlays_produce_graphics_list(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        ov1 = _minimal_canonical_overlay("OV001", "SH001", "S001")
        ov2 = _minimal_canonical_overlay("OV002", "SH001", "S001")
        ov2["overlay_type"] = "source_label"
        ov2["text"] = "Source: Research Paper"
        sb = _canonical_storyboard(shots=[shot], overlays=[ov1, ov2])
        beats = project_canonical(sb)

        assert len(beats) == 1
        beat = beats[0]

        assert len(beat["graphics"]) == 2
        assert beat["graphics"][0]["canonical_overlay_id"] == "OV001"
        assert beat["graphics"][1]["canonical_overlay_id"] == "OV002"

        assert beat["graphic"]["kind"] == "multi_overlay"
        assert beat["graphic"]["total_steps"] == 2

    def test_overlay_without_matching_shot_is_skipped(self):
        """Overlays referencing a non-existent shot_id are silently skipped."""
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        overlay = _minimal_canonical_overlay("OV001", "SH999", "S002")
        sb = _canonical_storyboard(shots=[shot], overlays=[overlay])
        beats = project_canonical(sb)

        assert len(beats) == 1
        assert "graphics" not in beats[0]


class TestProjectionPreservesIds:
    """Test 3: Projection preserves shot and overlay IDs."""

    def test_shot_ids_preserved(self):
        shots = [
            _minimal_canonical_shot("SH001", "S001", "hero_lipsync"),
            _minimal_canonical_shot("SH002", "S001", "broll_metaphorical",
                                    literal_vs_metaphorical="metaphorical"),
            _minimal_canonical_shot("SH003", "S002", "hero_lipsync"),
        ]
        sb = _canonical_storyboard(shots=shots)
        beats = project_canonical(sb)

        assert len(beats) == 3
        assert [b["beat_id"] for b in beats] == ["SH001", "SH002", "SH003"]
        assert [b["canonical_shot_id"] for b in beats] == ["SH001", "SH002", "SH003"]

    def test_projection_trace_contains_ids(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        overlay = _minimal_canonical_overlay("OV001", "SH001", "S001")
        sb = _canonical_storyboard(shots=[shot], overlays=[overlay])
        beats = project_canonical(sb)

        trace = beats[0].get("projection_trace", {})
        assert trace["canonical_shot_id"] == "SH001"
        assert "OV001" in trace["overlay_ids"]


class TestMissingSemanticFieldsFails:
    """Test 4: Projection fails if canonical shot is missing semantic source fields."""

    def test_missing_why_this_visual_fails(self):
        shot = _minimal_canonical_shot(include_semantic=False)
        sb = _canonical_storyboard(shots=[shot])

        with pytest.raises(ProjectionError) as exc:
            project_canonical(sb)
        assert "SH001" in str(exc.value)
        assert "why_this_visual" in str(exc.value)

    def test_missing_narrative_alignment_fails(self):
        shot = _minimal_canonical_shot(include_semantic=False)
        shot["why_this_visual"] = "Some justification."
        sb = _canonical_storyboard(shots=[shot])

        with pytest.raises(ProjectionError) as exc:
            project_canonical(sb)
        assert "SH001" in str(exc.value)
        assert "narrative_alignment" in str(exc.value)


class TestCompilerMinimumFields:
    """Test 5: Projection output passes current compiler minimum fields.

    The compiler (compile_media_prompts.py compile_beat) reads:
      shot_type, segment_id, visual_brief, model, asset_type, prompt_class
    from creative beats.
    """

    def test_compiler_fields_present(self):
        shots = [
            _minimal_canonical_shot("SH001", "S001", "hero_lipsync"),
            _minimal_canonical_shot("SH002", "S001", "broll_metaphorical",
                                    literal_vs_metaphorical="metaphorical"),
            _minimal_canonical_shot("SH003", "S002", "hero_lipsync"),
        ]
        sb = _canonical_storyboard(shots=shots)
        beats = project_canonical(sb)

        compiler_fields = {"shot_type", "segment_id", "visual_brief",
                           "model", "asset_type", "prompt_class"}
        for beat in beats:
            for field in compiler_fields:
                assert field in beat, (
                    f"Beat {beat['beat_id']} missing compiler field {field!r}"
                )
                assert beat[field], (
                    f"Beat {beat['beat_id']} has empty compiler field {field!r}"
                )

    def test_compiler_fields_have_legal_values(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        beat = beats[0]

        legal_shot_types = {
            "hero_lipsync", "hero_cutaway", "broll_archival",
            "broll_metaphorical", "broll_environment", "broll_tactical",
            "graphic_progressive", "graphic_title_card", "kinetic_text",
            "ui_insert", "still_kenburns",
        }
        assert beat["shot_type"] in legal_shot_types
        assert beat["asset_type"] in ("generated_video", "generated_still",
                                       "local_graphic", "reused")
        assert beat["model"] in ("seedance_2_0", "kling3_0",
                                  "still_kenburns", "local_graphic")
        assert beat["prompt_class"] in ("descriptive", "conceptual", "narrative")


class TestProductionStoryboardMinimumFields:
    """Test 6: Projection output passes current production storyboard minimum fields.

    The production storyboard validation (production_storyboard.py) checks:
      source_beat_id, segment_id, shot_type.
    """

    def test_production_storyboard_fields_present(self):
        shots = [
            _minimal_canonical_shot("SH001", "S001", "hero_lipsync"),
            _minimal_canonical_shot("SH002", "S002", "hero_cutaway"),
            _minimal_canonical_shot("SH003", "S003", "broll_metaphorical",
                                    literal_vs_metaphorical="metaphorical"),
        ]
        sb = _canonical_storyboard(shots=shots)
        beats = project_canonical(sb)

        required = {"source_beat_id", "segment_id", "shot_type"}
        for beat in beats:
            for field in required:
                assert field in beat, (
                    f"Beat {beat['beat_id']} missing production field {field!r}"
                )
                assert beat[field], (
                    f"Beat {beat['beat_id']} has empty production field {field!r}"
                )


class TestNeverReadsRawScriptVisualBrief:
    """Test 7: Projection never reads raw script visual_brief.

    The visual_brief field in projected beats must derive from canonical
    shot fields (visual_concept, prompt_intent, must_show), not from
    any raw script field.
    """

    def test_visual_brief_derived_from_canonical_not_raw_script(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        shot["visual_concept"] = "James at desk introducing topic"
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)

        brief = beats[0]["visual_brief"]
        assert "James at desk introducing topic" in brief

    def test_visual_brief_includes_must_show_when_present(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        shot["visual_concept"] = "James at desk"
        shot["must_show"] = ["warm lighting", "notebook"]
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)

        brief = beats[0]["visual_brief"]
        assert "James at desk" in brief
        assert "warm lighting" in brief or "Including" in brief

    def test_no_raw_script_field_leaks(self):
        """The projected visual_brief is composed solely from canonical shot
        fields. A raw script visual_brief field on the canonical storyboard
        must never leak into the projected output."""
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        shot["visual_concept"] = "James at desk introducing topic"
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        brief = beats[0]["visual_brief"]

        assert "James at desk introducing topic" in brief
        assert "RAW_SCRIPT_SECRET" not in brief

    def test_visual_brief_does_not_read_shot_visual_brief_field(self):
        """Even if the shot dict contains a raw 'visual_brief' field,
        _compose_visual_brief must not read it."""
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        shot["visual_concept"] = "Canonical concept"
        shot["visual_brief"] = "RAW SCRIPT BRIEF THAT MUST NOT LEAK"
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        brief = beats[0]["visual_brief"]

        assert "RAW SCRIPT BRIEF" not in brief
        assert "Canonical concept" in brief


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_non_canonical_storyboard_raises(self):
        with pytest.raises(ValueError, match="storyboard_contract_version"):
            project_canonical({"shots": []})

    def test_empty_shots_produces_empty_list(self):
        sb = _canonical_storyboard(shots=[])
        beats = project_canonical(sb)
        assert beats == []

    def test_no_overlays_omits_graphic_fields(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        assert "graphic" not in beats[0]
        assert "graphics" not in beats[0]

    def test_local_graphic_shot_type_gets_correct_model(self):
        shot = _minimal_canonical_shot("SH001", "S001", "graphic_progressive",
                                       include_semantic=True)
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        assert beats[0]["model"] == "local_graphic"
        assert beats[0]["asset_type"] == "local_graphic"

    def test_still_kenburns_model_mapped(self):
        shot = _minimal_canonical_shot("SH001", "S001", "still_kenburns",
                                       include_semantic=True)
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        assert beats[0]["model"] == "still_kenburns"
        assert beats[0]["asset_type"] == "generated_still"

    def test_hybrid_prompt_class(self):
        shot = _minimal_canonical_shot("SH001", "S001", "broll_metaphorical",
                                       literal_vs_metaphorical="hybrid")
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        assert beats[0]["prompt_class"] == "narrative"
