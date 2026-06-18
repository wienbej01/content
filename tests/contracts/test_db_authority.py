"""S1-T02: Enforce one database authority — no legacy JSON fallback reads.

Named tests required by the program:
  test_clean_execution_without_legacy_json
  test_stale_json_cannot_override_db
  test_runtime_file_trace_has_no_authority_reads
  test_exports_are_not_consumed_downstream
"""
import builtins
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import produce_db
from authoring_service import (
    save_research_brief,
    save_script,
    save_storyboard,
    get_script,
    get_research_brief,
    get_storyboard,
)


AUTHORITY_FILES = {
    "script.json",
    "storyboard.json",
    "research_brief.json",
    "media_plan.json",
    "beat_timing_map.json",
    "manifest.json",
    "state.json",
    "gates.json",
    "production_storyboard.json",
}


@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "auth_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("auth_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file, tmp_path
    _db._db_path_override = None


def _save_brief_and_script(production_id, db_path):
    """Set up a research brief and script in the DB (no files on disk)."""
    citations = [
        {"url": "https://example.com/1", "title": "Source 1", "source_type": "web",
         "published_at": "2024", "accessed_at": "2024", "is_primary": True},
        {"url": "https://example.com/2", "title": "Source 2", "source_type": "web",
         "published_at": "2024", "accessed_at": "2024", "is_primary": True},
        {"url": "https://example.com/3", "title": "Source 3", "source_type": "web",
         "published_at": "2024", "accessed_at": "2024", "is_primary": True},
    ]
    save_research_brief(
        production_id=production_id,
        brief_payload={"title": "Test Brief", "segments": [], "sources": citations},
        citations=citations,
        db_path=db_path,
    )
    save_script(
        production_id=production_id,
        script_payload={
            "project_id": "test",
            "title": "Test Script",
            "segments": [
                {"id": "S1", "text": "Hello world", "label": "B001", "visual_intent": {}},
                {"id": "S2", "text": "Second beat", "label": "B002", "visual_intent": {}},
            ],
        },
        db_path=db_path,
    )


def test_clean_execution_without_legacy_json(clean_db):
    """A DB-native stage (storyboard derivation) succeeds with zero legacy JSON
    files on disk — the DB is the sole authority."""
    prod, db_path, tmp_path = clean_db
    _save_brief_and_script(prod["id"], db_path)

    # No project_dir with legacy JSON exists. invoke_storyboard reads only from DB.
    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "s",
        "video_type": "short",
    }
    result = produce_db.invoke_storyboard(inputs, tmp_path)
    assert result["status"] == "saved"
    assert result["beats"] >= 2  # one beat per script segment

    # Verify the storyboard is in the DB
    sb = get_storyboard(prod["id"], db_path=db_path)
    assert sb is not None
    assert len(sb["beats"]) >= 2


def test_stale_json_cannot_override_db(clean_db, tmp_path):
    """A stale script.json on disk must NOT override the DB's active script.

    The DB-native path must read from the DB, not fall back to the file.
    """
    prod, db_path, _ = clean_db
    _save_brief_and_script(prod["id"], db_path)

    # Write a STALE script.json to disk with different content
    project_dir = tmp_path / "Videos" / "Projects" / prod["project_slug"]
    project_dir.mkdir(parents=True, exist_ok=True)
    stale_script = {"project_id": "stale", "segments": [{"id": "STALE", "text": "stale content"}]}
    (project_dir / "script.json").write_text(json.dumps(stale_script))

    # The DB-native review_storyboard should derive from the DB script, not the file
    db_script = get_script(prod["id"], db_path=db_path)
    assert db_script["segments"][0]["text"] == "Hello world"

    # invoke_storyboard reads from DB (get_script_segments), not from script.json
    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "s",
        "video_type": "short",
    }
    result = produce_db.invoke_storyboard(inputs, tmp_path)
    sb = get_storyboard(prod["id"], db_path=db_path)
    # The storyboard beats must match the DB script text, not the stale file
    texts = [b.get("narration_text", "") for b in sb["beats"]]
    assert "Hello world" in texts
    assert "stale content" not in texts


def test_runtime_file_trace_has_no_authority_reads(clean_db, tmp_path):
    """During DB-native storyboard derivation, no authority JSON file is opened
    for reading. We patch builtins.open to trace all read opens and verify none
    target an authority filename."""
    prod, db_path, _ = clean_db
    _save_brief_and_script(prod["id"], db_path)

    opened_files = []
    real_open = builtins.open

    def _tracing_open(file, mode="r", *args, **kwargs):
        if "r" in str(mode) or "b" in str(mode):
            fname = Path(str(file)).name
            opened_files.append(fname)
        return real_open(file, mode, *args, **kwargs)

    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "s",
        "video_type": "short",
    }
    with patch("builtins.open", side_effect=_tracing_open):
        produce_db.invoke_storyboard(inputs, tmp_path)

    authority_reads = [f for f in opened_files if f in AUTHORITY_FILES]
    assert authority_reads == [], (
        f"DB-native stage read authority JSON files: {authority_reads}")


def test_exports_are_not_consumed_downstream(clean_db, tmp_path):
    """Exported JSON (script.json, research_brief.json) is NOT read back by a
    downstream DB-native stage. We write exports, delete them, and prove the
    downstream stage still succeeds."""
    prod, db_path, _ = clean_db
    _save_brief_and_script(prod["id"], db_path)

    project_dir = tmp_path / "Videos" / "Projects" / prod["project_slug"]
    project_dir.mkdir(parents=True, exist_ok=True)
    # Simulate exports being present (as produce_db would write them)
    (project_dir / "script.json").write_text('{"export": true}')
    (project_dir / "research_brief.json").write_text('{"export": true}')

    # Run storyboard (downstream of write_script) — it reads from DB, not files
    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "s",
        "video_type": "short",
    }
    result = produce_db.invoke_storyboard(inputs, tmp_path)
    assert result["status"] == "saved"

    # Now delete ALL export JSON and re-run — the DB-native stage must still work
    for f in project_dir.glob("*.json"):
        f.unlink()
    if (project_dir / "narration").exists():
        for f in (project_dir / "narration").glob("*.json"):
            f.unlink()

    result2 = produce_db.invoke_storyboard(inputs, tmp_path)
    assert result2["status"] == "saved"
    assert result2["beats"] == result["beats"]  # same result (idempotent from DB)
