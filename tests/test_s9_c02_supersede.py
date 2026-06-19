"""S9-C02 — D-015: re-running compile (plan_render_units) after invalidation must
supersede the prior render-unit set, not append a duplicate one.

Defect: compile_render_plan -> plan_render_units appended a fresh unit set (status='ordered')
on every call WITHOUT staling the prior set. So re-compiling after an upstream invalidation
left TWO active sets: generate (filter status='ordered') saw 2x units (duplicate paid jobs),
and assembly (build_assembly_inputs, no status filter) saw a 2x timeline (clips=90s vs 45s).

Fix: plan_render_units marks the production's prior non-stale units 'stale' in the SAME
transaction (render units are immutable history, never deleted) and threads
parent_render_unit_id for traceability; build_assembly_inputs excludes 'stale'. Render units
keep the existing 'stale' status convention used by invalidate_render_units.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact,
    link_artifact_to_render_unit, get_render_units,
)
from media_service import run_render_unit_qa
from assemble_db import build_assembly_inputs


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "s9c02.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("s9c02_test", db_path=db)


_HERO = {"asset_type": "lipsync_video", "audio_policy": "HERO_SYNC_LOCKED",
         "final_audio_source": "master_narration", "provider_audio_usage": "diagnostic_only",
         "model": "seedance_2_0"}


def _hero_specs(spans):
    return [{"span_id": s["id"], **_HERO} for s in spans]


def _make_valid(prod_id, unit, db, tmp_path):
    """Register an artifact, link it, and QA-pass the unit -> status 'valid'."""
    f = tmp_path / f"{unit['id']}.mp4"
    f.write_bytes(b"fake video " * 100)
    art = register_artifact(prod_id, f, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)
    run_render_unit_qa(prod_id, unit["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True,
        "audio_policy_ok": True,
    }, db_path=db)


def test_replan_supersedes_prior_units(db, prod):
    """REPRODUCES D-015: re-planning must stale the prior set, leaving exactly one active set."""
    spans = commit_timeline_spans(
        prod["id"],
        [{"label": f"B{i:03d}", "start_ms": i * 5000, "end_ms": (i + 1) * 5000} for i in range(4)],
        db_path=db,
    )
    specs = _hero_specs(spans)
    plan_render_units(prod["id"], specs, db_path=db)          # first plan: 4 'ordered'
    plan_render_units(prod["id"], specs, db_path=db)          # re-plan (the D-015 scenario)

    stale = get_render_units(prod["id"], status="stale", db_path=db)
    ordered = get_render_units(prod["id"], status="ordered", db_path=db)
    assert len(stale) == 4, f"prior units must be staled, got {len(stale)}"
    assert len(ordered) == 4, f"only the new set must be active, got {len(ordered)}"
    # generate's filter (status IN ordered,change_requested) must not see duplicates
    active = [u for u in get_render_units(prod["id"], db_path=db)
              if u["status"] in ("ordered", "change_requested")]
    assert len(active) == 4


def test_replan_threads_parent_render_unit_id(db, prod):
    """New units record the superseded unit (same span) as parent for audit traceability."""
    spans = commit_timeline_spans(prod["id"], [{"label": "B000", "start_ms": 0, "end_ms": 5000}], db_path=db)
    spec = [{**_HERO, "span_id": spans[0]["id"]}]
    first = plan_render_units(prod["id"], spec, db_path=db)
    plan_render_units(prod["id"], spec, db_path=db)
    new = get_render_units(prod["id"], status="ordered", db_path=db)
    assert len(new) == 1
    assert new[0]["parent_render_unit_id"] == first[0]["id"]


def test_build_assembly_inputs_excludes_stale(db, prod, tmp_path):
    """Assembly must see only the CURRENT plan's valid unit, not the staled duplicate."""
    spans = commit_timeline_spans(prod["id"], [{"label": "B000", "start_ms": 0, "end_ms": 4000}], db_path=db)
    spec = [{**_HERO, "span_id": spans[0]["id"]}]
    u1 = plan_render_units(prod["id"], spec, db_path=db)[0]
    _make_valid(prod["id"], u1, db, tmp_path)                 # first unit valid + artifact

    u2 = plan_render_units(prod["id"], spec, db_path=db)[0]    # re-plan: u1 staled, u2 created
    _make_valid(prod["id"], u2, db, tmp_path)                  # second unit valid + artifact

    inputs = build_assembly_inputs(prod["id"], db_path=db)
    assert inputs["unit_count"] == 1, f"assembly saw staled duplicate: {inputs['unit_count']}"
    assert inputs["clips"][0]["clip_id"] == u2["id"]           # the current (non-stale) unit


def test_first_plan_is_a_noop_on_supersession(db, prod):
    """A fresh plan (no prior units) must not error and must produce exactly N active units."""
    spans = commit_timeline_spans(prod["id"], [{"label": "B000", "start_ms": 0, "end_ms": 5000}], db_path=db)
    units = plan_render_units(prod["id"], _hero_specs(spans), db_path=db)
    assert len(units) == 1
    assert get_render_units(prod["id"], status="stale", db_path=db) == []


def test_graphics_compositing_excludes_stale(db, prod):
    """invoke_graphics_compositing must filter out stale units (F-001 fix)."""
    # Create graphics units (asset_type='still_kenburns')
    spans = commit_timeline_spans(
        prod["id"],
        [{"label": f"G{i:03d}", "start_ms": i * 5000, "end_ms": (i + 1) * 5000} for i in range(3)],
        db_path=db,
    )
    graphics_specs = [
        {"span_id": s["id"], "asset_type": "still_kenburns",
         "audio_policy": "SILENT_GRAPHIC", "final_audio_source": "none",
         "provider_audio_usage": "discarded", "model": "image_gen_default"}
        for s in spans
    ]
    # First plan: 3 graphics units
    plan_render_units(prod["id"], graphics_specs, db_path=db)

    # Re-plan (the D-015 scenario): prior 3 units should be staled
    plan_render_units(prod["id"], graphics_specs, db_path=db)

    stale = get_render_units(prod["id"], status="stale", db_path=db)
    active = get_render_units(prod["id"], status="ordered", db_path=db)
    assert len(stale) == 3, f"prior graphics units must be staled, got {len(stale)}"
    assert len(active) == 3, f"only new graphics units must be active, got {len(active)}"

    # Verify invoke_graphics_compositing excludes stale units
    conn = _db.connect(db)
    graphics_units = conn.execute(
        """SELECT id, label, asset_type, active_artifact_id
           FROM render_units
           WHERE production_id=? AND asset_type='still_kenburns' AND status!='stale'
           ORDER BY ordinal""",
        (prod["id"],)
    ).fetchall()
    conn.close()

    # Should only see the 3 active units, not 6 (3 stale + 3 active)
    assert len(graphics_units) == 3, f"invoke_graphics_compositing must exclude stale, got {len(graphics_units)}"
