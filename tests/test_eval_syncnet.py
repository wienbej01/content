"""Tests for SyncNet eval (S07-T001)."""
import json
from pathlib import Path

RESULT = Path("reports/karpathy_loop/sprint_07/S07_T001/eval_result_before.json")


class TestSyncNetEval:
    def test_exists(self):
        assert RESULT.exists()
        d = json.loads(RESULT.read_text())
        assert d["eval_id"] == "S07_T001_syncnet"

    def test_required_fields(self):
        d = json.loads(RESULT.read_text())
        assert "syncnet_available" in d
        assert "dependencies" in d
        assert "overall" in d
        assert "syncnet_setup_instructions" in d

    def test_blocked_without_syncnet(self):
        d = json.loads(RESULT.read_text())
        if not d.get("syncnet_available"):
            assert d["overall"] == "BLOCKED_NEEDS_SYNCNET"
            assert len(d.get("syncnet_setup_instructions", "")) > 100

    def test_baseline_canary_exist(self):
        d = json.loads(RESULT.read_text())
        assert d["baseline_exists"] is True
        assert d["canary_exists"] is True

    def test_audio_correlation_present(self):
        d = json.loads(RESULT.read_text())
        assert "audio_cross_correlation" in d

    def test_no_render_path(self):
        with open("scripts/evals/eval_syncnet.py") as f:
            code = f.read()
        assert "higgsfield generate create" not in code
        assert "HIGGSFIELD_DRY_RUN=0" not in code
