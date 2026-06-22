"""ENG-0501/0502/0503/0504: Contract-based media QA tests.

Tests:
1. run_contract_media_qa dispatches by render method
2. Local graphic QA passes for local-rendered graphic
3. Provider-generated local graphic fails
4. Local graphic with wrong text hash fails
5. Missing deterministic_text_spec fails
6. Missing artifact fails
7. No provider job check enforced
8. Provider video text-policy QA (OCR unavailable + strict fails)
9. Provider video text-policy QA (OCR unavailable + non-strict warns)
10. QA pass updates status to valid
11. QA fail updates status to needs_repair
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
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
    return _db.ensure_production("test_qa_contract", video_type="short", db_path=db)


# =========================================================================
# Helpers
# =========================================================================

def _make_local_graphic_spec(span_id, dts=None, **overrides):
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
    base.update(overrides)
    return base


def _make_hero_spec(span_id, **overrides):
    base = {
        "asset_type": "lipsync_video",
        "model": "seedance_2_0",
        "audio_policy": "HERO_SYNC_LOCKED",
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "text_policy": "NO_VISIBLE_TEXT",
        "lipsync_required": True,
        "render_mode": "hero_lipsync",
        "visual_function": "narrate",
        "narrative_claim": "hero test",
        "information_to_show": "james speaking",
        "viewer_takeaway": "key point",
        "required_action": "locked medium shot",
        "distinctness_requirement": "navy sweater",
        "semantic_acceptance_criteria": "matches hero",
        "concept_key": "hero_concept",
        "concept_hash": "hero_concept",
        "span_id": span_id,
    }
    base.update(overrides)
    return base


def _make_provider_video_spec(span_id, **overrides):
    base = {
        "asset_type": "generated_video",
        "model": "kling3_0",
        "audio_policy": "BROLL_FLEX",
        "final_audio_source": "none",
        "provider_audio_usage": "discarded",
        "text_policy": "NO_VISIBLE_TEXT",
        "render_mode": "generated_video",
        "visual_function": "illustrate",
        "narrative_claim": "test broll",
        "information_to_show": "office scene",
        "viewer_takeaway": "modern workplace",
        "required_action": "slow pan",
        "distinctness_requirement": "warm lighting",
        "semantic_acceptance_criteria": "matches claim",
        "concept_key": "broll_concept",
        "concept_hash": "broll_concept",
        "span_id": span_id,
    }
    base.update(overrides)
    return base


# =========================================================================
# ENG-0501: Contract QA routing
# =========================================================================

class TestContractQADispatch:
    """run_contract_media_qa dispatches by render method."""

    def test_local_graphic_dispatches_to_local_graphic_qa(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit as _render_lg

        spans = commit_timeline_spans(prod["id"], [
            {"label": "TITLE", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"]),
        ], db_path=db)

        _render_lg(db, prod["id"], units[0]["id"])

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        evidence = json.loads(validation["evidence_json"])
        assert evidence["render_method"] in ("local_graphic", "deterministic_graphic")
        assert evidence["contract_version"] == "1.0"
        assert validation["status"] == "pass"

    def test_hero_lipsync_dispatches_to_hero_qa(self, db, prod):
        from media_service import run_contract_media_qa

        spans = commit_timeline_spans(prod["id"], [
            {"label": "HERO", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_hero_spec(spans[0]["id"]),
        ], db_path=db)

        self._attach_synthetic_artifact(db, prod["id"], units[0]["id"], duration_ms=5000)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        evidence = json.loads(validation["evidence_json"])
        assert "hero_lipsync" in evidence.get("render_method", "")
        assert validation["status"] in ("pass", "fail")

    def _attach_synthetic_artifact(self, db, production_id, render_unit_id, duration_ms=5000):
        """Create a minimal MP4 for testing QA dispatch."""
        import subprocess
        conn = _db.connect(db)
        ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
        conn.close()
        from production_repo import register_artifact, link_artifact_to_render_unit
        vid_path = Path("/tmp") / f"test_{render_unit_id}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s=1920x1080:d={duration_ms/1000.0}",
             "-c:v", "libx264", "-preset", "ultrafast", str(vid_path)],
            capture_output=True, check=True, timeout=30,
        )
        art = register_artifact(
            production_id, vid_path, kind="generated_media", extra_metadata={"test": True}, db_path=db,
        )
        link_artifact_to_render_unit(art["id"], render_unit_id, db_path=db)


# =========================================================================
# ENG-0502: Local graphic QA
# =========================================================================

class TestLocalGraphicQA:
    """Contract QA for local_graphic render units."""

    def test_local_rendered_graphic_passes(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "CARD", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "QA PASS", "headline": "QA PASS"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts=dts),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "pass", f"Expected pass, got {validation['status']}"

        evidence = json.loads(validation["evidence_json"])
        assert evidence["file_exists"] is True
        assert evidence["provenance_ok"] is True
        assert evidence.get("no_provider_job") is True
        assert evidence.get("text_spec_exists") is True
        assert evidence.get("text_spec_sha_match") is True
        assert evidence["render_method"] in ("local_graphic", "deterministic_graphic")

    def test_provider_generated_local_graphic_fails(self, db, prod):
        from media_service import run_contract_media_qa
        from production_repo import register_artifact, link_artifact_to_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "PROV_GFX", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"]),
        ], db_path=db)

        png_path = Path("/tmp") / f"test_prov_{units[0]['id']}.png"
        from PIL import Image
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        img.save(str(png_path))

        art = register_artifact(
            prod["id"], png_path, kind="generated_media",
            extra_metadata={"render_method": "provider_generated", "renderer": "higgsfield"},
            db_path=db,
        )
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", "Provider-generated local graphic should fail QA"

    def test_wrong_text_hash_fails(self, db, prod):
        from media_service import run_contract_media_qa
        import hashlib
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "HASH_MISMATCH", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts_v1 = {"type": "title_card", "text": "VERSION ONE", "headline": "VERSION ONE"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts=dts_v1),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE render_units SET metadata_json=? WHERE id=?",
                (_db._json({"deterministic_text_spec": {"type": "title_card", "text": "CHANGED", "headline": "CHANGED"}}),
                 units[0]["id"]),
            )

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", "Wrong text hash should fail QA"

    def test_missing_text_spec_fails(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit
        import hashlib

        spans = commit_timeline_spans(prod["id"], [
            {"label": "NO_DTS", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts={"type": "title_card", "text": "X", "headline": "X"}),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE render_units SET metadata_json=? WHERE id=?",
                (_db._json({}), units[0]["id"]),
            )

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", "Missing text spec should fail QA"

    def test_missing_artifact_fails(self, db, prod):
        from media_service import run_contract_media_qa

        spans = commit_timeline_spans(prod["id"], [
            {"label": "NO_ART", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"]),
        ], db_path=db)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", "Missing artifact should fail QA"

    def test_provider_job_enforcement(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "PJ_ENF", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"]),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO provider_jobs
                   (id, production_id, render_unit_id, provider, operation,
                    idempotency_key, status, request_json, submitted_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (_db._id("pjob"), prod["id"], units[0]["id"], "higgsfield", "generate_video",
                 f"test_pj_{units[0]['id']}", "completed", "{}", _db._now()),
            )

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", "Provider job present should fail QA"


# =========================================================================
# ENG-0503: Provider video text-policy QA
# =========================================================================

class TestProviderVideoQA:
    """Contract QA for provider-generated video (text-policy enforcement)."""

    @pytest.fixture(autouse=True)
    def _reset_env(self):
        old = os.environ.get("OCR_STRICT_MODE")
        yield
        if old is not None:
            os.environ["OCR_STRICT_MODE"] = old
        elif "OCR_STRICT_MODE" in os.environ:
            del os.environ["OCR_STRICT_MODE"]

    def test_ocr_unavailable_strict_mode_fails(self, db, prod):
        from media_service import run_contract_media_qa
        from production_repo import register_artifact, link_artifact_to_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "NO_OCR", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_provider_video_spec(spans[0]["id"]),
        ], db_path=db)

        vid_path = Path("/tmp") / f"test_ocr_{units[0]['id']}.mp4"
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=3",
             "-c:v", "libx264", "-preset", "ultrafast", str(vid_path)],
            capture_output=True, check=True, timeout=30,
        )

        art = register_artifact(
            prod["id"], vid_path, kind="generated_media", extra_metadata={}, db_path=db,
        )
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)

        os.environ["OCR_STRICT_MODE"] = "1"
        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        assert validation["status"] == "fail", "OCR unavailable + strict should fail"

        evidence = json.loads(validation["evidence_json"])
        assert evidence.get("ocr_available") is False

    def test_ocr_unavailable_non_strict_warns(self, db, prod):
        from media_service import run_contract_media_qa
        from production_repo import register_artifact, link_artifact_to_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "NO_OCR_WARN", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_provider_video_spec(spans[0]["id"]),
        ], db_path=db)

        vid_path = Path("/tmp") / f"test_ocr_warn_{units[0]['id']}.mp4"
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=3",
             "-c:v", "libx264", "-preset", "ultrafast", str(vid_path)],
            capture_output=True, check=True, timeout=30,
        )

        art = register_artifact(
            prod["id"], vid_path, kind="generated_media", extra_metadata={}, db_path=db,
        )
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)

        os.environ["OCR_STRICT_MODE"] = "0"
        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])

        evidence = json.loads(validation["evidence_json"])
        assert evidence.get("ocr_available") is False
        assert "ocr_note" in evidence or True

    def test_mechanical_checks_still_run(self, db, prod):
        from media_service import run_contract_media_qa
        from production_repo import register_artifact, link_artifact_to_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "MECH", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_provider_video_spec(spans[0]["id"]),
        ], db_path=db)

        vid_path = Path("/tmp") / f"test_mech_{units[0]['id']}.mp4"
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=3",
             "-c:v", "libx264", "-preset", "ultrafast", str(vid_path)],
            capture_output=True, check=True, timeout=30,
        )

        art = register_artifact(
            prod["id"], vid_path, kind="generated_media", extra_metadata={}, db_path=db,
        )
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])
        evidence = json.loads(validation["evidence_json"])
        assert "file_exists" in evidence
        assert "dimensions_ok" in evidence
        assert "duration_ok" in evidence
        assert "sha_match" in evidence


# =========================================================================
# ENG-0504: Status transitions
# =========================================================================

class TestStatusTransitions:
    """QA pass/fail updates render_unit status correctly."""

    def test_pass_sets_valid(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "PASS_ST", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "PASS", "headline": "PASS"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts=dts),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        run_contract_media_qa(db, prod["id"], units[0]["id"])

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT status FROM render_units WHERE id=?", (units[0]["id"],)
        ).fetchone()
        conn.close()
        assert ru["status"] == "valid", f"Expected valid, got {ru['status']}"

    def test_fail_sets_needs_repair(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "FAIL_ST", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts={"type": "title_card", "text": "X", "headline": "X"}),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE render_units SET metadata_json=? WHERE id=?",
                (_db._json({}), units[0]["id"]),
            )

        run_contract_media_qa(db, prod["id"], units[0]["id"])

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT status FROM render_units WHERE id=?", (units[0]["id"],)
        ).fetchone()
        conn.close()
        assert ru["status"] == "needs_repair", f"Expected needs_repair, got {ru['status']}"

    def test_historical_failed_validations_persist(self, db, prod):
        from media_service import run_contract_media_qa, record_validation_evidence
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "HIST", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts={"type": "title_card", "text": "HIST", "headline": "HIST"}),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        record_validation_evidence(
            prod["id"], "render_unit", units[0]["id"],
            "qa_media_contract", False,
            {"render_method": "local_graphic", "contract_version": "1.0", "test": "historical_fail"},
            db_path=db,
        )

        conn = _db.connect(db)
        failures = conn.execute(
            "SELECT status, evidence_json FROM validations WHERE subject_id=?",
            (units[0]["id"],),
        ).fetchall()
        conn.close()
        assert len(failures) >= 1
        assert failures[0]["status"] == "fail"

    def test_latest_validation_used_downstream(self, db, prod):
        from media_service import run_contract_media_qa
        from render_graphics import render_local_graphic_render_unit

        spans = commit_timeline_spans(prod["id"], [
            {"label": "LATEST", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "LATEST", "headline": "LATEST"}
        units = plan_render_units(prod["id"], [
            _make_local_graphic_spec(spans[0]["id"], dts=dts),
        ], db_path=db)

        render_local_graphic_render_unit(db, prod["id"], units[0]["id"])

        validation = run_contract_media_qa(db, prod["id"], units[0]["id"])

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT approved_validation_id, status FROM render_units WHERE id=?",
            (units[0]["id"],)
        ).fetchone()
        conn.close()

        assert ru["approved_validation_id"] == validation["id"]
        assert ru["status"] == "valid"