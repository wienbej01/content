"""Tests for graphic editorial quality report (S03-T004)."""
from pathlib import Path

import pytest

from scripts.evals.eval_graphic_editorial import (
    classify_editorial_role, analyze_text_quality, analyze_duration,
    eval_unit, eval_production,
)

HAS_DB = Path("db/production.db").exists()


class TestClassifyRole:
    def test_summary_role(self):
        assert classify_editorial_role("KEY POINTS SUMMARY", 5000) == "summary"

    def test_transition_role(self):
        assert classify_editorial_role("COMING UP NEXT", 3000) == "transition"

    def test_contrast_role(self):
        assert classify_editorial_role("SLACK VS TEAMS", 5000) == "contrast"

    def test_callout_role(self):
        assert classify_editorial_role("COSTS $5000", 4000) == "callout"

    def test_setup_role(self):
        assert classify_editorial_role("AI NOTIFICATIONS", 3000) == "setup"

    def test_missing_text_role(self):
        assert classify_editorial_role("", 1000) == "missing"


class TestTextQuality:
    def test_empty_text(self):
        r = analyze_text_quality("")
        assert r["text_empty"] is True
        assert r["is_complete_thought"] is False

    def test_complete_thought(self):
        r = analyze_text_quality("WHICH COSTS MORE SLACK")
        assert r["text_empty"] is False
        assert r["is_complete_thought"] is True
        assert r["word_count"] == 4

    def test_incomplete_thought(self):
        r = analyze_text_quality("SLACK")
        assert r["is_complete_thought"] is False


class TestDuration:
    def test_short_duration_not_readable(self):
        r = analyze_duration("AI NOTIFICATIONS", 500)
        assert r["duration_too_short"] is True

    def test_long_duration_excessive(self):
        r = analyze_duration("HI", 15000)
        assert r["duration_too_long"] is True

    def test_ok_duration(self):
        r = analyze_duration("WHICH COSTS MORE SLACK", 5000)
        assert r["duration_readable"] is True


class TestEvalUnit:
    def test_empty_text_is_weak(self):
        ru = {"id": "ru1", "label": "S003", "ordinal": 1, "required_duration_ms": 5000}
        dts = {"text": "", "type": "title_card"}
        result = eval_unit(ru, dts)
        assert result["is_weak"] is True
        assert result["text_empty"] is True

    def test_good_graphic_not_weak(self):
        ru = {"id": "ru2", "label": "S003", "ordinal": 2, "required_duration_ms": 4000}
        dts = {"text": "WHICH COSTS MORE SLACK", "type": "title_card"}
        result = eval_unit(ru, dts)
        assert result["is_weak"] is False

    def test_too_short_graphic_is_weak(self):
        ru = {"id": "ru3", "label": "S003", "ordinal": 3, "required_duration_ms": 100}
        dts = {"text": "AI NOTIFICATIONS", "type": "title_card"}
        result = eval_unit(ru, dts)
        assert result["is_weak"] is True
        assert result["duration_too_short"] is True


class TestEvalProduction:
    def test_bad_fixture_eval_returns_structure(self):
        if not HAS_DB:
            pytest.skip("Production DB not available")
        result = eval_production("prod_2f9bb58c0508465fb51ac6b4578bba92")
        assert "status" in result
        assert "graphics" in result
        # Non-stale graphic: has text "WHICH COSTS MORE: SLACK", 7167ms
        if result["count"] > 0:
            g = result["graphics"][0]
            assert g["graphic_id"]
            assert "editorial_role" in g
            assert "is_complete_thought" in g
