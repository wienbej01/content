"""Tests for Sprint 2: production_repo.py
(Timeline spans, render units, artifact registry — ID-202, ID-203, ART-204)
"""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from production_repo import (
    commit_timeline_spans, get_active_timeline_spans, TimelineSpanError,
    plan_render_units, invalidate_render_units, get_render_units, RenderUnitError,
    register_artifact, verify_artifact_on_disk, link_artifact_to_render_unit,
    ArtifactRegistryError,
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
    return _db.ensure_production("test_proj_sprint2", db_path=db)


# ---------------------------------------------------------------------------
# Timeline span tests
# ---------------------------------------------------------------------------

class TestTimelineSpans:
    def test_basic_commit(self, db, prod):
        spans = [
            {"label": "B001", "start_ms": 0, "end_ms": 3000, "narration_text": "Hello world"},
            {"label": "B002", "start_ms": 3000, "end_ms": 7000, "narration_text": "Second"},
        ]
        result = commit_timeline_spans(prod["id"], spans, db_path=db)
        assert len(result) == 2
        assert result[0]["start_ms"] == 0
        assert result[0]["end_ms"] == 3000
        assert result[0]["duration_ms"] == 3000
        assert result[0]["status"] == "active"

    def test_end_gt_start_enforced(self, db, prod):
        with pytest.raises(TimelineSpanError, match="end_ms"):
            commit_timeline_spans(
                prod["id"],
                [{"label": "B001", "start_ms": 5000, "end_ms": 3000}],
                db_path=db,
            )

    def test_zero_duration_rejected(self, db, prod):
        with pytest.raises(TimelineSpanError):
            commit_timeline_spans(
                prod["id"],
                [{"label": "B001", "start_ms": 3000, "end_ms": 3000}],
                db_path=db,
            )

    def test_overlap_rejected(self, db, prod):
        spans = [
            {"label": "A", "start_ms": 0, "end_ms": 4000},
            {"label": "B", "start_ms": 3000, "end_ms": 7000},  # overlaps A
        ]
        with pytest.raises(TimelineSpanError, match="overlaps"):
            commit_timeline_spans(prod["id"], spans, db_path=db)

    def test_empty_spans_rejected(self, db, prod):
        with pytest.raises(TimelineSpanError, match="empty"):
            commit_timeline_spans(prod["id"], [], db_path=db)

    def test_supersedes_prior_active(self, db, prod):
        spans_v1 = [{"label": "B001", "start_ms": 0, "end_ms": 3000}]
        spans_v2 = [{"label": "B001", "start_ms": 0, "end_ms": 5000}]
        commit_timeline_spans(prod["id"], spans_v1, db_path=db)
        commit_timeline_spans(prod["id"], spans_v2, db_path=db)
        active = get_active_timeline_spans(prod["id"], db_path=db)
        assert len(active) == 1
        assert active[0]["duration_ms"] == 5000

    def test_narration_text_sha_stored(self, db, prod):
        text = "Some narration here"
        spans = [{"label": "B001", "start_ms": 0, "end_ms": 5000, "narration_text": text}]
        result = commit_timeline_spans(prod["id"], spans, db_path=db)
        expected_sha = hashlib.sha256(text.encode()).hexdigest()
        assert result[0]["narration_text_sha256"] == expected_sha

    def test_non_integer_ms_rejected(self, db, prod):
        with pytest.raises(TimelineSpanError, match="integer"):
            commit_timeline_spans(
                prod["id"],
                [{"label": "B001", "start_ms": 0.5, "end_ms": 3000}],
                db_path=db,
            )


# ---------------------------------------------------------------------------
# Render unit tests
# ---------------------------------------------------------------------------

class TestRenderUnits:
    def _make_span(self, prod_id, db):
        spans = [{"label": "B001", "start_ms": 0, "end_ms": 5000}]
        return commit_timeline_spans(prod_id, spans, db_path=db)[0]

    def test_basic_plan(self, db, prod):
        span = self._make_span(prod["id"], db)
        specs = [{
            "span_id": span["id"],
            "asset_type": "lipsync_video",
            "model": "seedance_2_0",
            "audio_policy": "baked_in",
            "lipsync_required": True,
        }]
        units = plan_render_units(prod["id"], specs, db_path=db)
        assert len(units) == 1
        u = units[0]
        assert u["asset_type"] == "lipsync_video"
        assert u["required_start_ms"] == 0
        assert u["required_end_ms"] == 5000
        assert u["required_duration_ms"] == 5000
        assert u["status"] == "ordered"
        assert u["lipsync_required"] == 1

    def test_multi_slot_expansion(self, db, prod):
        span = self._make_span(prod["id"], db)
        specs = [{
            "span_id": span["id"],
            "asset_type": "lipsync_video",
            "model": "seedance_2_0",
            "audio_policy": "baked_in",
            "slots": [
                {"slot_index": 0, "slot_total": 2, "start_ms": 0, "end_ms": 2500},
                {"slot_index": 1, "slot_total": 2, "start_ms": 2500, "end_ms": 5000},
            ],
        }]
        units = plan_render_units(prod["id"], specs, db_path=db)
        assert len(units) == 2
        assert units[0]["slot_index"] == 0
        assert units[1]["slot_index"] == 1

    def test_invalid_span_id_raises(self, db, prod):
        with pytest.raises(RenderUnitError, match="not found"):
            plan_render_units(prod["id"], [{"span_id": "nonexistent", "asset_type": "x"}], db_path=db)

    def test_stale_span_rejected(self, db, prod):
        spans = [{"label": "B001", "start_ms": 0, "end_ms": 5000}]
        created = commit_timeline_spans(prod["id"], spans, db_path=db)
        # Supersede by committing new spans
        commit_timeline_spans(prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 6000}], db_path=db)
        with pytest.raises(RenderUnitError, match="not active"):
            plan_render_units(prod["id"], [{"span_id": created[0]["id"], "asset_type": "x"}], db_path=db)

    def test_invalidate_render_units(self, db, prod):
        span = self._make_span(prod["id"], db)
        plan_render_units(prod["id"], [{"span_id": span["id"], "asset_type": "still_kenburns"}], db_path=db)
        count = invalidate_render_units(prod["id"], [span["id"]], db_path=db)
        assert count == 1
        stale = get_render_units(prod["id"], status="stale", db_path=db)
        assert len(stale) == 1

    def test_empty_specs_raises(self, db, prod):
        with pytest.raises(RenderUnitError):
            plan_render_units(prod["id"], [], db_path=db)

    def test_invalid_slot_duration_raises(self, db, prod):
        span = self._make_span(prod["id"], db)
        with pytest.raises(RenderUnitError, match="end_ms"):
            plan_render_units(
                prod["id"],
                [{"span_id": span["id"], "asset_type": "x",
                  "slots": [{"start_ms": 5000, "end_ms": 1000}]}],
                db_path=db,
            )


