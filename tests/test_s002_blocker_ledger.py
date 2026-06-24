"""Tests for S002 blocker ledger entry (Sprint 09)."""
import json
from pathlib import Path

LEDGER = Path("reports/karpathy_loop/sprint_09/s002_blocker_ledger.json")


class TestS002BlockerLedger:
    def test_ledger_exists(self):
        assert LEDGER.exists()
        data = json.loads(LEDGER.read_text())
        assert data["blocker_id"] == "S002_HERO_SYNC_FAILED_OR_UNVERIFIED"

    def test_severity_is_blocker(self):
        data = json.loads(LEDGER.read_text())
        assert data["severity"] == "blocker"

    def test_s002_unit_identified(self):
        data = json.loads(LEDGER.read_text())
        assert "S002" in data.get("label", "")
        assert data["render_unit_id"] is not None

    def test_syncnet_evidence_recorded(self):
        data = json.loads(LEDGER.read_text())
        ev = data.get("evidence", {})
        assert ev.get("syncnet_offset_ms") is not None
        assert ev.get("syncnet_confidence") is not None
        assert ev.get("has_passing_validation") is False
        assert abs(ev.get("syncnet_offset_ms", 0)) >= 160

    def test_next_action_defined(self):
        data = json.loads(LEDGER.read_text())
        assert "CONTROLLED_S002_CANARY_RENDER" in data.get("next_required_action", "")

    def test_known_good_analog_present(self):
        data = json.loads(LEDGER.read_text())
        analog = data.get("known_good_analog", {})
        assert analog.get("unit") == "S000"
        assert analog.get("status") == "PASS"

    def test_timestamps_present(self):
        data = json.loads(LEDGER.read_text())
        assert data.get("created_at") is not None
        assert "resolved_at" in data
