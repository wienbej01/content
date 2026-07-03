#!/usr/bin/env python3
"""tests/test_storyboard_sonnet_repair_loop.py — S22_T010: Bounded Sonnet repair loop tests.

Tests 8 required scenarios:
  1. Stub repair fixes missing semantic_purpose.
  2. Stub repair fixes generic B-roll alignment.
  3. Repair attempt that changes narration fails.
  4. Repair attempt that rewrites unaffected segment fails.
  5. Repair using non-Sonnet profile fails.
  6. Invalid repair after max attempts fails BLOCKED_REPAIR_EXHAUSTED.
  7. Repair log includes affected IDs and changed fields.
  8. Dry-run produces prompt without invoking Kilo.

All tests use stub LLM functions. No real LLM calls, no paid APIs.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from repair_storyboard_v2 import (
    repair_canonical_storyboard,
    extract_affected_entities,
    extract_adjacent_entities,
    build_repair_prompt,
    validate_narration_immutability,
    validate_unaffected_preserved,
    compute_changed_fields,
    apply_repair,
    parse_stub_repair_response,
    BLOCKED_REPAIR_EXHAUSTED,
    BLOCKED_NARRATION_MUTATION,
    BLOCKED_UNAFFECTED_REWRITE,
    BLOCKED_NON_SONNET,
    BLOCKED_SONNET_UNAVAILABLE,
)


def _base_canonical_sb():
    return {
        "storyboard_contract_version": "1.0",
        "approved_script_revision_id": "rev_test_001",
        "approved_script_sha256": "e" * 64,
        "authoring_model_profile": "storyboard_sonnet5",
        "authoring_model": "kilo/anthropic/claude-sonnet-5-20250908",
        "claim_inventory": [
            {
                "claim_id": "C001",
                "claim_text": "AI models can exhibit unexpected capabilities at scale.",
                "claim_type": "narrative_premise",
                "source_refs": ["src_test"],
                "segment_ids": ["S001"],
                "visual_obligation": "must_show",
                "strength": "confirmed",
            }
        ],
        "narrative_beats": [
            {
                "beat_id": "NB001",
                "segment_id": "S001",
                "act": 1,
                "order": 1,
                "narration_text": "AI is transforming how we think about intelligence.",
                "narrative_function": "hook",
                "visual_function": "establishes",
                "viewer_question": "What is AI intelligence?",
                "retention_role": "curiosity_open",
                "source_claim_refs": ["C001"],
                "shot_ids": ["SH001", "SH002"],
                "overlay_ids": [],
                "must_avoid": ["sci-fi"],
            }
        ],
        "shots": [
            {
                "shot_id": "SH001",
                "segment_id": "S001",
                "visual_role": "hero_lipsync",
                "visual_concept": "James introducing the topic",
                "why_this_visual": "Establishes James as the trusted narrator introducing the AI topic.",
                "narrative_alignment": "Direct host address builds trust before presenting technical claims.",
                "claim_refs": ["C001"],
                "literal_vs_metaphorical": "literal",
                "must_show": ["James at desk"],
                "must_avoid": [],
                "planned_duration_sec": 8.5,
                "min_usable_duration_sec": 4.0,
                "max_usable_duration_sec": 12.0,
                "duration_drift_policy": "trim_ok",
                "assembly_fit_policy": "Lead shot, can be trimmed.",
                "generation_risk": "low",
                "fallback_strategy": "hero_cutaway",
                "qa_requirements": ["lipsync_score >= 0.85"],
            },
            {
                "shot_id": "SH002",
                "segment_id": "S001",
                "visual_role": "broll_metaphorical",
                "visual_concept": "Neural network visualization growing connections",
                "why_this_visual": "Helps viewers visualize scaling AI through growing network complexity.",
                "narrative_alignment": "Abstract neural connections support the claim about AI exhibiting unexpected capabilities.",
                "claim_refs": ["C001"],
                "literal_vs_metaphorical": "metaphorical",
                "must_show": ["network nodes"],
                "must_avoid": [],
                "planned_duration_sec": 5.0,
                "min_usable_duration_sec": 3.0,
                "max_usable_duration_sec": 6.5,
                "duration_drift_policy": "trim_ok",
                "assembly_fit_policy": "Trim to fit.",
                "generation_risk": "medium",
                "fallback_strategy": "still_kenburns_if_generation_fails",
                "qa_requirements": ["no_readable_text"],
            },
        ],
        "overlays": [
            {
                "overlay_id": "OV001",
                "segment_id": "S001",
                "shot_id": "SH001",
                "overlay_type": "stat_display",
                "text": "GPT-4: 90th percentile on Bar Exam",
                "semantic_purpose": "",
                "source_ref": "",
                "claim_refs": [],
                "trigger_phrase": "90th percentile",
                "start_time_offset_sec": 2.0,
                "end_time_offset_sec": 5.0,
                "position": "lower_third",
                "style_token": "stat_callout_primary",
                "animation": "fade_in",
                "safe_for_9x16": True,
                "qa_rules": ["text_legible"],
            }
        ],
        "segment_work_orders": [
            {
                "segment_id": "S001",
                "narration_text_exact": "AI is transforming how we think about intelligence.",
                "argument_summary": "Opening claim about AI and intelligence.",
                "viewer_question": "How is AI changing intelligence?",
                "retention_role": "hook_curiosity",
                "source_claim_refs": ["C001"],
                "shot_ids": ["SH001", "SH002"],
                "overlay_ids": ["OV001"],
                "broll_alignment_instruction": "B-roll shows abstract network growth.",
                "graphic_alignment_instruction": "No graphics for opening.",
                "conclusion_alignment_instruction": "N/A",
                "qa_acceptance_criteria": ["James confirmed", "B-roll not generic"],
                "must_avoid": ["sci-fi"],
            }
        ],
        "feedback_policy": {
            "repair_authority": "sonnet5_only",
            "max_repair_rounds": 3,
            "block_on_unresolved": True,
            "stale_on_repair": ["storyboard_creative_review", "compile_media"],
        },
        "timing_policy": {
            "planned_is_intent": True,
            "observed_is_truth": True,
            "drift_resolution_order": ["trim_ok", "pad_ok"],
            "default_policy": "trim_ok",
            "max_total_drift_pct": 15,
        },
        "approval": {
            "status": "draft",
            "approved_by": None,
            "approved_at": None,
            "creative_author": "kilo/anthropic/claude-sonnet-5-20250908",
        },
    }


def _stub_sonnet5_repair(data):
    def _fn(prompt):
        return (copy.deepcopy(data), json.dumps(data), "storyboard_director_sonnet5",
                "kilo/anthropic/claude-sonnet-5-20250908")
    return _fn


class TestRepairFixesMissingSemanticPurpose:
    def test_repair_fixes_missing_semantic_purpose(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "overlays[0].semantic_purpose",
                "entity_id": "OV001",
                "severity": "BLOCKER",
                "message": "BLOCKED_PURPOSELESS_OVERLAY: overlay 'OV001' missing semantic_purpose.",
            }
        ]

        repair_data = {
            "repair_metadata": {
                "errors_addressed": ["MISSING_SEMANTIC_PURPOSE"],
                "repair_round": 1,
                "max_repair_rounds": 2,
            },
            "repair_summary": [
                {
                    "entity_id": "OV001",
                    "entity_type": "overlay",
                    "changed_fields": ["semantic_purpose"],
                    "reason": "Missing semantic purpose for overlay.",
                    "before_value": "",
                    "after_value": "Displays GPT-4 benchmark statistic supporting the AI capability claim.",
                }
            ],
            "repaired_entities": {
                "overlays": [
                    {
                        "overlay_id": "OV001",
                        "segment_id": "S001",
                        "shot_id": "SH001",
                        "overlay_type": "stat_display",
                        "text": "GPT-4: 90th percentile on Bar Exam",
                        "semantic_purpose": "Displays GPT-4 benchmark statistic supporting the AI capability claim.",
                        "source_ref": "src_test",
                        "claim_refs": ["C001"],
                        "trigger_phrase": "90th percentile",
                        "start_time_offset_sec": 2.0,
                        "end_time_offset_sec": 5.0,
                        "position": "lower_third",
                        "style_token": "stat_callout_primary",
                        "animation": "fade_in",
                        "safe_for_9x16": True,
                        "qa_rules": ["text_legible"],
                    }
                ]
            },
        }

        llm_fn = _stub_sonnet5_repair(repair_data)
        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["OV001"],
            max_attempts=2,
            llm_fn=llm_fn,
        )

        assert result["status"] == "SUCCESS", f"Expected SUCCESS, got {result['status']}: {result.get('message', '')}"
        overlay = result["storyboard"]["overlays"][0]
        assert overlay["semantic_purpose"] == "Displays GPT-4 benchmark statistic supporting the AI capability claim."
        assert len(result["repair_log"]) >= 1
        assert result["repair_log"][0]["status"] == "REPAIR_ATTEMPTED"


class TestRepairFixesGenericBroll:
    def test_repair_fixes_generic_broll_alignment(self):
        sb = _base_canonical_sb()
        sb["shots"][1]["visual_concept"] = "business people in office"
        sb["shots"][1]["narrative_alignment"] = "Shows people working professionally."

        validation_errors = [
            {
                "path": "shots[1].visual_concept",
                "entity_id": "SH002",
                "severity": "BLOCKER",
                "message": "BLOCKED_GENERIC_BROLL: generic B-roll 'business people' detected.",
            }
        ]

        repair_data = {
            "repair_metadata": {"errors_addressed": ["GENERIC_BROLL"], "repair_round": 1, "max_repair_rounds": 2},
            "repair_summary": [
                {
                    "entity_id": "SH002",
                    "entity_type": "shot",
                    "changed_fields": ["visual_concept", "narrative_alignment"],
                    "reason": "Generic B-roll phrase 'business people' replaced with specific concept.",
                    "before_value": "business people in office",
                    "after_value": "Neural network visualization with growing connections",
                }
            ],
            "repaired_entities": {
                "shots": [
                    {
                        "shot_id": "SH002",
                        "segment_id": "S001",
                        "visual_role": "broll_metaphorical",
                        "visual_concept": "Neural network visualization with growing connections",
                        "why_this_visual": "Helps viewers visualize scaling AI through network complexity.",
                        "narrative_alignment": "Abstract neural connections support the claim about AI exhibiting unexpected capabilities.",
                        "claim_refs": ["C001"],
                        "literal_vs_metaphorical": "metaphorical",
                        "must_show": ["network nodes"],
                        "must_avoid": [],
                        "planned_duration_sec": 5.0,
                        "min_usable_duration_sec": 3.0,
                        "max_usable_duration_sec": 6.5,
                        "duration_drift_policy": "trim_ok",
                        "assembly_fit_policy": "Trim to fit.",
                        "generation_risk": "medium",
                        "fallback_strategy": "still_kenburns_if_generation_fails",
                        "qa_requirements": ["no_readable_text"],
                    }
                ]
            },
        }

        llm_fn = _stub_sonnet5_repair(repair_data)
        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["SH002"],
            max_attempts=2,
            llm_fn=llm_fn,
        )

        assert result["status"] == "SUCCESS"
        shot = result["storyboard"]["shots"][1]
        assert "business people" not in shot["visual_concept"].lower()
        assert "neural network" in shot["visual_concept"].lower()


class TestRepairNarrationMutation:
    def test_repair_changes_narration_fails(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "shots[0].visual_concept",
                "entity_id": "SH001",
                "severity": "BLOCKER",
                "message": "Test validation error.",
            }
        ]

        repair_data = {
            "repair_metadata": {"errors_addressed": ["TEST"], "repair_round": 1, "max_repair_rounds": 2},
            "repair_summary": [
                {
                    "entity_id": "NB001",
                    "entity_type": "narrative_beat",
                    "changed_fields": ["narration_text"],
                    "reason": "Changed narration.",
                    "before_value": "AI is transforming how we think about intelligence.",
                    "after_value": "AI is totally transforming how we think about intelligence.",
                }
            ],
            "repaired_entities": {
                "narrative_beats": [
                    {
                        "beat_id": "NB001",
                        "segment_id": "S001",
                        "act": 1,
                        "order": 1,
                        "narration_text": "AI is totally transforming how we think about intelligence.",
                        "narrative_function": "hook",
                        "visual_function": "establishes",
                        "viewer_question": "What is AI intelligence?",
                        "retention_role": "curiosity_open",
                        "source_claim_refs": ["C001"],
                        "shot_ids": ["SH001", "SH002"],
                        "overlay_ids": [],
                        "must_avoid": ["sci-fi"],
                    }
                ],
                "segment_work_orders": [
                    {
                        "segment_id": "S001",
                        "narration_text_exact": "AI is technically transforming how we think about intelligence.",
                        "argument_summary": "Opening claim.",
                        "viewer_question": "How is AI changing intelligence?",
                        "retention_role": "hook_curiosity",
                        "source_claim_refs": ["C001"],
                        "shot_ids": ["SH001", "SH002"],
                        "overlay_ids": ["OV001"],
                        "broll_alignment_instruction": "B-roll shows abstract network growth.",
                        "graphic_alignment_instruction": "No graphics.",
                        "conclusion_alignment_instruction": "N/A",
                        "qa_acceptance_criteria": ["James confirmed"],
                        "must_avoid": ["sci-fi"],
                    }
                ]
            },
        }

        llm_fn = _stub_sonnet5_repair(repair_data)
        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["SH001"],
            max_attempts=2,
            llm_fn=llm_fn,
        )

        assert result["status"] == "BLOCKED"
        assert result["error_code"] == BLOCKED_NARRATION_MUTATION
        assert any("NARRATION_MUTATION" in str(bc) for bc in result.get("block_chain", []))


class TestRepairRewritesUnaffected:
    def test_repair_rewrites_unaffected_segment_fails(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "shots[0].visual_concept",
                "entity_id": "SH001",
                "severity": "BLOCKER",
                "message": "Test validation error for SH001.",
            }
        ]

        repair_data = {
            "repair_metadata": {"errors_addressed": ["TEST"], "repair_round": 1, "max_repair_rounds": 2},
            "repair_summary": [
                {
                    "entity_id": "SH002",
                    "entity_type": "shot",
                    "changed_fields": ["visual_concept"],
                    "reason": "Changed unaffected shot.",
                    "before_value": "old value",
                    "after_value": "new value",
                }
            ],
            "repaired_entities": {
                "shots": [
                    {
                        "shot_id": "SH001",
                        "segment_id": "S001",
                        "visual_role": "hero_lipsync",
                        "visual_concept": "James introducing the topic",
                        "why_this_visual": "Establishes James as the trusted narrator.",
                        "narrative_alignment": "Direct host address builds trust.",
                        "claim_refs": ["C001"],
                        "literal_vs_metaphorical": "literal",
                        "must_show": ["James at desk"],
                        "must_avoid": [],
                        "planned_duration_sec": 8.5,
                        "min_usable_duration_sec": 4.0,
                        "max_usable_duration_sec": 12.0,
                        "duration_drift_policy": "trim_ok",
                        "assembly_fit_policy": "Lead shot.",
                        "generation_risk": "low",
                        "fallback_strategy": "hero_cutaway",
                        "qa_requirements": ["lipsync_score >= 0.85"],
                    },
                    {
                        "shot_id": "SH002",
                        "segment_id": "S001",
                        "visual_role": "broll_metaphorical",
                        "visual_concept": "COMPLETELY DIFFERENT UNAUTHORIZED CONCEPT",
                        "why_this_visual": "Helps viewers visualize scaling AI.",
                        "narrative_alignment": "Abstract neural connections support the claim.",
                        "claim_refs": ["C001"],
                        "literal_vs_metaphorical": "metaphorical",
                        "must_show": ["network nodes"],
                        "must_avoid": [],
                        "planned_duration_sec": 5.0,
                        "min_usable_duration_sec": 3.0,
                        "max_usable_duration_sec": 6.5,
                        "duration_drift_policy": "trim_ok",
                        "assembly_fit_policy": "Trim to fit.",
                        "generation_risk": "medium",
                        "fallback_strategy": "still_kenburns",
                        "qa_requirements": ["no_readable_text"],
                    }
                ]
            },
        }

        llm_fn = _stub_sonnet5_repair(repair_data)
        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["SH001"],
            max_attempts=2,
            llm_fn=llm_fn,
        )

        assert result["status"] == "BLOCKED"
        assert result["error_code"] == BLOCKED_UNAFFECTED_REWRITE
        assert any("UNAFFECTED" in str(bc) for bc in result.get("block_chain", []))


class TestNonSonnetProfileFails:
    def test_non_sonnet_profile_fails(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "shots[0].visual_concept",
                "entity_id": "SH001",
                "severity": "BLOCKER",
                "message": "Test error.",
            }
        ]

        def _non_sonnet_fn(prompt):
            raise RuntimeError(
                "BLOCKED_CREATIVE_FALLBACK_FORBIDDEN: task 'storyboard_repair' requires Sonnet 5 "
                "through Kilo. Profile 'auto_utility' is not permitted for runtime storyboard authoring.")

        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["SH001"],
            max_attempts=2,
            llm_fn=_non_sonnet_fn,
        )

        assert result["status"] == "BLOCKED"
        assert result["error_code"] == BLOCKED_NON_SONNET


class TestMaxAttemptsExhausted:
    def test_invalid_repair_after_max_attempts_fails(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "overlays[0].semantic_purpose",
                "entity_id": "OV001",
                "severity": "BLOCKER",
                "message": "BLOCKED_PURPOSELESS_OVERLAY: missing semantic_purpose.",
            }
        ]

        def _stub_always_broken(prompt):
            repair_data = {
                "repair_summary": [
                    {
                        "entity_id": "OV001",
                        "entity_type": "overlay",
                        "changed_fields": ["semantic_purpose"],
                        "reason": "Attempted fix.",
                        "before_value": "",
                        "after_value": "",
                    }
                ],
                "repaired_entities": {
                    "overlays": [
                        {
                            "overlay_id": "OV001",
                            "segment_id": "S001",
                            "shot_id": "SH001",
                            "overlay_type": "stat_display",
                            "text": "GPT-4: 90th percentile",
                            "semantic_purpose": "",
                            "source_ref": "",
                            "claim_refs": [],
                            "trigger_phrase": "90th percentile",
                            "start_time_offset_sec": 2.0,
                            "end_time_offset_sec": 5.0,
                            "position": "lower_third",
                            "style_token": "stat_callout_primary",
                            "animation": "fade_in",
                            "safe_for_9x16": True,
                            "qa_rules": ["text_legible"],
                        }
                    ]
                },
            }
            return (repair_data, json.dumps(repair_data), "storyboard_director_sonnet5",
                    "kilo/anthropic/claude-sonnet-5-20250908")

        def _always_fails_revalidator(storyboard):
            return [{
                "path": "overlays[0].semantic_purpose",
                "entity_id": "OV001",
                "severity": "BLOCKER",
                "message": "BLOCKED_PURPOSELESS_OVERLAY: still missing semantic_purpose.",
            }]

        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["OV001"],
            max_attempts=2,
            llm_fn=_stub_always_broken,
            revalidator_fn=_always_fails_revalidator,
        )

        assert result["status"] == "BLOCKED"
        assert result["error_code"] == BLOCKED_REPAIR_EXHAUSTED
        assert len(result["repair_log"]) >= 2


class TestRepairLog:
    def test_repair_log_includes_affected_ids_and_changed_fields(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "overlays[0].semantic_purpose",
                "entity_id": "OV001",
                "severity": "BLOCKER",
                "message": "BLOCKED_PURPOSELESS_OVERLAY: missing semantic_purpose.",
            }
        ]

        repair_data = {
            "repair_summary": [
                {
                    "entity_id": "OV001",
                    "entity_type": "overlay",
                    "changed_fields": ["semantic_purpose", "source_ref"],
                    "reason": "Added semantic purpose and source reference.",
                    "before_value": "",
                    "after_value": "Displays the benchmark statistic.",
                }
            ],
            "repaired_entities": {
                "overlays": [
                    {
                        "overlay_id": "OV001",
                        "segment_id": "S001",
                        "shot_id": "SH001",
                        "overlay_type": "stat_display",
                        "text": "GPT-4: 90th percentile on Bar Exam",
                        "semantic_purpose": "Displays the benchmark statistic supporting the AI capability claim.",
                        "source_ref": "src_test",
                        "claim_refs": ["C001"],
                        "trigger_phrase": "90th percentile",
                        "start_time_offset_sec": 2.0,
                        "end_time_offset_sec": 5.0,
                        "position": "lower_third",
                        "style_token": "stat_callout_primary",
                        "animation": "fade_in",
                        "safe_for_9x16": True,
                        "qa_rules": ["text_legible"],
                    }
                ]
            },
        }

        llm_fn = _stub_sonnet5_repair(repair_data)
        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["OV001"],
            max_attempts=2,
            llm_fn=llm_fn,
        )

        assert result["status"] == "SUCCESS"
        repair_log = result["repair_log"]
        assert len(repair_log) >= 1
        assert repair_log[0]["status"] == "REPAIR_ATTEMPTED"

        changed = repair_log[0].get("changed_fields", [])
        assert len(changed) >= 1
        assert changed[0]["entity_id"] == "OV001"
        assert "semantic_purpose" in changed[0]["changed_fields"]

        summary = repair_log[0].get("repair_summary", [])
        assert len(summary) >= 1


class TestDryRun:
    def test_dry_run_produces_prompt_without_invoking_kilo(self):
        sb = _base_canonical_sb()
        validation_errors = [
            {
                "path": "shots[0].narrative_alignment",
                "entity_id": "SH001",
                "severity": "BLOCKER",
                "message": "Test validation error.",
            }
        ]

        result = repair_canonical_storyboard(
            canonical_storyboard=sb,
            validation_errors=validation_errors,
            affected_entity_ids=["SH001"],
            max_attempts=2,
            dry_run=True,
        )

        assert result["status"] == "DRY_RUN"
        assert len(result["repair_log"]) == 1
        assert result["repair_log"][0]["status"] == "DRY_RUN"
        assert result["repair_log"][0]["prompt_chars"] > 0
        assert "prompt_preview" in result["repair_log"][0]
        assert "affected_entity_ids" in result["repair_log"][0]
        assert result["repair_log"][0]["affected_entity_ids"] == ["SH001"]


class TestExtractAffectedEntities:
    def test_extracts_affected_entities(self):
        sb = _base_canonical_sb()
        affected = extract_affected_entities(sb, ["SH001"])
        assert "shots" in affected
        assert len(affected["shots"]) == 1
        assert affected["shots"][0]["shot_id"] == "SH001"

    def test_extracts_multiple_collections(self):
        sb = _base_canonical_sb()
        affected = extract_affected_entities(sb, ["SH001", "OV001"])
        assert "shots" in affected
        assert "overlays" in affected
        assert len(affected["shots"]) == 1
        assert len(affected["overlays"]) == 1


class TestExtractAdjacentEntities:
    def test_extracts_adjacent_context(self):
        sb = _base_canonical_sb()
        adjacent = extract_adjacent_entities(sb, ["SH002"])
        assert "shots" in adjacent
        assert len(adjacent["shots"]) == 1
        assert adjacent["shots"][0]["shot_id"] == "SH001"


class TestBuildRepairPrompt:
    def test_prompt_includes_validation_errors(self):
        sb = _base_canonical_sb()
        affected = extract_affected_entities(sb, ["OV001"])
        adjacent = extract_adjacent_entities(sb, ["OV001"])
        errors = [{"entity_id": "OV001", "message": "Missing semantic_purpose."}]

        prompt = build_repair_prompt(sb, errors, affected, adjacent)
        assert "OV001" in prompt
        assert "Missing semantic_purpose" in prompt
        assert "semantic_purpose" in prompt.lower() or "semantic" in prompt.lower()


class TestValidateNarrationImmutability:
    def test_identical_narration_passes(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        errors = validate_narration_immutability(sb, repaired, [])
        assert errors == []

    def test_mutated_narration_fails(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        repaired["narrative_beats"][0]["narration_text"] = "Mutated narration."
        errors = validate_narration_immutability(sb, repaired, [])
        assert len(errors) >= 1
        assert any(BLOCKED_NARRATION_MUTATION in e["code"] for e in errors)

    def test_mutated_work_order_narration_fails(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        repaired["segment_work_orders"][0]["narration_text_exact"] = "Work order mutated."
        errors = validate_narration_immutability(sb, repaired, [])
        assert len(errors) >= 1
        assert any(BLOCKED_NARRATION_MUTATION in e["code"] for e in errors)


class TestValidateUnaffectedPreserved:
    def test_unaffected_preserved_passes(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        errors = validate_unaffected_preserved(sb, repaired, {"SH001"})
        assert errors == []

    def test_unaffected_modified_fails(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        repaired["shots"][1]["visual_concept"] = "RANDOM UNAUTHORIZED CHANGE"
        errors = validate_unaffected_preserved(sb, repaired, {"SH001"})
        assert len(errors) >= 1
        assert any(BLOCKED_UNAFFECTED_REWRITE in e["code"] for e in errors)


class TestApplyRepair:
    def test_apply_repair_merges_overlay(self):
        sb = _base_canonical_sb()
        repair_data = {
            "repaired_entities": {
                "overlays": [
                    {
                        "overlay_id": "OV001",
                        "segment_id": "S001",
                        "shot_id": "SH001",
                        "overlay_type": "stat_display",
                        "text": "Fixed overlay text",
                        "semantic_purpose": "Fixed semantic purpose.",
                        "source_ref": "src_test",
                        "claim_refs": ["C001"],
                        "trigger_phrase": "test",
                        "start_time_offset_sec": 2.0,
                        "end_time_offset_sec": 5.0,
                        "position": "lower_third",
                        "style_token": "stat_callout_primary",
                        "animation": "fade_in",
                        "safe_for_9x16": True,
                        "qa_rules": ["text_legible"],
                    }
                ]
            }
        }
        result = apply_repair(sb, repair_data)
        assert result["overlays"][0]["semantic_purpose"] == "Fixed semantic purpose."
        assert result["overlays"][0]["text"] == "Fixed overlay text"

    def test_apply_repair_preserves_unaffected_shot(self):
        sb = _base_canonical_sb()
        original_shot = copy.deepcopy(sb["shots"][0])
        repair_data = {
            "repaired_entities": {
                "overlays": [
                    copy.deepcopy(sb["overlays"][0])
                ]
            }
        }
        result = apply_repair(sb, repair_data)
        assert result["shots"][0] == original_shot


class TestComputeChangedFields:
    def test_computes_changed_fields(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        repaired["overlays"][0]["semantic_purpose"] = "New purpose."
        repaired["overlays"][0]["source_ref"] = "new_source"

        changed = compute_changed_fields(sb, repaired, {"OV001"})
        assert len(changed) == 1
        assert changed[0]["entity_id"] == "OV001"
        assert "semantic_purpose" in changed[0]["changed_fields"]
        assert "source_ref" in changed[0]["changed_fields"]

    def test_unchanged_entity_not_reported(self):
        sb = _base_canonical_sb()
        repaired = copy.deepcopy(sb)
        changed = compute_changed_fields(sb, repaired, {"OV001"})
        assert changed == []


class TestParseStubRepairResponse:
    def test_parses_dict_with_repaired_entities(self):
        data = {
            "repair_summary": [{"entity_id": "OV001", "changed_fields": ["semantic_purpose"]}],
            "repaired_entities": {"overlays": [{"overlay_id": "OV001"}]},
        }
        parsed = parse_stub_repair_response(data)
        assert parsed is not None
        assert "repaired_entities" in parsed

    def test_parses_dict_without_repaired_entities_key(self):
        data = {
            "repair_summary": [],
            "overlays": [{"overlay_id": "OV001"}],
        }
        parsed = parse_stub_repair_response(data)
        assert parsed is not None
        assert "repaired_entities" in parsed

    def test_list_creates_empty_result(self):
        parsed = parse_stub_repair_response([{"shot_id": "SH001"}])
        assert parsed is not None
        assert "repaired_entities" in parsed
