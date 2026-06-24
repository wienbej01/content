"""Tests for readiness scorecard (S06-T001)."""
import json
from pathlib import Path

RESULT = Path("reports/karpathy_loop/sprint_06/S06_T001/eval_result_before.json")


class TestReadinessScorecard:
    def test_exists(self):
        assert RESULT.exists()
        data = json.loads(RESULT.read_text())
        assert data["eval_id"] == "S06_T001_readiness_scorecard"

    def test_required_fields(self):
        data = json.loads(RESULT.read_text())
        assert "ready_for_actual_render" in data
        assert "ready_for_canary_unlock" in data
        assert "passed_sprints" in data
        assert "missing_requirements" in data
        assert "recommendation" in data

    def test_core_checks_pass(self):
        data = json.loads(RESULT.read_text())
        assert data["ready_for_canary_unlock"] is True

    def test_recommendation_valid(self):
        data = json.loads(RESULT.read_text())
        assert data["recommendation"] in ("remain_locked", "allow_one_canary")

    def test_unlock_instructions_present(self):
        data = json.loads(RESULT.read_text())
        assert len(data.get("unlock_instructions", "")) > 50
