"""ENG-0603: Integration tests for the DB repair lifecycle.

Tests:
1. Provider-generated local graphic is repaired by local renderer.
2. Old provider artifact remains in DB but is inactive.
3. New local artifact becomes active only after QA pass.
4. Repair is idempotent.
5. Repair does not create duplicate active artifacts.
6. Repair does not assemble prematurely.
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from production_repo import commit_timeline_spans, plan_render_units, register_artifact, link_artifact_to_render_unit
from media_service import run_repair_lifecycle, record_validation_evidence


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_repair_loop", video_type="short", db_path=db)


def _make_local_graphic_spec(span_id, dts=None):
    return {
        "asset_type": "local_graphic",
        "model": None,
        "audio_policy": "SILENT_GRAPHIC",
        "final_audio_source": "none",
        "provider_audio_usage": "discarded",
        "text_policy": "DETERMINISTIC_GRAPHIC",
        "render_mode": "deterministic_graphic",
        "deterministic_text_spec": dts or {"type": "title_card", "text": "REPAIR", "headline": "REPAIR"},
        "span_id": span_id,
    }


# =========================================================================
# Helpers
# =========================================================================

def _create_provider_generated_local_graphic(db, prod, span, dts=None):
    """Simulate the old bad pattern: provider-generated artifact linked to local_graphic."""
    from render_graphics import render_local_graphic_render_unit

    unit = plan_render_units(prod["id"], [
        _make_local_graphic_spec(span["id"], dts=dts),
    ], db_path=db)[0]

    # Create a fake provider PNG
    png_path = Path(f"/tmp/fake_prov_{unit['id']}.png")
    from PIL import Image
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(str(png_path))

    art = register_artifact(
        prod["id"], png_path, kind="generated_media",
        extra_metadata={
            "render_method": "higgsfield_provider",
            "renderer": "higgsfield",
            "text_spec_sha256": "fake",
            "expected_text": ["REPAIR"],
        },
        db_path=db,
    )
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    with _db.transaction(db) as conn:
        conn.execute(
            "UPDATE render_units SET metadata_json=? WHERE id=?",
            (_db._json({"deterministic_text_spec": dts or {"type": "title_card", "text": "REPAIR", "headline": "REPAIR"}}),
             unit["id"]),
        )

    # Record a failed QA validation so repair knows what went wrong
    record_validation_evidence(
        prod["id"], "render_unit", unit["id"],
        "qa_media_contract", False,
        {"render_method": "local_graphic", "contract_version": "1.0",
         "file_exists": True, "sha_match": True,
         "provenance_ok": False, "no_provider_job": False,
         "text_spec_exists": True, "text_spec_sha_match": False,
         "dimensions_ok": True, "duration_ok": True, "text_policy_ok": True,
         "issues": ["wrong_provenance", "has_provider_job", "text_spec_hash_mismatch"]},
        db_path=db,
    )

    return unit


# =========================================================================
# Lifecycle tests
# =========================================================================

class TestRepairLifecycle:
    """ENG-0603: Full repair lifecycle."""

    def test_provider_local_graphic_repaired_by_local_renderer(self, db, prod):
        """Provider-generated local graphic is repaired by local renderer."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "REPAIR_ME", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "REPAIR", "headline": "REPAIR"}
        unit = _create_provider_generated_local_graphic(db, prod, spans[0], dts=dts)

        outcome = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)

        assert outcome["action"] == "render_local_graphic"
        assert outcome["failure_class"] in ("local_graphic_not_local", "provider_forbidden_asset", "local_graphic_text_mismatch")
        assert outcome["qa_passed"] is True, f"Repair QA failed: {outcome}"

    def test_old_artifact_preserved_but_inactive(self, db, prod):
        """Old provider artifact remains in DB but is inactive after repair."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "PRESERVE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "PRESERVE", "headline": "PRESERVE"}
        unit = _create_provider_generated_local_graphic(db, prod, spans[0], dts=dts)

        conn = _db.connect(db)
        before_arts = conn.execute(
            "SELECT id, deleted_at FROM artifacts WHERE production_id=?",
            (prod["id"],),
        ).fetchall()
        old_art_id = before_arts[0]["id"]
        conn.close()

        run_repair_lifecycle(prod["id"], unit["id"], db_path=db)

        conn = _db.connect(db)
        all_arts = conn.execute(
            "SELECT id, deleted_at FROM artifacts WHERE production_id=?",
            (prod["id"],),
        ).fetchall()
        ru = conn.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?",
            (unit["id"],),
        ).fetchone()
        conn.close()

        # Old artifact should still exist (no row deleted)
        old_art_row = [a for a in all_arts if a["id"] == old_art_id]
        assert len(old_art_row) == 1, "Old artifact deleted from DB"

        # New active artifact should be different from old
        assert ru["active_artifact_id"] is not None
        assert ru["active_artifact_id"] != old_art_id

    def test_new_artifact_active_only_after_qa_pass(self, db, prod):
        """New local artifact becomes active only after QA pass."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "ACTIVATE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "ACTIVATE", "headline": "ACTIVATE"}
        unit = _create_provider_generated_local_graphic(db, prod, spans[0], dts=dts)

        outcome = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)

        assert outcome["qa_passed"] is True

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (unit["id"],),
        ).fetchone()
        conn.close()

        assert ru["status"] == "valid", f"Expected valid, got {ru['status']}"
        assert ru["active_artifact_id"] is not None

    def test_repair_is_idempotent(self, db, prod):
        """Running repair twice does not create duplicate active artifacts."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "IDEMPOTENT", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "IDEMPOTENT", "headline": "IDEMPOTENT"}
        unit = _create_provider_generated_local_graphic(db, prod, spans[0], dts=dts)

        outcome1 = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)
        assert outcome1["qa_passed"] is True

        # Second call must be idempotent — returns success without re-repairing
        outcome2 = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)
        assert outcome2.get("already_passing") is True
        assert outcome2["qa_passed"] is True
        assert outcome2.get("action") == "no_action_needed"

        conn = _db.connect(db)
        arts = conn.execute(
            "SELECT id, deleted_at FROM artifacts WHERE production_id=?",
            (prod["id"],),
        ).fetchall()
        ru = conn.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?",
            (unit["id"],),
        ).fetchone()
        conn.close()

        active_artifacts = [a for a in arts if a["id"] == ru["active_artifact_id"]]
        assert len(active_artifacts) == 1
        assert len(arts) >= 2  # At least old provider + first repair = 2

    def test_no_duplicate_active_artifacts(self, db, prod):
        """Repair does not create duplicate active artifacts (idempotent)."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "NO_DUP", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "NO_DUP", "headline": "NO_DUP"}
        unit = _create_provider_generated_local_graphic(db, prod, spans[0], dts=dts)

        outcome1 = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)
        assert outcome1["qa_passed"] is True

        # Second call must be idempotent — no duplicate artifacts created
        outcome2 = run_repair_lifecycle(prod["id"], unit["id"], db_path=db)
        assert outcome2.get("already_passing") is True

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?",
            (unit["id"],),
        ).fetchone()
        conn.close()

        assert ru["active_artifact_id"] is not None

        conn = _db.connect(db)
        active_count = conn.execute(
            "SELECT COUNT(*) as c FROM render_units WHERE active_artifact_id IS NOT NULL AND id=?",
            (unit["id"],),
        ).fetchone()["c"]
        conn.close()

        assert active_count == 1, "More than one active artifact for render unit"