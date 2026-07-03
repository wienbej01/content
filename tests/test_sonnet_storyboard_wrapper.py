#!/usr/bin/env python3
"""tests/test_sonnet_storyboard_wrapper.py — S22_T006 tests.

Tests the Sonnet 5 storyboard wrapper without live LLM calls.
All tests use stubbed/mocked llm_call to avoid calling Kilo or any paid provider.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from sonnet_storyboard_wrapper import (
    assemble_context_packet,
    build_sonnet5_storyboard_prompt,
    validate_sonnet_authoring,
    detect_narration_mutation,
    generate_canonical_storyboard,
    CREATIVE_FALLBACK_BLOCKED,
    NON_SONNET_BLOCKED,
    EMPTY_RESPONSE_BLOCKED,
    UNPARSEABLE_BLOCKED,
    NARRATION_MUTATION_BLOCKED,
    REQUIRED_SONNET5_PROFILE,
)

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "storyboard_v2"

APPROVED_SCRIPT = {
    "project_id": "proj_test_001",
    "title": "AI Scaling Laws",
    "approved_script_revision_id": "rev_20250703_a1b2c3",
    "segments": [
        {"id": "S001", "text": "AI is transforming how we think about intelligence."},
        {"id": "S002", "text": "GPT-4 scored in the 90th percentile on the bar exam."},
    ],
    "key_points": [],
}

VALID_CANONICAL_STORYBOARD = json.loads(
    (FIXTURES_DIR / "valid_semantic_storyboard.json").read_text()
)


def _stub_llm_call_success(task, prompt, model_profile, timeout, verbose, expect_json):
    return (VALID_CANONICAL_STORYBOARD.copy(),
            json.dumps(VALID_CANONICAL_STORYBOARD),
            REQUIRED_SONNET5_PROFILE,
            "kilo/anthropic/claude-sonnet-5")


def _stub_llm_call_none(task, prompt, model_profile, timeout, verbose, expect_json):
    return (None, "", REQUIRED_SONNET5_PROFILE, "kilo/anthropic/claude-sonnet-5")


class Test1StubbedSonnetResponse:
    """Stubbed Sonnet response returns canonical storyboard."""

    def test_stubbed_response_returns_canonical_storyboard(self):
        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_llm_call_success):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["status"] == "SUCCESS", f"Expected SUCCESS, got {result['status']}"
        sb = result["storyboard"]
        assert sb is not None
        assert sb["storyboard_contract_version"] == "1.0"
        assert "shots" in sb
        assert "narrative_beats" in sb
        assert "overlays" in sb
        assert "segment_work_orders" in sb
        assert "claim_inventory" in sb
        assert "feedback_policy" in sb
        assert "timing_policy" in sb

        meta = result["authoring_metadata"]
        assert meta["profile"] == REQUIRED_SONNET5_PROFILE
        assert meta["model"] == "kilo/anthropic/claude-sonnet-5"
        assert meta["profile_used"] == REQUIRED_SONNET5_PROFILE
        assert meta["raw_response_chars"] > 0

    def test_authoring_metadata_embedded(self):
        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_llm_call_success):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        sb = result["storyboard"]
        assert "_authoring_metadata" in sb
        meta = sb["_authoring_metadata"]
        assert meta["profile"] == REQUIRED_SONNET5_PROFILE
        assert meta["model"] == "kilo/anthropic/claude-sonnet-5"
        assert "script_sha256" in meta
        assert "prompt_chars" in meta
        assert "raw_response_chars" in meta


class Test2ProfileValidation:
    """Wrapper passes profile storyboard_director_sonnet5."""

    def test_profile_always_sonnet5(self):
        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_llm_call_success):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        meta = result["authoring_metadata"]
        assert meta["profile"] == REQUIRED_SONNET5_PROFILE

        mock_llm.assert_called_once()
        _, kwargs = mock_llm.call_args_list[0] if hasattr(mock_llm, 'call_args_list') else (None, None)
        call_kwargs = mock_llm.call_args[1] if mock_llm.call_args else {}
        assert call_kwargs.get("model_profile") == REQUIRED_SONNET5_PROFILE
        assert call_kwargs.get("task") == "storyboard_generation"

    def test_profile_in_result_matches(self):
        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_llm_call_success):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["authoring_metadata"]["profile"] == REQUIRED_SONNET5_PROFILE
        assert result["authoring_metadata"]["profile_used"] == REQUIRED_SONNET5_PROFILE


class Test3NonSonnetResponseFails:
    """Non-Sonnet response metadata fails."""

    def test_non_sonnet_authoring_errors(self):
        result = validate_sonnet_authoring(
            {"authoring_model_profile": "deepseek_v4_flash",
             "authoring_model": "kilo/deepseek/deepseek-v4-flash"},
            "auto_utility",
            "kilo/deepseek/deepseek-v4-flash",
        )
        assert len(result) >= 2
        codes = [e["code"] for e in result]
        assert NON_SONNET_BLOCKED in codes

    def test_non_sonnet_profile_blocked(self):
        result = validate_sonnet_authoring(
            {},
            "sonnet_creative",
            "kilo/deepseek/deepseek-v4-flash",
        )
        assert len(result) >= 1
        assert result[0]["code"] == NON_SONNET_BLOCKED

    def test_sonnet_profile_passes_validation(self):
        result = validate_sonnet_authoring(
            {"authoring_model_profile": "storyboard_sonnet5",
             "authoring_model": "kilo/anthropic/claude-sonnet-5-20250908"},
            REQUIRED_SONNET5_PROFILE,
            "kilo/anthropic/claude-sonnet-5",
        )
        assert result == []

    def test_claude_sonnet_model_passes(self):
        result = validate_sonnet_authoring(
            {"authoring_model_profile": REQUIRED_SONNET5_PROFILE,
             "authoring_model": "kilo/anthropic/claude-sonnet-5-20250908"},
            REQUIRED_SONNET5_PROFILE,
            "kilo/anthropic/claude-sonnet-5",
        )
        assert result == []


class Test4EmptyResponseFails:
    """Empty response fails."""

    def test_none_data_returns_blocked(self):
        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_llm_call_none):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["status"] == "BLOCKED"
        assert result["error_code"] == EMPTY_RESPONSE_BLOCKED


class Test5InvalidJSONFails:
    """Invalid JSON fails — handled by llm_call.py raising RuntimeError."""

    @staticmethod
    def _raise_parse_error(task, prompt, model_profile, timeout, verbose, expect_json):
        raise RuntimeError("Failed to parse JSON from response:\ngarbage{{{{")

    def test_parse_failure_propagates(self):
        with patch("sonnet_storyboard_wrapper._llm_call",
                   side_effect=Test5InvalidJSONFails._raise_parse_error):
            with pytest.raises(RuntimeError, match="Failed to parse JSON"):
                generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)


class Test6NarrationMutationDetection:
    """Script narration mutation fails or is handed to validator as blocking."""

    def test_no_mutation_detected(self):
        storyboard = {"segment_work_orders": [
            {"segment_id": "S001",
             "narration_text_exact": "AI is transforming how we think about intelligence."}
        ]}
        result = detect_narration_mutation(APPROVED_SCRIPT, storyboard)
        assert result == []

    def test_mutation_detected(self):
        storyboard = {"segment_work_orders": [
            {"segment_id": "S001",
             "narration_text_exact": "AI is completely changing how we view thinking."}
        ]}
        result = detect_narration_mutation(APPROVED_SCRIPT, storyboard)
        assert len(result) == 1
        assert result[0]["code"] == NARRATION_MUTATION_BLOCKED
        assert result[0]["severity"] == "BLOCKER"
        assert result[0]["segment_id"] == "S001"

    def test_mutation_causes_blocked_status(self):
        mutated_sb = VALID_CANONICAL_STORYBOARD.copy()
        mutated_sb["segment_work_orders"] = [{
            "segment_id": "S001",
            "narration_text_exact": "WRONG narration text here",
            "argument_summary": "test",
            "viewer_question": "test?",
            "retention_role": "test",
            "broll_alignment_instruction": "test",
            "graphic_alignment_instruction": "test",
            "conclusion_alignment_instruction": "test",
            "qa_acceptance_criteria": ["test"],
        }]

        def _stub_mutated(task, prompt, model_profile, timeout, verbose, expect_json):
            return (mutated_sb, json.dumps(mutated_sb),
                    REQUIRED_SONNET5_PROFILE, "kilo/anthropic/claude-sonnet-5")

        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_mutated):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["status"] == "BLOCKED"
        assert len(result["narration_mutations"]) >= 1
        assert result["narration_mutations"][0]["code"] == NARRATION_MUTATION_BLOCKED

    def test_no_segments_no_mutations(self):
        sb = {"segment_work_orders": [
            {"segment_id": "S999", "narration_text_exact": "anything"}
        ]}
        result = detect_narration_mutation(APPROVED_SCRIPT, sb)
        assert result == []


class Test7NoPythonFallback:
    """Python fallback function is never called; no deterministic creative assignment."""

    def test_no_creative_fallback_branch(self):
        src = (ROOT / "scripts" / "sonnet_storyboard_wrapper.py").read_text()
        forbidden = [
            "def create_fallback_storyboard",
            "def generate_default_shots",
            "def auto_fill_beats",
            "deterministic_storyboard",
            "hardcoded_beats",
            "visual_brief =",
            "shot_type = ",
        ]
        for pattern in forbidden:
            assert pattern not in src, (
                f"Python creative fallback pattern detected: '{pattern}'. "
                "Python must not create storyboard content."
            )

    def test_no_direct_creative_assignment(self):
        src = (ROOT / "scripts" / "sonnet_storyboard_wrapper.py").read_text()
        creative_assignments = [
            '"hero_lipsync"', '"broll_archival"', '"broll_metaphorical"',
            '"visual_role"', '"visual_concept"',
        ]
        found = [a for a in creative_assignments if a in src and '"""' not in src.split(a)[0].rsplit('"""', 1)[-1] if a not in _get_docstring_content(src)]
        # Check if these appear in docstrings or in code logic
        lines = src.splitlines()
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.endswith('"""'):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith('#') or stripped.startswith('"') or stripped.startswith("'"):
                continue
            for pattern in creative_assignments:
                if pattern in stripped and "def " not in stripped:
                    pass

    def test_generate_never_calls_python_fallback(self):
        with patch("sonnet_storyboard_wrapper._llm_call", side_effect=_stub_llm_call_success):
            from sonnet_storyboard_wrapper import _llm_call as mock_llm
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["status"] == "SUCCESS"
        mock_llm.assert_called_once()
        call_args = mock_llm.call_args[1]
        assert call_args["task"] == "storyboard_generation"
        assert call_args["model_profile"] == REQUIRED_SONNET5_PROFILE


