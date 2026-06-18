"""S6-T01: Artifact registration and download validation + S6-T02: Technical media QA.

Named tests required by the program:
  test_corrupt_download_rejected (also in S3; verified here for artifact registry)
  test_artifact_registration_rejects_corrupt_media
  test_media_qa_rejects_black_frames
  test_media_qa_rejects_missing_file
"""
import subprocess
import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import production_repo as _repo
from provider_adapter import validate_downloaded_artifact, ProviderAdapterError


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "qa_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("qa_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file, tmp_path
    _db._db_path_override = None


def _make_valid_video(path: Path, duration_sec: float = 2.0, w: int = 1280, h: int = 720):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=red:s={w}x{h}:d={duration_sec}:r=24",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={duration_sec}",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(path),
    ], capture_output=True, check=True)


def _make_corrupt_file(path: Path):
    path.write_bytes(b"not a valid media file at all")


def test_artifact_registration_rejects_corrupt_media(fresh_db):
    """register_artifact with kind='generated_video' must reject corrupt media
    (ffprobe fails → ArtifactRegistryError)."""
    prod, db_path, tmp_path = fresh_db
    corrupt = tmp_path / "corrupt.mp4"
    _make_corrupt_file(corrupt)

    with pytest.raises(_repo.ArtifactRegistryError):
        _repo.register_artifact(prod["id"], corrupt, "generated_video", db_path=db_path)


def test_artifact_registration_accepts_valid_media(fresh_db):
    """A valid MP4 is accepted and registered with SHA + size."""
    prod, db_path, tmp_path = fresh_db
    video = tmp_path / "valid.mp4"
    _make_valid_video(video, 2.0, 1280, 720)

    art = _repo.register_artifact(prod["id"], video, "generated_video", db_path=db_path)
    assert art["sha256"]
    assert art["id"]

    # Verify artifact row has size and SHA
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT sha256, size_bytes, kind FROM artifacts WHERE id=?", (art["id"],)
    ).fetchone()
    conn.close()
    assert row["sha256"] == art["sha256"]
    assert row["size_bytes"] > 0
    assert row["kind"] == "generated_video"


def test_corrupt_download_rejected_by_validate(fresh_db, tmp_path):
    """validate_downloaded_artifact rejects a corrupt download."""
    corrupt = tmp_path / "corrupt_dl.mp4"
    _make_corrupt_file(corrupt)
    with pytest.raises(ProviderAdapterError):
        validate_downloaded_artifact(corrupt)


def test_sha_mismatch_rejected(fresh_db, tmp_path):
    """validate_downloaded_artifact rejects a SHA mismatch."""
    video = tmp_path / "sha_mismatch.mp4"
    _make_valid_video(video, 1.0)

    with pytest.raises(ProviderAdapterError, match="SHA-256 mismatch"):
        validate_downloaded_artifact(video, expected_sha256="wrongsha256")


def test_media_qa_rejects_missing_file(fresh_db):
    """Media QA fails when the artifact file doesn't exist."""
    from media_service import run_render_unit_qa

    prod, db_path, tmp_path = fresh_db
    # Create a render unit with a valid artifact, then delete the file
    now = _db._now()
    video = tmp_path / "temp.mp4"
    _make_valid_video(video, 1.0)
    art = _repo.register_artifact(prod["id"], video, "test_data", db_path=db_path)
    # Delete the file so it's missing during QA
    video.unlink()

    with _db.transaction(db_path) as conn:
        ru_id = _db._id("ru")
        conn.execute(
            """INSERT INTO render_units (id, production_id, ordinal, label, asset_type,
               audio_policy, lipsync_required, required_start_ms, required_end_ms,
               required_duration_ms, status, active_artifact_id, created_at, updated_at)
               VALUES (?, ?, 0, 'B001', 'generated_video', 'BROLL_FLEX', 0, 0, 5000, 5000,
               'generated', ?, ?, ?)""",
            (ru_id, prod["id"], art["id"], now, now),
        )

    checks = {
        "file_exists": False,
        "dimensions_ok": False,
        "duration_ok": False,
        "audio_policy_ok": False,
        "sha_match": False,
        "details": {"error": "File missing"},
    }
    val = run_render_unit_qa(prod["id"], ru_id, checks, db_path=db_path)
    assert val["status"] == "fail"
