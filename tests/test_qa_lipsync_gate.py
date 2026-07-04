"""Tests for lipsync QA evidence gates (S01-T004)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import production_db as _db
from media_service import run_contract_media_qa, submit_provider_job, ProviderJobError
from qa_final import run_db_contract_checks
from sync_scorer.scorer import _set_sync_scorer_backend, FixtureSyncBackend


FIXTURE = Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    prod_row = _db.ensure_production("s01_t004_test", db_path=db)
    with _db.transaction(db) as conn:
        conn.execute(
            "INSERT INTO approval_requests(id, production_id, gate_name, status, requested_at) "
            "VALUES(?,?,?,?,?)",
            ("ar_test", prod_row["id"], "gate_a_spend", "pass", _db._now()),
        )
    return prod_row["id"]


@pytest.fixture(autouse=True)
def _sync_scorer_fixture(monkeypatch, db):
    """Ensure sync scorer is configured for contract QA tests."""
    import media_service
    from sync_scorer.scorer import _set_sync_scorer_backend
    _set_sync_scorer_backend(FixtureSyncBackend(
        offset_ms=10.0, confidence=0.8, face_track_found=True,
    ))
    yield
    _set_sync_scorer_backend(None)


def _create_hero_unit_with_artifact(conn, prod_id, unit_id, label, art_id, art_path):
    """Create a HERO_SYNC_LOCKED render unit with a linked artifact."""
    # Insert artifact FIRST (FK constraint)
    conn.execute(
        """INSERT INTO artifacts(id, production_id, kind, sha256, size_bytes, uri, mime_type, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (art_id, prod_id, "generated_media", "b" * 64, 1000, str(art_path), "video/mp4", _db._now()),
    )
    conn.execute(
        """INSERT INTO render_units
           (id, production_id, label, asset_type, audio_policy, lipsync_required,
            required_start_ms, required_end_ms, required_duration_ms,
            ordinal, slot_index, slot_total, status, render_mode,
            active_artifact_id, source_slice_sha256, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (unit_id, prod_id, label, "lipsync_video", "HERO_SYNC_LOCKED", 1,
         0, 4000, 4000,
         1, 0, 1, "valid", "generated_video",
         art_id, "a" * 64, _db._now(), _db._now()),
    )


class TestQaHeroLipsync:
    """_qa_hero_lipsync records lipsync drift evidence."""

    def test_qa_includes_lipsync_evidence(self, db, prod, tmp_path):
        """S01-T004-R1: QA for hero unit includes lipsync evidence."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        art_id = "art_test_001"
        with _db.transaction(db) as conn:
            _create_hero_unit_with_artifact(conn, prod, "ru_test_001", "S000",
                                            art_id, FIXTURE)

        result = run_contract_media_qa(db, prod, "ru_test_001")
        assert result["validator_name"] == "qa_media_contract"
        evidence = json.loads(result["evidence_json"] or "{}")
        assert "lipsync_drift_ms" in evidence, "Missing lipsync_drift_ms"
        assert "lipsync_drift_ok" in evidence, "Missing lipsync_drift_ok"
        assert "lipsync_qa_method" in evidence, "Missing lipsync_qa_method"
        assert evidence["lipsync_qa_method"] is not None, "lipsync_qa_method should not be None"

    def test_qa_records_lipsync_review_outcome(self, db, prod, tmp_path):
        """S01-T004-R2: QA records drift only when evidence supports it."""
        if not FIXTURE.exists():
            pytest.skip("Fixture MP4 not available")
        art_id = "art_test_002"
        with _db.transaction(db) as conn:
            _create_hero_unit_with_artifact(conn, prod, "ru_test_002", "S000",
                                            art_id, FIXTURE)

        result = run_contract_media_qa(db, prod, "ru_test_002")
        evidence = json.loads(result["evidence_json"] or "{}")
        assert evidence["lipsync_qa_method"] == "fixture_sync_scorer"
        assert evidence["lipsync_review_status"] in {
            "PASS", "WARN", "FAIL", "NEEDS_HUMAN_AV_REVIEW", "BLOCKED"
        }
        assert evidence["lipsync_drift_ok"] is True
        assert evidence["lipsync_drift_ms"] is not None

    def _qa_hero_lipsync_with_mock(self, args, kwargs, backend):
        """Helper to test _qa_hero_lipsync with mocked sync scorer -- not used,
        instead we monkeypatch the sync_scorer module directly."""
        pass  # placeholder replaced below

    def test_duration_mismatch_is_not_lipsync_drift(self, monkeypatch, tmp_path):
        """Provider padding/tail duration mismatch must not be mislabeled as drift."""
        import media_service
        from sync_scorer.scorer import FixtureSyncBackend

        video = tmp_path / "hero.mp4"
        video.write_bytes(b"not-probed-because-ffprobe-is-patched")
        monkeypatch.setattr(
            media_service, "_ffprobe_dimensions_duration",
            lambda _path: {"duration_ms": 8080, "width": 864, "height": 496},
        )
        monkeypatch.setattr(media_service, "_check_sha_match", lambda *_args: True)

        mock_backend = FixtureSyncBackend(
            offset_ms=10.0, confidence=0.41,
            face_track_found=False,
        )
        from sync_scorer.scorer import _set_sync_scorer_backend
        _set_sync_scorer_backend(mock_backend)
        # Stub record_validation_evidence (db_path=None with no DB set would fail)
        monkeypatch.setattr(
            media_service, "record_validation_evidence",
            lambda *args, **kwargs: {"id": "val_stub", "status": "pass"},
        )

        passed, evidence = media_service._qa_hero_lipsync(
            "prod",
            {"id": "ru", "required_duration_ms": 7471, "hero_framing": "medium"},
            {"sha256": "a" * 64},
            video,
        )

        assert passed is True
        assert evidence["duration_mismatch_ms"] == 609
        assert evidence["duration_delta_ms"] == 609
        assert evidence["duration_ok"] is True
        assert evidence["lipsync_drift_ms"] == 10.0
        assert evidence["lipsync_review_status"] == "PASS"
        assert evidence["lipsync_confidence"] == 0.41
        assert evidence["lipsync_face_track_found"] is False

    def test_human_review_lipsync_failure_class_is_known(self):
        """Repair routing should not collapse review-required sync to unknown."""
        from media_service import classify_validation_failure

        assert classify_validation_failure({
            "file_exists": True,
            "sha_match": True,
            "render_method": "hero_lipsync",
            "duration_ok": True,
            "lipsync_review_status": "NEEDS_HUMAN_AV_REVIEW",
        }) == "hero_lipsync_needs_human_review"

    def test_eval_lipsync_low_confidence_requires_human_review(self, monkeypatch, tmp_path):
        """Fallback mouth-motion proxy must not fake a hard drift verdict."""
        import evals.eval_lipsync as eval_lipsync

        monkeypatch.setattr(
            eval_lipsync, "extract_audio_envelope",
            lambda *_args: {"envelope": [1, 2, 1, 2, 1], "frame_rate": 20.0},
        )
        monkeypatch.setattr(
            eval_lipsync, "compute_visual_activity",
            lambda *_args: {"signal": [1, 1, 2, 1, 1], "fps": 24.0},
        )
        monkeypatch.setattr(
            eval_lipsync, "correlate_signals",
            lambda *_args: {"offset_ms": -1600.0, "confidence": 0.34},
        )

        result = eval_lipsync.analyze_video(tmp_path / "hero.mp4", "ru", "medium")

        assert result["status"] == "needs_human_av_review"
        assert result["face_track_found"] is False
        assert "No confident face-track" in result["reason"]


class TestQaFinalLipsyncCheck:
    """qa_final checks for lipsync evidence on HERO units."""

    def test_qa_final_rejects_missing_lipsync_evidence(self, db, prod, tmp_path):
        """S01-T004-R3: qa_final rejects hero unit without lipsync evidence."""
        # Create a deliverable with a HERO unit that has QA but no lipsync evidence
        del_id = "del_test_003"
        art_id = "art_test_003"
        art_path = tmp_path / "dummy.mp4"
        art_path.write_bytes(b"\x00\x00\x00\x00\x00\x00\x00\x00")  # dummy file

        with _db.transaction(db) as conn:
            # Insert artifacts FIRST (FK constraints)
            conn.execute(
                "INSERT INTO artifacts(id, production_id, kind, sha256, size_bytes, uri, mime_type, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (art_id, prod, "deliverable_16x9", "c" * 64, 100, str(art_path), "video/mp4", _db._now()),
            )
            # Create hero unit with a QA that has no lipsync evidence
            _create_hero_unit_with_artifact(conn, prod, "ru_test_003", "S000", "art_ru_003", art_path)
            # Record a QA with NO lipsync evidence (simulating old-style QA)
            no_lipsync_evidence = json.dumps({
                "file_exists": True, "dimensions_ok": True, "sha_match": True,
                "duration_ok": True, "render_method": "hero_lipsync",
            })
            conn.execute(
                "INSERT INTO validations(id, production_id, subject_id, subject_type, "
                "validator_name, status, evidence_json, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                ("val_no_lipsync", prod, "ru_test_003", "render_unit",
                 "qa_media_contract", "pass", no_lipsync_evidence, _db._now()),
            )
            # Create deliverable AFTER artifacts and render units
            conn.execute(
                "INSERT INTO deliverables(id, production_id, variant, status, artifact_id) "
                "VALUES(?,?,?,?,?)",
                (del_id, prod, "16x9", "assembled", art_id),
            )

        import pytest
        result = run_db_contract_checks(prod, del_id, db_path=db)
        assert result.get("all_contract_checks_pass") is not True, (
            "qa_final should fail when hero unit lacks lipsync evidence"
        )
        issues_str = json.dumps(result.get("contract_issues", []))
        assert "F-QA-001" in issues_str, (
            "qa_final should cite F-QA-001 when lipsync evidence missing"
        )

    def test_qa_final_accepts_lipsync_evidence(self, db, prod, tmp_path):
        """S01-T004-R4: qa_final accepts hero unit WITH lipsync evidence."""
        del_id = "del_test_004"
        art_id = "art_test_004"
        art_path = tmp_path / "dummy2.mp4"
        art_path.write_bytes(b"\x00\x00\x00\x00\x00\x00\x00\x00")

        with _db.transaction(db) as conn:
            # Insert artifacts FIRST (FK constraints)
            conn.execute(
                "INSERT INTO artifacts(id, production_id, kind, sha256, size_bytes, uri, mime_type, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (art_id, prod, "deliverable_16x9", "d" * 64, 100, str(art_path), "video/mp4", _db._now()),
            )
            _create_hero_unit_with_artifact(conn, prod, "ru_test_004", "S000", "art_ru_004", art_path)
            # Record a QA WITH lipsync evidence
            with_lipsync_evidence = json.dumps({
                "file_exists": True, "dimensions_ok": True, "sha_match": True,
                "duration_ok": True, "render_method": "hero_lipsync",
                "lipsync_drift_ms": 10, "lipsync_drift_ok": True,
                "lipsync_qa_method": "qa_lipsync.detect_lipsync_drift_ms",
            })
            conn.execute(
                "INSERT INTO validations(id, production_id, subject_id, subject_type, "
                "validator_name, status, evidence_json, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                ("val_with_lipsync", prod, "ru_test_004", "render_unit",
                 "qa_media_contract", "pass", with_lipsync_evidence, _db._now()),
            )
            # Create deliverable AFTER artifacts and render units
            conn.execute(
                "INSERT INTO deliverables(id, production_id, variant, status, artifact_id) "
                "VALUES(?,?,?,?,?)",
                (del_id, prod, "16x9", "assembled", art_id),
            )

        result = run_db_contract_checks(prod, del_id, db_path=db)
        # In test env, assembly_preflight will fail, so all_contract_checks_pass may be False.
        # Verify that the lipsync-specific check passes: all_passing_qa must be True
        # (meaning the hero unit's lipsync evidence is accepted).
        assert result.get("all_passing_qa") is True, (
            f"qa_final should accept hero unit with lipsync evidence, got: {result}"
        )
