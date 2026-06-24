"""Tests for repair audit report (S04-T004)."""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from scripts.evals.eval_repair_audit import audit_production


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    row = _db.ensure_production("s04_t004_test", db_path=db)
    return row["id"]


def _create_cr(conn, prod_id, cr_id, subject_id, change_type, target_stage, reason):
    """Create a change_request."""
    conn.execute(
        "INSERT INTO change_requests(id, production_id, subject_type, subject_id, "
        "change_type, requested_by_stage, target_stage, reason, status, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (cr_id, prod_id, "render_unit", subject_id,
         change_type, "qa_media", target_stage, reason, "open", _db._now()),
    )


class TestRepairAudit:

    def test_no_change_requests_clean(self, db, prod):
        """No open change_requests → clean audit."""
        result = audit_production(prod, db_path=db)
        assert result["open_change_request_count"] == 0
        assert result["would_call_provider_render"] is False
        assert result["minimality_ok"] is True

    def test_render_stage_change_request_detected(self, db, prod):
        """Change_request targeting render_media → would_call_provider_render=True."""
        with _db.transaction(db) as conn:
            _create_cr(conn, prod, "cr_001", "ru_001", "re_generate",
                       "render_media", "repair: F-LIP-001")
        result = audit_production(prod, db_path=db)
        assert result["would_call_provider_render"] is True

    def test_non_render_stage_not_counted(self, db, prod):
        """Non-render stage → would_call_provider_render=False."""
        with _db.transaction(db) as conn:
            _create_cr(conn, prod, "cr_002", "ru_002", "re_slice",
                       "audio_timing", "repair: F-LIP-004")
        result = audit_production(prod, db_path=db)
        assert result["would_call_provider_render"] is False

    def test_render_lock_status_checked(self, db, prod):
        """Render lock env vars are checked."""
        result = audit_production(prod, db_path=db)
        # Set in conftest/CI
        assert result["render_lock_status"] in ("PASS", "FAIL")

    def test_minimality_detects_overrouting(self, db, prod):
        """CR routing to render_media when non-render suffices → issue."""
        with _db.transaction(db) as conn:
            # F-LIP-004 should route to audio_timing, not render_media
            _create_cr(conn, prod, "cr_over", "ru_over", "re_generate",
                       "render_media", "repair: F-LIP-004")
        result = audit_production(prod, db_path=db)
        assert len(result["issues"]) > 0
        assert "render_media" in result["issues"][0]

    def test_change_request_has_all_fields(self, db, prod):
        """Each change_request entry has expected fields."""
        with _db.transaction(db) as conn:
            _create_cr(conn, prod, "cr_fields", "ru_fields", "re_plan",
                       "graphics_compositing", "repair: F-GFX-001")
        result = audit_production(prod, db_path=db)
        cr = result["change_requests"][0]
        assert "id" in cr
        assert "subject_id" in cr
        assert "change_type" in cr
        assert "target_stage" in cr
        assert "reason" in cr
        assert "would_call_provider_render" in cr

    def test_audit_output_format(self, db, prod):
        """Audit has all required top-level fields."""
        result = audit_production(prod, db_path=db)
        assert "production_id" in result
        assert "change_requests" in result
        assert "would_call_provider_render" in result
        assert "render_lock_status" in result
        assert "minimality_ok" in result
        assert "issues" in result
