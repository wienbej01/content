"""S2-T02: Stage result semantics — success requires committed output.

Named tests required by the program:
  test_stage_success_requires_committed_output
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from stage_runner import (
    STAGE_REGISTRY, LegacyAdapter, StageSkipped, _verify_committed_output,
    save_document_revision,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "sem_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("sem_test", seed="s", video_type="short", db_path=db_file)
    yield prod, db_file
    _db._db_path_override = None


def test_stage_success_requires_committed_output(fresh_db):
    """A stage with output_kind set MUST commit a document revision — the
    LegacyAdapter enforces this by calling save_document_revision. After
    success, the document must exist in the DB with an active status."""
    prod, db_path = fresh_db

    def stub_invoker(inputs, tmp_path):
        return {"beats": [{"label": "B001"}]}

    adapter = LegacyAdapter(
        stage_name="storyboard",  # produces_kinds=["storyboard"]
        output_kind="storyboard",
        invoke_fn=stub_invoker,
    )

    result = adapter.run(prod["id"], {"production_id": prod["id"]}, db_path=db_path)
    assert result["beats"][0]["label"] == "B001"

    # Verify the document was committed to the DB (active revision exists)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT status, kind FROM document_revisions WHERE production_id=? AND kind='storyboard' AND status='active'",
        (prod["id"],),
    ).fetchone()
    conn.close()
    assert row is not None, "stage must commit a document revision to be marked succeeded"
    assert row["status"] == "active"

    # Verify the stage_run was marked succeeded
    conn = _db.connect(db_path)
    run = conn.execute(
        "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='storyboard' ORDER BY attempt DESC LIMIT 1",
        (prod["id"],),
    ).fetchone()
    conn.close()
    assert run["status"] == "succeeded"


def test_stage_success_with_committed_output(fresh_db):
    """A stage that saves its document revision is accepted."""
    prod, db_path = fresh_db

    def good_invoker(inputs, tmp_path):
        # Save the document revision (simulates what a real invoker does)
        save_document_revision(prod["id"], "storyboard", {"beats": [{"label": "B001"}]}, db_path=db_path)
        return {"status": "saved", "document_id": "doc_1"}

    adapter = LegacyAdapter(
        stage_name="storyboard",
        output_kind="storyboard",
        invoke_fn=good_invoker,
    )

    result = adapter.run(prod["id"], {"production_id": prod["id"]}, db_path=db_path)
    assert result["status"] == "saved"


def test_gate_stages_exempt_from_committed_output(fresh_db):
    """Gate/approval stages (requires_committed_output=False) don't need
    committed output — they just record an approval decision."""
    prod, db_path = fresh_db

    # gate_a_content has requires_committed_output=False
    gate_def = STAGE_REGISTRY["gate_a_content"]
    assert gate_def.requires_committed_output is False

    def gate_invoker(inputs, tmp_path):
        return {"status": "pass", "approval_id": "app_1"}

    adapter = LegacyAdapter(
        stage_name="gate_a_content",
        output_kind="gate_a_content_approval",
        invoke_fn=gate_invoker,
    )

    # Should succeed without committed output (gate doesn't produce a document)
    result = adapter.run(prod["id"], {"production_id": prod["id"]}, db_path=db_path)
    assert result["status"] == "pass"
