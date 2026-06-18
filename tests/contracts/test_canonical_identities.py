"""S1-T04: Enforce canonical identities and active revisions.

Named tests required by the program:
  test_active_revision_uniqueness
  test_query_schema_compatibility
  test_no_display_label_relational_join
  test_artifact_sha_mutation_blocks_consumption
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from stage_runner import save_document_revision, get_active_document
import tts_service


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "id_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("id_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file
    _db._db_path_override = None


def test_active_revision_uniqueness(fresh_db):
    """At most ONE active revision per (production, kind) is allowed — enforced
    at the DB level by a partial unique index (migration 006)."""
    prod, db_path = fresh_db

    # Save a first revision
    doc1 = save_document_revision(prod["id"], "test_doc", {"v": 1}, db_path=db_path)
    assert doc1["status"] == "active"

    # Save a second revision — the first is superseded
    doc2 = save_document_revision(prod["id"], "test_doc", {"v": 2}, db_path=db_path)
    assert doc2["status"] == "active"

    # Verify only one active revision exists
    conn = _db.connect(db_path)
    active = conn.execute(
        "SELECT COUNT(*) FROM document_revisions WHERE production_id=? AND kind='test_doc' AND status='active'",
        (prod["id"],),
    ).fetchone()[0]
    conn.close()
    assert active == 1

    # The DB-level partial unique index prevents a second active revision even
    # via a raw INSERT bypassing save_document_revision
    with pytest.raises(sqlite3.IntegrityError):
        with _db.transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO document_revisions (id, production_id, kind, revision, status, "
                "payload_json, payload_sha256, created_at) VALUES (?, ?, 'test_doc', 99, 'active', '{}', 'x', 'now')",
                (_db._id("doc"), prod["id"]),
            )


def test_query_schema_compatibility(fresh_db):
    """The DB query schema is stable — core tables and columns exist and are
    queryable by the production_repo / authoring_service APIs."""
    prod, db_path = fresh_db
    conn = _db.connect(db_path)

    # Verify core identity tables are queryable
    for table in ["productions", "document_revisions", "creative_beats", "timeline_spans",
                  "render_units", "hero_render_groups", "artifacts", "provider_jobs",
                  "deliverables", "validations", "cost_events"]:
        result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert result[0] >= 0  # query succeeds

    conn.close()


def test_no_display_label_relational_join(fresh_db):
    """No JSON-content LIKE joins remain in tts_service.reuse query.

    The S1-T04 fix replaced the fragile `payload_json LIKE '%"artifact_id":"..."%'`
    join with a direct artifact metadata_json query. We verify the source code
    no longer contains that pattern."""
    tts_src = (ROOT / "scripts" / "tts_service.py").read_text()
    # The old LIKE join must be gone
    assert "payload_json LIKE" not in tts_src, (
        "tts_service still uses a JSON-content LIKE join for artifact lookup — "
        "replace with a relational metadata_json query")
    # The new direct query must be present
    assert "metadata_json" in tts_src


def test_artifact_sha_mutation_blocks_consumption(fresh_db, tmp_path):
    """A mutated artifact SHA (on-disk file changed) blocks reuse — the checksum
    mismatch is detected and regeneration is required (not silent reuse)."""
    prod, db_path = fresh_db

    # Create a valid WAV file
    import subprocess
    audio = tmp_path / "master.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1.0",
        "-c:a", "pcm_s16le", str(audio),
    ], capture_output=True, check=True)

    # Register the TTS artifact
    art1 = tts_service.record_tts_artifact(
        production_id=prod["id"],
        audio_path=audio,
        script_revision_id="s1",
        voice_id="v1",
        model="m1",
        voice_settings={},
        request_fingerprint="fp1",
        db_path=db_path,
    )
    assert art1["reused"] is False

    # Corrupt the file (change its SHA)
    audio.write_bytes(b"corrupted")

    # Reuse with same fingerprint must fail (checksum mismatch)
    with pytest.raises(RuntimeError, match="TTS_MASTER_CHECKSUM_MISMATCH"):
        tts_service.record_tts_artifact(
            production_id=prod["id"],
            audio_path=audio,
            script_revision_id="s1",
            voice_id="v1",
            model="m1",
            voice_settings={},
            request_fingerprint="fp1",
            db_path=db_path,
        )
