#!/usr/bin/env python3
"""tests/test_graphic_qa.py — S16_T004: Graphic semantic alignment gate tests.

Tests verify:
1. Black title cards fail with BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD
2. Topic-misaligned graphics fail with BLOCKED_GRAPHIC_MISALIGNED
3. Aligned 3-step framework graphics pass
4. Professional graphic templates with meaningful content pass
5. Weak titles generate warnings
6. Semantic overlap calculation works correctly
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evals.eval_graphic_qa import (
    is_black_title_card,
    is_weak_title,
    extract_keywords_from_text,
    compute_semantic_overlap,
    check_3step_framework_alignment,
    eval_graphic_unit,
)


def _with_graphic_provenance(ru):
    ru = dict(ru)
    ru.setdefault("asset_type", "local_graphic")
    ru["artifact_metadata"] = {
        "render_method": "local_graphic",
        "renderer": "render_graphics.py",
        "expected_text": ["deterministic text"],
        "text_spec_sha256": "test-sha",
    }
    return ru


# ============================================================================
# Black Title Card Tests
# ============================================================================

class TestBlackTitleCardDetection:
    """Tests for black title card detection."""

    def test_empty_text_is_black_title(self):
        """Empty text should be detected as black title card."""
        assert is_black_title_card("") is True
        assert is_black_title_card("   ") is True

    def test_generic_titles_are_black_cards(self):
        """Generic title-only text should be black cards."""
        assert is_black_title_card("Title") is True
        assert is_black_title_card("Intro") is True
        assert is_black_title_card("Chapter 1") is True
        assert is_black_title_card("Part 2") is True
        assert is_black_title_card("Section 3") is True

    def test_placeholder_text_is_black_card(self):
        """Placeholder text should be black cards."""
        assert is_black_title_card("Placeholder") is True
        assert is_black_title_card("TBC") is True
        assert is_black_title_card("TODO") is True

    def test_meaningful_text_is_not_black_card(self):
        """Meaningful text should not be black cards."""
        assert is_black_title_card("The power of compound interest") is False
        assert is_black_title_card("Three steps to financial freedom") is False
        assert is_black_title_card("Investing vs Saving comparison") is False


class TestWeakTitleDetection:
    """Tests for weak title detection."""

    def test_numeric_slides_are_weak(self):
        """Numeric slide references are weak titles."""
        assert is_weak_title("Slide 1") is True
        assert is_weak_title("Screen 2") is True
        assert is_weak_title("Graphic 3") is True
        assert is_weak_title("Image 4") is True
        assert is_weak_title("Fig 5") is True

    def test_meaningful_text_is_not_weak(self):
        """Meaningful text should not be weak."""
        assert is_weak_title("Key investment principles") is False
        assert is_weak_title("Market analysis 2024") is False


# ============================================================================
# Semantic Overlap Tests
# ============================================================================

class TestSemanticOverlap:
    """Tests for semantic overlap computation."""

    def test_no_overlap_returns_zero(self):
        """No semantic overlap should return 0.0."""
        overlap = compute_semantic_overlap("cats dogs", "planes trains")
        assert overlap == 0.0

    def test_full_overlap_returns_one(self):
        """Full semantic overlap should return 1.0."""
        overlap = compute_semantic_overlap("investment strategy", "investment strategy")
        assert overlap == 1.0

    def test_partial_overlap_calculated_correctly(self):
        """Partial overlap should be calculated correctly."""
        overlap = compute_semantic_overlap("investment growth strategy", "investment risk management")
        # Common keywords: "investment" (1) / union: investment, growth, strategy, risk, management (5) = 0.2
        assert 0.15 <= overlap <= 0.25

    def test_empty_text_returns_zero(self):
        """Empty text should return 0.0 overlap."""
        assert compute_semantic_overlap("", "investment") == 0.0
        assert compute_semantic_overlap("investment", "") == 0.0


# ============================================================================
# 3-Step Framework Alignment Tests
# ============================================================================

class Test3StepFrameworkAlignment:
    """Tests for 3-step framework semantic alignment."""

    def test_aligned_3step_framework_passes(self):
        """Aligned 3-step framework should pass."""
        dts = {
            "template_type": "framework_3_step",
            "content": {
                "title": "Investment Framework",
                "steps": [
                    {"label": "Research", "description": "Study market opportunities"},
                    {"label": "Invest", "description": "Allocate capital wisely"},
                    {"label": "Review", "description": "Monitor performance regularly"}
                ]
            }
        }
        narration = "The investment framework involves three key steps: research market opportunities, allocate capital wisely, and monitor performance regularly."

        result = check_3step_framework_alignment(dts, narration)
        assert result["applicable"] is True
        assert result["aligned"] is True
        assert "aligned" in result["reason"].lower()

    def test_misaligned_3step_framework_fails(self):
        """Misaligned 3-step framework should fail."""
        dts = {
            "template_type": "framework_3_step",
            "content": {
                "title": "Cooking Framework",
                "steps": [
                    {"label": "Prepare", "description": "Gather ingredients"},
                    {"label": "Cook", "description": "Apply heat"},
                    {"label": "Serve", "description": "Present the dish"}
                ]
            }
        }
        narration = "The investment framework involves three key steps: research, invest, and review."

        result = check_3step_framework_alignment(dts, narration)
        assert result["applicable"] is True
        assert result["aligned"] is False
        assert "misaligned" in result["reason"].lower() or "insufficient" in result["reason"].lower()

    def test_non_3step_framework_skips(self):
        """Non-3-step frameworks should skip 3-step alignment check."""
        dts = {
            "template_type": "comparison_card",
            "content": {
                "left_column": {"title": "Before", "items": ["A"]},
                "right_column": {"title": "After", "items": ["B"]}
            }
        }
        narration = "Any narration here"

        result = check_3step_framework_alignment(dts, narration)
        assert result["applicable"] is False


# ============================================================================
# Graphic Unit Evaluation Tests
# ============================================================================

class TestGraphicUnitEvaluation:
    """Tests for complete graphic unit evaluation."""

    def test_black_title_card_fails(self):
        """Black title card should fail with BLOCKED error."""
        ru = {
            "id": "graphic_1",
            "label": "intro_card",
            "ordinal": 0,
            "required_duration_ms": 3000,
            "metadata_json": json.dumps({
                "deterministic_text_spec": {
                    "text": "Title"
                }
            })
        }

        result = eval_graphic_unit(_with_graphic_provenance(ru))

        assert result["is_black_title_card"] is True
        assert result["alignment"] == "fail"
        assert "BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD" in result["alignment_reason"]

    def test_topic_misaligned_graphic_fails(self):
        """Topic-misaligned graphic should fail with BLOCKED error."""
        ru = {
            "id": "graphic_1",
            "label": "concept_card",
            "ordinal": 1,
            "required_duration_ms": 4000,
            "metadata_json": json.dumps({
                "deterministic_text_spec": {
                    "text": "Cooking pasta requires three steps: boil water, add pasta, drain",
                    "template_type": "framework_3_step"
                }
            })
        }

        result = eval_graphic_unit(_with_graphic_provenance(ru), "The investment strategy involves: research, invest, review")

        assert result["alignment"] == "fail"
        assert "BLOCKED_GRAPHIC_MISALIGNED" in result["alignment_reason"]

    def test_aligned_3step_passes(self):
        """Aligned 3-step framework should pass."""
        ru = {
            "id": "graphic_1",
            "label": "framework_card",
            "ordinal": 2,
            "required_duration_ms": 5000,
            "metadata_json": json.dumps({
                "deterministic_text_spec": {
                    "text": "Investment Framework: Research opportunities, Allocate capital, Monitor growth",
                    "template_type": "framework_3_step",
                    "content": {
                        "title": "Investment Framework",
                        "steps": [
                            {"label": "Research", "description": "Study market"},
                            {"label": "Invest", "description": "Allocate capital"},
                            {"label": "Monitor", "description": "Track performance"}
                        ]
                    }
                }
            })
        }

        result = eval_graphic_unit(_with_graphic_provenance(ru), "The investment framework helps you research opportunities, allocate capital wisely, and monitor performance growth")

        assert result["alignment"] == "pass"
        assert "aligned" in result["alignment_reason"].lower() or "meaningful" in result["alignment_reason"].lower()

    def test_professional_graphic_with_content_passes(self):
        """Professional graphic with meaningful content should pass."""
        ru = {
            "id": "graphic_1",
            "label": "comparison_card",
            "ordinal": 1,
            "required_duration_ms": 3000,
            "metadata_json": json.dumps({
                "deterministic_text_spec": {
                    "text": "Stocks vs Bonds: Risk and Return Comparison",
                    "template_type": "comparison_card"
                }
            })
        }

        result = eval_graphic_unit(_with_graphic_provenance(ru))

        assert result["is_black_title_card"] is False
        assert result["alignment"] in ["pass", "warn"]  # Warn allowed for weak but not black

    def test_weak_title_generates_warning(self):
        """Weak title should generate warning, not fail."""
        ru = {
            "id": "graphic_1",
            "label": "slide_1",
            "ordinal": 1,
            "required_duration_ms": 2000,
            "metadata_json": json.dumps({
                "deterministic_text_spec": {
                    "text": "Slide 1"
                }
            })
        }

        result = eval_graphic_unit(_with_graphic_provenance(ru))

        assert result["is_black_title_card"] is False
        assert result["is_weak_title"] is True
        assert result["alignment"] == "warn"


# ============================================================================
# Regression Tests
# ============================================================================

class TestExistingGraphicsTestsGreen:
    """Verify existing graphics tests remain green."""

    def test_no_import_errors(self):
        """Module should import without errors."""
        import evals.eval_graphic_qa
        assert hasattr(evals.eval_graphic_qa, 'eval_production')

    def test_function_signatures_compatible(self):
        """Function signatures should be compatible with existing eval scripts."""
        from evals.eval_graphic_qa import eval_production
        import inspect

        sig = inspect.signature(eval_production)
        params = list(sig.parameters.keys())
        assert 'production_id' in params
        assert 'db_path' in params


# ============================================================================
# Integration Tests
# ============================================================================

class TestSemanticIntegration:
    """Integration tests for semantic alignment with other systems."""

    def test_keywords_extraction_case_insensitive(self):
        """Keyword extraction should be case-insensitive."""
        kw1 = extract_keywords_from_text("Investment Strategy")
        kw2 = extract_keywords_from_text("investment strategy")
        assert kw1 == kw2

    def test_stop_words_filtered_correctly(self):
        """Common stop words should be filtered from keywords."""
        keywords = extract_keywords_from_text("The investment strategy for the future")
        # "the", "for", "the" should be filtered
        assert "the" not in keywords
        assert "for" not in keywords
        assert "investment" in keywords
        assert "strategy" in keywords
