"""Tests for dry-run provider request audit (S06-T002)."""
import json
from pathlib import Path

RESULT = Path("reports/karpathy_loop/sprint_06/S06_T002/eval_result_before.json")


class TestDryRunAudit:
    def test_exists(self):
        assert RESULT.exists()
        data = json.loads(RESULT.read_text())
        assert data["eval_id"] == "S06_T002_dry_run_audit"

    def test_required_fields(self):
        data = json.loads(RESULT.read_text())
        assert "dry_run" in data
        assert "would_submit_provider_job" in data
        assert "payload_hash" in data
        assert "audio_sha256_verified" in data
        assert "prompt_policy_ok" in data
        assert "issues" in data

    def test_dry_run_active(self):
        data = json.loads(RESULT.read_text())
        assert data["dry_run"] is True

    def test_no_external_job(self):
        data = json.loads(RESULT.read_text())
        assert data["would_submit_provider_job"] is False

    def test_audio_verified(self):
        data = json.loads(RESULT.read_text())
        assert data["audio_sha256_verified"] is True

    def test_prompt_clean(self):
        data = json.loads(RESULT.read_text())
        assert data["prompt_policy_ok"] is True
