"""S22_T012 - Gate storyboard human approval stage tests.

Verifies:
1. TTS blocked before gate_storyboard approval.
2. Compile blocked before storyboard approval.
3. Approval request subject is active storyboard revision/hash.
4. Storyboard revision change stales approval.
5. YT_TEST_MODE=1 auto-approves only in test mode.
6. Gate A content still applies to script only.
7. Gate A spend still applies to render plan/cost only.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from stage_runner import STAGE_REGISTRY, deps_satisfied
from authoring_service import (
    request_approval, record_approval_decision, is_approved, get_approval,
    save_script, save_research_brief, save_storyboard, get_active_script_revision_id,
    _get_active_storyboard_revision_id,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "gate_sb_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("gate_sb_test", seed="t", video_type="short", db_path=db_file)
    yield prod, db_file
    _db._db_path_override = None


def _seed_storyboard(production_id, db_path):
    citations = [
        {"url": f"https://x.com/{i}", "title": f"S{i}", "source_type": "web",
         "published_at": "2024", "accessed_at": "2024", "is_primary": True}
        for i in range(3)
    ]
    save_research_brief(production_id, {"title": "B"}, citations, db_path=db_path)
    save_script(production_id, {"segments": [{"id": "S1", "text": "hello world"}]}, db_path=db_path)
    save_storyboard(
        production_id,
        {"beats": [{"label": "B001", "shot_type": "hero_lipsync", "narration_text": "hello"}]},
        db_path=db_path,
    )


# --- Test 1: TTS blocked before gate_storyboard approval ---

def test_tts_blocked_before_storyboard_approval(fresh_db):
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    satisfied, missing = deps_satisfied("tts", prod["id"], db_path=db_path)
    assert not satisfied, "TTS must not be satisfied before gate_storyboard"
    assert "gate_storyboard" in missing or "review_storyboard" in missing


# --- Test 2: Compile blocked before storyboard approval ---

def test_compile_blocked_before_storyboard_approval(fresh_db):
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    satisfied, missing = deps_satisfied("compile_media", prod["id"], db_path=db_path)
    assert not satisfied, "compile_media must not be satisfied before gate_storyboard"


# --- Test 3: Approval request subject is active storyboard revision/hash ---

def test_approval_subject_is_storyboard_revision(fresh_db):
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    sb_rev_id = _get_active_storyboard_revision_id(prod["id"], db_path=db_path)
    assert sb_rev_id, "storyboard revision must exist"

    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT payload_sha256 FROM document_revisions WHERE id=?", (sb_rev_id,)
    ).fetchone()
    conn.close()
    payload_hash = row["payload_sha256"]

    subject_hash = f"storyboard:{sb_rev_id}:{payload_hash[:16]}"

    approval = request_approval(
        production_id=prod["id"],
        gate_name="gate_storyboard",
        subject_type="storyboard",
        subject_id=sb_rev_id,
        subject_sha256=subject_hash,
        db_path=db_path,
    )

    assert approval["subject_type"] == "storyboard"
    assert approval["subject_id"] == sb_rev_id
    assert approval["status"] == "pending"


# --- Test 4: Storyboard revision change stales approval ---

def test_storyboard_change_stales_approval(fresh_db):
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    sb_rev_id = _get_active_storyboard_revision_id(prod["id"], db_path=db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT payload_sha256 FROM document_revisions WHERE id=?", (sb_rev_id,)
    ).fetchone()
    conn.close()
    subject_hash = f"storyboard:{sb_rev_id}:{row['payload_sha256'][:16]}"

    request_approval(
        prod["id"], "gate_storyboard", "storyboard", sb_rev_id, subject_hash, db_path=db_path)
    record_approval_decision(prod["id"], "gate_storyboard", "pass", "tester", db_path=db_path)
    assert is_approved(prod["id"], "gate_storyboard", db_path=db_path)

    save_storyboard(
        prod["id"],
        {"beats": [{"label": "B001", "shot_type": "hero_lipsync", "narration_text": "hello"},
                    {"label": "B002", "shot_type": "broll_archival", "narration_text": "world"}]},
        db_path=db_path,
    )

    new_rev_id = _get_active_storyboard_revision_id(prod["id"], db_path=db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT payload_sha256 FROM document_revisions WHERE id=?", (new_rev_id,)
    ).fetchone()
    conn.close()
    new_subject_hash = f"storyboard:{new_rev_id}:{row['payload_sha256'][:16]}"
    request_approval(
        prod["id"], "gate_storyboard", "storyboard", new_rev_id, new_subject_hash, db_path=db_path)

    assert not is_approved(prod["id"], "gate_storyboard", db_path=db_path), (
        "approval must be stale after storyboard changes and re-request")


# --- Test 5: YT_TEST_MODE=1 auto-approves only in test mode ---

def test_yt_test_mode_auto_approves(monkeypatch, fresh_db):
    monkeypatch.setenv("YT_TEST_MODE", "1")
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    from produce_db import invoke_gate_storyboard
    os.environ["PRODUCTION_DB_PATH"] = db_path
    _db._db_path_override = db_path

    result = invoke_gate_storyboard(
        {"production_id": prod["id"], "project_slug": "gate_sb_test", "seed": "t", "video_type": "short"},
        Path("/tmp"),
    )
    assert result["status"] == "pass"
    assert result["test_mode"] is True

    assert is_approved(prod["id"], "gate_storyboard", db_path=db_path)


def test_non_test_mode_requires_human_approval(fresh_db, monkeypatch):
    monkeypatch.delenv("YT_TEST_MODE", raising=False)
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    os.environ["PRODUCTION_DB_PATH"] = db_path
    _db._db_path_override = db_path

    from produce_db import invoke_gate_storyboard
    with pytest.raises(RuntimeError, match="pending approval"):
        invoke_gate_storyboard(
            {"production_id": prod["id"], "project_slug": "gate_sb_test", "seed": "t", "video_type": "short"},
            Path("/tmp"),
        )


# --- Test 6: Gate A content still applies to script only ---

def test_gate_a_content_applies_to_script_only(fresh_db):
    prod, db_path = fresh_db
    _seed_storyboard(prod["id"], db_path)

    script_rev = get_active_script_revision_id(prod["id"], db_path=db_path)

    approval = request_approval(
        prod["id"], "gate_a_content", "script", script_rev, f"script:{script_rev}", db_path=db_path)
    assert approval["subject_type"] == "script"

    gate_a = get_approval(prod["id"], "gate_a_content", db_path=db_path)
    assert gate_a is not None
    assert gate_a["subject_type"] == "script"


# --- Test 7: Gate A spend still applies to render plan/cost only ---

def test_gate_a_spend_applies_to_render_plan_only(fresh_db):
    prod, db_path = fresh_db

    approval = request_approval(
        prod["id"], "gate_a_spend", "render_plan", "rp_1", "sha_1", db_path=db_path)
    assert approval["subject_type"] == "render_plan"

    gate_spend = get_approval(prod["id"], "gate_a_spend", db_path=db_path)
    assert gate_spend is not None
    assert gate_spend["subject_type"] == "render_plan"


# --- Stage registry dependency order ---

def test_gate_storyboard_in_registry():
    assert "gate_storyboard" in STAGE_REGISTRY
    gs = STAGE_REGISTRY["gate_storyboard"]
    assert "review_storyboard" in gs.depends_on
    assert "storyboard" in gs.consumes_kinds
    assert "gate_storyboard_approval" in gs.produces_kinds


def test_tts_depends_on_gate_storyboard():
    tts = STAGE_REGISTRY["tts"]
    assert "gate_storyboard" in tts.depends_on
    assert "review_storyboard" not in tts.depends_on


def test_downstream_stages_include_gate_storyboard():
    from stage_runner import downstream_stages
    ds = downstream_stages("review_storyboard")
    assert "gate_storyboard" in ds
    assert "tts" in ds
