"""ENG-0402: Integration tests for graphics_compositing stage.

Required tests:
1. graphics_compositing renders all pending local_graphic units.
2. It creates zero provider jobs.
3. Rerun is idempotent.
4. Old provider-generated local graphic can be invalidated and replaced locally.
5. Local graphic artifact is usable by assembly input builder.
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from produce_db import invoke_graphics_compositing
from production_repo import commit_timeline_spans, plan_render_units


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
    return _db.ensure_production("test_gfx_compositing", video_type="short", db_path=db)


# =========================================================================
# Helpers
# =========================================================================

def _make_gfx_spec(span_id, asset_type="local_graphic", dts=None, **overrides):
    if asset_type == "local_graphic":
        base = {
            "asset_type": "local_graphic",
            "model": None,
            "audio_policy": "SILENT_GRAPHIC",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "DETERMINISTIC_GRAPHIC",
            "render_mode": "deterministic_graphic",
            "deterministic_text_spec": dts or {"type": "title_card", "text": "TEST", "headline": "TEST"},
            "span_id": span_id,
        }
    else:
        base = {
            "asset_type": asset_type,
            "model": "kling3_0",
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "NO_VISIBLE_TEXT",
            "render_mode": "generated_video",
            "visual_function": "illustrate",
            "narrative_claim": "test narrative",
            "information_to_show": "test visual",
            "viewer_takeaway": "test takeaway",
            "required_action": "slow pan",
            "distinctness_requirement": "test distinctness",
            "semantic_acceptance_criteria": "matches test",
            "concept_key": "test_concept",
            "concept_hash": "test_concept",
            "span_id": span_id,
        }
    base.update(overrides)
    return base


def _count_provider_jobs(production_id, db_path):
    conn = _db.connect(db_path)
    cnt = conn.execute(
        "SELECT COUNT(*) as c FROM provider_jobs WHERE production_id=?",
        (production_id,)
    ).fetchone()["c"]
    conn.close()
    return cnt


def _count_artifacts(production_id, db_path):
    conn = _db.connect(db_path)
    cnt = conn.execute(
        "SELECT COUNT(*) as c FROM artifacts WHERE production_id=?",
        (production_id,)
    ).fetchone()["c"]
    conn.close()
    return cnt


# =========================================================================
# ENG-0402: graphics_compositing stage
# =========================================================================

class TestGraphicsCompositing:
    """Integration tests for invoke_graphics_compositing."""

    def test_renders_all_pending_local_graphic_units(self, db, prod):
        """Compositing renders all pending local_graphic units."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
            {"label": "SOURCE", "start_ms": 5000, "end_ms": 10000},
            {"label": "BROLL", "start_ms": 10000, "end_ms": 15000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_gfx_spec(spans[0]["id"], dts={"type": "title_card", "text": "TITLE", "headline": "TITLE"}),
            _make_gfx_spec(spans[1]["id"], dts={"type": "source_card", "text": "Source text", "headline": "SRC"}),
            _make_gfx_spec(spans[2]["id"], asset_type="generated_video"),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_gfx_compositing", "video_type": "short"}
        result = invoke_graphics_compositing(inputs, Path("/tmp"))

        assert result["status"] == "completed"
        assert result["graphics_units"] == 2
        assert result["local_graphic_rendered"] == 2

        conn = _db.connect(db)
        rendered = conn.execute(
            """SELECT id, asset_type, active_artifact_id, status
               FROM render_units
               WHERE production_id=? AND asset_type='local_graphic'""",
            (prod["id"],)
        ).fetchall()
        conn.close()

        for ru in rendered:
            assert ru["active_artifact_id"] is not None, f"{ru['id']} has no artifact"
            assert ru["status"] in ("generated",), f"{ru['id']} status is {ru['status']}"

    def test_creates_zero_provider_jobs(self, db, prod):
        """Compositing creates zero provider jobs for local graphics."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_gfx_spec(spans[0]["id"]),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_gfx_compositing", "video_type": "short"}
        invoke_graphics_compositing(inputs, Path("/tmp"))

        assert _count_provider_jobs(prod["id"], db) == 0

    def test_rerun_is_idempotent(self, db, prod):
        """Rerunning graphics_compositing does not create duplicate artifacts."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_gfx_spec(spans[0]["id"]),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_gfx_compositing", "video_type": "short"}

        result1 = invoke_graphics_compositing(inputs, Path("/tmp"))
        assert result1["local_graphic_rendered"] == 1
        art_count_after_first = _count_artifacts(prod["id"], db)

        result2 = invoke_graphics_compositing(inputs, Path("/tmp"))
        assert result2["rendered"] == 1
        art_count_after_second = _count_artifacts(prod["id"], db)

        assert art_count_after_second == art_count_after_first, "Idempotency violated: duplicate artifact created"

    def test_invalidate_and_replace_local_graphic(self, db, prod):
        """Old local graphic can be invalidated and replaced locally on rerun."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_gfx_spec(spans[0]["id"], dts={"type": "title_card", "text": "VERSION_ONE", "headline": "VERSION_ONE"}),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_gfx_compositing", "video_type": "short"}
        invoke_graphics_compositing(inputs, Path("/tmp"))

        conn = _db.connect(db)
        original_ru = conn.execute(
            "SELECT id, active_artifact_id, status FROM render_units WHERE production_id=? AND status!='stale'",
            (prod["id"],)
        ).fetchone()
        original_artifact_id = original_ru["active_artifact_id"]
        conn.close()

        assert original_artifact_id is not None

        from production_repo import invalidate_render_units
        invalidate_render_units(prod["id"], [spans[0]["id"]], reason="test invalidation", db_path=db)

        plan_render_units(prod["id"], [
            _make_gfx_spec(spans[0]["id"], dts={"type": "title_card", "text": "VERSION_TWO", "headline": "VERSION_TWO"}),
        ], db_path=db)

        result = invoke_graphics_compositing(inputs, Path("/tmp"))
        assert result["local_graphic_rendered"] == 1

        conn = _db.connect(db)
        new_ru = conn.execute(
            "SELECT id, active_artifact_id, status FROM render_units WHERE production_id=? AND status!='stale'",
            (prod["id"],)
        ).fetchone()
        conn.close()

        assert new_ru is not None
        assert new_ru["active_artifact_id"] is not None
        assert new_ru["active_artifact_id"] != original_artifact_id
        assert new_ru["id"] != original_ru["id"]

    def test_local_graphic_artifact_has_assembly_usable_metadata(self, db, prod):
        """Local graphic artifact metadata includes fields assembly needs."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_gfx_spec(spans[0]["id"]),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_gfx_compositing", "video_type": "short"}
        invoke_graphics_compositing(inputs, Path("/tmp"))

        conn = _db.connect(db)
        arts = conn.execute(
            "SELECT uri, kind, mime_type, metadata_json FROM artifacts WHERE production_id=?",
            (prod["id"],)
        ).fetchall()
        conn.close()

        assert len(arts) >= 1
        for art in arts:
            meta = json.loads(art["metadata_json"])
            assert meta.get("render_method") in ("local_graphic", "local_graphic_animated")
            assert meta.get("renderer") == "render_graphics.py"
            assert "expected_text" in meta
            uri = art["uri"]
            assert uri.endswith(".png") or uri.endswith(".mp4"), f"Expected PNG or MP4 artifact, got {uri}"