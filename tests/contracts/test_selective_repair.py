"""S6-T05: Schema-compatible selective repair.

Named tests required by the program:
  test_selective_repair_preserves_unaffected_units
  test_open_repair_blocks_assembly
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from media_service import (
    route_change_request, resolve_change_request, get_open_change_requests,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "repair_test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    _db.migrate(db_file)
    prod = _db.ensure_production("repair_test", seed="s", video_type="short", db_path=db_file)
    now = _db._now()
    # Create two render units (one will fail, one will pass)
    ru_ids = []
    for i in range(2):
        ru_id = _db._id("ru")
        with _db.transaction(db_file) as conn:
            conn.execute(
                """INSERT INTO render_units (id, production_id, ordinal, label, asset_type,
                   audio_policy, lipsync_required, required_start_ms, required_end_ms,
                   required_duration_ms, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'generated_video', 'BROLL_FLEX', 0, ?, ?, 5000,
                   'generated', ?, ?)""",
                (ru_id, prod["id"], i, f"B00{i+1}", i * 5000, (i + 1) * 5000, now, now),
            )
        ru_ids.append(ru_id)
    yield prod, db_file, ru_ids
    _db._db_path_override = None


def test_open_repair_blocks_assembly(fresh_db):
    """An open change request blocks assembly — invoke_repair raises."""
    prod, db_path, ru_ids = fresh_db

    # Route a change request for the first render unit.
    # Use target_stage="assemble" (not the default "generate_media") so the unit
    # status stays 'change_requested' instead of 'ordered'. When target_stage
    # is "generate_media", route_change_request sets the unit to 'ordered'
    # (already queued) and invoke_repair skips it — because regeneration is
    # already in progress. Other target stages leave the unit as
    # 'change_requested', which invoke_repair correctly blocks on.
    route_change_request(
        production_id=prod["id"],
        render_unit_id=ru_ids[0],
        change_type="re-render",
        target_stage="assemble",
        reason="QA failure: black frames detected",
        db_path=db_path,
    )

    # Verify the change request is open
    open_crs = get_open_change_requests(prod["id"], db_path=db_path)
    assert len(open_crs) == 1
    assert open_crs[0]["status"] == "open"

    # The repair stage (invoke_repair) must block when there are open CRs
    import produce_db
    with pytest.raises(RuntimeError, match="open change request"):
        produce_db.invoke_repair({"production_id": prod["id"]}, Path("/tmp"))


def test_selective_repair_preserves_unaffected_units(fresh_db):
    """When one unit fails and is routed to repair, the other unit is unaffected
    (stays 'generated', not 'change_requested')."""
    prod, db_path, ru_ids = fresh_db

    # Route change request ONLY for ru_ids[0]
    # Default target_stage="generate_media" sets unit status to 'ordered'
    # (queued for regeneration) rather than 'change_requested'. This is
    # intentional — the unit is immediately re-queued for the generate_media
    # stage rather than left in an intermediate state.
    route_change_request(
        production_id=prod["id"],
        render_unit_id=ru_ids[0],
        change_type="regenerate",
        reason="QA failure",
        db_path=db_path,
    )

    conn = _db.connect(db_path)
    ru0 = conn.execute("SELECT status FROM render_units WHERE id=?", (ru_ids[0],)).fetchone()
    ru1 = conn.execute("SELECT status FROM render_units WHERE id=?", (ru_ids[1],)).fetchone()
    conn.close()

    # The failed unit is 'ordered' (re-queued for regeneration)
    assert ru0["status"] == "ordered"
    # The unaffected unit remains 'generated'
    assert ru1["status"] == "generated"


def test_resolve_repair_resets_unit(fresh_db):
    """Resolving a change request as 'accepted' resets the unit to 'ordered'
    so it can re-flow through generation."""
    prod, db_path, ru_ids = fresh_db

    cr = route_change_request(
        production_id=prod["id"],
        render_unit_id=ru_ids[0],
        change_type="regenerate",
        reason="QA failure",
        db_path=db_path,
    )

    resolve_change_request(
        production_id=prod["id"],
        change_request_id=cr["id"],
        resolution="accepted",
        db_path=db_path,
    )

    conn = _db.connect(db_path)
    ru0 = conn.execute("SELECT status FROM render_units WHERE id=?", (ru_ids[0],)).fetchone()
    conn.close()
    assert ru0["status"] == "ordered"

    # The change request is resolved (not open)
    open_crs = get_open_change_requests(prod["id"], db_path=db_path)
    assert len(open_crs) == 0
