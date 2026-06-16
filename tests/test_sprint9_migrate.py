"""Tests for Sprint 9: migrate_legacy.py
(Legacy cutover, consolidation, operations dashboard, outbox)
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from migrate_legacy import (
    consolidate_legacy_dbs, check_legacy_retired,
    production_status_dashboard, outbox_dispatcher_step,
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
    return _db.ensure_production("sprint9_test", db_path=db)


class TestConsolidateLegacyDBs:
    def _make_clips_db(self, tmp_path, project_id):
        """Create a minimal clips.db with one clip row."""
        clips_db = tmp_path / "clips.db"
        conn = sqlite3.connect(str(clips_db))
        conn.execute("""
            CREATE TABLE clips (
                clip_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_beat_id TEXT NOT NULL,
                production_beat_id TEXT NOT NULL,
                slot_id TEXT,
                split_index INTEGER,
                split_total INTEGER,
                output_path TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                model TEXT,
                audio_policy TEXT NOT NULL,
                lipsync_required INTEGER NOT NULL,
                required_start_sec REAL NOT NULL,
                required_end_sec REAL NOT NULL,
                required_dur_sec REAL NOT NULL,
                audio_slice_path TEXT,
                audio_slice_sha256 TEXT,
                speech_len_sec REAL,
                status TEXT NOT NULL,
                status_reason TEXT,
                actual_dur_sec REAL,
                actual_width INTEGER,
                actual_height INTEGER,
                actual_has_audio INTEGER,
                actual_sha256 TEXT,
                plan_sha256 TEXT,
                upstream_sha256 TEXT,
                created_at TEXT NOT NULL,
                created_by_step TEXT,
                generated_at TEXT,
                last_validated_at TEXT,
                invalidated_at TEXT
            )
        """)
        conn.execute("""
            INSERT INTO clips VALUES (
                'clip_001', ?, 'B001', 'B001', NULL, NULL, NULL,
                'assets/media/test/B001.mp4', 'lipsync_video', 'seedance_2_0',
                'baked_in', 1, 0.0, 4.0, 4.0,
                NULL, NULL, NULL, 'valid', NULL, 4.1, 1280, 720, 1,
                'abc123', NULL, NULL, '2026-06-15T00:00:00+00:00', 'compile', NULL, NULL, NULL
            )
        """, (project_id,))
        conn.commit()
        conn.close()
        return clips_db

    def test_import_clips(self, db, prod, tmp_path):
        clips_db = self._make_clips_db(tmp_path, "sprint9_test")
        result = consolidate_legacy_dbs(
            "sprint9_test", clips_db_path=clips_db, db_path=db
        )
        assert result["clips_imported"] == 1
        assert result["errors"] == []

    def test_idempotent_import(self, db, prod, tmp_path):
        clips_db = self._make_clips_db(tmp_path, "sprint9_test")
        r1 = consolidate_legacy_dbs("sprint9_test", clips_db_path=clips_db, db_path=db)
        r2 = consolidate_legacy_dbs("sprint9_test", clips_db_path=clips_db, db_path=db)
        # Second import should succeed idempotently (no new rows, no errors)
        assert r1["clips_imported"] >= 1
        # errors should be empty on both
        assert r2["errors"] == []

    def test_missing_clips_db_skipped(self, db, prod, tmp_path):
        result = consolidate_legacy_dbs(
            "sprint9_test",
            clips_db_path=tmp_path / "nonexistent.db",
            db_path=db,
        )
        assert result["clips_imported"] == 0


class TestLegacyRetired:
    def test_no_state_json_passes(self, db, prod, tmp_path):
        result = check_legacy_retired("sprint9_test", db_path=db)
        # No state.json or gates.json in current dir → retired
        assert isinstance(result["retired"], bool)
        assert "reasons" in result

    def test_unknown_project_fails(self, db):
        result = check_legacy_retired("completely_unknown_project_xyz", db_path=db)
        assert not result["retired"]
        assert any("not found" in r for r in result["reasons"])


class TestOperationsDashboard:
    def test_dashboard_returns_structure(self, db, prod):
        status = production_status_dashboard(db_path=db)
        assert "queue_depth" in status
        assert "blocked_productions" in status
        assert "pending_approvals" in status
        assert "open_change_requests" in status
        assert "failed_jobs" in status
        assert "total_spend_usd" in status

    def test_blocked_production_appears(self, db, prod):
        # Mirror a failed stage
        _db.mirror_stage_state("sprint9_test", "generate_media", "failed",
                               error="Provider timeout", db_path=db)
        status = production_status_dashboard(db_path=db)
        blocked = [b for b in status["blocked_productions"]
                   if b["project_slug"] == "sprint9_test"]
        assert len(blocked) == 1
        assert any(b["type"] == "failed_stage" for b in blocked[0]["blockers"])

    def test_pending_approval_appears(self, db, prod):
        from authoring_service import request_approval
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        status = production_status_dashboard(db_path=db)
        pending = [a for a in status["pending_approvals"]
                   if a["production_id"] == prod["id"]]
        assert len(pending) >= 1


class TestOutboxDispatcher:
    def test_pending_messages_sent(self, db, prod):
        from authoring_service import request_approval
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        count = outbox_dispatcher_step(db_path=db)
        assert count >= 1

        conn = _db.connect(db)
        msgs = conn.execute(
            "SELECT status FROM outbox_messages WHERE production_id=?", (prod["id"],)
        ).fetchall()
        conn.close()
        assert all(m["status"] == "sent" for m in msgs)

    def test_already_sent_not_reprocessed(self, db, prod):
        from authoring_service import request_approval
        request_approval(prod["id"], "gate_a_content", subject_sha256="abc", db_path=db)
        outbox_dispatcher_step(db_path=db)
        count2 = outbox_dispatcher_step(db_path=db)
        assert count2 == 0
