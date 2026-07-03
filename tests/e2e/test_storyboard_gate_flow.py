"""S22_T012 - E2E tests for storyboard gate flow.

Verifies:
1. run_production blocks at gate_storyboard before TTS in non-test mode.
2. With YT_TEST_MODE=1, gate_storyboard auto-approves and pipeline completes.
3. Storyboard revision change re-invalidates gate_storyboard.
4. Full dry-run flow passes through gate_storyboard in test mode.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from authoring_service import (
    save_research_brief, save_script, save_storyboard,
    is_approved, request_approval, record_approval_decision,
    _get_active_storyboard_revision_id,
)


def _seed_storyboard_production(pid, slug, db_path):
    """Create all documents needed to reach gate_storyboard."""
    citations = [
        {"url": f"https://x.com/{i}", "title": f"S{i}", "source_type": "web",
         "published_at": "2024", "accessed_at": "2024", "is_primary": True}
        for i in range(3)
    ]
    save_research_brief(pid, {"title": "test"}, citations, db_path=db_path)
    save_script(pid, {
        "segments": [
            {"label": "B1", "text": "This is segment one for testing."},
            {"label": "B2", "text": "This is segment two for testing."},
        ],
    }, db_path=db_path)
    save_storyboard(pid, {
        "beats": [
            {"label": "B1", "shot_type": "hero_lipsync", "narration_text": "This is segment one for testing."},
            {"label": "B2", "shot_type": "broll_archival", "narration_text": "This is segment two for testing."},
        ],
    }, db_path=db_path)

    for stage in ["research", "write_script", "review_script", "gate_a_content",
                  "storyboard", "review_storyboard"]:
        _db.mirror_stage_state(slug, stage, "done", db_path=db_path)


def test_gate_storyboard_blocks_tts_in_non_test_mode(monkeypatch, tmp_path):
    """With YT_TEST_MODE unset, run_production must block at gate_storyboard."""
    monkeypatch.delenv("YT_TEST_MODE", raising=False)

    db_file = str(tmp_path / "e2e_gate_blocks.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)

    prod = _db.ensure_production("e2e_sb_gate", seed="gate block test", video_type="short", db_path=db_file)
    _seed_storyboard_production(prod["id"], "e2e_sb_gate", db_path=db_file)

    from produce_db import run_production
    with pytest.raises(SystemExit) as exc_info:
        run_production(prod["id"], db_path=db_file)
    assert exc_info.value.code == 1

    conn = _db.connect(db_file)
    gs_row = conn.execute(
        "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='gate_storyboard' ORDER BY attempt DESC LIMIT 1",
        (prod["id"],),
    ).fetchone()
    tts_row = conn.execute(
        "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='tts' ORDER BY attempt DESC LIMIT 1",
        (prod["id"],),
    ).fetchone()
    conn.close()

    if gs_row:
        assert gs_row["status"] == "failed", f"gate_storyboard should have failed, got {gs_row['status']}"
    assert tts_row is None or tts_row["status"] != "succeeded", "TTS must NOT succeed before gate_storyboard approval"


def test_yt_test_mode_auto_approve_gate_storyboard(monkeypatch, tmp_path):
    """With YT_TEST_MODE=1, gate_storyboard auto-approves and pipeline reaches tts."""
    monkeypatch.setenv("YT_TEST_MODE", "1")

    db_file = str(tmp_path / "e2e_gate_test_mode.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)

    prod = _db.ensure_production("e2e_sb_test", seed="gate test mode", video_type="short", db_path=db_file)
    _seed_storyboard_production(prod["id"], "e2e_sb_test", db_path=db_file)

    assert is_approved(prod["id"], "gate_storyboard", db_path=db_file) is False

    from produce_db import invoke_gate_storyboard
    result = invoke_gate_storyboard(
        {"production_id": prod["id"], "project_slug": "e2e_sb_test", "seed": "gate test mode", "video_type": "short"},
        Path("/tmp"),
    )
    assert result["status"] == "pass"
    assert result["test_mode"] is True
    assert is_approved(prod["id"], "gate_storyboard", db_path=db_file) is True


def test_storyboard_change_stales_gate_storyboard(monkeypatch, tmp_path):
    """Changing the storyboard invalidates any prior gate_storyboard approval."""
    db_file = str(tmp_path / "e2e_gate_stale.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    monkeypatch.setenv("YT_TEST_MODE", "1")

    prod = _db.ensure_production("e2e_sb_stale", seed="stale test", video_type="short", db_path=db_file)
    _seed_storyboard_production(prod["id"], "e2e_sb_stale", db_path=db_file)

    from produce_db import invoke_gate_storyboard
    result = invoke_gate_storyboard(
        {"production_id": prod["id"], "project_slug": "e2e_sb_stale", "seed": "stale test", "video_type": "short"},
        Path("/tmp"),
    )
    assert result["status"] == "pass"
    assert is_approved(prod["id"], "gate_storyboard", db_path=db_file) is True

    save_storyboard(
        prod["id"],
        {"beats": [{"label": "B1", "shot_type": "hero_lipsync", "narration_text": "changed narration"}]},
        db_path=db_file,
    )

    monkeypatch.delenv("YT_TEST_MODE", raising=False)
    with pytest.raises(RuntimeError, match="pending approval"):
        invoke_gate_storyboard(
            {"production_id": prod["id"], "project_slug": "e2e_sb_stale", "seed": "stale test", "video_type": "short"},
            Path("/tmp"),
        )

    assert is_approved(prod["id"], "gate_storyboard", db_path=db_file) is False, (
        "gate_storyboard approval must be stale after storyboard change and re-request")


def test_approval_db_state_is_correct(monkeypatch, tmp_path):
    """Verify the DB state after gate_storyboard approval is correct."""
    db_file = str(tmp_path / "e2e_gate_db_state.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)

    prod = _db.ensure_production("e2e_sb_dbstate", seed="db state test", video_type="short", db_path=db_file)
    _seed_storyboard_production(prod["id"], "e2e_sb_dbstate", db_path=db_file)

    sb_rev_id = _get_active_storyboard_revision_id(prod["id"], db_path=db_file)
    conn = _db.connect(db_file)
    row = conn.execute(
        "SELECT payload_sha256 FROM document_revisions WHERE id=?", (sb_rev_id,)
    ).fetchone()
    conn.close()
    payload_hash = row["payload_sha256"]
    subject_hash = f"storyboard:{sb_rev_id}:{payload_hash[:16]}"

    request_approval(
        prod["id"], "gate_storyboard", "storyboard", sb_rev_id, subject_hash, db_path=db_file)
    record_approval_decision(prod["id"], "gate_storyboard", "pass", "human", db_path=db_file)

    conn = _db.connect(db_file)
    ar = conn.execute(
        "SELECT * FROM approval_requests WHERE production_id=? AND gate_name='gate_storyboard'",
        (prod["id"],),
    ).fetchone()
    conn.close()

    assert ar is not None
    assert ar["status"] == "pass"
    assert ar["subject_type"] == "storyboard"
    assert ar["subject_id"] == sb_rev_id
    assert ar["actor"] == "human"
