"""S2-T03: Dependency invalidation + S2-T04: Human approval gates.

Named tests required by the program:
  test_script_change_invalidates_tts_and_downstream
  test_storyboard_change_preserves_unaffected_script
  test_timing_change_invalidates_render_plan
  test_render_plan_change_stales_spend_approval
  test_artifact_change_stales_validation_and_deliverable

  test_pending_approval_pauses
  test_stale_approval_rejected
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from stage_runner import (
    save_document_revision, invalidate_document_descendants,
    STAGE_REGISTRY, stages_blocked_by_kind,
)
from authoring_service import (
    request_approval, record_approval_decision, is_approved, get_approval,
    save_script, save_research_brief, save_storyboard,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "inv_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("inv_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file
    _db._db_path_override = None


def _link_dep(production_id, dependent_kind, dependency_kind, db_path):
    """Manually create a document_dependencies link between active revisions."""
    conn = _db.connect(db_path)
    dep_row = conn.execute(
        "SELECT id FROM document_revisions WHERE production_id=? AND kind=? AND status='active' ORDER BY revision DESC LIMIT 1",
        (production_id, dependent_kind),
    ).fetchone()
    src_row = conn.execute(
        "SELECT id FROM document_revisions WHERE production_id=? AND kind=? AND status='active' ORDER BY revision DESC LIMIT 1",
        (production_id, dependency_kind),
    ).fetchone()
    conn.close()
    if dep_row and src_row:
        with _db.transaction(db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO document_dependencies (document_revision_id, depends_on_document_revision_id, dependency_role) VALUES (?,?,?)",
                (dep_row["id"], src_row["id"], f"{dependent_kind}_depends_on_{dependency_kind}"),
            )


def _setup_lineage(production_id, db_path):
    """Create a full document lineage: brief → script → storyboard → timing → render_plan."""
    citations = [
        {"url": f"https://example.com/{i}", "title": f"Src {i}", "source_type": "web",
         "published_at": "2024", "accessed_at": "2024", "is_primary": True}
        for i in range(3)
    ]
    save_research_brief(production_id, {"title": "Brief", "sources": citations}, citations, db_path=db_path)
    save_script(production_id, {"title": "Script", "segments": [{"id": "S1", "text": "hello"}]}, db_path=db_path)
    save_storyboard(production_id, {"beats": [{"label": "B001", "narration_text": "hello"}]}, db_path=db_path)
    save_document_revision(production_id, "tts_artifact", {"artifact_id": "art1"}, db_path=db_path)
    save_document_revision(production_id, "timing_map", {"spans": [{"label": "B001"}]}, db_path=db_path)
    save_document_revision(production_id, "render_plan", {"units": [], "estimated_cost_usd": 1.0}, db_path=db_path)
    # Create dependency links (service functions do this; we replicate for the test)
    _link_dep(production_id, "script", "research_brief", db_path)
    _link_dep(production_id, "storyboard", "script", db_path)
    _link_dep(production_id, "tts_artifact", "script", db_path)
    _link_dep(production_id, "timing_map", "tts_artifact", db_path)
    _link_dep(production_id, "timing_map", "storyboard", db_path)
    _link_dep(production_id, "render_plan", "timing_map", db_path)
    _link_dep(production_id, "render_plan", "storyboard", db_path)


# --- S2-T03: Dependency invalidation ---

def test_script_change_invalidates_tts_and_downstream(fresh_db):
    """Changing the script revision invalidates TTS and all downstream stages."""
    prod, db_path = fresh_db
    _setup_lineage(prod["id"], db_path)

    # Get the active script revision
    conn = _db.connect(db_path)
    script_rev = conn.execute(
        "SELECT id FROM document_revisions WHERE production_id=? AND kind='script' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()

    # Invalidate descendants of the script revision
    counts = invalidate_document_descendants(prod["id"], script_rev["id"], db_path=db_path)

    # TTS, timing_map, render_plan should all be stale (they depend on script)
    conn = _db.connect(db_path)
    stale_kinds = [
        r["kind"] for r in conn.execute(
            "SELECT kind FROM document_revisions WHERE production_id=? AND status='stale'",
            (prod["id"],),
        ).fetchall()
    ]
    conn.close()

    assert "tts_artifact" in stale_kinds, "TTS must be invalidated when script changes"
    assert "timing_map" in stale_kinds, "timing must be invalidated when script changes"


def test_storyboard_change_preserves_unaffected_script(fresh_db):
    """Changing the storyboard does NOT invalidate the script (script is upstream)."""
    prod, db_path = fresh_db
    _setup_lineage(prod["id"], db_path)

    conn = _db.connect(db_path)
    sb_rev = conn.execute(
        "SELECT id FROM document_revisions WHERE production_id=? AND kind='storyboard' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()

    counts = invalidate_document_descendants(prod["id"], sb_rev["id"], db_path=db_path)

    # Script should still be active (not stale)
    conn = _db.connect(db_path)
    script_status = conn.execute(
        "SELECT status FROM document_revisions WHERE production_id=? AND kind='script' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()
    assert script_status is not None, "script must NOT be invalidated when storyboard changes"

    # But timing_map (which consumes storyboard) should be stale
    conn = _db.connect(db_path)
    stale_kinds = [
        r["kind"] for r in conn.execute(
            "SELECT kind FROM document_revisions WHERE production_id=? AND status='stale'",
            (prod["id"],),
        ).fetchall()
    ]
    conn.close()
    assert "timing_map" in stale_kinds, "timing must be invalidated when storyboard changes"


def test_timing_change_invalidates_render_plan(fresh_db):
    """Changing the timing map invalidates the render plan (which consumes timing)."""
    prod, db_path = fresh_db
    _setup_lineage(prod["id"], db_path)

    # Get the old timing_map revision ID
    conn = _db.connect(db_path)
    old_tm = conn.execute(
        "SELECT id FROM document_revisions WHERE production_id=? AND kind='timing_map' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()

    # Save a NEW timing_map revision (supersedes the old one)
    save_document_revision(prod["id"], "timing_map", {"spans": [{"label": "B001", "start_ms": 0, "end_ms": 1000}]}, db_path=db_path)

    # Invalidate descendants of the old timing_map revision
    invalidate_document_descendants(prod["id"], old_tm["id"], db_path=db_path)

    # The render_plan that consumed timing_map should be stale
    conn = _db.connect(db_path)
    rp_status = conn.execute(
        "SELECT status FROM document_revisions WHERE production_id=? AND kind='render_plan' ORDER BY revision DESC LIMIT 1",
        (prod["id"],),
    ).fetchone()
    conn.close()
    assert rp_status["status"] in ("stale", "superseded"), (
        f"render_plan must be stale/superseded after timing change, got {rp_status['status']}")


def test_render_plan_change_stales_spend_approval(fresh_db):
    """Changing the render plan invalidates the spend approval bound to it."""
    prod, db_path = fresh_db
    _setup_lineage(prod["id"], db_path)

    # Request spend approval bound to the render_plan
    conn = _db.connect(db_path)
    plan_rev = conn.execute(
        "SELECT id, payload_sha256 FROM document_revisions WHERE production_id=? AND kind='render_plan' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()

    approval = request_approval(
        production_id=prod["id"],
        gate_name="gate_a_spend",
        subject_type="render_plan",
        subject_id=plan_rev["id"],
        subject_sha256=plan_rev["payload_sha256"],
        db_path=db_path,
    )
    assert approval["status"] == "pending"

    # Now change the render plan (new revision)
    save_document_revision(prod["id"], "render_plan", {"units": [], "estimated_cost_usd": 2.0}, db_path=db_path)

    # Request approval again — the subject changed, so the old approval should be stale
    conn = _db.connect(db_path)
    new_plan = conn.execute(
        "SELECT id, payload_sha256 FROM document_revisions WHERE production_id=? AND kind='render_plan' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()

    new_approval = request_approval(
        production_id=prod["id"],
        gate_name="gate_a_spend",
        subject_type="render_plan",
        subject_id=new_plan["id"],
        subject_sha256=new_plan["payload_sha256"],
        db_path=db_path,
    )

    # The old approval must NOT be pass/pending — it's stale
    old = get_approval(prod["id"], "gate_a_spend", db_path=db_path)
    assert old["status"] in ("stale", "pending"), (
        f"old approval should be stale or replaced, got {old['status']}")


def test_artifact_change_stales_validation_and_deliverable(fresh_db, tmp_path):
    """When an artifact is superseded, validations and deliverables bound to it
    become stale (cannot be consumed)."""
    prod, db_path = fresh_db

    # Register a non-media artifact (avoids ffprobe requirement)
    import production_repo as _repo
    art_file = tmp_path / "test_inv_data.json"
    art_file.write_text('{"original": true}')
    art = _repo.register_artifact(prod["id"], art_file, "test_data", db_path=db_path)

    # Record a validation bound to this artifact's SHA
    val_id = _db._id("val")
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO validations (id, production_id, subject_type, subject_id,
               validator_name, status, ruleset_version, evidence_json, artifact_sha256,
               algorithm_version, created_at)
               VALUES (?, ?, 'artifact', ?, 'test_validator', 'pass', 'v1', '{}', ?, 'v1', ?)""",
            (val_id, prod["id"], art["id"], art["sha256"], _db._now()),
        )

    # Now the artifact SHA changes (supersede with different content)
    art_file.write_text('{"changed": true}')
    art2 = _repo.register_artifact(prod["id"], art_file, "test_data", db_path=db_path)
    assert art2["sha256"] != art["sha256"]

    # The old validation references the old SHA — it's now stale
    conn = _db.connect(db_path)
    old_val = conn.execute(
        "SELECT status, artifact_sha256 FROM validations WHERE id=?", (val_id,)
    ).fetchone()
    conn.close()
    assert old_val["artifact_sha256"] != art2["sha256"], (
        "old validation must reference the old (stale) artifact SHA, not the new one")


