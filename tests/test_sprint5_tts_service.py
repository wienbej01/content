"""Tests for Sprint 5: tts_service.py
(TTS artifact provenance, timing spans from map, render plan compilation, budget)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from tts_service import (
    record_tts_artifact, commit_timing_spans_from_map,
    reconcile_storyboard_with_timing, compile_render_plan,
    request_spend_approval, record_cost_event, get_total_spend,
)
from authoring_service import save_storyboard, record_approval_decision, request_approval


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("sprint5_test", db_path=db)


@pytest.fixture
def audio_file(tmp_path):
    p = tmp_path / "narration.mp3"
    p.write_bytes(b"fake audio data " * 100)
    return p


class TestTTSArtifact:
    def test_record_tts_creates_artifact(self, db, prod, audio_file):
        _db.mirror_stage_state("sprint5_test", "write_script", "succeeded", db_path=db)
        # Need an active script revision first
        from stage_runner import save_document_revision
        script_doc = save_document_revision(prod["id"], "script", {"text": "hello"}, db_path=db)
        art = record_tts_artifact(
            prod["id"], audio_file, script_doc["id"],
            {"voice_id": "james", "stability": 0.5},
            db_path=db,
        )
        assert art["kind"] == "tts_master"
        assert art["sha256"] is not None

    def test_missing_audio_file_raises(self, db, prod):
        with pytest.raises(FileNotFoundError):
            record_tts_artifact(prod["id"], "/nonexistent/audio.mp3", "rev_id", {}, db_path=db)

    def test_idempotent(self, db, prod, audio_file):
        from stage_runner import save_document_revision
        script_doc = save_document_revision(prod["id"], "script", {"text": "hello"}, db_path=db)
        art1 = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)
        art2 = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)
        assert art1["id"] == art2["id"]


class TestTimingSpans:
    def test_commit_from_map(self, db, prod, audio_file):
        from stage_runner import save_document_revision
        script_doc = save_document_revision(prod["id"], "script", {"text": "test"}, db_path=db)
        art = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)

        timing_map = [
            {"label": "B001", "start_ms": 0, "end_ms": 3000, "narration_text": "Hello"},
            {"label": "B002", "start_ms": 3000, "end_ms": 7500, "narration_text": "World"},
        ]
        spans = commit_timing_spans_from_map(prod["id"], art["id"], timing_map, db_path=db)
        assert len(spans) == 2
        assert spans[0]["start_ms"] == 0
        assert spans[1]["end_ms"] == 7500

    def test_sec_to_ms_conversion(self, db, prod, audio_file):
        from stage_runner import save_document_revision
        script_doc = save_document_revision(prod["id"], "script", {"text": "test"}, db_path=db)
        art = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)
        timing_map = [{"label": "B001", "start_sec": 0.0, "end_sec": 3.5}]
        spans = commit_timing_spans_from_map(prod["id"], art["id"], timing_map, db_path=db)
        assert spans[0]["start_ms"] == 0
        assert spans[0]["end_ms"] == 3500

    def test_empty_map_raises(self, db, prod):
        with pytest.raises(ValueError, match="empty"):
            commit_timing_spans_from_map(prod["id"], "art_id", [], db_path=db)


class TestStoryboardReconciliation:
    def test_reconcile_matches_by_label(self, db, prod, audio_file):
        from stage_runner import save_document_revision
        script_doc = save_document_revision(prod["id"], "script", {"text": "test"}, db_path=db)
        art = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)
        save_storyboard(prod["id"], {
            "beats": [
                {"label": "B001", "shot_type": "lipsync", "narration_text": "A"},
                {"label": "B002", "shot_type": "b_roll", "narration_text": "B"},
            ]
        }, db_path=db)
        commit_timing_spans_from_map(prod["id"], art["id"], [
            {"label": "B001", "start_ms": 0, "end_ms": 3000},
            {"label": "B002", "start_ms": 3000, "end_ms": 6000},
        ], db_path=db)
        result = reconcile_storyboard_with_timing(prod["id"], db_path=db)
        assert result["matched"] == 2
        assert result["unmatched"] == []

    def test_reconcile_no_spans_raises(self, db, prod):
        with pytest.raises(RuntimeError, match="No active timeline spans"):
            reconcile_storyboard_with_timing(prod["id"], db_path=db)


class TestRenderPlan:
    def test_compile_render_plan(self, db, prod, audio_file):
        from stage_runner import save_document_revision
        from production_repo import commit_timeline_spans
        script_doc = save_document_revision(prod["id"], "script", {"text": "test"}, db_path=db)
        art = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)
        spans = commit_timing_spans_from_map(prod["id"], art["id"], [
            {"label": "B001", "start_ms": 0, "end_ms": 4000},
        ], db_path=db)
        span_specs = [{
            "span_id": spans[0]["id"],
            "asset_type": "lipsync_video",
            "model": "seedance_2_0",
            "audio_policy": "baked_in",
        }]
        plan = compile_render_plan(prod["id"], span_specs, estimated_cost_usd=5.0, db_path=db)
        assert len(plan["render_units"]) == 1
        assert plan["estimated_usd"] == 5.0
        assert plan["plan_revision_id"]


class TestBudget:
    def test_request_spend_approval(self, db, prod, audio_file):
        from stage_runner import save_document_revision
        script_doc = save_document_revision(prod["id"], "script", {"text": "test"}, db_path=db)
        art = record_tts_artifact(prod["id"], audio_file, script_doc["id"], {}, db_path=db)
        spans = commit_timing_spans_from_map(prod["id"], art["id"], [
            {"label": "B001", "start_ms": 0, "end_ms": 4000},
        ], db_path=db)
        plan = compile_render_plan(prod["id"], [{
            "span_id": spans[0]["id"],
            "asset_type": "lipsync_video",
        }], estimated_cost_usd=10.0, db_path=db)
        ar = request_spend_approval(prod["id"], plan["plan_revision_id"], 10.0, db_path=db)
        assert ar["status"] == "pending"
        assert ar["gate_name"] == "gate_a_spend"

    def test_cost_event_append_only(self, db, prod):
        record_cost_event(prod["id"], "tts_generation", "elevenlabs",
                          estimated_usd=0.50, db_path=db)
        record_cost_event(prod["id"], "image_generation", "higgsfield",
                          actual_usd=1.20, db_path=db)
        spend = get_total_spend(prod["id"], db_path=db)
        assert spend["total_estimated"] == pytest.approx(0.50)
        assert spend["total_actual"] == pytest.approx(1.20)
        assert spend["event_count"] == 2
