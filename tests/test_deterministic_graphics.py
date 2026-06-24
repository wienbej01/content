"""Tests for deterministic graphics eval (S03-T001)."""
import json
import sqlite3
from pathlib import Path

import pytest

import production_db as _db
from scripts.evals.eval_deterministic_graphics import eval_graphics_qa_gates


HAS_DB = Path("db/production.db").exists()

# Reuse _qa_local_graphic from media_service
# (import is at fixture-runtime to avoid circular issues before DB is set up)


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
    row = _db.ensure_production("s03_t001_test", db_path=db)
    return row["id"]


def _create_graphic_unit(conn, prod_id, unit_id, label, dts=None, artifact_id=None):
    """Create a local_graphic render unit."""
    meta = json.dumps({"deterministic_text_spec": dts}) if dts else "{}"
    conn.execute(
        """INSERT INTO render_units
           (id, production_id, label, asset_type, audio_policy, lipsync_required,
            required_start_ms, required_end_ms, required_duration_ms,
            ordinal, status, render_mode, metadata_json, active_artifact_id,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (unit_id, prod_id, label, "local_graphic", "SILENT_GRAPHIC", 0,
         15000, 22000, 7000,
         1, "valid", "still_kenburns", meta, artifact_id,
         _db._now(), _db._now()),
    )


def _create_artifact(conn, prod_id, art_id, uri="/tmp/dummy.png", sha="a" * 64):
    """Create a local graphic artifact."""
    conn.execute(
        "INSERT INTO artifacts(id, production_id, kind, sha256, size_bytes, uri, mime_type, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (art_id, prod_id, "local_graphic", sha, 100, uri, "image/png", _db._now()),
    )


def _record_qa(conn, prod_id, unit_id, evidence_dict, status="pass"):
    """Record a qa_media_contract validation."""
    conn.execute(
        "INSERT INTO validations(id, production_id, subject_id, subject_type, "
        "validator_name, status, evidence_json, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (f"val_{unit_id}", prod_id, unit_id, "render_unit",
         "qa_media_contract", status, json.dumps(evidence_dict), _db._now()),
    )


class TestQaTextLengthCheck:
    """_qa_local_graphic text length check."""

    def test_text_length_ok(self, db, prod, tmp_path):
        """Normal text length (1-500 chars) passes."""
        from media_service import _qa_local_graphic
        art_id = "art_len_ok"
        ru_id = "ru_len_ok"
        art_path = tmp_path / "dummy.png"
        art_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        with _db.transaction(db) as conn:
            _create_artifact(conn, prod, art_id, str(art_path))
            _create_graphic_unit(conn, prod, ru_id, "S003",
                                 dts={"text": "Hello world", "font": "Arial"},
                                 artifact_id=art_id)
            ru = conn.execute("SELECT * FROM render_units WHERE id=?", (ru_id,)).fetchone()
            art = conn.execute("SELECT * FROM artifacts WHERE id=?", (art_id,)).fetchone()

        passed, evidence = _qa_local_graphic(prod, dict(ru), dict(art), art_path, db_path=db)
        assert evidence.get("text_length_ok") is True, f"text_length_ok should be True: {evidence}"
        assert "text_length" in evidence

    def test_text_too_long_fails(self, db, prod, tmp_path):
        """Text > 500 chars fails."""
        from media_service import _qa_local_graphic
        art_id = "art_long"
        ru_id = "ru_long"
        art_path = tmp_path / "dummy.png"
        art_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        long_text = "x" * 501

        with _db.transaction(db) as conn:
            _create_artifact(conn, prod, art_id, str(art_path))
            _create_graphic_unit(conn, prod, ru_id, "S003",
                                 dts={"text": long_text, "font": "Arial"},
                                 artifact_id=art_id)
            ru = conn.execute("SELECT * FROM render_units WHERE id=?", (ru_id,)).fetchone()
            art = conn.execute("SELECT * FROM artifacts WHERE id=?", (art_id,)).fetchone()

        passed, evidence = _qa_local_graphic(prod, dict(ru), dict(art), art_path, db_path=db)
        assert evidence.get("text_length_ok") is False
        assert any("text_length" in i for i in evidence.get("issues", []))

    def test_empty_text_fails(self, db, prod, tmp_path):
        """Empty text string fails."""
        from media_service import _qa_local_graphic
        art_id = "art_empty"
        ru_id = "ru_empty"
        art_path = tmp_path / "dummy.png"
        art_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        with _db.transaction(db) as conn:
            _create_artifact(conn, prod, art_id, str(art_path))
            _create_graphic_unit(conn, prod, ru_id, "S003",
                                 dts={"text": "", "font": "Arial"},
                                 artifact_id=art_id)
            ru = conn.execute("SELECT * FROM render_units WHERE id=?", (ru_id,)).fetchone()
            art = conn.execute("SELECT * FROM artifacts WHERE id=?", (art_id,)).fetchone()

        passed, evidence = _qa_local_graphic(prod, dict(ru), dict(art), art_path, db_path=db)
        assert evidence.get("text_length_ok") is False
        assert "text_empty" in evidence.get("issues", [])


class TestEvalGates:
    """Full eval gate check."""

    def test_eval_detects_missing_dts(self, db, prod):
        """Eval detects graphic unit without deterministic_text_spec."""
        with _db.transaction(db) as conn:
            _create_graphic_unit(conn, prod, "ru_no_dts", "NO_DTS", dts=None)
            _record_qa(conn, prod, "ru_no_dts", {
                "file_exists": True, "text_spec_exists": False,
            })
        result = eval_graphics_qa_gates(prod, db_path=db)
        assert result["status"] == "fail"
        no_dts = [r for r in result["results"] if not r["has_deterministic_text_spec"]]
        assert len(no_dts) == 1

    def test_eval_with_real_production(self):
        """Full production eval returns structure."""
        if not HAS_DB:
            pytest.skip("Production DB not available")
        result = eval_graphics_qa_gates("prod_2f9bb58c0508465fb51ac6b4578bba92")
        assert "status" in result
        assert "results" in result
