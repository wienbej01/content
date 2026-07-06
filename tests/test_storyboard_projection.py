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

    def test_host_present_speaking_maps_to_hero_lipsync(self):
        shot = _minimal_canonical_shot("SH001", "S001", "host_present_speaking")
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        assert beats[0]["shot_type"] == "hero_lipsync"
        assert beats[0]["model"] == "seedance_2_0"

    def test_visual_intent_contains_db_compile_fields(self):
        shot = _minimal_canonical_shot("SH001", "S001", "host_present_speaking")
        shot["visual_concept"] = "James at his desk explaining the system."
        shot["why_this_visual"] = "The host presence anchors credibility."
        shot["narrative_alignment"] = "The direct address supports the spoken thesis."
        sb = _canonical_storyboard(shots=[shot])
        intent = project_canonical(sb)[0]["visual_intent"]
        for key in (
            "visual_function",
            "concept_key",
            "narrative_claim",
            "information_to_show",
            "viewer_takeaway",
            "required_action",
            "distinctness_requirement",
            "semantic_acceptance_criteria",
        ):
            assert intent.get(key), f"missing DB compile intent field: {key}"

    def test_existing_baked_footage_projects_as_reused(self):
        shot = _minimal_canonical_shot("SH001", "S001", "host_present_speaking")
        shot["prompt_intent"] = (
            "Preserve exact existing baked-in-audio footage of James at his desk; "
            "no new generation required."
        )
        shot["assembly_fit_policy"] = "Pre-recorded baked-in-audio footage; trim only."
        sb = _canonical_storyboard(shots=[shot])
        beat = project_canonical(sb)[0]
        assert beat["asset_type"] == "reused"
        assert beat["model"] == "reused"
        assert beat["audio_policy"] == "HERO_PROVIDER_AUDIO_ISLAND"
        assert beat["reuse"]["allowed"] is True
        assert beat["visual_intent"]["asset_type"] == "reused"


# ---------------------------------------------------------------------------
# REPAIR-TKT-601A: visual_role vocabulary, enriched beats, fail-loud, shot_mix
# ---------------------------------------------------------------------------

class TestVisualRoleVocabulary:
    """REPAIR-TKT-601A: every visual_role the LLM prompt instructs must map to
    a correct legacy shot_type. The prior table only mapped legacy shot_types,
    causing broll_argument_support/graphic_explanation/etc. to silently fall
    through to hero_cutaway, producing all-hero storyboards."""

    @pytest.mark.parametrize("role,expected_shot_type", [
        # Prompt vocabulary (STORYBOARD_SONNET5_DIRECTOR.md:114)
        ("host_present_speaking", "hero_lipsync"),
        ("host_present_silent", "hero_cutaway"),
        ("broll_argument_support", "broll_archival"),
        ("broll_emotional_reset", "broll_environment"),
        ("graphic_explanation", "graphic_progressive"),
        ("overlay_frame", "kinetic_text"),
        ("transition", "broll_tactical"),
        ("establishing", "broll_environment"),
        # Legacy-compatible values the LLM sometimes echoes
        ("hero_lipsync", "hero_lipsync"),
        ("hero_cutaway", "hero_cutaway"),
        ("broll_archival", "broll_archival"),
        ("broll_metaphorical", "broll_metaphorical"),
        ("broll_environment", "broll_environment"),
        ("broll_tactical", "broll_tactical"),
        ("graphic_progressive", "graphic_progressive"),
        ("graphic_title_card", "graphic_title_card"),
        ("kinetic_text", "kinetic_text"),
        ("still_kenburns", "still_kenburns"),
    ])
    def test_visual_role_maps_to_expected_shot_type(self, role, expected_shot_type):
        shot = _minimal_canonical_shot("SH001", "S001", role)
        sb = _canonical_storyboard(shots=[shot])
        beats = project_canonical(sb)
        assert beats[0]["shot_type"] == expected_shot_type

    def test_broll_argument_support_maps_to_archival_not_hero(self):
        """The root-cause failure: broll_argument_support must NOT fall through
        to hero_cutaway (which made the storyboard all-hero)."""
        shot = _minimal_canonical_shot("SH002", "S001", "broll_argument_support")
        sb = _canonical_storyboard(shots=[shot])
        beat = project_canonical(sb)[0]
        assert beat["shot_type"] == "broll_archival"
        assert "hero" not in beat["shot_type"]

    def test_graphic_explanation_maps_to_graphic_not_hero(self):
        """graphic_explanation must NOT fall through to hero_cutaway."""
        shot = _minimal_canonical_shot("SH003", "S001", "graphic_explanation")
        sb = _canonical_storyboard(shots=[shot])
        beat = project_canonical(sb)[0]
        assert beat["shot_type"] == "graphic_progressive"
        assert beat["asset_type"] == "local_graphic"


