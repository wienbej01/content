"""Tests for diagnostic audio extraction and tagging (Ticket LB-401)."""
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import production_db as _db
from media_service import complete_provider_job, _extract_and_register_diagnostic_audio


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    import os
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("lb401_test", db_path=db)


def _make_dummy_video_with_audio(path: Path):
    """Create a dummy MP4 with a silent audio stream for testing."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=2",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)],
        capture_output=True, check=True
    )


def _make_dummy_video_without_audio(path: Path):
    """Create a dummy MP4 without an audio stream for testing."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=2",
         "-c:v", "libx264", str(path)],
        capture_output=True, check=True
    )


class TestDiagnosticAudioExtraction:
    def test_provider_audio_is_registered_separately(self, db, prod):
        """Verify that embedded provider audio is extracted and registered as a separate artifact."""
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "test_video.mp4"
            _make_dummy_video_with_audio(video_path)
            
            # Create a mock render unit and provider job
            conn = _db.connect(db)
            conn.execute(
                """INSERT INTO render_units (id, production_id, ordinal, asset_type, audio_policy, lipsync_required, required_start_ms, required_end_ms, required_duration_ms, status, created_at, updated_at)
                   VALUES ('ru_1', ?, 0, 'generated_video', 'HERO_SYNC_LOCKED', 1, 0, 5000, 5000, 'ordered', '2026-01-01', '2026-01-01')""",
                (prod["id"],)
            )
            conn.execute(
                """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key)
                   VALUES ('job_123', ?, 'ru_1', 'higgsfield', 'generate_video', 'running', 'idem_123')""",
                (prod["id"],)
            )
            conn.commit()
            conn.close()
            
            # Complete the job
            complete_provider_job(
                provider_job_id="job_123",
                result_artifact_path=video_path,
                result_metadata={"source_slice_artifact_id": "slice_abc"},
                db_path=db
            )
            
            # Verify both artifacts exist
            conn = _db.connect(db)
            video_art = conn.execute(
                "SELECT * FROM artifacts WHERE production_id=? AND kind='generated_media'",
                (prod["id"],)
            ).fetchone()
            audio_art = conn.execute(
                "SELECT * FROM artifacts WHERE production_id=? AND kind='provider_diagnostic_audio'",
                (prod["id"],)
            ).fetchone()
            conn.close()
            
            assert video_art is not None
            assert audio_art is not None
            assert audio_art["uri"].endswith(".diagnostic_audio.wav")

    def test_missing_provider_audio_does_not_fail_generation(self, db, prod):
        """Verify that a video without audio does not fail the completion process."""
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "test_video_no_audio.mp4"
            _make_dummy_video_without_audio(video_path)
            
            conn = _db.connect(db)
            conn.execute(
                """INSERT INTO render_units (id, production_id, ordinal, asset_type, audio_policy, lipsync_required, required_start_ms, required_end_ms, required_duration_ms, status, created_at, updated_at)
                   VALUES ('ru_2', ?, 0, 'generated_video', 'BROLL_FLEX', 0, 0, 5000, 5000, 'ordered', '2026-01-01', '2026-01-01')""",
                (prod["id"],)
            )
            conn.execute(
                """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key)
                   VALUES ('job_456', ?, 'ru_2', 'higgsfield', 'generate_video', 'running', 'idem_456')""",
                (prod["id"],)
            )
            conn.commit()
            conn.close()
            
            # Should not raise an error
            complete_provider_job(
                provider_job_id="job_456",
                result_artifact_path=video_path,
                result_metadata={},
                db_path=db
            )
            
            # Verify only video artifact exists
            conn = _db.connect(db)
            audio_art = conn.execute(
                "SELECT * FROM artifacts WHERE production_id=? AND kind='provider_diagnostic_audio'",
                (prod["id"],)
            ).fetchone()
            conn.close()
            
            assert audio_art is None  # No diagnostic audio should be registered

    def test_diagnostic_audio_tagged_ineligible_for_narration(self, db, prod):
        """Verify that the extracted audio is explicitly tagged as ineligible for final narration."""
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "test_video.mp4"
            _make_dummy_video_with_audio(video_path)
            
            conn = _db.connect(db)
            conn.execute(
                """INSERT INTO render_units (id, production_id, ordinal, asset_type, audio_policy, lipsync_required, required_start_ms, required_end_ms, required_duration_ms, status, created_at, updated_at)
                   VALUES ('ru_3', ?, 0, 'generated_video', 'HERO_SYNC_LOCKED', 1, 0, 5000, 5000, 'ordered', '2026-01-01', '2026-01-01')""",
                (prod["id"],)
            )
            conn.execute(
                """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key)
                   VALUES ('job_789', ?, 'ru_3', 'higgsfield', 'generate_video', 'running', 'idem_789')""",
                (prod["id"],)
            )
            conn.commit()
            conn.close()
            
            complete_provider_job(
                provider_job_id="job_789",
                result_artifact_path=video_path,
                result_metadata={"source_slice_artifact_id": "slice_xyz"},
                db_path=db
            )
            
            conn = _db.connect(db)
            audio_art = conn.execute(
                "SELECT * FROM artifacts WHERE production_id=? AND kind='provider_diagnostic_audio'",
                (prod["id"],)
            ).fetchone()
            conn.close()
            
            metadata = json.loads(audio_art["metadata_json"])
            assert metadata["eligible_for_final_narration"] is False
            assert metadata["usage_policy"] == "diagnostic_only"
            assert metadata["source_slice_artifact_id"] == "slice_xyz"
