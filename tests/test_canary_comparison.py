"""Tests for baseline-vs-canary comparison (S06-T004)."""
import json
from pathlib import Path

RESULT = Path("reports/karpathy_loop/sprint_06/S06_T004/eval_result_before.json")


class TestComparisonStructure:
    def test_exists(self):
        assert RESULT.exists()
        data = json.loads(RESULT.read_text())
        assert "production_id" in data

    def test_baseline_section(self):
        data = json.loads(RESULT.read_text())
        assert "baseline" in data
        assert "path" in data["baseline"]

    def test_canary_section(self):
        data = json.loads(RESULT.read_text())
        assert "canary" in data
        assert "path" in data["canary"]

    def test_provenance_section(self):
        data = json.loads(RESULT.read_text())
        assert "provenance" in data
        assert "source_slice_sha256" in data["provenance"]

    def test_lipsync_section(self):
        data = json.loads(RESULT.read_text())
        assert "lipsync" in data
        assert "baseline_offset_ms" in data["lipsync"]
        assert "canary_offset_ms" in data["lipsync"]

    def test_findings_list(self):
        data = json.loads(RESULT.read_text())
        assert len(data["findings"]) >= 3

    def test_decision_present(self):
        data = json.loads(RESULT.read_text())
        assert "decision" in data
        assert data["decision"] in (
            "PASS_FORENSIC_COMPLETED", "FAIL_NEEDS_REPAIR",
            "FAIL_NEEDS_RESYNC", "FAIL_NEEDS_PROVIDER_RERENDER",
            "BLOCKED_NEEDS_SYNCNET"
        )

    def test_canary_has_audio(self):
        data = json.loads(RESULT.read_text())
        assert data["canary"]["audio"] is not None

    def test_no_publishable(self):
        """Canary should NOT be marked publishable."""
        data = json.loads(RESULT.read_text())
        assert data.get("decision") != "PASS_FORENSIC_COMPLETED"
        assert data["decision"] in (
            "FAIL_NEEDS_REPAIR", "FAIL_NEEDS_RESYNC",
            "FAIL_NEEDS_PROVIDER_RERENDER", "BLOCKED_NEEDS_SYNCNET"
        )