# ---------------------------------------------------------------------------
# Artifact registry tests
# ---------------------------------------------------------------------------

class TestArtifactRegistry:
    def test_register_text_file(self, db, prod, tmp_path):
        f = tmp_path / "script.json"
        f.write_text('{"hello": "world"}')
        art = register_artifact(prod["id"], f, "script", db_path=db)
        assert art["sha256"] is not None
        assert art["uri"] == str(f.resolve())
        assert art["kind"] == "script"
        assert art["storage_backend"] == "local"

    def test_idempotent_registration(self, db, prod, tmp_path):
        f = tmp_path / "file.mp4"
        f.write_bytes(b"fake video data")
        art1 = register_artifact(prod["id"], f, "media", db_path=db)
        art2 = register_artifact(prod["id"], f, "media", db_path=db)
        assert art1["id"] == art2["id"]

    def test_changed_file_new_artifact(self, db, prod, tmp_path):
        f = tmp_path / "file.mp4"
        f.write_bytes(b"version 1")
        art1 = register_artifact(prod["id"], f, "media", db_path=db)
        f.write_bytes(b"version 2")
        art2 = register_artifact(prod["id"], f, "media", db_path=db)
        assert art1["id"] != art2["id"]
        assert art1["sha256"] != art2["sha256"]

    def test_missing_file_raises(self, db, prod):
        with pytest.raises(ArtifactRegistryError, match="not found"):
            register_artifact(prod["id"], "/nonexistent/file.mp4", "media", db_path=db)

    def test_verify_on_disk_ok(self, db, prod, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")
        art = register_artifact(prod["id"], f, "text", db_path=db)
        ok, msg = verify_artifact_on_disk(art["id"], db_path=db)
        assert ok, msg

    def test_verify_detects_modification(self, db, prod, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("original")
        art = register_artifact(prod["id"], f, "text", db_path=db)
        f.write_text("tampered")
        ok, msg = verify_artifact_on_disk(art["id"], db_path=db)
        assert not ok
        assert "mismatch" in msg

    def test_verify_detects_missing(self, db, prod, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")
        art = register_artifact(prod["id"], f, "text", db_path=db)
        f.unlink()
        ok, msg = verify_artifact_on_disk(art["id"], db_path=db)
        assert not ok
        assert "missing" in msg

    def test_link_to_render_unit(self, db, prod, tmp_path):
        f = tmp_path / "clip.mp4"
        f.write_bytes(b"fake mp4")
        span = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )[0]
        units = plan_render_units(
            prod["id"], [{"span_id": span["id"], "asset_type": "lipsync_video"}], db_path=db
        )
        art = register_artifact(prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
        updated = get_render_units(prod["id"], db_path=db)
        assert updated[0]["active_artifact_id"] == art["id"]
        assert updated[0]["status"] == "generated"

    def test_cross_production_link_rejected(self, db, tmp_path):
        p1 = _db.ensure_production("cross_p1", db_path=db)
        p2 = _db.ensure_production("cross_p2", db_path=db)
        f = tmp_path / "f.mp4"
        f.write_bytes(b"x")
        span = commit_timeline_spans(p2["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db)[0]
        units = plan_render_units(p2["id"], [{"span_id": span["id"], "asset_type": "x"}], db_path=db)
        art = register_artifact(p1["id"], f, "media", db_path=db)
        with pytest.raises(ArtifactRegistryError, match="different productions"):
            link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