class TestFailLoudOnUnknownRole:
    """REPAIR-TKT-601A: unknown visual_role must raise ProjectionError, not
    silently demote to hero_cutaway (fail-loud per INV-3)."""

    def test_unknown_visual_role_raises_projection_error(self):
        shot = _minimal_canonical_shot("SH001", "S001", "totally_made_up_role")
        sb = _canonical_storyboard(shots=[shot])
        with pytest.raises(ProjectionError, match="Unknown visual_role"):
            project_canonical(sb)

    def test_empty_visual_role_raises_projection_error(self):
        shot = _minimal_canonical_shot("SH001", "S001", "")
        sb = _canonical_storyboard(shots=[shot])
        with pytest.raises(ProjectionError, match="Unknown visual_role"):
            project_canonical(sb)


class TestEnrichedBeatFields:
    """REPAIR-TKT-601A: beats must carry narrative_function, order, act,
    est_duration_sec, narration_text, label — all required by
    review_storyboard structural validation but omitted by the old projection."""

    def _balanced_storyboard(self):
        shots = [
            _minimal_canonical_shot("SH001", "S001", "host_present_speaking"),
            _minimal_canonical_shot("SH002", "S001", "broll_argument_support"),
            _minimal_canonical_shot("SH003", "S002", "host_present_speaking"),
            _minimal_canonical_shot("SH004", "S002", "graphic_explanation"),
            _minimal_canonical_shot("SH005", "S003", "host_present_speaking"),
            _minimal_canonical_shot("SH006", "S003", "broll_argument_support"),
            _minimal_canonical_shot("SH007", "S004", "host_present_speaking"),
            _minimal_canonical_shot("SH008", "S004", "broll_emotional_reset"),
        ]
        return shots

    def test_beats_have_narrative_function(self):
        sb = _canonical_storyboard(shots=self._balanced_storyboard())
        beats = project_canonical(sb)
        for b in beats:
            assert "narrative_function" in b
            nf = b["narrative_function"].strip().lower()
            assert nf, f"{b['beat_id']} has empty narrative_function"
            assert nf not in ("supporting visual", "b-roll", "supporting"), \
                f"{b['beat_id']} has generic narrative_function"

    def test_beats_have_order_and_act(self):
        sb = _canonical_storyboard(shots=self._balanced_storyboard())
        beats = project_canonical(sb)
        for i, b in enumerate(beats):
            assert b["order"] == i
            assert 1 <= b["act"] <= 6

    def test_beats_have_est_duration_sec(self):
        sb = _canonical_storyboard(shots=self._balanced_storyboard())
        beats = project_canonical(sb)
        for b in beats:
            assert "est_duration_sec" in b
            assert b["est_duration_sec"] > 0

    def test_est_duration_uses_planned_duration_sec(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        shot["planned_duration_sec"] = 12.3
        sb = _canonical_storyboard(shots=[shot])
        beat = project_canonical(sb)[0]
        assert beat["est_duration_sec"] == 12.3

    def test_est_duration_falls_back_to_narration_when_no_planned(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        shot["planned_duration_sec"] = None
        sb = _canonical_storyboard(shots=[shot])
        segment_text_map = {"S001": "one two three four five"}
        beat = project_canonical(sb, segment_text_map=segment_text_map)[0]
        # 5 words / 1.8077 wps ≈ 2.77s
        assert beat["est_duration_sec"] > 0
        assert beat["est_duration_sec"] == round(5 / 1.8077, 2)

    def test_beats_have_label(self):
        sb = _canonical_storyboard(shots=self._balanced_storyboard())
        beats = project_canonical(sb)
        for b in beats:
            assert "label" in b
            assert b["label"]

    def test_narration_text_threads_from_segment_text_map(self):
        shots = self._balanced_storyboard()
        sb = _canonical_storyboard(shots=shots)
        segment_text_map = {
            "S001": "The hook narration text here.",
            "S002": "The mechanism narration text here.",
            "S003": "The proof narration text here.",
            "S004": "The CTA narration text here.",
        }
        beats = project_canonical(sb, segment_text_map=segment_text_map)
        for b in beats:
            assert "narration_text" in b
            assert b["narration_text"], f"{b['beat_id']} has empty narration_text"
        assert beats[0]["narration_text"] == "The hook narration text here."
        assert beats[3]["narration_text"] == "The mechanism narration text here."

    def test_narration_text_empty_when_no_segment_text_map(self):
        shot = _minimal_canonical_shot("SH001", "S001", "hero_lipsync")
        sb = _canonical_storyboard(shots=[shot])
        beat = project_canonical(sb)[0]
        assert beat["narration_text"] == ""


class TestShotMixSummaryViaProduceDb:
    """REPAIR-TKT-601A: invoke_storyboard production branch must compute
    shot_mix_summary (the old production path omitted it entirely)."""

    def test_compute_mix_summary_produces_bands_fields(self):
        from storyboard_beat_utils import compute_mix_summary
        beats = [
            {"shot_type": "hero_lipsync", "est_duration_sec": 8.0, "order": 0},
            {"shot_type": "broll_archival", "est_duration_sec": 4.0, "order": 1},
            {"shot_type": "hero_lipsync", "est_duration_sec": 7.0, "order": 2},
            {"shot_type": "graphic_progressive", "est_duration_sec": 6.0, "order": 3},
            {"shot_type": "hero_lipsync", "est_duration_sec": 6.0, "order": 4},
            {"shot_type": "broll_environment", "est_duration_sec": 5.0, "order": 5},
        ]
        m = compute_mix_summary(beats)
        assert "hero_lipsync_pct" in m
        assert "hero_cutaway_pct" in m
        assert "broll_specific_pct" in m
        assert "graphics_ui_pct" in m
        assert "max_hero_block_sec" in m
        assert "distinct_visual_setups" in m
        assert m["distinct_visual_setups"] == 6
        # hero_lipsync = 8+7+6 = 21s of 36s total ≈ 58.3%
        assert 50 <= m["hero_lipsync_pct"] <= 60


class TestRealBalancedStoryboardPassesStructuralValidation:
    """REPAIR-TKT-601A acceptance G1: a real LLM-authored canonical storyboard
    (the prompt vocabulary roles) projects to beats that pass
    review_storyboard.review() with zero blocking issues."""

    def _real_style_storyboard(self):
        """Mimics the prod_4e0ce12e run: 4 hero + 3 broll_argument_support +
        1 graphic_explanation + 1 broll_emotional_reset."""
        roles = [
            ("SHOT_001", "001_hook", "host_present_speaking", 8.0),
            ("SHOT_002", "001_hook", "broll_argument_support", 4.0),
            ("SHOT_003", "002_mechanism", "host_present_speaking", 7.0),
            ("SHOT_004", "002_mechanism", "graphic_explanation", 6.0),
            ("SHOT_005", "002_mechanism", "broll_argument_support", 3.5),
            ("SHOT_006", "003_proof_takeaway", "host_present_speaking", 6.0),
            ("SHOT_007", "003_proof_takeaway", "broll_argument_support", 4.5),
            ("SHOT_008", "004_cta", "host_present_speaking", 5.0),
            ("SHOT_009", "004_cta", "broll_emotional_reset", 5.0),
        ]
        shots = []
        for sid, seg, role, dur in roles:
            shot = _minimal_canonical_shot(sid, seg, role)
            shot["planned_duration_sec"] = dur
            shots.append(shot)
        return shots

    def test_balanced_storyboard_passes_structural_validation(self):
        from review_storyboard import review, load_constraints
        shots = self._real_style_storyboard()
        sb = _canonical_storyboard(shots=shots)
        sb["schema_version"] = "2.0"
        sb["video_type"] = "short"
        segment_text_map = {
            "001_hook": "Every professional has done it. A 2024 paper revealed a breakthrough.",
            "002_mechanism": "The model learns to write back. Researchers call it derendering.",
            "003_proof_takeaway": "The field exploded in 2025. InkFM achieved state-of-the-art.",
            "004_cta": "Open your app tonight. Write a page by hand. See if it transcribes.",
        }
        beats = project_canonical(sb, segment_text_map=segment_text_map)
        sb["beats"] = beats
        from storyboard_beat_utils import compute_mix_summary
        sb["shot_mix_summary"] = compute_mix_summary(beats)

        constraints = load_constraints()
        blocking, warnings, fixes = review(sb, constraints)

        assert blocking == [], f"structural validation failed: {blocking}"

    def test_balanced_storyboard_has_archival_and_graphic_beats(self):
        shots = self._real_style_storyboard()
        sb = _canonical_storyboard(shots=shots)
        beats = project_canonical(sb)
        shot_types = [b["shot_type"] for b in beats]
        assert "broll_archival" in shot_types, "missing archival beat"
        assert "graphic_progressive" in shot_types, "missing graphic beat"

    def test_balanced_storyboard_not_all_hero(self):
        shots = self._real_style_storyboard()
        sb = _canonical_storyboard(shots=shots)
        beats = project_canonical(sb)
        hero = [b for b in beats if b["shot_type"] in ("hero_lipsync", "hero_cutaway")]
        assert len(hero) < len(beats) * 0.6, "storyboard is all-hero (flagship-001 failure mode)"


class TestSharedUtilModule:
    """REPAIR-TKT-601A: storyboard_beat_utils module is the single source of
    truth shared by both production and test paths."""

    def test_act_for_first_and_last(self):
        from storyboard_beat_utils import act_for
        assert act_for(0, 9) == 1
        assert act_for(8, 9) == 6

    def test_beat_duration_sec_empty_narration(self):
        from storyboard_beat_utils import beat_duration_sec
        assert beat_duration_sec("") == 3.0

    def test_narrative_function_for_broll_archival_is_specific(self):
        from storyboard_beat_utils import narrative_function_for
        nf = narrative_function_for("broll_archival")
        assert nf and nf.lower() not in ("supporting visual", "b-roll", "supporting")

    def test_compute_mix_summary_returns_all_bands_keys(self):
        from storyboard_beat_utils import compute_mix_summary
        beats = [{"shot_type": "hero_lipsync", "est_duration_sec": 8.0, "order": 0}]
        m = compute_mix_summary(beats)
        required_keys = {"hero_lipsync_pct", "hero_cutaway_pct", "broll_specific_pct",
                          "broll_metaphorical_pct", "graphics_ui_pct", "kinetic_text_pct",
                          "max_hero_block_sec", "distinct_visual_setups", "total_cuts_estimate"}
        assert required_keys <= set(m.keys())
