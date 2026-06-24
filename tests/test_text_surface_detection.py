"""Tests for provider text surface detection (S03-T002)."""
import json
import sqlite3
from pathlib import Path

import pytest

import production_db as _db
from scripts.evals.eval_text_surface import eval_production

HAS_DB = Path("db/production.db").exists()


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    import os
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    row = _db.ensure_production("s03_t002_test", db_path=db)
    return row["id"]


def _create_broll_unit(conn, prod_id, unit_id, label, text_policy="NO_VISIBLE_TEXT"):
    """Create a BROLL_FLEX render unit with a text policy."""
    conn.execute(
        """INSERT INTO render_units
           (id, production_id, label, asset_type, audio_policy, lipsync_required,
            text_policy, required_start_ms, required_end_ms, required_duration_ms,
            ordinal, status, render_mode, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (unit_id, prod_id, label, "generated_video", "BROLL_FLEX", 0,
         text_policy, 5000, 10000, 5000,
         2, "valid", "generated_video",
         _db._now(), _db._now()),
    )


def _record_qa(conn, prod_id, unit_id, evidence, status="pass"):
    """Record a QA validation with given evidence."""
    conn.execute(
        "INSERT INTO validations(id, production_id, subject_id, subject_type, "
        "validator_name, status, evidence_json, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (f"val_{unit_id}", prod_id, unit_id, "render_unit",
         "qa_media_contract", status, json.dumps(evidence), _db._now()),
    )


class TestEvalTextSurface:
    """Text surface detection eval."""

    def test_ocr_available_no_text_passes(self, db, prod):
        """OCR available, no text detected → pass."""
        with _db.transaction(db) as conn:
            _create_broll_unit(conn, prod, "ru_pass", "B001")
            _record_qa(conn, prod, "ru_pass", {
                "text_policy_ok": True, "ocr_available": True,
                "text_detected": False, "ocr_frames_checked": 4,
            })
        result = eval_production(prod, db_path=db)
        matched = [r for r in result["results"] if r["render_unit_id"] == "ru_pass"]
        assert len(matched) == 1
        assert matched[0]["status"] == "pass"

    def test_ocr_available_text_detected_fails(self, db, prod):
        """OCR available, text detected → fail."""
        with _db.transaction(db) as conn:
            _create_broll_unit(conn, prod, "ru_fail", "B002")
            _record_qa(conn, prod, "ru_fail", {
                "text_policy_ok": False, "ocr_available": True,
                "text_detected": True, "ocr_frames_checked": 4,
                "sample_detected_text": ["Hello world"],
            })
        result = eval_production(prod, db_path=db)
        matched = [r for r in result["results"] if r["render_unit_id"] == "ru_fail"]
        assert matched[0]["status"] == "fail"
        assert matched[0].get("note") == "visible_text_detected"

    def test_ocr_unavailable_inconclusive(self, db, prod):
        """OCR unavailable, no QA evidence → inconclusive."""
        with _db.transaction(db) as conn:
            _create_broll_unit(conn, prod, "ru_inc", "B003")
            # No QA recorded — OCR was never attempted
        result = eval_production(prod, db_path=db)
        matched = [r for r in result["results"] if r["render_unit_id"] == "ru_inc"]
        assert matched[0]["status"] == "inconclusive"
        assert "requires_human_review" in matched[0].get("note", "")

    def test_ocr_unavailable_strict_fails(self, db, prod):
        """OCR unavailable in strict mode → QA fails (test via evidence)."""
        with _db.transaction(db) as conn:
            _create_broll_unit(conn, prod, "ru_strict", "B004")
            _record_qa(conn, prod, "ru_strict", {
                "text_policy_ok": False, "ocr_available": False,
                "ocr_error": "tesseract binary not available",
            })
        result = eval_production(prod, db_path=db)
        matched = [r for r in result["results"] if r["render_unit_id"] == "ru_strict"]
        assert matched[0]["status"] == "fail"
        assert "ocr_unavailable" in matched[0].get("note", "")

    def test_no_text_policy_passes(self, db, prod):
        """Unit WITHOUT text_policy set is excluded from text-surface eval."""
        from media_service import _qa_provider_video
        # Create unit without text_policy (NULL) — shouldn't trigger text enforcement
        conn2 = sqlite3.connect(db)
        conn2.execute(
            """INSERT INTO render_units
               (id, production_id, label, asset_type, audio_policy, lipsync_required,
                required_start_ms, required_end_ms, required_duration_ms,
                ordinal, status, render_mode, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("ru_no_pol", prod, "B005", "generated_video", "BROLL_FLEX", 0,
             5000, 10000, 5000,
             2, "valid", "generated_video",
             _db._now(), _db._now()),
        )
        conn2.commit()
        conn2.close()
        result = eval_production(prod, db_path=db)
        matched = [r for r in result["results"] if r["render_unit_id"] == "ru_no_pol"]
        # Unit with NULL text_policy won't appear in text-surface eval results
        assert len(matched) == 0, f"NULL text_policy should not trigger text eval: {matched}"

    def test_real_production(self):
        """Eval runs on real production DB."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        result = eval_production("prod_2f9bb58c0508465fb51ac6b4578bba92")
        assert "status" in result
        assert "results" in result