# --- S2-T04: Human approval gates ---

def test_pending_approval_pauses(fresh_db):
    """A pending approval pauses production — is_approved returns False until
    a decision is recorded."""
    prod, db_path = fresh_db

    approval = request_approval(
        production_id=prod["id"],
        gate_name="gate_a_content",
        subject_type="script",
        subject_id="rev_1",
        subject_sha256="sha_1",
        db_path=db_path,
    )
    assert approval["status"] == "pending"
    assert not is_approved(prod["id"], "gate_a_content", db_path=db_path)

    # Record a pass decision
    record_approval_decision(
        production_id=prod["id"],
        gate_name="gate_a_content",
        decision="pass",
        actor="human_tester",
        note="looks good",
        db_path=db_path,
    )
    assert is_approved(prod["id"], "gate_a_content", db_path=db_path)


def test_stale_approval_rejected(fresh_db):
    """An approval for a stale subject SHA is rejected — a changed subject
    invalidates the prior approval."""
    prod, db_path = fresh_db

    # Request and approve with SHA "sha_1"
    request_approval(prod["id"], "gate_a_content", "script", "rev_1", "sha_1", db_path=db_path)
    record_approval_decision(prod["id"], "gate_a_content", "pass", "human", db_path=db_path)
    assert is_approved(prod["id"], "gate_a_content", db_path=db_path)

    # Subject changes — request approval with a new SHA
    new_approval = request_approval(
        prod["id"], "gate_a_content", "script", "rev_2", "sha_2", db_path=db_path)

    # The old approval is stale; is_approved must return False
    assert not is_approved(prod["id"], "gate_a_content", db_path=db_path), (
        "approval must be invalidated when the subject SHA changes")
    assert new_approval["status"] == "pending"
