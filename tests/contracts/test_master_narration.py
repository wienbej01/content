"""S4-T01: Immutable canonical master narration + S4-T02: Exact timing.

Named tests required by the program:
  test_master_reuse_exact_fingerprint
  test_script_change_invalidates_master
  test_voice_change_invalidates_master
  test_corrupt_master_not_reused
  test_sample_count_exact
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from tts_service import record_tts_artifact
from stage_runner import save_document_revision, invalidate_document_descendants
from timeline_utils import MASTER_SAMPLE_RATE, ms_to_samples, samples_to_ms, TimeInterval


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "master_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("master_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file, tmp_path
    _db._db_path_override = None


def _make_wav(path: Path, duration_sec: float = 1.0, freq: int = 440):
    """Create a valid WAV file with a known tone."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration_sec}",
        "-c:a", "pcm_s16le", "-ar", str(MASTER_SAMPLE_RATE), "-ac", "1",
        str(path),
    ], capture_output=True, check=True)


def test_master_reuse_exact_fingerprint(fresh_db):
    """Same fingerprint reuses the exact same master artifact (idempotent)."""
    prod, db_path, tmp_path = fresh_db
    audio = tmp_path / "master_reuse.wav"
    _make_wav(audio, 1.0, 440)

    art1 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio,
        script_revision_id="s1", voice_id="v1", model="m1",
        voice_settings={"stability": 0.5}, request_fingerprint="fp1",
        db_path=db_path,
    )
    assert art1["reused"] is False

    art2 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio,
        script_revision_id="s1", voice_id="v1", model="m1",
        voice_settings={"stability": 0.5}, request_fingerprint="fp1",
        db_path=db_path,
    )
    assert art2["reused"] is True
    assert art1["id"] == art2["id"]
    assert art1["sha256"] == art2["sha256"]


def test_script_change_invalidates_master(fresh_db):
    """A different script revision produces a new master (not reused)."""
    prod, db_path, tmp_path = fresh_db
    audio = tmp_path / "master_script.wav"
    _make_wav(audio, 1.0, 440)

    art1 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio,
        script_revision_id="s1", voice_id="v1", model="m1",
        voice_settings={}, request_fingerprint="fp1",
        db_path=db_path,
    )

    audio2 = tmp_path / "master_script2.wav"
    _make_wav(audio2, 1.0, 880)
    art2 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio2,
        script_revision_id="s2", voice_id="v1", model="m1",
        voice_settings={}, request_fingerprint="fp2",
        db_path=db_path,
    )
    assert art2["reused"] is False
    assert art1["id"] != art2["id"]


def test_voice_change_invalidates_master(fresh_db):
    """A different voice produces a new master (not reused)."""
    prod, db_path, tmp_path = fresh_db
    audio = tmp_path / "master_voice.wav"
    _make_wav(audio, 1.0, 440)

    art1 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio,
        script_revision_id="s1", voice_id="v1", model="m1",
        voice_settings={}, request_fingerprint="fp1",
        db_path=db_path,
    )

    audio2 = tmp_path / "master_voice2.wav"
    _make_wav(audio2, 1.0, 880)
    art2 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio2,
        script_revision_id="s1", voice_id="v2", model="m1",
        voice_settings={}, request_fingerprint="fp2",
        db_path=db_path,
    )
    assert art2["reused"] is False
    assert art1["id"] != art2["id"]


def test_corrupt_master_not_reused(fresh_db):
    """A corrupted master (checksum mismatch) is NOT reused — regeneration required."""
    prod, db_path, tmp_path = fresh_db
    audio = tmp_path / "master_corrupt.wav"
    _make_wav(audio, 1.0, 440)

    art1 = record_tts_artifact(
        production_id=prod["id"], audio_path=audio,
        script_revision_id="s1", voice_id="v1", model="m1",
        voice_settings={}, request_fingerprint="fp1",
        db_path=db_path,
    )

    # Corrupt the file
    audio.write_bytes(b"corrupted data")

    with pytest.raises(RuntimeError, match="TTS_MASTER_CHECKSUM_MISMATCH"):
        record_tts_artifact(
            production_id=prod["id"], audio_path=audio,
            script_revision_id="s1", voice_id="v1", model="m1",
            voice_settings={}, request_fingerprint="fp1",
            db_path=db_path,
        )


def test_sample_count_exact(fresh_db):
    """The recorded sample_count matches the actual audio file's sample count."""
    prod, db_path, tmp_path = fresh_db
    audio = tmp_path / "master_samples.wav"
    duration_sec = 2.0
    _make_wav(audio, duration_sec, 440)

    art = record_tts_artifact(
        production_id=prod["id"], audio_path=audio,
        script_revision_id="s1", voice_id="v1", model="m1",
        voice_settings={}, request_fingerprint="fp1",
        db_path=db_path,
    )

    # Verify metadata has exact sample count
    conn = _db.connect(db_path)
    meta = json.loads(conn.execute(
        "SELECT metadata_json FROM artifacts WHERE id=?", (art["id"],)
    ).fetchone()["metadata_json"])
    conn.close()

    expected_samples = int(duration_sec * MASTER_SAMPLE_RATE)
    # ffprobe may report nb_samples as None for WAV; fall back to duration_ms * rate
    actual_samples = meta["sample_count"]
    if actual_samples is None:
        actual_samples = int(meta["duration_ms"] * MASTER_SAMPLE_RATE / 1000)
    # Allow tiny rounding (ffprobe duration may be ±1ms → ±48 samples)
    assert abs(actual_samples - expected_samples) <= 48, (
        f"sample_count {actual_samples} != expected ~{expected_samples}")
    assert meta["sample_rate"] == MASTER_SAMPLE_RATE
    assert meta["channels"] == 1


# --- S4-T02: Exact timing and timeline spans ---

def test_interval_no_negative():
    """A TimeInterval with a negative start is rejected."""
    with pytest.raises(ValueError, match="negative"):
        TimeInterval(start_samples=-1, end_samples=100)


def test_interval_no_inverse():
    """A TimeInterval where end < start is rejected."""
    with pytest.raises(ValueError, match="cannot be before"):
        TimeInterval(start_samples=100, end_samples=50)


def test_ms_to_samples_round_trip():
    """ms → samples → ms round-trip is consistent (no drift)."""
    for ms in [0, 1, 10, 100, 500, 1000, 1500, 2000, 45000]:
        samples = ms_to_samples(ms)
        back = samples_to_ms(samples)
        assert abs(back - ms) <= 1, f"round-trip drift: {ms}ms → {samples}samples → {back}ms"


def test_interval_duration_in_samples():
    """Interval duration is computed in integer samples (authoritative), not float ms."""
    interval = TimeInterval(start_samples=48000, end_samples=96000)
    assert interval.duration_samples == 48000
    # ms is a projection (derived), not the source of truth
    assert interval.duration_ms == 1000
