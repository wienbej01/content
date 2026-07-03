#!/usr/bin/env python3
"""tests/test_storyboard_prompt_packet.py — Prompt guardrail tests for S22_T004.

Verifies that all three Sonnet 5 prompt files contain the required guardrail
text specified in the ticket. These are text-presence tests; no LLM is called.

10 required tests:
  1.  Director prompt contains immutable narration rule
  2.  Director prompt contains strict JSON rule
  3.  Director prompt contains Sonnet 5 authority language
  4.  Director prompt requires segment_work_orders
  5.  Director prompt requires why_this_visual, narrative_alignment, semantic_purpose
  6.  Director prompt bans generic B-roll terms
  7.  Director prompt requires conclusion-alignment instruction
  8.  Director prompt requires duration drift policy
  9.  Repair prompt forbids unrelated rewrites
  10. Creative review prompt cannot approve Python-authored storyboards
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "docs" / "prompts"


def _load_prompt(name):
    path = PROMPTS_DIR / name
    assert path.exists(), f"Prompt file not found: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def director_prompt():
    return _load_prompt("STORYBOARD_SONNET5_DIRECTOR.md")


@pytest.fixture(scope="module")
def repair_prompt():
    return _load_prompt("STORYBOARD_SONNET5_REPAIR.md")


@pytest.fixture(scope="module")
def creative_review_prompt():
    return _load_prompt("STORYBOARD_SONNET5_CREATIVE_REVIEW.md")


# ── Test 1: Immutable narration rule ────────────────────────────────

def test_immutable_narration_rule(director_prompt):
    """Prompt contains immutable narration rule forbidding rewrite/shorten/extend/paraphrase."""
    required_phrases = [
        "immutable",
        "Do not rewrite",
        "shorten",
        "extend",
        "paraphrase",
    ]
    for phrase in required_phrases:
        assert phrase.lower() in director_prompt.lower(), \
            f"Director prompt missing immutable narration phrase: '{phrase}'"

    assert "BLOCKED_SCRIPT_NARRATION_MUTATION" in director_prompt, \
        "Director prompt missing BLOCKED_SCRIPT_NARRATION_MUTATION error code"


# ── Test 2: Strict JSON rule ────────────────────────────────────────

def test_strict_json_rule(director_prompt):
    """Prompt contains strict JSON output rule: no fences, no prose, no comments."""
    required_phrases = [
        "raw JSON only",
        "no markdown fences",
        "no prose",
        "no comments",
        "no trailing explanation",
    ]
    for phrase in required_phrases:
        assert phrase.lower() in director_prompt.lower(), \
            f"Director prompt missing strict JSON phrase: '{phrase}'"


# ── Test 3: Sonnet 5 authority language ──────────────────────────────

def test_sonnet5_authority_language(director_prompt):
    """Prompt contains Sonnet 5 authority language asserting exclusive authorship."""
    required_phrases = [
        "Sonnet 5",
        "only model authorized",
        "authoring authority",
    ]
    for phrase in required_phrases:
        assert phrase.lower() in director_prompt.lower(), \
            f"Director prompt missing Sonnet 5 authority phrase: '{phrase}'"

    assert "Python does not" in director_prompt, \
        "Director prompt missing Python design prohibition"


# ── Test 4: segment_work_orders requirement ───────────────────────────

def test_segment_work_orders_required(director_prompt):
    """Prompt requires segment_work_orders with required fields."""
    assert "segment_work_orders" in director_prompt, \
        "Director prompt missing segment_work_orders"

    required_fields = [
        "narration_text_exact",
        "argument_summary",
        "viewer_question",
        "retention_role",
        "broll_alignment_instruction",
        "graphic_alignment_instruction",
        "conclusion_alignment_instruction",
        "qa_acceptance_criteria",
    ]
    for field in required_fields:
        assert field in director_prompt, \
            f"Director prompt missing segment_work_order field: '{field}'"


# ── Test 5: why_this_visual, narrative_alignment, semantic_purpose ──

def test_required_semantic_fields(director_prompt):
    """Prompt requires why_this_visual, narrative_alignment, and semantic_purpose."""
    assert "why_this_visual" in director_prompt, \
        "Director prompt missing why_this_visual requirement"
    assert "narrative_alignment" in director_prompt, \
        "Director prompt missing narrative_alignment requirement"
    assert "semantic_purpose" in director_prompt, \
        "Director prompt missing semantic_purpose requirement"


# ── Test 6: Generic B-roll ban ──────────────────────────────────────

def test_generic_broll_ban(director_prompt):
    """Prompt bans generic B-roll terms explicitly."""
    generic_terms = [
        "business people",
        "professional environment",
        "generic office",
        "people working",
        "stock footage",
        "abstract data",
        "city skyline",
        "person typing",
    ]
    lower = director_prompt.lower()

    for term in generic_terms:
        assert term.lower() in lower, \
            f"Director prompt must explicitly forbid generic term: '{term}'"

    assert "forbidden" in lower, \
        "Director prompt must use 'forbidden' language for generic B-roll"
    assert "BLOCKED_GENERIC_BROLL" in director_prompt, \
        "Director prompt missing BLOCKED_GENERIC_BROLL error code"


# ── Test 7: Conclusion-alignment instruction ────────────────────────

def test_conclusion_alignment_instruction(director_prompt):
    """Prompt requires conclusion-alignment instruction."""
    assert "conclusion_alignment_instruction" in director_prompt, \
        "Director prompt missing conclusion_alignment_instruction field"

    assert "conclusion" in director_prompt.lower(), \
        "Director prompt should discuss conclusion strategy"


# ── Test 8: Duration drift policy ───────────────────────────────────

def test_duration_drift_policy(director_prompt):
    """Prompt requires duration_drift_policy and all allowed values."""
    assert "duration_drift_policy" in director_prompt, \
        "Director prompt missing duration_drift_policy requirement"

    drift_values = [
        "trim_ok",
        "pad_ok",
        "extend_still_ok",
        "regenerate_required",
        "sonnet_repair_required",
        "human_review_required",
    ]
    for value in drift_values:
        assert value in director_prompt, \
            f"Director prompt missing drift policy value: '{value}'"

    assert "assembly_fit_policy" in director_prompt, \
        "Director prompt missing assembly_fit_policy"


# ── Test 9: Repair prompt forbids unrelated rewrites ────────────────

def test_repair_forbids_unrelated_rewrites(repair_prompt):
    """Repair prompt forbids narration changes and unrelated rewrites."""
    assert "NO NARRATION CHANGES" in repair_prompt, \
        "Repair prompt missing NO NARRATION CHANGES rule"
    assert "NO UNRELATED REWRITES" in repair_prompt, \
        "Repair prompt missing NO UNRELATED REWRITES rule"
    assert "BLOCKED_SCRIPT_NARRATION_MUTATION" in repair_prompt, \
        "Repair prompt missing BLOCKED_SCRIPT_NARRATION_MUTATION error code"
    assert "FIX ONLY" in repair_prompt, \
        "Repair prompt missing 'FIX ONLY affected entities' constraint"
    assert "KEEP SAME IDS" in repair_prompt or "KEEP SAME IDs" in repair_prompt, \
        "Repair prompt missing 'KEEP SAME IDs' constraint"


# ── Test 10: Creative review bans Python-authored approval ─────────

def test_creative_review_bans_python_author(creative_review_prompt):
    """Creative review prompt cannot approve Python-authored storyboards."""
    assert "Python-authored" in creative_review_prompt, \
        "Creative review prompt missing Python-authored prohibition"
    assert "BLOCKED_NON_SONNET_AUTHOR" in creative_review_prompt, \
        "Creative review prompt missing BLOCKED_NON_SONNET_AUTHOR error code"
    assert "Sonnet 5" in creative_review_prompt, \
        "Creative review prompt must reference Sonnet 5"
    assert "storyboard was authored by python" in creative_review_prompt.lower(), \
        "Creative review prompt must explicitly reject Python-authored storyboards"
    assert "authoring_model_profile" in creative_review_prompt, \
        "Creative review prompt must check authoring_model_profile"


# ── Additional: verify all prompt files exist ────────────────────────

def test_all_prompt_files_exist():
    for name in (
        "STORYBOARD_SONNET5_DIRECTOR.md",
        "STORYBOARD_SONNET5_REPAIR.md",
        "STORYBOARD_SONNET5_CREATIVE_REVIEW.md",
    ):
        assert (PROMPTS_DIR / name).exists(), \
            f"Prompt file missing: {name}"


# ── Additional: verify repair prompt contains repair_summary requirement

def test_repair_prompt_requires_repair_summary(repair_prompt):
    """Repair prompt requires repair_summary with changed fields."""
    assert "repair_summary" in repair_prompt, \
        "Repair prompt missing repair_summary requirement"
    assert "changed_fields" in repair_prompt, \
        "Repair prompt missing changed_fields in repair summary"


# ── Additional: verify creative review references all four perspectives

def test_creative_review_four_perspectives(creative_review_prompt):
    """Creative review prompt includes all four review perspectives."""
    for perspective in ("visual_director", "filmmaker", "audience", "technical"):
        assert perspective in creative_review_prompt.lower(), \
            f"Creative review missing perspective: {perspective}"
