"""Tests for final defect ledger (S05-T001)."""
import json
from pathlib import Path

import pytest

from scripts.evals.eval_final_defect_ledger import consolidate

LEDGER_PATH = Path("reports/karpathy_loop/sprint_05/S05_T001/eval_result_before.json")
HAS_LEDGER = LEDGER_PATH.exists()


class TestLedgerStructure:
    """Ledger has required top-level fields."""

    def test_ledger_exists(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        assert LEDGER_PATH.exists()
        data = json.loads(LEDGER_PATH.read_text())
        assert "production_id" in data
        assert "deliverable_id" in data
        assert "overall_status" in data
        assert "defects" in data
        assert "metrics" in data
        assert "evidence_files" in data

    def test_production_id_correct(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert data["production_id"] == "prod_2f9bb58c0508465fb51ac6b4578bba92"

    def test_deliverable_id_present(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert len(data.get("deliverable_id", "")) > 0

    def test_overall_status_valid(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert data["overall_status"] in ("pass", "fail", "human_review_required")

    def test_defects_is_list(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert isinstance(data["defects"], list)

    def test_metrics_is_dict(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert isinstance(data["metrics"], dict)

    def test_evidence_files_is_list(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert isinstance(data["evidence_files"], list)


class TestDefects:
    """Defect entries have required fields."""

    def test_all_original_defects_present(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        # Should have at least 10 defects (from open_defects)
        assert len(data["defects"]) >= 10

    def test_each_defect_has_required_fields(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        required = {"failure_class", "severity", "description", "resolved_by_sprint", "detected_in"}
        for d in data["defects"]:
            missing = required - set(d.keys())
            assert len(missing) == 0, f"Defect {d.get('failure_class','?')} missing: {missing}"


class TestMetrics:
    """Metrics are populated."""

    def test_fixture_exists(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert data["metrics"].get("fixture_exists") is True

    def test_render_lock_reported(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert data["metrics"].get("render_lock_status") in ("PASS", "FAIL")

    def test_eval_scripts_counted(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        assert data["metrics"].get("eval_scripts_count", 0) >= 6


class TestPassGate:
    """Final QA fails or requires human review when evidence is missing/failing."""

    def test_ledger_does_not_fake_pass(self):
        if not HAS_LEDGER:
            pytest.skip("Ledger not yet generated")
        data = json.loads(LEDGER_PATH.read_text())
        # Overall status should NOT be 'pass' when there are open defects
        assert data["overall_status"] in ("fail", "human_review_required")
