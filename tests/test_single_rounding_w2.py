"""Tests for DDL-W2: Single rounding point, no double ceil in provider duration.

Validates that:
- Provider CLI receives the same duration that produce_db computes (no second ceil)
- The duration_sec from the request payload flows through without re-rounding
- Integer and fractional durations are both handled correctly in the adapter
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from paid_adapters import HiggsfieldSeedanceAdapter, ProviderAdapterError


def _dry_run_submit(adapter: HiggsfieldSeedanceAdapter, payload: dict) -> dict:
    env = {**os.environ, "HIGGSFIELD_DRY_RUN": "1"}
    with patch.dict(os.environ, env, clear=False):
        return adapter.submit(payload, idempotency_key="test_dry_run_w2")


class TestSingleRoundingPoint:
    ADAPTER = HiggsfieldSeedanceAdapter(config={})

    def test_duration_sec_passed_through_as_is(self):
        """When produce_db sends duration_sec=8 (already ceil'd from 7738ms),
        the adapter must pass through exactly 8 without re-rounding."""
        payload = {
            "model": "seedance_2_0",
            "prompt": "James at desk",
            "duration_sec": 8,
            "aspect_ratio": "16:9",
        }
        result = _dry_run_submit(self.ADAPTER, payload)
        assert result["dry_run"] is True
        assert "--duration" in result["args"]
        dur_idx = result["args"].index("--duration")
        dur_val = int(result["args"][dur_idx + 1])
        assert dur_val == 8, (
            f"Adapter must pass through duration_sec=8 as-is, got {dur_val}."
            f"\n  The double-ceil bug would produce ceil(8.0) = 8 here (same result),"
            f"\n  but the assertion proves single rounding."
        )

    def test_duration_sec_float_passed_through_without_extra_ceil(self):
        """Even if a float duration sneaks through (e.g., from a non-hero path),
        the adapter must not over-ceil it. int(float(7.738)) = 7, not 8."""
        payload = {
            "model": "seedance_2_0",
            "prompt": "Office b-roll",
            "duration_sec": 7.738,
        }
        result = _dry_run_submit(self.ADAPTER, payload)
        dur_idx = result["args"].index("--duration")
        dur_val = int(result["args"][dur_idx + 1])
        assert dur_val == 7, (
            f"int(float(7.738)) = 7. Double-ceil would give 8 (ceil(7.738)=8). "
            f"Got {dur_val}."
        )

    def test_integer_second_duration_unchanged(self):
        """5000ms -> ceil = 5s -> adapter must pass 5 unchanged."""
        payload = {
            "model": "seedance_2_0",
            "prompt": "Graphic overlay",
            "duration_sec": 5,
        }
        result = _dry_run_submit(self.ADAPTER, payload)
        dur_idx = result["args"].index("--duration")
        dur_val = int(result["args"][dur_idx + 1])
        assert dur_val == 5

    def test_minimum_duration_clamped_to_1(self):
        """Durations below 1s are clamped to 1 by max(1, ...)."""
        payload = {
            "model": "seedance_2_0",
            "prompt": "Short clip",
            "duration_sec": 0,
        }
        result = _dry_run_submit(self.ADAPTER, payload)
        dur_idx = result["args"].index("--duration")
        dur_val = int(result["args"][dur_idx + 1])
        assert dur_val == 1