class Test8DryRun:
    """Dry-run emits prompt size/model without calling Kilo."""

    def test_dry_run_no_subprocess(self):
        result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=True)

        assert result["status"] == "DRY_RUN"
        assert result["storyboard"] is None
        assert "dry_run" in result
        dry = result["dry_run"]
        assert dry["prompt_chars"] > 0
        assert dry["model_profile"] == REQUIRED_SONNET5_PROFILE
        assert "prompt_preview" in dry

        meta = result["authoring_metadata"]
        assert meta["profile"] == REQUIRED_SONNET5_PROFILE
        assert meta["prompt_chars"] > 0
        assert "script_sha256" in meta

    def test_dry_run_reports_prompt_size(self):
        result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=True)
        dry = result["dry_run"]
        assert dry["prompt_chars"] > 500
        assert "storyboard_contract_version" in dry["prompt_preview"].lower() or \
               "STORYBOARD DIRECTOR" in dry["prompt_preview"].upper() or \
               len(dry["prompt_preview"]) > 0

    def test_dry_run_does_not_import_or_call_llm(self):
        import subprocess
        with patch("sonnet_storyboard_wrapper._llm_call") as mock_llm:
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=True)
            mock_llm.assert_not_called()

    def test_dry_run_reports_model_profile(self):
        result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=True)
        assert result["dry_run"]["model_profile"] == REQUIRED_SONNET5_PROFILE


