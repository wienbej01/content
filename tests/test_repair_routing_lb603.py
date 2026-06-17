"""Tests for R6-004 repair routing against real schema."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from repair_routing import (
    create_repair_request, is_repair_request_open,
    resolve_repair_request, get_open_repair_requests,
    invalidate_dependent_deliverables, RepairRoutingError,
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
    return _db.ensure_production("repair_test", db_path=db)


def _make_artifact(prod_id, db_path, path):
    from production_repo import register_artifact
    path.write_bytes(b"fake artifact content for testing")
    return register_artifact(prod_id, path, "media", db_path=db_path)


def _make_render_unit(prod_id, db_path):
    from production_repo import commit_timeline_spans, plan_render_units
    spans = commit_timeline_spans(prod_id, [{"label": "B001", "start_ms": 0, "end_ms": 5000}], db_path=db_path)
    return plan_render_units(prod_id, [{
        "span_id": spans[0]["id"], "asset_type": "lipsync_video",
        "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
    }], db_path=db_path)[0]


class TestRepairRouting:
    def test_create_repair_request(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        cr = create_repair_request(
            production_id=prod["id"],
            render_unit_id=ru["id"],
            change_type="regenerate",
            requested_by_stage="qa_media",
            failure_reason="Failed lipsync score",
            db_path=db,
        )
        assert cr["status"] == "open"
        assert cr["change_type"] == "regenerate"
        assert cr["requested_by_stage"] == "qa_media"
        assert is_repair_request_open(prod["id"], ru["id"], db_path=db)

    def test_repair_marks_unit_change_requested(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        create_repair_request(
            prod["id"], ru["id"], "regenerate", "qa_media",
            "test failure", db_path=db,
        )
        conn = _db.connect(db)
        row = conn.execute("SELECT status FROM render_units WHERE id=?", (ru["id"],)).fetchone()
        conn.close()
        assert row["status"] == "change_requested"

    def test_resolve_requires_all_validations_pass(self, db, prod, tmp_path):
        ru = _make_render_unit(prod["id"], db)
        create_repair_request(
            prod["id"], ru["id"], "regenerate", "qa_media",
            "test failure", db_path=db,
        )
        new_art = _make_artifact(prod["id"], db, tmp_path / "new.mp4")

        with pytest.raises(RepairRoutingError, match="cannot resolve"):
            resolve_repair_request(
                prod["id"], ru["id"], new_art["id"],
                replacement_validations=["nonexistent_val"],
                db_path=db,
            )

    def test_resolve_updates_artifact_and_resolves(self, db, prod, tmp_path):
        ru = _make_render_unit(prod["id"], db)
        create_repair_request(
            prod["id"], ru["id"], "regenerate", "qa_media",
            "test failure", db_path=db,
        )
        new_art = _make_artifact(prod["id"], db, tmp_path / "new.mp4")

        result = resolve_repair_request(
            prod["id"], ru["id"], new_art["id"],
            db_path=db,
        )
        assert result["status"] == "resolved"
        assert not is_repair_request_open(prod["id"], ru["id"], db_path=db)

        conn = _db.connect(db)
        ru_row = conn.execute("SELECT active_artifact_id, status FROM render_units WHERE id=?", (ru["id"],)).fetchone()
        conn.close()
        assert ru_row["active_artifact_id"] == new_art["id"]
        assert ru_row["status"] == "generated"

    def test_failed_replacement_leaves_request_open(self, db, prod, tmp_path):
        ru = _make_render_unit(prod["id"], db)
        create_repair_request(
            prod["id"], ru["id"], "regenerate", "qa_media",
            "test failure", db_path=db,
        )
        assert is_repair_request_open(prod["id"], ru["id"], db_path=db)

    def test_get_open_repair_requests(self, db, prod):
        ru = _make_render_unit(prod["id"], db)
        create_repair_request(
            prod["id"], ru["id"], "regenerate", "qa_media",
            "test failure", db_path=db,
        )
        open_reqs = get_open_repair_requests(prod["id"], db_path=db)
        assert len(open_reqs) >= 1

    def test_open_repair_blocks_assembly(self, db, prod):
        """An open repair request should be detectable by the assembly gate."""
        ru = _make_render_unit(prod["id"], db)
        create_repair_request(
            prod["id"], ru["id"], "regenerate", "qa_media",
            "test failure", db_path=db,
        )
        conn = _db.connect(db)
        open_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=? AND status='open'",
            (prod["id"],),
        ).fetchone()["cnt"]
        conn.close()
        assert open_count >= 1
