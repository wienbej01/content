"""Tests for actual render canary (S06-T003)."""
import json
from pathlib import Path

RESULT = Path("reports/karpathy_loop/sprint_06/S06_T003/eval_result_before.json")


class TestCanaryEvidence:
    def test_exists(self):
        assert RESULT.exists()
        data = json.loads(RESULT.read_text())
        assert "provider_job_id" in data
        assert "external_job_id" in data

    def test_external_job_present(self):
        data = json.loads(RESULT.read_text())
        assert len(data.get("external_job_id", "")) > 0

    def test_source_slice_sha_present(self):
        data = json.loads(RESULT.read_text())
        assert len(data.get("source_slice_sha256", "")) > 0

    def test_idempotency_key_present(self):
        data = json.loads(RESULT.read_text())
        assert len(data.get("idempotency_key", "")) > 0

    def test_env_snapshot(self):
        data = json.loads(RESULT.read_text())
        assert "env" in data
        assert data["env"]["HIGGSFIELD_DRY_RUN"] == "0"
        assert data["env"]["YT_TEST_MODE"] == "1"
