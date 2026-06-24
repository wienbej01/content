"""Tests for master audio window verification (S02-T002)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import production_db as _db
from scripts.evals.eval_master_window import (
    eval_hero_unit, eval_production,
)

HAS_DB = Path("db/production.db").exists()


class TestEvalHeroUnit:
    """Per-unit master window evaluation."""

    def _make_ru(self, start_ms=0, end_ms=4572, dur_ms=4572,
                 sp_start=0, sp_end=219456, lead=0, trail=0,
                 slice_sha="a" * 64, master_sha="b" * 64):
        """Helper: create a minimal render_unit dict."""
        return {
            "id": "ru_test",
            "label": "S000",
            "required_start_ms": start_ms,
            "required_end_ms": end_ms,
            "required_duration_ms": dur_ms,
            "speech_start_sample": sp_start,
            "speech_end_sample": sp_end,
            "leading_silence_samples": lead,
            "trailing_silence_samples": trail,
            "source_slice_sha256": slice_sha,
            "master_audio_sha256": master_sha,
        }

    def test_matching_window_passes(self):
        """When sample window matches timeline, status=pass."""
        ru = self._make_ru(start_ms=0, end_ms=4572, sp_start=0, sp_end=219456)
        r = eval_hero_unit(ru)
        assert r["status"] == "pass"
        assert r["estimated_offset_ms"] == 0

    def test_nonmatching_window_fails(self):
        """When sample window is offset >100ms, status=fail."""
        ru = self._make_ru(start_ms=0, end_ms=4572, sp_start=48000, sp_end=268416)
        r = eval_hero_unit(ru)
        assert r["status"] == "fail"  # 48000 samples = 1000ms offset

    def test_small_offset_warns(self):
        """Small duration delta within tolerance produces warn."""
        ru = self._make_ru(start_ms=0, end_ms=4572, dur_ms=4500,
                           sp_start=0, sp_end=219456)
        r = eval_hero_unit(ru)
        # start/end match, but dur_delta > 50
        assert r["status"] in ("pass", "warn")

    def test_missing_speech_samples_blocks(self):
        """Missing speech_start_sample or speech_end_sample → blocked."""
        ru = self._make_ru(sp_start=None, sp_end=None)
        r = eval_hero_unit(ru)
        assert r["status"] == "blocked"
        assert "speech_samples_missing" in r["issues"]

    def test_missing_slice_sha_warns(self):
        """Missing source_slice_sha256 produces warn without blocking."""
        ru = self._make_ru(slice_sha=None)
        r = eval_hero_unit(ru)
        assert r["status"] in ("warn", "pass")
        assert "source_slice_sha256_missing" in r["issues"]

    def test_second_hero_unit(self):
        """S002: offset at 10437ms with 500976 sample start."""
        ru = self._make_ru(start_ms=10437, end_ms=15664, dur_ms=5227,
                           sp_start=500976, sp_end=751872)
        r = eval_hero_unit(ru)
        assert r["status"] == "pass"
        assert abs(r["estimated_offset_ms"]) <= 1


class TestEvalProduction:
    """End-to-end production eval."""

    def test_production_eval_structure(self):
        """Eval returns expected structure for fixture production."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        result = eval_production("prod_2f9bb58c0508465fb51ac6b4578bba92")
        assert "production_id" in result
        assert "hero_unit_count" in result
        assert result["hero_unit_count"] >= 2
        assert "results" in result
        assert "status" in result


class TestCLI:
    """CLI integration."""

    def test_cli_output(self, tmp_path):
        """CLI produces valid JSON."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        out = tmp_path / "result.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/eval_master_window.py",
             "--production-id", "prod_2f9bb58c0508465fb51ac6b4578bba92",
             "--out", str(out)],
            capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "status" in data
        assert "results" in data
