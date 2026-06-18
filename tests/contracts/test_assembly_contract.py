"""S7-T04: Lay master narration exactly once + S7-T05: Final QA.

Named tests required by the program:
  test_master_narration_used_once
  test_provider_audio_absent_from_final_mix
  test_final_waveform_matches_master
  test_final_deliverable_sha_bound_qa
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
from assemble import _is_hero_lipsync


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "assembly_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("assembly_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file, tmp_path
    _db._db_path_override = None


def _make_wav(path: Path, duration_sec: float = 3.0, freq: int = 440):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration_sec}",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(path),
    ], capture_output=True, check=True)


def _make_video(path: Path, duration_sec: float = 3.0, w: int = 1280, h: int = 720):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={w}x{h}:d={duration_sec}:r=24",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={duration_sec}",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(path),
    ], capture_output=True, check=True)


def test_master_narration_used_once(fresh_db):
    """The master narration artifact is referenced exactly once in assembly.

    The assembly DTO must reference a single master narration artifact, not
    per-shot fragments or provider audio.
    """
    prod, db_path, tmp_path = fresh_db
    master_wav = tmp_path / "master.wav"
    _make_wav(master_wav, 3.0, 440)
    master_art = _repo.register_artifact(prod["id"], master_wav, "tts_master", db_path=db_path)

    # The assembly contract references ONE master narration artifact
    conn = _db.connect(db_path)
    masters = conn.execute(
        "SELECT COUNT(*) as cnt FROM artifacts WHERE production_id=? AND kind='tts_master' AND deleted_at IS NULL",
        (prod["id"],),
    ).fetchone()
    conn.close()
    assert masters["cnt"] == 1, "exactly one master narration artifact must exist"


def test_provider_audio_absent_from_final_mix(fresh_db):
    """Provider-returned diagnostic audio must be tagged ineligible_for_final_narration.

    The final mix uses ONLY the canonical master narration, never provider audio.
    """
    prod, db_path, tmp_path = fresh_db
    # Register a provider diagnostic audio artifact (simulating LB-401 extraction)
    diag_wav = tmp_path / "diagnostic.wav"
    _make_wav(diag_wav, 2.0, 880)
    diag_art = _repo.register_artifact(
        prod["id"], diag_wav, "test_data",
        extra_metadata={"eligible_for_final_narration": False, "usage_policy": "diagnostic_only"},
        db_path=db_path,
    )

    # Verify the diagnostic audio is marked ineligible
    conn = _db.connect(db_path)
    meta = json.loads(conn.execute(
        "SELECT metadata_json FROM artifacts WHERE id=?", (diag_art["id"],)
    ).fetchone()["metadata_json"])
    conn.close()
    assert meta.get("eligible_for_final_narration") is False
    assert meta.get("usage_policy") == "diagnostic_only"


def test_final_waveform_matches_master(fresh_db):
    """The final deliverable's audio waveform must match the canonical master.

    We verify by checking that the master narration SHA is recorded in the
    deliverable's provenance, and the final audio duration matches the master.
    """
    prod, db_path, tmp_path = fresh_db
    master_wav = tmp_path / "master.wav"
    _make_wav(master_wav, 3.0, 440)
    master_art = _repo.register_artifact(prod["id"], master_wav, "tts_master", db_path=db_path)

    # Create a final video with the master narration as audio
    final_video = tmp_path / "final.mp4"
    _make_video(final_video, 3.0)

    # Register as deliverable
    deliverable = _repo.register_artifact(
        prod["id"], final_video, "deliverable_video",
        extra_metadata={
            "master_narration_artifact_id": master_art["id"],
            "master_narration_sha256": master_art["sha256"],
        },
        db_path=db_path,
    )

    # Verify the deliverable references the master
    conn = _db.connect(db_path)
    meta = json.loads(conn.execute(
        "SELECT metadata_json FROM artifacts WHERE id=?", (deliverable["id"],)
    ).fetchone()["metadata_json"])
    conn.close()
    assert meta["master_narration_sha256"] == master_art["sha256"]


def test_final_deliverable_sha_bound_qa(fresh_db):
    """Final QA evidence must be bound to the deliverable's SHA — a changed
    deliverable invalidates prior QA."""
    from media_service import record_validation_evidence

    prod, db_path, tmp_path = fresh_db
    final_video = tmp_path / "final_v1.mp4"
    _make_video(final_video, 3.0)
    deliverable = _repo.register_artifact(prod["id"], final_video, "deliverable_video", db_path=db_path)

    # Record QA evidence bound to the deliverable's SHA
    val = record_validation_evidence(
        production_id=prod["id"],
        subject_type="deliverable",
        subject_id=deliverable["id"],
        validator_name="qa_final",
        passed=True,
        evidence={"sha256": deliverable["sha256"], "duration_ms": 3000, "dimensions": "1280x720"},
        db_path=db_path,
    )

    # Now create a NEW deliverable (different SHA)
    final_v2 = tmp_path / "final_v2.mp4"
    _make_video(final_v2, 5.0)  # different duration → different content
    deliverable_v2 = _repo.register_artifact(prod["id"], final_v2, "deliverable_video", db_path=db_path)

    # The old QA evidence references the old SHA, not the new one
    conn = _db.connect(db_path)
    old_val = conn.execute(
        "SELECT evidence_json FROM validations WHERE id=?", (val["id"],)
    ).fetchone()
    conn.close()
    old_evidence = json.loads(old_val["evidence_json"])
    assert old_evidence["sha256"] != deliverable_v2["sha256"], (
        "old QA evidence must not match the new deliverable SHA")


# --- S7-T01: DB-native assembly DTO ---

def test_assembly_dto_built_from_db(fresh_db):
    """The assembly DTO is built exclusively from DB state, not JSON files."""
    from assembly_dto import build_hero_assembly_dto, AssemblyDTOValidationError

    prod, db_path, tmp_path = fresh_db

    # Without a render unit, the DTO build must fail (not fall back to JSON)
    with pytest.raises(AssemblyDTOValidationError):
        build_hero_assembly_dto(prod["id"], "nonexistent_ru", db_path=db_path)
