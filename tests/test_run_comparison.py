"""Tests for run comparison report (S05-T002)."""
import json
from pathlib import Path

import pytest

RESULT = Path("reports/karpathy_loop/sprint_05/S05_T002/eval_result_before.json")


class TestReportStructure:
    """Report has required fields."""

    def test_report_exists(self):
        assert RESULT.exists(), "Report not found"
        data = json.loads(RESULT.read_text())
        assert "production_id" in data
        assert "fixture" in data
        assert "candidate_available" in data
        assert "baseline_count" in data
        assert "baseline_results" in data
        assert "comparison" in data

    def test_no_candidate(self):
        data = json.loads(RESULT.read_text())
        assert data["candidate_available"] is False
        assert data["comparison"]["status"] == "baseline_only"

    def test_baseline_results_present(self):
        data = json.loads(RESULT.read_text())
        assert data["baseline_count"] >= 5
        assert len(data["baseline_results"]) == data["baseline_count"]

    def test_each_result_has_required_fields(self):
        data = json.loads(RESULT.read_text())
        required = {"eval_name", "script", "success", "result"}
        for r in data["baseline_results"]:
            missing = required - set(r.keys())
            assert len(missing) == 0, f"Result {r.get('eval_name','?')} missing: {missing}"

    def test_baseline_passed_majority(self):
        data = json.loads(RESULT.read_text())
        assert data["baseline_passed"] >= data["baseline_count"] * 0.5


class TestPassGate:
    """Report clearly shows baseline failures and candidate status."""

    def test_candidate_status_clear(self):
        data = json.loads(RESULT.read_text())
        assert data["candidate_available"] is False
        assert "no candidate" in data.get("candidate_note", "").lower() or \
               "render lock" in data.get("candidate_note", "").lower()

    def test_baseline_failures_documented(self):
        data = json.loads(RESULT.read_text())
        for r in data["baseline_results"]:
            if not r["success"]:
                assert r.get("error") or r.get("stdout"), \
                    f"Failed eval {r['eval_name']} missing error details"
