"""Tests for TKT-001: Reject simulated QA evidence outside test mode.

Validates that:
- In production mode, simulated `syncnet_offset` and `semantic_role_qa` evidence
  is rejected with BLOCKED_SIMULATED_EVIDENCE_REJECTED.
- Under YT_TEST_MODE=1, simulated evidence passes gates as before.
- Real (non-simulated) evidence passes gates in production mode.
"""

import json
import os
import sys
import uuid
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact,
    link_artifact_to_render_unit,
)
from media_service import run_render_unit_qa
from assemble_db import (
    validate_assembly_inputs, validate_semantic_role_qa, AssemblyError,
)


@pytest.fixture
def db_path(tmp_path):
    """Isolated test DB at a known path."""
    p = tmp_path / "test.db"
    _db.migrate(str(p))
    return str(p)


@pytest.fixture
def prod(db_path):
    return _db.ensure_production("test_project", video_type="short_educational",
                                 db_path=db_path)


def _hero_with_simulated_syncnet(prod_id, db_p, tmp_path, offset_ms=0.0,
                                  confidence=3.0):
    spans = commit_timeline_spans(
        prod_id, [{"label": "H001", "start_ms": 0, "end_ms": 4000}],
        db_path=db_p)
    units = plan_render_units(prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": "HERO_SYNC_LOCKED", "model": "seedance_2_0",
          "final_audio_source": "master_narration",
          "provider_audio_usage": "diagnostic_only"}], db_path=db_p)
    unit = units[0]

    fake_video = tmp_path / "hero.mp4"
    fake_video.write_bytes(b"fake provider video" * 100)
    art = register_artifact(prod_id, fake_video, "generated_media", db_path=db_p)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db_p)

    run_render_unit_qa(prod_id, unit["id"],
        {"file_exists": True, "dimensions_ok": True,
         "duration_ok": True, "audio_policy_ok": True}, db_path=db_p)

    comp_path = tmp_path / "hero_compensated.mp4"
    comp_path.write_bytes(b"compensated hero video" * 100)

    with _db.transaction(db_p) as conn:
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation, status,
                idempotency_key, compensated_artifact_path, submitted_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (f"pj_{uuid.uuid4().hex[:8]}", prod_id, unit["id"], "seedance",
             "generate_lipsync", "completed",
             f"idemp_{uuid.uuid4().hex[:8]}", str(comp_path)))
        evidence = json.dumps({
            "offset_ms": offset_ms, "confidence": confidence,
            "method": "yt_test_mode_fake_provider", "simulated": True,
            "publish_grade": False,
        })
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name,
                status, evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (f"val_{uuid.uuid4().hex[:8]}", prod_id, "render_unit", unit["id"],
             "syncnet_offset", "pass", evidence, _db._now()))
        conn.execute("UPDATE render_units SET status='valid' WHERE id=?",
                     (unit["id"],))
    return unit


def _hero_with_real_syncnet(prod_id, db_p, tmp_path, offset_ms=25.0,
                             confidence=2.8):
    spans = commit_timeline_spans(prod_id,
        [{"label": "HReal", "start_ms": 0, "end_ms": 4000}], db_path=db_p)
    units = plan_render_units(prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": "HERO_SYNC_LOCKED", "model": "seedance_2_0",
          "final_audio_source": "master_narration",
          "provider_audio_usage": "diagnostic_only"}], db_path=db_p)
    unit = units[0]

    fake_video = tmp_path / "real_hero.mp4"
    fake_video.write_bytes(b"fake provider video" * 100)
    art = register_artifact(prod_id, fake_video, "generated_media", db_path=db_p)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db_p)
    run_render_unit_qa(prod_id, unit["id"],
        {"file_exists": True, "dimensions_ok": True,
         "duration_ok": True, "audio_policy_ok": True}, db_path=db_p)

    comp_path = tmp_path / "real_hero_comp.mp4"
    comp_path.write_bytes(b"compensated hero video" * 100)

    with _db.transaction(db_p) as conn:
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation, status,
                idempotency_key, compensated_artifact_path, submitted_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (f"pj_{uuid.uuid4().hex[:8]}", prod_id, unit["id"], "seedance",
             "generate_lipsync", "completed", f"idemp_{uuid.uuid4().hex[:8]}",
             str(comp_path)))
        real_evidence = json.dumps({"offset_ms": offset_ms, "confidence": confidence})
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name,
                status, evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (f"val_{uuid.uuid4().hex[:8]}", prod_id, "render_unit",
             unit["id"], "syncnet_offset", "pass", real_evidence, _db._now()))
        conn.execute("UPDATE render_units SET status='valid' WHERE id=?",
                     (unit["id"],))
    return unit


