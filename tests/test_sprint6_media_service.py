"""Tests for Sprint 6: media_service.py
(Provider jobs, QA evidence, change-request routing)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from production_repo import commit_timeline_spans, plan_render_units
from authoring_service import request_approval, record_approval_decision
from media_service import (
    submit_provider_job, poll_provider_job, complete_provider_job, fail_provider_job,
    ProviderJobError,
    record_validation_evidence, run_render_unit_qa,
    route_change_request, resolve_change_request, get_open_change_requests,
)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("sprint6_test", db_path=db)


@pytest.fixture
def approved_prod(db):
    p = _db.ensure_production("sprint6_approved", db_path=db)
    # Set up spend approval
    from stage_runner import save_document_revision
    save_document_revision(p["id"], "render_plan", {"units": [], "estimated_usd": 5.0}, db_path=db)
    request_approval(p["id"], "gate_a_spend", subject_sha256="plan_sha", db_path=db)
    record_approval_decision(p["id"], "gate_a_spend", "pass", db_path=db)
    return p


@pytest.fixture
def render_unit(approved_prod, db):
    spans = commit_timeline_spans(
        approved_prod["id"],
        [{"label": "B001", "start_ms": 0, "end_ms": 5000}],
        db_path=db,
    )
    units = plan_render_units(
        approved_prod["id"],
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video", "model": "seedance_2_0",
          "audio_policy": "baked_in", "lipsync_required": True}],
        db_path=db,
    )
    return units[0]


class TestProviderJob:
    def test_submit_requires_spend_approval(self, db, prod):
        with pytest.raises(ProviderJobError, match="gate_a_spend"):
            submit_provider_job(
                prod["id"], "fake_render_unit_id",
                "higgsfield", "seedance_2_0", {"prompt": "test"},
                db_path=db,
            )

    def test_submit_creates_job(self, db, approved_prod, render_unit):
        job = submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "James sitting"},
            db_path=db,
        )
        assert job["status"] == "submitted"
        assert job["provider"] == "higgsfield"
        assert job["render_unit_id"] == render_unit["id"]

    def test_idempotent_same_key(self, db, approved_prod, render_unit):
        idem = "test_key_abc"
        j1 = submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "test"},
            idempotency_key=idem, db_path=db,
        )
        j2 = submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "different"},
            idempotency_key=idem, db_path=db,
        )
        assert j1["id"] == j2["id"]

    def test_render_unit_status_advances_to_generating(self, db, approved_prod, render_unit):
        submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "test"},
            db_path=db,
        )
        conn = _db.connect(db)
        ru = conn.execute("SELECT status FROM render_units WHERE id=?", (render_unit["id"],)).fetchone()
        conn.close()
        assert ru["status"] == "generating"

    def test_complete_job_registers_artifact(self, db, approved_prod, render_unit, tmp_path):
        job = submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "test"},
            db_path=db,
        )
        result_file = tmp_path / "output.mp4"
        result_file.write_bytes(b"fake video " * 50)
        art = complete_provider_job(job["id"], result_file, db_path=db)
        assert art["kind"] == "generated_media"
        assert art["sha256"] is not None

        conn = _db.connect(db)
        ru = conn.execute("SELECT status FROM render_units WHERE id=?", (render_unit["id"],)).fetchone()
        pj = conn.execute("SELECT status FROM provider_jobs WHERE id=?", (job["id"],)).fetchone()
        conn.close()
        assert ru["status"] == "generated"
        assert pj["status"] == "completed"

    def test_fail_job(self, db, approved_prod, render_unit):
        job = submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "test"},
            db_path=db,
        )
        result = fail_provider_job(job["id"], "API timeout", db_path=db)
        assert result["status"] == "failed"

        conn = _db.connect(db)
        ru = conn.execute("SELECT status FROM render_units WHERE id=?", (render_unit["id"],)).fetchone()
        conn.close()
        assert ru["status"] == "failed"

    def test_poll_updates_status(self, db, approved_prod, render_unit):
        job = submit_provider_job(
            approved_prod["id"], render_unit["id"],
            "higgsfield", "seedance_2_0", {"prompt": "test"},
            db_path=db,
        )
        updated = poll_provider_job(job["id"], external_job_id="ext_123", new_status="running", db_path=db)
        assert updated["external_job_id"] == "ext_123"
        assert updated["status"] == "running"


class TestQAEvidence:
    def test_passing_validation_marks_valid(self, db, approved_prod, render_unit, tmp_path):
        f = tmp_path / "clip.mp4"
        f.write_bytes(b"video")
        from production_repo import register_artifact, link_artifact_to_render_unit
        art = register_artifact(approved_prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], render_unit["id"], db_path=db)

        checks = {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True,
            "audio_policy_ok": True, "sha_match": True,
        }
        val = run_render_unit_qa(approved_prod["id"], render_unit["id"], checks, db_path=db)
        assert val["status"] == "pass"

        conn = _db.connect(db)
        ru = conn.execute("SELECT status FROM render_units WHERE id=?", (render_unit["id"],)).fetchone()
        conn.close()
        assert ru["status"] == "valid"

    def test_failing_validation_not_valid(self, db, approved_prod, render_unit, tmp_path):
        f = tmp_path / "clip.mp4"
        f.write_bytes(b"video")
        from production_repo import register_artifact, link_artifact_to_render_unit
        art = register_artifact(approved_prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], render_unit["id"], db_path=db)

        checks = {"file_exists": True, "dimensions_ok": False, "duration_ok": True, "audio_policy_ok": True}
        val = run_render_unit_qa(approved_prod["id"], render_unit["id"], checks, db_path=db)
        assert val["status"] == "fail"

    def test_qa_without_artifact_raises(self, db, approved_prod, render_unit):
        with pytest.raises(ValueError, match="no active artifact"):
            run_render_unit_qa(approved_prod["id"], render_unit["id"], {}, db_path=db)


class TestChangeRequests:
    def test_route_change_request(self, db, approved_prod, render_unit):
        req = route_change_request(
            approved_prod["id"], render_unit["id"],
            "regenerate", "Wrong angle",
            db_path=db,
        )
        assert req["status"] == "open"
        assert req["change_type"] == "regenerate"

        conn = _db.connect(db)
        ru = conn.execute("SELECT status FROM render_units WHERE id=?", (render_unit["id"],)).fetchone()
        conn.close()
        assert ru["status"] == "change_requested"

    def test_resolve_accepted_resets_to_ordered(self, db, approved_prod, render_unit):
        req = route_change_request(
            approved_prod["id"], render_unit["id"],
            "regenerate", "Bad quality",
            db_path=db,
        )
        resolve_change_request(approved_prod["id"], req["id"], "accepted", db_path=db)

        conn = _db.connect(db)
        ru = conn.execute("SELECT status FROM render_units WHERE id=?", (render_unit["id"],)).fetchone()
        conn.close()
        assert ru["status"] == "ordered"

    def test_filter_by_target_stage(self, db, approved_prod, render_unit):
        route_change_request(
            approved_prod["id"], render_unit["id"],
            "regenerate", "reason", target_stage="generate_media", db_path=db,
        )
        open_reqs = get_open_change_requests(approved_prod["id"], target_stage="generate_media", db_path=db)
        assert len(open_reqs) == 1

        other_stage = get_open_change_requests(approved_prod["id"], target_stage="assemble", db_path=db)
        assert len(other_stage) == 0
