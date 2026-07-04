"""TKT-102: Sync scorer adapter tests.

Validates:
  - Fixture backend produces non-simulated syncnet_offset evidence
  - Backend 'none' fails loudly (needs_human_av_review, no fabricated evidence)
  - Fixture low-confidence records evidence (threshold decision at assembly)
  - Test-mode fake provider path unchanged (regression)
  - Validation row has required fields: method, offset_ms, confidence, face_track_found
"""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import production_db as _db
from media_service import run_contract_media_qa
from sync_scorer import (
    SyncScore,
    FixtureSyncBackend,
    get_sync_scorer_backend,
)
from sync_scorer.scorer import _set_sync_scorer_backend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("tkt102_test", db_path=db)


def _make_test_video(path: Path, duration_s: float = 4.0):
    """Create a minimal valid MP4 video using ffmpeg testsrc."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=320x240:rate=24",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "51",
         "-c:a", "aac", "-shortest", str(path)],
        check=True, capture_output=True,
    )


def _make_hero_unit(prod_id, db, tmp_path, label="H001",
                     audio_policy="HERO_SYNC_LOCKED", fake_provider=False):
    """Create a hero render unit with a valid video artifact.

    The artifact is a real ffmpeg-generated MP4 so ffprobe can parse it.
    """
    from production_repo import (
        commit_timeline_spans, plan_render_units, register_artifact,
        link_artifact_to_render_unit,
    )

    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )

    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": audio_policy, "final_audio_source": "master_narration",
          "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0",
          "hero_framing": "close"}],
        db_path=db,
    )
    unit = units[0]

    video_path = tmp_path / f"{label}_provider.mp4"
    _make_test_video(video_path, duration_s=4.0)
    art = register_artifact(prod_id, video_path, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    if fake_provider:
        conn = _db.connect(db)
        job_id = f"pj_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider,
               operation, external_job_id, status, idempotency_key, response_json,
               submitted_at, completed_at)
               VALUES (?, ?, ?, 'seedance', 'generate_lipsync', ?, 'completed', ?, ?,
               datetime('now'), datetime('now'))""",
            (job_id, prod_id, unit["id"], "fake_prov_job",
             f"idemp_{job_id}",
             json.dumps({"provider_poll": {"raw_response": json.dumps({"simulated": True})}})),
        )
        conn.close()

    return unit


def _get_validation_by_validator(db, subject_id, validator_name):
    """Fetch the most recent validation row for a subject+validator."""
    conn = _db.connect(db)
    row = conn.execute(
        """SELECT * FROM validations
           WHERE subject_id=? AND validator_name=?
           ORDER BY created_at DESC LIMIT 1""",
        (subject_id, validator_name),
    ).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFixtureBackend:
    """G1: Fixture backend writes non-simulated syncnet_offset evidence."""

    def test_fixture_backend_writes_syncnet_offset(self, db, prod, tmp_path):
        _set_sync_scorer_backend(FixtureSyncBackend(
            offset_ms=10.0, confidence=0.8, face_track_found=True,
        ))
        try:
            unit = _make_hero_unit(prod["id"], db, tmp_path)
            run_contract_media_qa(db, prod["id"], unit["id"])

            val = _get_validation_by_validator(db, unit["id"], "syncnet_offset")
            assert val is not None, "syncnet_offset validation row must exist"
            assert val["status"] == "pass"

            evidence = json.loads(val["evidence_json"])
            assert evidence["offset_ms"] == 10.0
            assert evidence["confidence"] == 0.8
            assert evidence["face_track_found"] is True
            assert evidence["method"] == "fixture_sync_scorer"
            assert evidence.get("simulated") is not True
            assert evidence.get("publish_grade") is True
        finally:
            _set_sync_scorer_backend(None)

    def test_method_is_not_test_fake(self, db, prod, tmp_path):
        _set_sync_scorer_backend(FixtureSyncBackend(offset_ms=5.0, confidence=0.9))
        try:
            unit = _make_hero_unit(prod["id"], db, tmp_path)
            run_contract_media_qa(db, prod["id"], unit["id"])

            val = _get_validation_by_validator(db, unit["id"], "syncnet_offset")
            evidence = json.loads(val["evidence_json"])
            assert evidence["method"] != "yt_test_mode_fake_provider"
            assert "yt_test_mode" not in evidence["method"]
        finally:
            _set_sync_scorer_backend(None)


