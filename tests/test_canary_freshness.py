"""Tests for canary freshness gate (S06_FIX_T003)."""
import json
from pathlib import Path

import pytest

RESULT = Path("/tmp/canary_freshness_check.json")


class TestFreshnessEvalStructure:
    def test_exists(self):
        assert RESULT.exists()
        data = json.loads(RESULT.read_text())
        assert data["eval_id"] == "S06_FIX_T003_canary_freshness"

    def test_required_fields(self):
        data = json.loads(RESULT.read_text())
        assert "fresh" in data
        assert "overall" in data
        assert "checks" in data
        assert "issues" in data

    def test_overall_valid_values(self):
        data = json.loads(RESULT.read_text())
        assert data["overall"] in ("PASS_FRESH_CANARY", "ACTUAL_CANARY_RENDER_NOT_EXECUTED",
                                   "BLOCKED_NEEDS_FRESH_CANARY_RENDER", "IDEMPOTENCY_REUSE_CHECK_PASS")


class TestInvalidPriorAttempt:
    """The prior S06_T003 attempt should be classified as invalid."""

    def test_prior_attempt_not_fresh(self):
        data = json.loads(RESULT.read_text())
        assert data["fresh"] is False

    def test_prior_attempt_blocked(self):
        data = json.loads(RESULT.read_text())
        assert data["overall"] == "BLOCKED_NEEDS_FRESH_CANARY_RENDER"

    def test_missing_attempt_id_flagged(self):
        data = json.loads(RESULT.read_text())
        missing = [c for c in data["checks"] if c["check"] == "unlock_has_canary_attempt_id"]
        assert len(missing) == 1
        assert missing[0]["pass"] is False
