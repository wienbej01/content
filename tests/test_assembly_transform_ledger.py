"""Tests for assembly transform ledger (S02-T001)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.evals.assembly_transform_ledger import (
    build_ledger_from_render_units, _classify_transforms,
)
HAS_DB = Path("db/production.db").exists()


class TestClassifyTransforms:
    """Transform classification for different clip types."""

    def test_hero_lipsync_transforms(self):
        """HERO_SYNC_LOCKED lipsync unit has specific transforms."""
        tx = _classify_transforms("lipsync_video", "HERO_SYNC_LOCKED", 1, True, 5000)
        assert "scale_crop" in tx["operations"]
        assert "mute_audio" in tx["operations"]
        assert "replace_audio" in tx["operations"]
        assert "speed_change" in tx["forbidden_operations"]
        assert "setpts" in tx["forbidden_operations"]
        assert tx["forbidden_hero_operation_detected"] is False

    def test_still_image_transforms(self):
        """Still images use loop_still."""
        tx = _classify_transforms("still_image", "NARRATION_OVERLAY", 0, False)
        assert "loop_still" in tx["operations"]
        assert "speed_change" in tx["forbidden_operations"]

    def test_local_graphic_transforms(self):
        """Local graphics use drawtext_overlay."""
        tx = _classify_transforms("local_graphic", "DETERMINISTIC_GRAPHIC", 0, False)
        assert "drawtext_overlay" in tx["operations"]
        assert "fade_in" in tx["operations"]

    def test_broll_flex_transforms(self):
        """BROLL_FLEX units are muted with narration overlay."""
        tx = _classify_transforms("generated_video", "BROLL_FLEX", 0, False)
        assert "mute_audio" in tx["operations"]
        assert "scale_crop" in tx["operations"]

    def test_forbidden_hero_not_detected_by_default(self):
        """No forbidden operations detected when none applied."""
        tx = _classify_transforms("lipsync_video", "HERO_SYNC_LOCKED", 1, True, 3000)
        assert tx["forbidden_hero_operation_detected"] is False


class TestLedgerFromDB:
    """Build ledger from production DB."""

    def test_ledger_has_expected_structure(self):
        """Ledger contains required fields for all clips."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        ledger = build_ledger_from_render_units(
            "prod_2f9bb58c0508465fb51ac6b4578bba92"
        )
        assert "production_id" in ledger
        assert "clips" in ledger
        assert ledger["clip_count"] > 0
        clip = ledger["clips"][0]
        assert "render_unit_id" in clip
        assert "source_artifact" in clip or "source_artifact_id" in clip
        assert "start_ms" in clip
        assert "end_ms" in clip
        assert "operations" in clip
        assert "forbidden_hero_operation_detected" in clip

    def test_hero_units_marked_correctly(self):
        """HERO_SYNC_LOCKED units are marked as hero lipsync."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        ledger = build_ledger_from_render_units(
            "prod_2f9bb58c0508465fb51ac6b4578bba92"
        )
        hero_units = [c for c in ledger["clips"] if c["is_hero_lipsync"]]
        assert len(hero_units) >= 2, "Expected at least 2 hero units"
        for h in hero_units:
            assert "mute_audio" in h["operations"]
            assert "replace_audio" in h["operations"]

    def test_no_forbidden_ops_in_current_assembly(self):
        """Current assembly should not have forbidden hero operations."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        ledger = build_ledger_from_render_units(
            "prod_2f9bb58c0508465fb51ac6b4578bba92"
        )
        assert ledger["forbidden_operations_count"] == 0, (
            "Assembly should not have forbidden hero operations"
        )


class TestCLI:
    """CLI integration tests."""

    def test_cli_output(self, tmp_path):
        """CLI produces valid JSON ledger."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        out = tmp_path / "ledger.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/assembly_transform_ledger.py",
             "--production-id", "prod_2f9bb58c0508465fb51ac6b4578bba92",
             "--output", str(out)],
            capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 0, f"CLI failed: {r.stderr}"
        assert out.exists()
        data = json.loads(out.read_text())
        assert "clips" in data
        assert len(data["clips"]) > 0

    def test_cli_missing_production_id(self, tmp_path):
        """CLI fails without production-id."""
        out = tmp_path / "ledger.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/assembly_transform_ledger.py",
             "--output", str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
