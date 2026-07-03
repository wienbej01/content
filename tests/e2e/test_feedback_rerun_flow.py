"""E2E tests for S22_T020: feedback-driven rerun flow.

Validates end-to-end that invalidation produces correct stage state transitions
and that the correct stages re-run after invalidation in YT_TEST_MODE.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT / "tests" / "e2e"))
sys.path.insert(0, str(SCRIPTS))

from s8_helpers import build_production, run_to_completion, latest_stage_status

import production_db as _db
import rerun_planner
from rerun_planner import ChangeRequest, plan_and_apply


@pytest.mark.slow
class TestFeedbackRerunFlow:
    """E2E: invalidation plans execute correctly in a real DB."""

    def test_shot_repair_rerun_chain(self, monkeypatch):
        """After shot repair invalidation, the correct stages re-execute."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_shot_repair")

        # Run to completion first
        assert run_to_completion(pid), "initial production failed"

        # Verify baseline: all stages succeeded
        assert latest_stage_status(pid, "assemble") == "succeeded"

        # Create a change request for a shot repair
        change = ChangeRequest(
            entity_type="shot",
            entity_id="ru_test_shot",
            reason="shot repair: visual quality",
        )

        # Apply invalidation
        result = plan_and_apply(pid, change, db_path=None)
        assert result["stages_staled"] > 0
        assert "compile_media" in result["next_actions"]

        # Resume — should re-run from compile_media through gate_b_review
        assert run_to_completion(pid), "resume after shot repair failed"
        assert latest_stage_status(pid, "assemble") == "succeeded"
        assert latest_stage_status(pid, "gate_b_review") == "succeeded"

    def test_overlay_repair_rerun_chain(self, monkeypatch):
        """After overlay repair, only graphics + assembly stages re-run."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_overlay_repair")

        assert run_to_completion(pid), "initial production failed"
        assert latest_stage_status(pid, "assemble") == "succeeded"

        change = ChangeRequest(
            entity_type="overlay",
            entity_id="ru_test_overlay",
            reason="overlay text corrected",
        )
        result = plan_and_apply(pid, change, db_path=None)
        assert result["stages_staled"] > 0

        # Graphics compositing and downstream should re-run
        assert "graphics_compositing" in result["next_actions"]
        # But generate_media should NOT be in next actions
        assert "generate_media" not in result["next_actions"]

        assert run_to_completion(pid), "resume after overlay repair failed"
        assert latest_stage_status(pid, "gate_b_review") == "succeeded"

    def test_media_drift_rerun_chain(self, monkeypatch):
        """After media drift detection, qa_media + assembly re-run."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_media_drift")

        assert run_to_completion(pid), "initial production failed"
        assert latest_stage_status(pid, "assemble") == "succeeded"

        change = ChangeRequest(
            entity_type="media_artifact",
            entity_id="art_drift",
            reason="observed duration 5.1s vs planned 4.2s",
        )
        result = plan_and_apply(pid, change, db_path=None)
        assert result["stages_staled"] > 0

        assert "qa_media" in result["next_actions"]
        assert "assemble" in result["next_actions"]
        # generate_media and compile_media must not re-run
        assert "generate_media" not in result["next_actions"]
        assert "compile_media" not in result["next_actions"]

        assert run_to_completion(pid), "resume after media drift failed"
        assert latest_stage_status(pid, "gate_b_review") == "succeeded"

    def test_storyboard_revision_rerun_chain(self, monkeypatch):
        """After storyboard revision, full downstream chain re-runs."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_sb_revision")

        assert run_to_completion(pid), "initial production failed"

        change = ChangeRequest(
            entity_type="storyboard_revision",
            entity_id="doc_sb_latest",
            reason="storyboard updated for narrative alignment",
        )
        result = plan_and_apply(pid, change, db_path=None)
        assert result["stages_staled"] > 0

        assert "gate_storyboard" in result["next_actions"]
        assert "tts" in result["next_actions"]
        assert "compile_media" in result["next_actions"]

        assert run_to_completion(pid), "resume after storyboard revision failed"
        assert latest_stage_status(pid, "assemble") == "succeeded"

    def test_unaffected_assets_survive(self, monkeypatch):
        """After shot repair, early-stage stage_runs remain succeeded."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_unaffected")

        assert run_to_completion(pid), "initial production failed"

        change = ChangeRequest(
            entity_type="shot",
            entity_id="ru_unaffected_test",
            reason="shot repair",
        )
        plan_and_apply(pid, change, db_path=None)

        # Pre-compile stages must remain succeeded
        conn = _db.connect(None)
        for stage in ["research", "write_script", "review_script",
                       "storyboard", "gate_storyboard", "tts", "audio_timing"]:
            row = conn.execute(
                "SELECT status FROM stage_runs WHERE production_id=? AND stage_name=?",
                (pid, stage),
            ).fetchone()
            assert row is not None, f"stage {stage} missing"
            assert row["status"] == "succeeded", \
                f"stage {stage} was incorrectly staled (got {row['status']})"
        conn.close()

    def test_stale_approvals_blocked_after_invalidation(self, monkeypatch):
        """After invalidation, stale approvals cannot pass."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_stale_approval")

        assert run_to_completion(pid), "initial production failed"

        # Check that approvals were set up
        conn = _db.connect(None)
        approvals = conn.execute(
            "SELECT gate_name, status FROM approval_requests WHERE production_id=?",
            (pid,),
        ).fetchall()
        conn.close()
        assert any(r["status"] == "pass" for r in approvals), \
            "expected at least one passing approval"

        change = ChangeRequest(
            entity_type="storyboard_revision",
            entity_id="doc_sb_001",
            reason="storyboard updated",
        )
        plan_and_apply(pid, change, db_path=None)

        conn = _db.connect(None)
        stale_approvals = conn.execute(
            "SELECT gate_name, status FROM approval_requests "
            "WHERE production_id=? AND status='stale'",
            (pid,),
        ).fetchall()
        conn.close()
        assert len(stale_approvals) > 0, "no approvals were staled"
        # gate_storyboard must be staled for a storyboard revision
        stale_names = {r["gate_name"] for r in stale_approvals}
        assert "gate_storyboard" in stale_names

    def test_idempotent_resume(self, monkeypatch):
        """Running invalidation + resume twice is stable."""
        monkeypatch.setenv("YT_TEST_MODE", "1")
        pid, slug, project_dir = build_production("s22_t020_idempotent_resume")

        assert run_to_completion(pid), "initial production failed"

        change = ChangeRequest(
            entity_type="shot",
            entity_id="ru_idem_e2e",
            reason="shot repair",
        )

        result1 = plan_and_apply(pid, change, db_path=None)
        # Apply again — same invalidation
        result2 = plan_and_apply(pid, change, db_path=None)

        # Both should produce the same next actions
        assert result1["next_actions"] == result2["next_actions"]

        # Resume after first invalidation
        assert run_to_completion(pid), "first resume failed"
        # Resume a second time — should be idempotent
        assert run_to_completion(pid), "second resume failed"
        assert latest_stage_status(pid, "assemble") == "succeeded"
