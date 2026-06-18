"""Tests for TTS artifact registration and reuse rules (Ticket LB-200)."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import production_db as _db
from tts_service import record_tts_artifact

TEST_DB = Path(__file__).resolve().parent.parent / "db" / "test_tts_lb200.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure a clean test database for each test."""
    if TEST_DB.exists():
        TEST_DB.unlink()
    yield
    if TEST_DB.exists():
        TEST_DB.unlink()


def _create_dummy_audio(path: Path):
    """Create a dummy audio file for testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")


class TestTTSArtifactReuse:
    def test_exact_tts_fingerprint_reuses_master(self, setup_test_db):
        """Verify that an exact fingerprint match reuses the existing master artifact."""
        prod = _db.ensure_production("reuse_test", seed="test", video_type="short", db_path=TEST_DB)
        audio_path = Path(tempfile.gettempdir()) / "test_master.mp3"
        _create_dummy_audio(audio_path)
        
        voice_settings = {"stability": 0.5, "similarity": 0.75}
        fingerprint = "hash_of_script_voice_model_settings"
        
        # First call: registers new
        art1 = record_tts_artifact(
            production_id=prod["id"],
            audio_path=audio_path,
            script_revision_id="script_rev_1",
            voice_id="voice_123",
            model="eleven_v3",
            voice_settings=voice_settings,
            request_fingerprint=fingerprint,
            db_path=TEST_DB
        )
        assert art1["reused"] is False
        
        # Second call with exact same fingerprint: should reuse
        art2 = record_tts_artifact(
            production_id=prod["id"],
            audio_path=audio_path,
            script_revision_id="script_rev_1",
            voice_id="voice_123",
            model="eleven_v3",
            voice_settings=voice_settings,
            request_fingerprint=fingerprint,
            db_path=TEST_DB
        )
        assert art2["reused"] is True
        assert art2["id"] == art1["id"]

    def test_script_change_invalidates_master(self, setup_test_db):
        """Verify that a script revision change forces a new artifact."""
        prod = _db.ensure_production("script_change_test", seed="test", video_type="short", db_path=TEST_DB)
        audio_path1 = Path(tempfile.gettempdir()) / "test_master_script1.mp3"
        _create_dummy_audio(audio_path1)
        
        fingerprint1 = "hash_1"
        fingerprint2 = "hash_2"
        
        art1 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path1,
            script_revision_id="script_rev_1", voice_id="v1", model="m1",
            voice_settings={}, request_fingerprint=fingerprint1, db_path=TEST_DB
        )
        
        # Simulate regeneration with a new audio file due to script change
        audio_path2 = Path(tempfile.gettempdir()) / "test_master_script2.mp3"
        _create_dummy_audio(audio_path2)
        # Make it slightly different to ensure different sha256
        audio_path2.write_bytes(audio_path2.read_bytes() + b"extra")
        
        art2 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path2,
            script_revision_id="script_rev_2",  # Changed
            voice_id="v1", model="m1", voice_settings={},
            request_fingerprint=fingerprint2, db_path=TEST_DB
        )
        assert art2["reused"] is False
        assert art2["id"] != art1["id"]

    def test_voice_change_invalidates_master(self, setup_test_db):
        """Verify that a voice ID change forces a new artifact."""
        prod = _db.ensure_production("voice_change_test", seed="test", video_type="short", db_path=TEST_DB)
        audio_path = Path(tempfile.gettempdir()) / "test_master3.mp3"
        _create_dummy_audio(audio_path)
        
        art1 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="voice_A", model="m1",
            voice_settings={}, request_fingerprint="fp1", db_path=TEST_DB
        )
        
        art2 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="voice_B",  # Changed
            model="m1", voice_settings={}, request_fingerprint="fp2", db_path=TEST_DB
        )
        assert art2["reused"] is False

    def test_voice_setting_change_invalidates_master(self, setup_test_db):
        """Verify that a voice setting change forces a new artifact."""
        prod = _db.ensure_production("setting_change_test", seed="test", video_type="short", db_path=TEST_DB)
        audio_path = Path(tempfile.gettempdir()) / "test_master4.mp3"
        _create_dummy_audio(audio_path)
        
        art1 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="v1", model="m1",
            voice_settings={"stability": 0.5}, request_fingerprint="fp1", db_path=TEST_DB
        )
        
        art2 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="v1", model="m1",
            voice_settings={"stability": 0.8},  # Changed
            request_fingerprint="fp2", db_path=TEST_DB
        )
        assert art2["reused"] is False

    def test_checksum_mismatch_invalidates_master(self, setup_test_db):
        """A tampered master (checksum no longer matches) is NOT reused.

        The immutable master must never be silently reused when its on-disk bytes
        have changed, and corrupt bytes must not be registered as a new media
        artifact. The service must refuse and require regeneration instead.
        """
        prod = _db.ensure_production("checksum_test", seed="test", video_type="short", db_path=TEST_DB)
        audio_path = Path(tempfile.gettempdir()) / "test_master5.mp3"
        _create_dummy_audio(audio_path)

        art1 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="v1", model="m1",
            voice_settings={}, request_fingerprint="fp1", db_path=TEST_DB
        )

        # Corrupt the file so its checksum no longer matches the recorded sha256.
        audio_path.write_bytes(b"corrupted data")

        # Reuse with the same fingerprint must be refused (not silently reused,
        # and the corrupt bytes must not be registered as media).
        with pytest.raises(RuntimeError, match="TTS_MASTER_CHECKSUM_MISMATCH"):
            record_tts_artifact(
                production_id=prod["id"], audio_path=audio_path,
                script_revision_id="s1", voice_id="v1", model="m1",
                voice_settings={}, request_fingerprint="fp1", db_path=TEST_DB
            )

    def test_retry_does_not_duplicate_tts_job(self, setup_test_db):
        """Verify that a retry with the exact same parameters returns the existing artifact."""
        prod = _db.ensure_production("retry_test", seed="test", video_type="short", db_path=TEST_DB)
        audio_path = Path(tempfile.gettempdir()) / "test_master6.mp3"
        _create_dummy_audio(audio_path)
        
        fp = "retry_fingerprint"
        art1 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="v1", model="m1",
            voice_settings={}, request_fingerprint=fp, db_path=TEST_DB
        )
        
        # Simulate a retry
        art2 = record_tts_artifact(
            production_id=prod["id"], audio_path=audio_path,
            script_revision_id="s1", voice_id="v1", model="m1",
            voice_settings={}, request_fingerprint=fp, db_path=TEST_DB
        )
        
        assert art1["id"] == art2["id"]
        assert art2["reused"] is True
