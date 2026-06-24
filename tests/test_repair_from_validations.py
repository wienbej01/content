"""Tests for repair from failed validations only (S04-T002)."""
import json
import sqlite3
import os
from pathlib import Path

import pytest

import production_db as _db
from media_service import run_repair_lifecycle, run_contract_media_qa


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    row = _db.ensure_production("s04_t002_test", db_path=db)
    with _db.transaction(db) as conn:
        conn.execute(
            "INSERT INTO approval_requests(id, production_id, gate_name, status, requested_at) "
            "VALUES(?,?,?,?,?)",
            ("ar_test", row["id"], "gate_a_spend", "pass", _db._now()),
        )
    return row["id"]


def _create_basic_unit(conn, prod_id, unit_id):
    conn.execute(
        "INSERT INTO render_units(id, production_id, label, asset_type, audio_policy, "
        "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
        "ordinal, status, render_mode, source_slice_sha256, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (unit_id, prod_id, "S000", "generated_video", "BROLL_FLEX", 0,
         0, 5000, 5000, 1, "valid", "generated_video",
         "a" * 64, _db._now(), _db._now()),
    )


def _record_validation(conn, prod_id, unit_id, status, evidence, val="qa_media_contract"):
    conn.execute(
        "INSERT INTO validations(id, production_id, subject_id, subject_type, "
        "validator_name, status, evidence_json, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (f"val_{unit_id}", prod_id, unit_id, "render_unit",
         val, status, json.dumps(evidence), _db._now()),
    )


class TestEvidenceValidation:

    def test_repair_without_evidence_blocked(self, db, prod):
        with _db.transaction(db) as conn:
            _create_basic_unit(conn, prod, "ru_no_ev")
            _record_validation(conn, prod, "ru_no_ev", "fail", {})
        with pytest.raises(RuntimeError, match="REPAIR BLOCKED"):
            run_repair_lifecycle(prod, "ru_no_ev", db_path=db)

    def test_repair_with_evidence_proceeds(self, db, prod):
        with _db.transaction(db) as conn:
            _create_basic_unit(conn, prod, "ru_ev")
            _record_validation(conn, prod, "ru_ev", "fail", {
                "file_exists": True, "sha_match": False, "dimensions_ok": True,
                "duration_ok": True, "render_method": "generated_video",
            })
        with pytest.raises(RuntimeError, match="manual review"):
            run_repair_lifecycle(prod, "ru_ev", db_path=db)

    def test_already_passing_returns_early(self, db, prod):
        with _db.transaction(db) as conn:
            _create_basic_unit(conn, prod, "ru_pass")
            _record_validation(conn, prod, "ru_pass", "pass", {
                "file_exists": True, "sha_match": True,
            })
        result = run_repair_lifecycle(prod, "ru_pass", db_path=db)
        assert result.get("already_passing") is True
        assert result.get("failure_class") is None


class TestChangeRequestCreation:

    def _cr_count(self, db):
        return sqlite3.connect(db).execute("SELECT COUNT(*) FROM change_requests").fetchone()[0]

    def _last_cr(self, db):
        return sqlite3.connect(db).execute(
            "SELECT reason, failure_evidence_json, change_type, target_stage, repair_routing_stage "
            "FROM change_requests ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    def test_change_request_has_failure_class(self, db, prod):
        with _db.transaction(db) as conn:
            _create_basic_unit(conn, prod, "ru_cr")
            _record_validation(conn, prod, "ru_cr", "fail", {
                "file_exists": True, "sha_match": False, "dimensions_ok": True,
                "duration_ok": True, "render_method": "generated_video",
            })
        before = self._cr_count(db)
        with pytest.raises(RuntimeError, match="manual review"):
            run_repair_lifecycle(prod, "ru_cr", db_path=db)
        after = self._cr_count(db)
        assert after > before, "Change request should be created"
        cr = self._last_cr(db)
        assert "sha_mismatch" in cr[0], f"Reason should contain failure class: {cr[0]}"
        assert cr[1] is not None, "failure_evidence_json should not be None"
        assert "sha_match" in str(cr[1])

    def test_change_request_has_evidence_json(self, db, prod):
        with _db.transaction(db) as conn:
            _create_basic_unit(conn, prod, "ru_cr2")
            _record_validation(conn, prod, "ru_cr2", "fail", {
                "file_exists": True, "sha_match": False, "dimensions_ok": True,
                "duration_ok": True, "render_method": "generated_video",
            })
        with pytest.raises(RuntimeError, match="manual review"):
            run_repair_lifecycle(prod, "ru_cr2", db_path=db)
        cr = self._last_cr(db)
        ev = json.loads(cr[1])
        assert "sha_match" in ev
        assert ev["sha_match"] is False

    def test_reason_includes_failure_class(self, db, prod):
        with _db.transaction(db) as conn:
            _create_basic_unit(conn, prod, "ru_cr3")
            _record_validation(conn, prod, "ru_cr3", "fail", {
                "file_exists": True, "sha_match": False, "dimensions_ok": True,
                "duration_ok": True, "render_method": "generated_video",
            })
        with pytest.raises(RuntimeError, match="manual review"):
            run_repair_lifecycle(prod, "ru_cr3", db_path=db)
        cr = self._last_cr(db)
        assert "sha_mismatch" in cr[0]