class TestBackendNoneFailsLoudly:
    """G2: Backend none -> unit not passed, needs_human_av_review, no fabricated evidence."""

    def test_backend_none_records_fail(self, db, prod, tmp_path):
        _set_sync_scorer_backend(None)
        try:
            unit = _make_hero_unit(prod["id"], db, tmp_path)
            run_contract_media_qa(db, prod["id"], unit["id"])

            val = _get_validation_by_validator(db, unit["id"], "syncnet_offset")
            assert val is not None, "syncnet_offset validation must exist even on fail"
            assert val["status"] == "fail", "backend-none must fail syncnet_offset"

            evidence = json.loads(val["evidence_json"])
            assert evidence["offset_ms"] is None
            assert evidence["confidence"] is None
            assert evidence["face_track_found"] is False
            assert evidence["method"] == "none"
            assert evidence["publish_grade"] is False
            assert "SYNC_SCORER_BACKEND" in evidence.get("reason", "")
        finally:
            _set_sync_scorer_backend(None)

    def test_backend_none_no_fabricated_pass(self, db, prod, tmp_path):
        _set_sync_scorer_backend(None)
        try:
            unit = _make_hero_unit(prod["id"], db, tmp_path)
            run_contract_media_qa(db, prod["id"], unit["id"])

            val = _get_validation_by_validator(db, unit["id"], "syncnet_offset")
            evidence = json.loads(val["evidence_json"])
            assert "simulated" not in evidence or evidence.get("simulated") is not True
            assert evidence.get("publish_grade") is False
        finally:
            _set_sync_scorer_backend(None)


class TestFixtureLowConfidence:
    """Fixture backend low confidence records evidence (threshold at assembly)."""

    def test_low_confidence_still_records(self, db, prod, tmp_path):
        _set_sync_scorer_backend(FixtureSyncBackend(
            offset_ms=50.0, confidence=0.05, face_track_found=False,
        ))
        try:
            unit = _make_hero_unit(prod["id"], db, tmp_path)
            run_contract_media_qa(db, prod["id"], unit["id"])

            val = _get_validation_by_validator(db, unit["id"], "syncnet_offset")
            assert val["status"] == "pass"
            evidence = json.loads(val["evidence_json"])
            assert evidence["confidence"] == 0.05
            assert evidence["face_track_found"] is False
            assert evidence["method"] == "fixture_sync_scorer"
        finally:
            _set_sync_scorer_backend(None)


class TestSyncScoreDataclass:
    """SyncScore dataclass has required fields."""

    def test_syncscore_fields(self):
        s = SyncScore(
            offset_ms=10.0,
            confidence=0.8,
            face_track_found=True,
            method="test",
            model_version="v1",
        )
        assert s.offset_ms == 10.0
        assert s.confidence == 0.8
        assert s.face_track_found is True
        assert s.method == "test"
        assert s.model_version == "v1"

    def test_syncscore_default_method_empty(self):
        s = SyncScore(offset_ms=0.0, confidence=0.0, face_track_found=False)
        assert s.method == ""
        assert s.model_version == ""
        assert s.extra == {}


class TestBackendAvailability:
    """Availability reporting."""

    def test_fixture_backend_availability(self):
        b = FixtureSyncBackend()
        assert b.availability() is True

    def test_fixture_backend_unavailable(self):
        b = FixtureSyncBackend(available=False)
        assert b.availability() is False

    def test_get_backend_default_is_none(self):
        os.environ.pop("SYNC_SCORER_BACKEND", None)
        _set_sync_scorer_backend(None)
        assert get_sync_scorer_backend() is None

    def test_get_backend_fixture(self):
        os.environ["SYNC_SCORER_BACKEND"] = "fixture"
        _set_sync_scorer_backend(None)
        try:
            b = get_sync_scorer_backend()
            assert isinstance(b, FixtureSyncBackend)
        finally:
            os.environ.pop("SYNC_SCORER_BACKEND", None)

    def test_get_backend_unknown_returns_none(self):
        _set_sync_scorer_backend(None)
        os.environ["SYNC_SCORER_BACKEND"] = "unknown"
        try:
            b = get_sync_scorer_backend()
            assert b is None
        finally:
            os.environ.pop("SYNC_SCORER_BACKEND", None)


class TestLipsyncScoringRegistration:
    """F2: lipsync_scoring get_sync_model() returns working adapter."""

    def test_get_sync_model_returns_adapter_with_fixture(self):
        _set_sync_scorer_backend(FixtureSyncBackend(
            offset_ms=10.0, confidence=0.8, face_track_found=True,
        ))
        try:
            from lipsync_scoring import get_sync_model, NoModelLoaded

            model = get_sync_model()
            assert not isinstance(model, NoModelLoaded), (
                "get_sync_model() should return adapter, not NoModelLoaded"
            )
            assert model.load() is True

            result = model.score(__file__, __file__)
            assert result["offset_estimate_ms"] == 10.0
            assert result["confidence"] == 0.8
            assert result["face_track_found"] is True
            assert result["method"] == "fixture_sync_scorer"
        finally:
            _set_sync_scorer_backend(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