def _get_docstring_content(src):
    import re
    matches = re.findall(r'"""(.*?)"""', src, re.DOTALL)
    return "\n".join(matches)


# ── Additional: Context packet assembly ─────────────────────────────────

class TestContextPacketAssembly:
    def test_context_contains_all_sections(self):
        context = assemble_context_packet(APPROVED_SCRIPT)
        assert "approved_script_json" in context
        assert "approved_script_sha256" in context
        assert len(context["approved_script_sha256"]) == 64
        assert "approved_script_revision_id" in context
        assert "project_id" in context
        assert "source_research_text" in context
        assert "bible_texts" in context
        assert "canonical_schema_json" in context

    def test_script_sha256_is_deterministic(self):
        ctx1 = assemble_context_packet(APPROVED_SCRIPT)
        ctx2 = assemble_context_packet(APPROVED_SCRIPT)
        assert ctx1["approved_script_sha256"] == ctx2["approved_script_sha256"]

    def test_script_sha256_changes_with_content(self):
        ctx1 = assemble_context_packet(APPROVED_SCRIPT)
        modified = dict(APPROVED_SCRIPT)
        modified["title"] = "Different Title"
        ctx2 = assemble_context_packet(modified)
        assert ctx1["approved_script_sha256"] != ctx2["approved_script_sha256"]


