"""Tests for Gate B evidence pack (S05-T003)."""
import json
from pathlib import Path

import pytest

RESULT = Path("reports/karpathy_loop/sprint_05/S05_T003/eval_result_before.json")


class TestEvidencePack:
    def test_exists(self):
        assert RESULT.exists()
        data = json.loads(RESULT.read_text())
        assert data["gate"] == "B"
        assert data["production_id"] == "prod_2f9bb58c0508465fb51ac6b4578bba92"

    def test_required_sections(self):
        data = json.loads(RESULT.read_text())
        assert "lipsync_eval_summary" in data
        assert "audio_provenance_summary" in data
        assert "graphics_text_summary" in data
        assert "assembly_transform_summary" in data
        assert "artifact_paths" in data
        assert "unresolved_defects" in data
        assert "recommendation" in data
        assert "render_lock_status" in data

    def test_artifact_paths(self):
        data = json.loads(RESULT.read_text())
        assert data["artifact_paths"]["final_mp4_size_bytes"] > 0
        assert data["artifact_paths"]["final_mp4_sha256"] is not None

    def test_recommendation_valid(self):
        data = json.loads(RESULT.read_text())
        assert data["recommendation"] in ("approve", "reject", "rerender_canary")

    def test_lipsync_provisional(self):
        data = json.loads(RESULT.read_text())
        assert data["lipsync_eval_summary"]["provisional"] is True

    def test_render_lock(self):
        data = json.loads(RESULT.read_text())
        assert data["render_lock_status"] == "PASS"

    def test_defects_present(self):
        data = json.loads(RESULT.read_text())
        assert data["defects_total"] >= 10
