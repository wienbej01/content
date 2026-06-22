"""ENG-0401: Tests for DB-native local graphic rendering.

Required tests:
1. Local graphic render unit renders a file.
2. Missing deterministic text spec fails.
3. Non-local graphic render unit fails.
4. Artifact is registered in DB.
5. Artifact metadata includes renderer provenance.
6. Active artifact is linked to render unit.
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from production_repo import commit_timeline_spans, plan_render_units
from render_graphics import render_local_graphic_render_unit


# =========================================================================
# Helpers
# =========================================================================

def _make_local_graphic_spec(span_id, deterministic_text_spec, **overrides):
    """Build a span render spec for a local_graphic unit with deterministic text."""
    base = {
        "asset_type": "local_graphic",
        "model": None,
        "audio_policy": "SILENT_GRAPHIC",
        "final_audio_source": "none",
        "provider_audio_usage": "discarded",
        "text_policy": "DETERMINISTIC_GRAPHIC",
        "render_mode": "deterministic_graphic",
        "deterministic_text_spec": deterministic_text_spec,
        "span_id": span_id,
    }
    base.update(overrides)
    return base


# =========================================================================
# ENG-0401: render_local_graphic_render_unit
# =========================================================================

class TestRenderLocalGraphicRenderUnit:
    """Tests for render_local_graphic_render_unit."""

    def test_renders_local_graphic_file(self, db, prod):
        """A local_graphic render unit renders a file with deterministic text."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "MY TITLE CARD", "headline": "MY TITLE CARD"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts),
        ], db_path=db)

        result_path = render_local_graphic_render_unit(db, prod["id"], units[0]["id"])
        assert Path(result_path).exists()
        assert result_path.endswith(".png")

    def test_missing_deterministic_text_spec_fails(self, db, prod):
        """A local_graphic unit without deterministic_text_spec raises RuntimeError."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        spec = _make_local_graphic_spec(spans[0]["id"], {"type": "title_card", "text": "X"})
        del spec["deterministic_text_spec"]
        units = plan_render_units(prod["id"], [spec], db_path=db)

        with pytest.raises(RuntimeError, match="no deterministic_text_spec"):
            render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

    def test_non_local_graphic_fails(self, db, prod):
        """A render unit with asset_type != local_graphic raises RuntimeError."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "BROLL", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            {
                "span_id": spans[0]["id"],
                "asset_type": "generated_video",
                "model": "kling3_0",
                "audio_policy": "BROLL_FLEX",
                "final_audio_source": "none",
                "provider_audio_usage": "discarded",
                "text_policy": "NO_VISIBLE_TEXT",
                "render_mode": "generated_video",
                "visual_function": "illustrate",
                "narrative_claim": "Productivity is rising",
                "information_to_show": "modern office",
                "viewer_takeaway": "people work smarter",
                "required_action": "slow pan",
                "distinctness_requirement": "warm light",
                "semantic_acceptance_criteria": "matches claim",
                "concept_key": "prod_concept",
                "concept_hash": "prod_concept",
            },
        ], db_path=db)

        with pytest.raises(RuntimeError, match="requires asset_type='local_graphic'"):
            render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

    def test_artifact_registered_in_db(self, db, prod):
        """After rendering, an artifact row exists in the DB."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "CARD", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "TEST REGISTRATION", "headline": "TEST REGISTRATION"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        conn = _db.connect(db)
        arts = conn.execute(
            "SELECT id, uri, kind, metadata_json FROM artifacts WHERE production_id=?",
            (prod["id"],)
        ).fetchall()
        conn.close()

        assert len(arts) == 1
        art = dict(arts[0])
        assert art["kind"] == "generated_media"
        assert art["uri"].endswith(".png")

    def test_artifact_metadata_has_renderer_provenance(self, db, prod):
        """Artifact metadata includes render_method, renderer, text_spec_sha256, expected_text."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "SRC", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "source_card", "text": "Harvard Business Review 2025", "headline": "Harvard Business Review"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        conn = _db.connect(db)
        arts = conn.execute(
            "SELECT metadata_json FROM artifacts WHERE production_id=?",
            (prod["id"],)
        ).fetchall()
        conn.close()

        assert len(arts) == 1
        meta = json.loads(arts[0]["metadata_json"])
        assert meta["render_method"] == "local_graphic"
        assert meta["renderer"] == "render_graphics.py"
        assert "text_spec_sha256" in meta
        assert "expected_text" in meta
        assert meta["source_render_unit_id"] == units[0]["id"]

    def test_active_artifact_linked_to_render_unit(self, db, prod):
        """After rendering, render_unit.active_artifact_id is set to the artifact."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "CARD", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "LINKED", "headline": "LINKED"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT active_artifact_id, status FROM render_units WHERE id=?",
            (units[0]["id"],)
        ).fetchone()
        conn.close()

        assert ru["active_artifact_id"] is not None
        assert ru["status"] == "generated"

    def test_source_card_renders_as_lower_third(self, db, prod):
        """Source card deterministic text spec renders as lower_third layout."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "SRC", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "source_card", "text": "McKinsey 2025 report", "headline": "McKinsey"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts),
        ], db_path=db)

        result_path = render_local_graphic_render_unit(db, prod["id"], units[0]["id"])
        assert Path(result_path).exists()

        from PIL import Image
        img = Image.open(result_path)
        assert img.size == (1920, 1080)

    def test_quote_card_renders_as_key_line(self, db, prod):
        """Quote card deterministic text spec renders as key_line layout."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "QT", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "quote_card", "text": "A famous quote", "quote": "A famous quote"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts),
        ], db_path=db)

        result_path = render_local_graphic_render_unit(db, prod["id"], units[0]["id"])
        assert Path(result_path).exists()

        from PIL import Image
        img = Image.open(result_path)
        assert img.size == (1920, 1080)


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
    return _db.ensure_production("test_local_graphic_db", db_path=db)