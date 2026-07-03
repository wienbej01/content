"""S22_T017 - Record observed artifact durations.

Tests:
  1. Registering 5.1s fixture artifact records artifacts.duration_ms.
  2. Linked render unit records actual_render_duration_ms.
  3. Required duration remains unchanged.
  4. Missing/corrupt artifact fails with explicit probe error.
  5. Non-video local graphic duration is handled or fails clearly.
  6. Re-registering same artifact remains idempotent.
  7. Duration evidence is included in validation/report output.
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


@pytest.fixture
def db(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    p = tmp_path / "obsdur_test.db"
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(p))
    import production_db as _db
    _db.migrate(str(p))
    yield str(p)


@pytest.fixture
def prod(db):
    import production_db as _db
    return _db.ensure_production("obsdur_test_prod", seed="obsdur test", video_type="short", db_path=db)


def _make_video(tmp_path, duration_sec, label="test"):
    """Create an MP4 video of exact duration with ffmpeg lavfi color source."""
    video = tmp_path / f"{label}_{duration_sec}s.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=blue:s=320x240:d={duration_sec}:r=30",
        "-pix_fmt", "yuv420p", str(video),
    ], capture_output=True, check=True)
    return video


def _make_render_unit(prod_id, db_path):
    from production_repo import commit_timeline_spans, plan_render_units
    spans = commit_timeline_spans(
        prod_id,
        [{"label": "O001", "start_ms": 0, "end_ms": 4000}],
        db_path=db_path,
    )
    return plan_render_units(prod_id, [{
        "span_id": spans[0]["id"],
        "asset_type": "lipsync_video",
        "audio_policy": "HERO_SYNC_LOCKED",
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
    }], db_path=db_path)[0]


class TestObservedArtifactDuration:
    """S22_T017 — observed artifact duration recording."""

    def test_register_artifact_records_duration_ms(self, db, prod, tmp_path):
        """Registering 5.1s fixture artifact stores duration_ms on artifacts."""
        from production_repo import register_artifact

        video = _make_video(tmp_path, 5.1)
        art = register_artifact(prod["id"], video, "generated_video", db_path=db)

        assert art["duration_ms"] is not None, "duration_ms must be set"
        assert 5000 <= art["duration_ms"] <= 5200, (
            f"Expected ~5100ms, got {art['duration_ms']}ms"
        )

    def test_linked_render_unit_records_actual_render_duration_ms(self, db, prod, tmp_path):
        """Linked render unit records actual_render_duration_ms from artifact."""
        from production_repo import register_artifact, link_artifact_to_render_unit
        import production_db as _db

        unit = _make_render_unit(prod["id"], db)
        video = _make_video(tmp_path, 3.0)
        art = register_artifact(prod["id"], video, "generated_video", db_path=db)

        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        conn = _db.connect(db)
        ru = dict(conn.execute("SELECT * FROM render_units WHERE id=?", (unit["id"],)).fetchone())
        conn.close()

        assert ru["actual_render_duration_ms"] is not None, "actual_render_duration_ms must be set"
        assert 2900 <= ru["actual_render_duration_ms"] <= 3100, (
            f"Expected ~3000ms, got {ru['actual_render_duration_ms']}ms"
        )

    def test_required_duration_remains_unchanged(self, db, prod, tmp_path):
        """Required duration is preserved after observed duration recording."""
        from production_repo import (
            register_artifact, link_artifact_to_render_unit,
            record_observed_artifact_duration,
        )
        import production_db as _db

        unit = _make_render_unit(prod["id"], db)
        original_required = unit["required_duration_ms"]

        video = _make_video(tmp_path, 2.5)
        art = register_artifact(prod["id"], video, "generated_video", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        evidence = record_observed_artifact_duration(
            prod["id"], art["id"], render_unit_id=unit["id"], db_path=db,
        )

        conn = _db.connect(db)
        ru = dict(conn.execute("SELECT * FROM render_units WHERE id=?", (unit["id"],)).fetchone())
        conn.close()

        assert ru["required_duration_ms"] == original_required, (
            f"required_duration_ms changed from {original_required} to {ru['required_duration_ms']}"
        )
        assert evidence["required_duration_ms"] == original_required

    def test_missing_artifact_fails_with_explicit_error(self, db, prod):
        """Missing/corrupt artifact fails with explicit BLOCKED_DURATION_PROBE_FAILED."""
        from production_repo import record_observed_artifact_duration

        with pytest.raises(Exception) as exc_info:
            record_observed_artifact_duration(
                prod["id"], "art_nonexistent", render_unit_id="render_nonexistent", db_path=db,
            )
        assert "BLOCKED_DURATION_PROBE_FAILED" in str(exc_info.value)

    def test_corrupt_artifact_file_fails_with_explicit_probe_error(self, db, prod, tmp_path):
        """Corrupt/non-media file fails with explicit probe error."""
        from production_repo import register_artifact, record_observed_artifact_duration

        corrupt = tmp_path / "corrupt.mp4"
        corrupt.write_bytes(b"not a video file")

        # register_artifact will succeed if kind allows it, or we test a known path
        # Use a non-media kind to register, then test that record_observed probes fail
        import production_db as _db
        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO artifacts
                   (id, production_id, kind, uri, storage_backend, sha256, size_bytes, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("art_corrupt_01", prod["id"], "generated_video", str(corrupt), "local",
                 "deadbeef", 16, _db._now()),
            )

        with pytest.raises(Exception) as exc_info:
            record_observed_artifact_duration(
                prod["id"], "art_corrupt_01", db_path=db,
            )
        assert "BLOCKED_DURATION_PROBE_FAILED" in str(exc_info.value)

    def test_non_video_local_graphic_handled_or_fails(self, db, prod, tmp_path):
        """Non-video local graphic artifact: handled by renderer metadata or fails clearly."""
        from production_repo import record_observed_artifact_duration
        import production_db as _db

        # Create a truly unparseable non-media file that ffprobe can't handle
        nonmedia = tmp_path / "not_media.txt"
        nonmedia.write_bytes(b"this is definitely not a media file")

        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO artifacts
                   (id, production_id, kind, uri, storage_backend, sha256, size_bytes, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("art_graphic_fail", prod["id"], "local_graphic", str(nonmedia), "local",
                 _db._sha256_file(nonmedia), nonmedia.stat().st_size, _db._now()),
            )

        with pytest.raises(Exception) as exc_info:
            record_observed_artifact_duration(
                prod["id"], "art_graphic_fail", db_path=db,
            )
        assert "BLOCKED_DURATION_PROBE_FAILED" in str(exc_info.value)

    def test_re_registering_same_artifact_is_idempotent(self, db, prod, tmp_path):
        """Re-registering the same artifact (same path+sha) returns the existing row."""
        from production_repo import register_artifact

        video = _make_video(tmp_path, 5.1)
        art1 = register_artifact(prod["id"], video, "generated_video", db_path=db)
        art2 = register_artifact(prod["id"], video, "generated_video", db_path=db)

        assert art1["id"] == art2["id"], "Idempotent registration must return same id"
        assert art1["duration_ms"] == art2["duration_ms"], "duration_ms must match"
        assert art1["sha256"] == art2["sha256"], "sha256 must match"

    def test_duration_evidence_in_validation_output(self, db, prod, tmp_path):
        """Duration evidence is included in validation/report output."""
        from production_repo import (
            register_artifact, link_artifact_to_render_unit,
            record_observed_artifact_duration,
        )
        import production_db as _db

        unit = _make_render_unit(prod["id"], db)
        video = _make_video(tmp_path, 3.0)
        art = register_artifact(prod["id"], video, "generated_video", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        evidence = record_observed_artifact_duration(
            prod["id"], art["id"], render_unit_id=unit["id"], db_path=db,
        )

        assert evidence["artifact_id"] == art["id"], "artifact_id must be in evidence"
        assert evidence["render_unit_id"] == unit["id"], "render_unit_id must be in evidence"
        assert evidence["actual_duration_ms"] is not None, "actual_duration_ms must be in evidence"
        assert evidence["required_duration_ms"] is not None, "required_duration_ms must be in evidence"
        assert evidence["delta_ms"] is not None, "delta_ms must be in evidence"
        assert evidence["validation_id"] is not None, "validation_id must be in evidence"

        # Verify the validation row exists in the DB
        conn = _db.connect(db)
        val = conn.execute(
            "SELECT * FROM validations WHERE id=?", (evidence["validation_id"],)
        ).fetchone()
        conn.close()
        assert val is not None, "Validation row must exist"
        assert val["validator_name"] == "observed_duration"
        assert val["status"] == "pass"

        # Verify evidence_json contains all required fields
        stored_evidence = json.loads(val["evidence_json"] or "{}")
        for key in ("artifact_id", "render_unit_id", "required_duration_ms",
                    "actual_duration_ms", "delta_ms", "artifact_uri"):
            assert key in stored_evidence, f"{key} missing from validation evidence"

    def test_record_observed_artifact_duration_without_render_unit(self, db, prod, tmp_path):
        """record_observed_artifact_duration works with just artifact_id (no render unit)."""
        from production_repo import register_artifact, record_observed_artifact_duration
        import production_db as _db

        video = _make_video(tmp_path, 1.7)
        art = register_artifact(prod["id"], video, "generated_video", db_path=db)

        evidence = record_observed_artifact_duration(
            prod["id"], art["id"], db_path=db,
        )

        assert evidence["artifact_id"] == art["id"]
        assert evidence["render_unit_id"] is None
        assert evidence["required_duration_ms"] is None
        assert evidence["delta_ms"] is None
        assert evidence["actual_duration_ms"] is not None
        assert evidence["validation_id"] is not None

        # artifact.duration_ms should be updated
        conn = _db.connect(db)
        art_updated = dict(conn.execute("SELECT * FROM artifacts WHERE id=?", (art["id"],)).fetchone())
        conn.close()
        assert art_updated["duration_ms"] is not None

    def test_link_artifact_updates_actual_render_and_preserves_required(self, db, prod, tmp_path):
        """After link_artifact_to_render_unit, show actual and required are distinct columns."""
        from production_repo import register_artifact, link_artifact_to_render_unit
        import production_db as _db

        unit = _make_render_unit(prod["id"], db)
        video = _make_video(tmp_path, 3.0)
        art = register_artifact(prod["id"], video, "generated_video", db_path=db)

        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        conn = _db.connect(db)
        ru = dict(conn.execute("SELECT * FROM render_units WHERE id=?", (unit["id"],)).fetchone())
        conn.close()

        assert ru["required_duration_ms"] is not None
        assert ru["actual_render_duration_ms"] is not None
        assert ru["required_duration_ms"] != ru["actual_render_duration_ms"], \
            "required and actual durations should be distinct (planned vs observed)"