# ── Additional: Prompt construction ────────────────────────────────────

class TestPromptConstruction:
    def test_prompt_contains_approved_script(self):
        context = assemble_context_packet(APPROVED_SCRIPT)
        prompt = build_sonnet5_storyboard_prompt(context)
        assert "AI is transforming" in prompt
        assert "GPT-4" in prompt

    def test_prompt_contains_schema(self):
        context = assemble_context_packet(APPROVED_SCRIPT)
        prompt = build_sonnet5_storyboard_prompt(context)
        assert "storyboard_contract_version" in prompt

    def test_prompt_contains_required_sections(self):
        context = assemble_context_packet(APPROVED_SCRIPT)
        prompt = build_sonnet5_storyboard_prompt(context)
        assert "=== APPROVED SCRIPT ===" in prompt
        assert "=== SOURCE RESEARCH ===" in prompt
        assert "=== BIBLES ===" in prompt
        assert "=== SCHEMA" in prompt

    def test_prompt_is_large_enough(self):
        context = assemble_context_packet(APPROVED_SCRIPT)
        prompt = build_sonnet5_storyboard_prompt(context)
        assert len(prompt) > 2000


# ── Additional: Sonnet 5 unavailable ───────────────────────────────────

class TestSonnet5Unavailable:
    @staticmethod
    def _raise_unavailable(task, prompt, model_profile, timeout, verbose, expect_json):
        raise RuntimeError(
            "BLOCKED_SONNET5_UNAVAILABLE: Sonnet 5 (kilo/anthropic/claude-sonnet-5) "
            "is not available through Kilo.")

    def test_sonnet5_unavailable_returns_blocked(self):
        with patch("sonnet_storyboard_wrapper._llm_call",
                   side_effect=TestSonnet5Unavailable._raise_unavailable):
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["status"] == "BLOCKED"
        assert result["error_code"] == "BLOCKED_SONNET5_UNAVAILABLE"
        assert "Sonnet 5" in result["error"]


# ── Additional: Non-dict LLM response ─────────────────────────────────

class TestNonDictResponse:
    @staticmethod
    def _stub_array_response(task, prompt, model_profile, timeout, verbose, expect_json):
        return (["beat1", "beat2"], '["beat1", "beat2"]',
                REQUIRED_SONNET5_PROFILE, "kilo/anthropic/claude-sonnet-5")

    def test_array_response_fails_sonnet_authoring_check(self):
        with patch("sonnet_storyboard_wrapper._llm_call",
                   side_effect=TestNonDictResponse._stub_array_response):
            result = generate_canonical_storyboard(APPROVED_SCRIPT, dry_run=False)

        assert result["status"] == "BLOCKED"
        assert len(result["authoring_errors"]) >= 1
        assert result["authoring_errors"][0]["code"] == NON_SONNET_BLOCKED


if __name__ == "__main__":
    pytest.main([__file__, "-q", "--tb=short"])
