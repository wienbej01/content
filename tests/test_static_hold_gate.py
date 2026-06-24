"""Tests for static graphic hold gate (S03-T003)."""
from pathlib import Path
import logging

import pytest

import production_db as _db
from assemble_db import _validate_timeline_heuristics, AssemblyError
from scripts.evals.eval_static_hold import eval_production, WARN_MS, FAIL_MS

HAS_DB = Path("db/production.db").exists()


class TestThresholdConstants:
    """Threshold values are correct."""

    def test_warn_threshold_correct(self):
        assert WARN_MS == 4000, f"Expected 4000ms, got {WARN_MS}"

    def test_fail_threshold_correct(self):
        assert FAIL_MS == 6000, f"Expected 6000ms, got {FAIL_MS}"

    def test_fail_greater_than_warn(self):
        assert FAIL_MS > WARN_MS


class TestValidateTimelineHeuristics:
    """_validate_timeline_heuristics reactions to different hold durations."""

    def _make_unit(self, dur_ms, label="S003", asset_type="local_graphic"):
        return {"id": f"ru_{dur_ms}", "label": label, "asset_type": asset_type,
                "required_duration_ms": dur_ms, "ordinal": 1, "timeline_span_id": None}

    def test_short_hold_passes(self):
        """Hold under 4s passes."""
        u = self._make_unit(3000)
        _validate_timeline_heuristics([u])  # should not raise

    def test_hold_between_warn_and_fail_warns(self, caplog):
        """Hold between 4s and 6s logs a warning but doesn't raise."""
        u = self._make_unit(5000)
        with caplog.at_level(logging.WARNING):
            _validate_timeline_heuristics([u])
        assert len(caplog.records) >= 1
        assert any("exceeds" in r.getMessage() for r in caplog.records)

    def test_hold_over_fail_raises(self):
        """Hold over 6s raises AssemblyError."""
        u = self._make_unit(7000)
        with pytest.raises(AssemblyError, match="BLOCKED"):
            _validate_timeline_heuristics([u])

    def test_hold_over_fail_with_hold_marker_passes(self):
        """Hold over 6s with 'hold' in label passes."""
        u = self._make_unit(7000, label="S003_hold")
        _validate_timeline_heuristics([u])  # should not raise

    def test_non_graphic_bypasses(self):
        """Non-graphic units are not checked."""
        u = self._make_unit(10000, asset_type="generated_video")
        _validate_timeline_heuristics([u])  # should not raise


class TestEvalStaticHold:
    """Eval detects excessive holds."""

    def test_eval_real_production(self):
        """Bad fixture should show at least warn status for 7s hold."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        result = eval_production("prod_2f9bb58c0508465fb51ac6b4578bba92")
        assert result["status"] in ("fail", "warn")
        assert any(r["duration_ms"] >= FAIL_MS for r in result["results"])