class TestSimulatedSyncnetEvidence:
    def test_prod_mode_rejects_simulated_syncnet(self, db_path, prod, tmp_path,
                                                  monkeypatch):
        monkeypatch.delenv("YT_TEST_MODE", raising=False)
        _hero_with_simulated_syncnet(prod["id"], db_path, tmp_path)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db_path)

        assert "BLOCKED_SIMULATED_EVIDENCE_REJECTED" in str(exc_info.value)

    def test_test_mode_allows_simulated_syncnet(self, db_path, prod, tmp_path,
                                                 monkeypatch):
        monkeypatch.setenv("YT_TEST_MODE", "1")
        _hero_with_simulated_syncnet(prod["id"], db_path, tmp_path)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db_path)

        assert "BLOCKED_SIMULATED_EVIDENCE_REJECTED" not in str(exc_info.value)

    def test_prod_mode_allows_real_syncnet(self, db_path, prod, tmp_path,
                                            monkeypatch):
        monkeypatch.delenv("YT_TEST_MODE", raising=False)
        _hero_with_real_syncnet(prod["id"], db_path, tmp_path)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db_path)

        assert "BLOCKED_SIMULATED_EVIDENCE_REJECTED" not in str(exc_info.value)


class TestSimulatedSemanticRoleQA:
    def test_prod_mode_rejects_simulated_semantic(self, db_path, prod, monkeypatch):
        monkeypatch.delenv("YT_TEST_MODE", raising=False)

        unit_id = "ru_sem_001"
        with _db.transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO render_units
                   (id, production_id, ordinal, label, visual_role, asset_type,
                    audio_policy, required_start_ms, required_end_ms,
                    required_duration_ms, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (unit_id, prod["id"], 0, unit_id, "hero_trust", "lipsync_video",
                 "HERO_SYNC_LOCKED", 0, 4000, 4000, "valid",
                 _db._now(), _db._now()))
            evidence = json.dumps({
                "render_unit_id": unit_id, "visual_role": "hero_trust",
                "result": "pass",
                "details": {"method": "yt_test_mode_deterministic_fixture",
                             "publish_grade": False},
            })
            conn.execute(
                """INSERT INTO validations
                   (id, production_id, subject_type, subject_id, validator_name,
                    status, evidence_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (f"val_{uuid.uuid4().hex[:8]}", prod["id"], "render_unit",
                 unit_id, "semantic_role_qa", "pass", evidence, _db._now()))

        conn = _db.connect(db_path)
        with pytest.raises(AssemblyError) as exc_info:
            validate_semantic_role_qa(conn,
                [{"id": unit_id, "visual_role": "hero_trust", "label": unit_id}],
                publish_grade=True)
        conn.close()
        assert "BLOCKED_SIMULATED_EVIDENCE_REJECTED" in str(exc_info.value)

    def test_test_mode_allows_simulated_semantic(self, db_path, prod, monkeypatch):
        monkeypatch.setenv("YT_TEST_MODE", "1")

        unit_id = "ru_sem_002"
        with _db.transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO render_units
                   (id, production_id, ordinal, label, visual_role, asset_type,
                    audio_policy, required_start_ms, required_end_ms,
                    required_duration_ms, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (unit_id, prod["id"], 0, unit_id, "hero_trust", "lipsync_video",
                 "HERO_SYNC_LOCKED", 0, 4000, 4000, "valid",
                 _db._now(), _db._now()))
            evidence = json.dumps({
                "render_unit_id": unit_id, "visual_role": "hero_trust",
                "result": "pass",
                "details": {"method": "yt_test_mode_deterministic_fixture",
                             "publish_grade": False},
            })
            conn.execute(
                """INSERT INTO validations
                   (id, production_id, subject_type, subject_id, validator_name,
                    status, evidence_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (f"val_{uuid.uuid4().hex[:8]}", prod["id"], "render_unit",
                 unit_id, "semantic_role_qa", "pass", evidence, _db._now()))

        conn = _db.connect(db_path)
        validate_semantic_role_qa(conn,
            [{"id": unit_id, "visual_role": "hero_trust", "label": unit_id}],
            publish_grade=True)
        conn.close()

    def test_prod_mode_allows_real_semantic(self, db_path, prod, monkeypatch):
        monkeypatch.delenv("YT_TEST_MODE", raising=False)

        unit_id = "ru_sem_003"
        with _db.transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO render_units
                   (id, production_id, ordinal, label, visual_role, asset_type,
                    audio_policy, required_start_ms, required_end_ms,
                    required_duration_ms, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (unit_id, prod["id"], 0, unit_id, "hero_trust", "lipsync_video",
                 "HERO_SYNC_LOCKED", 0, 4000, 4000, "valid",
                 _db._now(), _db._now()))
            evidence = json.dumps({
                "render_unit_id": unit_id, "visual_role": "hero_trust",
                "result": "pass",
            })
            conn.execute(
                """INSERT INTO validations
                   (id, production_id, subject_type, subject_id, validator_name,
                    status, evidence_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (f"val_{uuid.uuid4().hex[:8]}", prod["id"], "render_unit",
                 unit_id, "semantic_role_qa", "pass", evidence, _db._now()))

        conn = _db.connect(db_path)
        validate_semantic_role_qa(conn,
            [{"id": unit_id, "visual_role": "hero_trust", "label": unit_id}],
            publish_grade=True)
        conn.close()
