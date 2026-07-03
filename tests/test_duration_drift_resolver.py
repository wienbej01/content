"""Tests for scripts/duration_drift.py — S22_T018 duration drift resolver."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from duration_drift import (
    DriftInput,
    DriftResolution,
    resolve_drift,
    resolve_batch,
    resolution_manifest_entry,
    DurationDriftError,
    ALLOWED_DRIFT_POLICIES,
    DURATION_MATCH_TOLERANCE_SEC,
    HERO_LIPSYNC_MAX_DRIFT_SEC,
)


def _ri(**overrides) -> DriftInput:
    defaults = {
        "render_unit_id": "ru_001",
        "production_id": "prod_001",
        "artifact_id": "art_001",
        "shot_id": "shot_001",
        "required_duration_ms": 4200,
        "actual_duration_ms": 4200,
        "min_usable_duration_ms": 3000,
        "max_usable_duration_ms": 8000,
        "duration_drift_policy": "trim_ok",
        "asset_type": "generated_video",
        "audio_policy": "generated_tts",
        "is_hero_lipsync": False,
    }
    defaults.update(overrides)
    return DriftInput(**defaults)


# ---- Test 1: B-roll trim_ok with excess actual duration ----
def test_planned_42_actual_51_broll_trim_ok():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=5100,
        duration_drift_policy="trim_ok",
        asset_type="generated_video",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"
    assert result.assembly_action == "trim"
    assert result.assembly_metadata.get("trim_duration_sec") == pytest.approx(0.9, abs=0.01)
    assert result.assembly_metadata.get("trim_from_end") is True
    assert result.planned_duration_sec == pytest.approx(4.2)
    assert result.actual_duration_sec == pytest.approx(5.1)
    assert result.delta_sec == pytest.approx(0.9)


# ---- Test 2: Local graphic extend_still_ok with short actual duration ----
def test_planned_42_actual_39_local_graphic_extend_still_ok():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=3900,
        duration_drift_policy="extend_still_ok",
        asset_type="local_graphic",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"
    assert result.assembly_action == "extend"
    assert result.assembly_metadata.get("extend_duration_sec") == pytest.approx(0.3, abs=0.01)
    assert result.assembly_metadata.get("extension_type") == "freeze_frame"


# ---- Test 3: Hero lipsync with significant drift → blocked ----
def test_planned_42_actual_32_hero_lipsync_blocked():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=3200,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="regenerate_required",
        asset_type="lipsync_video",
        audio_policy="HERO_SYNC_LOCKED",
        is_hero_lipsync=True,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "regenerate_same_prompt"
    assert "BLOCKED_DURATION_DRIFT" in result.reason
    assert "hero lipsync" in result.reason.lower()
    assert "unfixable" not in result.resolution


# ---- Test 4: Actual exceeds max_usable_duration_sec → blocking ----
def test_actual_exceeds_max_usable_duration():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=9000,
        max_usable_duration_ms=8000,
        duration_drift_policy="trim_ok",
        asset_type="generated_video",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "exceeds" in result.reason.lower()
    assert "max_usable" in result.reason.lower()


# ---- Test 5: Actual below min_usable_duration_sec → blocking unless policy allows extension ----
def test_actual_below_min_usable_duration_no_extension_policy():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=2500,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="regenerate_required",
        asset_type="generated_video",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "below" in result.reason.lower()
    assert "min_usable" in result.reason.lower()


def test_actual_below_min_usable_with_extension_allowed():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=2500,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="extend_still_ok",
        asset_type="local_graphic",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"
    assert result.assembly_action == "extend"


# ---- Test 6: Missing actual duration → BLOCKED ----
def test_missing_actual_duration():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=None,
        duration_drift_policy="trim_ok",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "BLOCKED_DURATION_DRIFT_UNRESOLVED" in result.reason
    assert "missing" in result.reason.lower()


# ---- Test 7: Unknown policy → block ----
def test_unknown_policy():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=5100,
        duration_drift_policy="bogus_policy",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "unknown" in result.reason.lower() or "BLOCKED" in result.reason


def test_missing_policy():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=5100,
        duration_drift_policy=None,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "BLOCKED_DURATION_DRIFT_UNRESOLVED" in result.reason


# ---- Test 8: Accepted trim decision available to assembly manifest ----
def test_trim_decision_available_to_assembly_manifest():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=5100,
        duration_drift_policy="trim_ok",
        asset_type="generated_video",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)

    manifest_entry = resolution_manifest_entry(result, segment_id="seg_001")

    assert "drift_resolution" in manifest_entry
    assert manifest_entry["drift_resolution"] == "accepted"
    assert "trim" in manifest_entry
    trim = manifest_entry["trim"]
    assert trim["action"] == "trim_from_end"
    assert trim["trim_duration_sec"] == pytest.approx(0.9, abs=0.01)
    assert trim["planned_duration_sec"] == pytest.approx(4.2)
    assert trim["actual_duration_sec"] == pytest.approx(5.1)


# ---- Additional edge case tests ----

def test_duration_within_tolerance_accepted():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=4250,
        duration_drift_policy="trim_ok",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"
    assert result.assembly_action is None


def test_regenerate_required_policy_short():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=3500,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="regenerate_required",
        asset_type="generated_video",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, create_change_requests=False)
    assert result.resolution == "regenerate_same_prompt"


def test_sonnet_repair_required_policy():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=5100,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="sonnet_repair_required",
        asset_type="generated_video",
    )
    result = resolve_drift(inp, create_change_requests=False)
    assert result.resolution == "sonnet_repair_storyboard"


def test_human_review_required_policy():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=3500,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="human_review_required",
        asset_type="generated_video",
    )
    result = resolve_drift(inp, create_change_requests=False)
    assert result.resolution == "human_review_required"


def test_pad_ok_policy_short():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=3900,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="pad_ok",
        asset_type="generated_video",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"
    assert result.assembly_action == "extend"
    assert result.assembly_metadata.get("extension_type") == "pad"


def test_extend_manifest_entry():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=3900,
        duration_drift_policy="extend_still_ok",
    )
    result = resolve_drift(inp, create_change_requests=False)
    entry = resolution_manifest_entry(result)

    assert "extend" in entry
    ext = entry["extend"]
    assert ext["action"] == "freeze_last_frame"
    assert ext["extend_duration_sec"] == pytest.approx(0.3, abs=0.01)


def test_resolve_batch():
    inputs = [
        _ri(render_unit_id="ru_a", required_duration_ms=4200, actual_duration_ms=4200),
        _ri(render_unit_id="ru_b", required_duration_ms=4200, actual_duration_ms=5100,
            duration_drift_policy="trim_ok"),
    ]
    results = resolve_batch(inputs, create_change_requests=False)

    assert len(results) == 2
    assert results[0].resolution == "accepted"
    assert results[1].resolution == "accepted"
    assert results[1].assembly_action == "trim"


def test_missing_required_duration():
    inp = _ri(
        required_duration_ms=None,
        actual_duration_ms=4200,
        duration_drift_policy="trim_ok",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "BLOCKED_DURATION_DRIFT_UNRESOLVED" in result.reason


def test_hero_lipsync_within_tolerance():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=4250,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="regenerate_required",
        is_hero_lipsync=True,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"


def test_hero_lipsync_slight_drift_still_blocks():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=4400,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="regenerate_required",
        is_hero_lipsync=True,
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "regenerate_same_prompt"
    assert "BLOCKED_DURATION_DRIFT" in result.reason
    assert "hero lipsync" in result.reason.lower()


def test_resolution_to_dict():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=5100,
        duration_drift_policy="trim_ok",
    )
    result = resolve_drift(inp, create_change_requests=False)
    d = result.to_dict()

    assert d["resolution"] == "accepted"
    assert "assembly_metadata" in d
    assert "input_snapshot" in d
    assert d["delta_sec"] == pytest.approx(0.9)


def test_drift_input_to_dict():
    inp = _ri(required_duration_ms=4200, actual_duration_ms=5100)
    d = inp.to_dict()

    assert d["required_duration_ms"] == 4200
    assert d["actual_duration_ms"] == 5100
    assert d["is_hero_lipsync"] is False


def test_max_usable_exceeded_even_with_trim_policy():
    inp = _ri(
        required_duration_ms=4200,
        actual_duration_ms=9000,
        max_usable_duration_ms=5000,
        duration_drift_policy="trim_ok",
        asset_type="generated_video",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "reject_unfixable"
    assert "exceeds" in result.reason.lower()


def test_extension_allowed_below_min_usable_with_pad_policy():
    inp = _ri(
        required_duration_ms=6000,
        actual_duration_ms=2500,
        min_usable_duration_ms=3000,
        max_usable_duration_ms=8000,
        duration_drift_policy="pad_ok",
        asset_type="generated_video",
    )
    result = resolve_drift(inp, create_change_requests=False)

    assert result.resolution == "accepted"
    assert result.assembly_action == "extend"


# ---- DB integration tests ----

@pytest.fixture
def test_db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def test_production(test_db):
    return _db.ensure_production("drift_test", db_path=test_db)


def _make_render_unit(prod_id, db_path):
    from production_repo import commit_timeline_spans, plan_render_units
    spans = commit_timeline_spans(
        prod_id, [{"label": "B001", "start_ms": 0, "end_ms": 5000}], db_path=db_path
    )
    return plan_render_units(prod_id, [{
        "span_id": spans[0]["id"],
        "asset_type": "generated_video",
        "audio_policy": "VIDEO_ONLY_OVER_CANONICAL_NARRATION",
        "final_audio_source": "master_narration",
        "render_mode": "generated_video",
        "visual_function": "demonstrate",
        "narrative_claim": "test claim",
        "information_to_show": "test visual",
        "viewer_takeaway": "test takeaway",
        "required_action": "test action",
        "distinctness_requirement": "test distinctness",
        "semantic_acceptance_criteria": "test criteria",
        "concept_key": "test_drift_001",
    }], db_path=db_path)[0]


def test_blocking_drift_creates_change_request(test_db, test_production):
    ru = _make_render_unit(test_production["id"], test_db)

    inp = _ri(
        render_unit_id=ru["id"],
        production_id=test_production["id"],
        required_duration_ms=4200,
        actual_duration_ms=9000,
        max_usable_duration_ms=5000,
        duration_drift_policy="trim_ok",
        is_hero_lipsync=False,
    )
    result = resolve_drift(inp, db_path=test_db, create_change_requests=True)

    assert result.resolution == "reject_unfixable"
    assert result.change_request_id is not None
    assert result.change_request_id.startswith("cr_")
    assert result.validation_id is not None
    assert result.validation_id.startswith("val_")

    conn = _db.connect(test_db)
    cr = conn.execute(
        "SELECT * FROM change_requests WHERE id=?", (result.change_request_id,)
    ).fetchone()
    conn.close()
    assert cr is not None
    assert cr["status"] == "open"
    assert cr["change_type"] == "duration_drift_blocked"
    assert cr["subject_type"] == "render_unit"
    assert cr["subject_id"] == ru["id"]


def test_hero_lipsync_block_creates_change_request(test_db, test_production):
    ru = _make_render_unit(test_production["id"], test_db)

    inp = _ri(
        render_unit_id=ru["id"],
        production_id=test_production["id"],
        required_duration_ms=4200,
        actual_duration_ms=3500,
        duration_drift_policy="regenerate_required",
        is_hero_lipsync=True,
    )
    result = resolve_drift(inp, db_path=test_db, create_change_requests=True)

    assert result.resolution == "regenerate_same_prompt"
    assert result.change_request_id is not None

    conn = _db.connect(test_db)
    cr = conn.execute(
        "SELECT * FROM change_requests WHERE id=?", (result.change_request_id,)
    ).fetchone()
    conn.close()
    assert cr["status"] == "open"


def test_no_change_request_when_accept_tolerated(test_db, test_production):
    ru = _make_render_unit(test_production["id"], test_db)

    inp = _ri(
        render_unit_id=ru["id"],
        production_id=test_production["id"],
        required_duration_ms=4200,
        actual_duration_ms=4200,
        duration_drift_policy="trim_ok",
    )
    result = resolve_drift(inp, db_path=test_db, create_change_requests=True)

    assert result.resolution == "accepted"
    assert result.change_request_id is None
