"""Tests for scripts/rerun_planner.py — S22_T020 downstream invalidation planner.

Per the ticket, 8 focused tests are required:
1. Shot repair stales compile, spend gate, generate for affected unit, QA,
   assemble, final QA, Gate B.
2. Overlay repair stales graphics_compositing, assemble, final QA, Gate B only.
3. Media artifact drift repair stales qa_media, assemble, final QA, Gate B.
4. Storyboard revision change stales storyboard approval and downstream.
5. Unaffected render unit remains valid.
6. Stale artifact reuse is blocked.
7. Planner emits deterministic next actions.
8. Running planner twice is idempotent.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import production_db as _db
import stage_runner
import rerun_planner
from rerun_planner import (
    ChangeRequest,
    InvalidationPlan,
    plan_shot_repair_invalidation,
    plan_overlay_repair_invalidation,
    plan_media_drift_invalidation,
    plan_storyboard_revision_invalidation,
    apply_invalidation,
    plan_and_apply,
)

# Must import production_repo for helpers
sys.path.insert(0, str(SCRIPTS))
import production_repo as _repo


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "test_rerun.db"
        os.environ["PRODUCTION_DB_PATH"] = str(p)
        _db.migrate(str(p))
        yield str(p)
        del os.environ["PRODUCTION_DB_PATH"]


def _make_production(db_path):
    return _db.ensure_production(
        "rerun_test_prod", seed="test seed", video_type="short", db_path=db_path
    )


def _seed_stages(production_id, slug, db_path):
    """Seed all stages as succeeded so we can test selective invalidation."""
    for stage_name in stage_runner.STAGE_REGISTRY:
        _db.mirror_stage_state(slug, stage_name, "done", db_path=db_path)


def _seed_approval(production_id, gate_name, db_path):
    """Insert a pass approval for a gate."""
    from production_repo import record_validation
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO approval_requests
               (id, production_id, gate_name, subject_sha256, status,
                requested_at, decided_at, actor)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                _db._id("approval"), production_id, gate_name,
                "sha_test", "pass", _db._now(), _db._now(), "test",
            ),
        )


def _seed_render_unit(production_id, db_path, asset_type="lipsync_video",
                      audio_policy="HERO_SYNC_LOCKED", label="R001"):
    """Create a timeline_span + render_unit record."""
    from production_repo import commit_timeline_spans, plan_render_units
    spans = commit_timeline_spans(
        production_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db_path,
    )
    units = plan_render_units(
        production_id,
        [{
            "span_id": spans[0]["id"],
            "asset_type": asset_type,
            "model": "test_model",
            "audio_policy": audio_policy,
            "final_audio_source": "master_narration" if audio_policy == "HERO_SYNC_LOCKED" else "none",
            "provider_audio_usage": "diagnostic_only" if audio_policy == "HERO_SYNC_LOCKED" else "discarded",
        }],
        db_path=db_path,
    )
    return units[0]


class TestShotRepairInvalidation:
    """Test 1: Shot repair stales compile, spend gate, generate, QA, assemble,
       final QA, Gate B."""

    def test_plan_shot_repair_stages(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)
        _seed_approval(prod["id"], "gate_a_spend", db_path)
        _seed_approval(prod["id"], "gate_b_review", db_path)

        plan = plan_shot_repair_invalidation(
            prod["id"], "ru_test_001", db_path=db_path,
        )

        assert "compile_media" in plan.stages_to_stale
        assert "gate_a_spend" in plan.stages_to_stale
        assert "generate_media" in plan.stages_to_stale
        assert "qa_media" in plan.stages_to_stale
        assert "assemble" in plan.stages_to_stale
        assert "qa_final" in plan.stages_to_stale
        assert "gate_b_review" in plan.stages_to_stale
        # Must NOT stale pre-compile stages
        assert "research" not in plan.stages_to_stale
        assert "write_script" not in plan.stages_to_stale
        assert "storyboard" not in plan.stages_to_stale

    def test_shot_repair_stales_approvals(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)
        _seed_approval(prod["id"], "gate_a_spend", db_path)
        _seed_approval(prod["id"], "gate_b_review", db_path)

        plan = plan_shot_repair_invalidation(
            prod["id"], "ru_test_001", db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        assert result["approvals_staled"] == 2
        # Check DB directly
        conn = _db.connect(db_path)
        rows = conn.execute(
            "SELECT gate_name, status FROM approval_requests WHERE production_id=?",
            (prod["id"],),
        ).fetchall()
        conn.close()
        stale_gates = {r["gate_name"] for r in rows if r["status"] == "stale"}
        assert "gate_a_spend" in stale_gates
        assert "gate_b_review" in stale_gates

    def test_shot_repair_stages_not_too_broad(self, db_path):
        """No global reset — unaffected stages remain succeeded."""
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan = plan_shot_repair_invalidation(
            prod["id"], "ru_test_001", db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        # Research, script, storyboard must NOT be staled
        conn = _db.connect(db_path)
        for stage in ["research", "write_script", "storyboard", "tts"]:
            row = conn.execute(
                "SELECT status FROM stage_runs WHERE production_id=? AND stage_name=?",
                (prod["id"], stage),
            ).fetchone()
            assert row is not None
            assert row["status"] == "succeeded", f"{stage} should remain succeeded"
        conn.close()


class TestOverlayRepairInvalidation:
    """Test 2: Overlay repair stales graphics_compositing, assemble, final QA,
       Gate B only."""

    def test_plan_overlay_repair_stages(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan = plan_overlay_repair_invalidation(
            prod["id"], "ru_overlay_001", db_path=db_path,
        )

        assert "graphics_compositing" in plan.stages_to_stale
        assert "assemble" in plan.stages_to_stale
        assert "qa_final" in plan.stages_to_stale
        assert "gate_b_review" in plan.stages_to_stale
        # Must NOT stale generate_media or gate_a_spend
        assert "generate_media" not in plan.stages_to_stale
        assert "gate_a_spend" not in plan.stages_to_stale
        assert "compile_media" not in plan.stages_to_stale

    def test_overlay_repair_stales_only_gate_b(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)
        _seed_approval(prod["id"], "gate_a_spend", db_path)
        _seed_approval(prod["id"], "gate_b_review", db_path)

        plan = plan_overlay_repair_invalidation(
            prod["id"], "ru_overlay_001", db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        conn = _db.connect(db_path)
        rows = conn.execute(
            "SELECT gate_name, status FROM approval_requests WHERE production_id=? ORDER BY gate_name",
            (prod["id"],),
        ).fetchall()
        conn.close()
        for r in rows:
            if r["gate_name"] == "gate_b_review":
                assert r["status"] == "stale"
            elif r["gate_name"] == "gate_a_spend":
                assert r["status"] == "pass", "gate_a_spend must not be staled for overlay repair"


class TestMediaDriftInvalidation:
    """Test 3: Media artifact drift repair stales qa_media, assemble, final QA,
       Gate B."""

    def test_plan_media_drift_stages(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan = plan_media_drift_invalidation(
            prod["id"], "art_drift_001", "ru_drift_001", db_path=db_path,
        )

        assert "qa_media" in plan.stages_to_stale
        assert "assemble" in plan.stages_to_stale
        assert "qa_final" in plan.stages_to_stale
        assert "gate_b_review" in plan.stages_to_stale
        # Must NOT stale generate_media or compile_media
        assert "generate_media" not in plan.stages_to_stale
        assert "compile_media" not in plan.stages_to_stale
        assert "gate_a_spend" not in plan.stages_to_stale

    def test_media_drift_stales_render_unit(self, db_path):
        prod = _make_production(db_path)
        ru = _seed_render_unit(prod["id"], db_path, label="drift_unit")
        ru_id = ru["id"]

        plan = plan_media_drift_invalidation(
            prod["id"], "art_drift_001", ru_id, db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        assert result["render_units_staled"] == 1
        conn = _db.connect(db_path)
        row = conn.execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru_id,),
        ).fetchone()
        conn.close()
        assert row["status"] == "stale"
        assert row["active_artifact_id"] is None


class TestStoryboardRevisionInvalidation:
    """Test 4: Storyboard revision change stales storyboard approval and
       downstream."""

    def test_plan_storyboard_revision_stages(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan = plan_storyboard_revision_invalidation(
            prod["id"], "doc_storyboard_001", db_path=db_path,
        )

        assert "gate_storyboard" in plan.stages_to_stale
        assert "tts" in plan.stages_to_stale
        assert "compile_media" in plan.stages_to_stale
        assert "generate_media" in plan.stages_to_stale
        assert "assemble" in plan.stages_to_stale
        assert "qa_final" in plan.stages_to_stale
        assert "gate_b_review" in plan.stages_to_stale

    def test_storyboard_revision_stales_all_gate_approvals(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)
        _seed_approval(prod["id"], "gate_storyboard", db_path)
        _seed_approval(prod["id"], "gate_a_spend", db_path)
        _seed_approval(prod["id"], "gate_b_review", db_path)

        plan = plan_storyboard_revision_invalidation(
            prod["id"], "doc_sb_002", db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        assert result["approvals_staled"] == 3


class TestUnaffectedRenderUnit:
    """Test 5: Unaffected render unit remains valid."""

    def test_unaffected_unit_stays_valid(self, db_path):
        prod = _make_production(db_path)
        ru_affected = _seed_render_unit(prod["id"], db_path, label="affected",
                                         asset_type="lipsync_video")
        ru_unaffected = _seed_render_unit(prod["id"], db_path, label="unaffected",
                                           asset_type="lipsync_video")

        plan = plan_shot_repair_invalidation(
            prod["id"], ru_affected["id"], db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        conn = _db.connect(db_path)
        row = conn.execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru_unaffected["id"],),
        ).fetchone()
        conn.close()
        # Unaffected unit should NOT be staled (shot repair only stales the
        # specific render_unit, not all render_units)
        assert row["status"] != "stale", "unaffected render_unit must not be staled"


class TestStaleArtifactReuseBlocked:
    """Test 6: Stale artifact reuse is blocked."""

    def test_stale_artifact_cleared_from_render_unit(self, db_path):
        prod = _make_production(db_path)
        ru = _seed_render_unit(prod["id"], db_path, label="stale_test",
                               audio_policy="HERO_SYNC_LOCKED",
                               asset_type="lipsync_video")

        # Simulate an active artifact on the render unit
        from production_repo import register_artifact
        import subprocess
        video_path = Path(db_path).parent / "test_stale.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=blue:s=640x480:d=4,format=yuv420p",
            "-t", "4", str(video_path),
        ], capture_output=True, check=True)
        art = register_artifact(prod["id"], video_path,
                                "lipsync_video", db_path=db_path)
        with _db.transaction(db_path) as conn:
            conn.execute(
                "UPDATE render_units SET active_artifact_id=?, status='generated' WHERE id=?",
                (art["id"], ru["id"]),
            )

        plan = plan_shot_repair_invalidation(
            prod["id"], ru["id"], db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        assert result["render_units_staled"] == 1
        conn = _db.connect(db_path)
        row = conn.execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru["id"],),
        ).fetchone()
        conn.close()
        assert row["status"] == "stale"
        assert row["active_artifact_id"] is None, \
            "active_artifact must be cleared to block stale reuse"


class TestDeterministicNextActions:
    """Test 7: Planner emits deterministic next actions."""

    def test_next_actions_deterministic(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan1 = plan_shot_repair_invalidation(
            prod["id"], "ru_det_001", db_path=db_path,
        )
        plan2 = plan_shot_repair_invalidation(
            prod["id"], "ru_det_001", db_path=db_path,
        )

        assert plan1.next_actions == plan2.next_actions
        assert len(plan1.next_actions) > 0

    def test_next_actions_in_canonical_order(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan = plan_shot_repair_invalidation(
            prod["id"], "ru_order_001", db_path=db_path,
        )
        actions = plan.next_actions

        # Verify canonical ordering
        positions = [stage_runner.STAGE_REGISTRY if isinstance(s, str) else None
                     for s in actions]
        # Each next stage must appear after the previous in canonical order
        idxs = [
            list(stage_runner.STAGE_REGISTRY.keys()).index(a)
            for a in actions
            if a in stage_runner.STAGE_REGISTRY
        ]
        assert idxs == sorted(idxs), "next actions must be in canonical stage order"


class TestIdempotency:
    """Test 8: Running planner twice is idempotent."""

    def test_apply_invalidation_twice_same_result(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)
        _seed_approval(prod["id"], "gate_a_spend", db_path)
        _seed_approval(prod["id"], "gate_b_review", db_path)

        plan = plan_shot_repair_invalidation(
            prod["id"], "ru_idem_001", db_path=db_path,
        )

        result1 = apply_invalidation(prod["id"], plan, db_path=db_path)
        # Apply again — should not change state (already stale)
        result2 = apply_invalidation(prod["id"], plan, db_path=db_path)

        # Second application should not stale more rows (they're already stale)
        assert result2["stages_staled"] <= result1["stages_staled"]
        assert result2["approvals_staled"] <= result1["approvals_staled"]

    def test_plan_and_apply_twice_idempotent(self, db_path):
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)
        _seed_approval(prod["id"], "gate_b_review", db_path)

        change = ChangeRequest(
            entity_type="overlay",
            entity_id="ru_overlay_idem",
            reason="overlay text repaired",
        )
        result1 = plan_and_apply(prod["id"], change, db_path=db_path)
        result2 = plan_and_apply(prod["id"], change, db_path=db_path)

        assert result1["next_actions"] == result2["next_actions"]
        assert result2["stages_staled"] <= result1["stages_staled"]


class TestNegativeCases:
    """Additional negative tests for coverage."""

    def test_unknown_entity_type_raises(self, db_path):
        prod = _make_production(db_path)
        change = ChangeRequest(
            entity_type="bogus_type",
            entity_id="x",
            reason="test",
        )
        with pytest.raises(RuntimeError, match="BLOCKED_FEEDBACK_UNROUTED"):
            plan_and_apply(prod["id"], change, db_path=db_path)

    def test_invalidation_preserves_early_stages(self, db_path):
        """Ensure storyboard revision change doesn't stale research or script."""
        prod = _make_production(db_path)
        slug = prod["project_slug"]
        _seed_stages(prod["id"], slug, db_path)

        plan = plan_storyboard_revision_invalidation(
            prod["id"], "doc_sb_003", db_path=db_path,
        )
        result = apply_invalidation(prod["id"], plan, db_path=db_path)

        conn = _db.connect(db_path)
        for stage in ["research", "write_script", "review_script",
                       "gate_a_content", "storyboard", "review_storyboard"]:
            row = conn.execute(
                "SELECT status FROM stage_runs WHERE production_id=? AND stage_name=?",
                (prod["id"], stage),
            ).fetchone()
            assert row is not None
            assert row["status"] == "succeeded", \
                f"{stage} must remain succeeded after storyboard invalidation"
        conn.close()
