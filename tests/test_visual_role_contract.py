"""S15-T002: Visual role contract tests.

visual_role is the editorial FUNCTION of a shot (why it is on screen), kept
separate from the technical asset_type and the audio/sync audio_policy. It is
sourced from the creative_beat and propagated onto the render_unit through the
timeline span (DB-native planning), and is required on every render_unit of a
publish-grade production at the assembly gate.

These tests build real contract-compliant publish-grade batches (opening hero,
>=2 hero/lipsync units with SyncNet + compensated artifacts, >=1 b-roll, >=1
graphic, no consecutive heroes) so that shot-mix validation PASSES and the
visual_role gate is actually reached — missing/invalid visual_role must fail
for a visual_role-specific reason, never be masked by BLOCKED_SHOT_MIX_CONTRACT.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact, link_artifact_to_render_unit,
)
from media_service import run_render_unit_qa
from authoring_service import save_storyboard, get_creative_beats
from assemble_db import (
    validate_assembly_inputs, AssemblyError, validate_visual_roles, ALLOWED_VISUAL_ROLES,
)
from shot_mix_contract import get_contract
from visual_role_fixtures import seed_visual_roles, seed_semantic_role_qa


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    # Default video_type=None -> resolves to the publish-grade short_educational contract.
    return _db.ensure_production("s15_visual_role_test", db_path=db)


# ---------------------------------------------------------------------------
# Contract-compliant publish-grade batch helper (H001 -> B001 -> H002 -> G001)
# ---------------------------------------------------------------------------

def _make_publish_batch(prod_id, db, tmp_path, *, seed_roles=True):
    """Build a contract-compliant publish-grade batch.

    Structure: H001 (hero), B001 (b-roll), H002 (hero), G001 (graphic).
    Heroes carry per-segment SyncNet + compensated artifacts; every unit has an
    artifact and passing QA. When ``seed_roles`` is True, creative_beats carry a
    valid visual_role that propagates onto every render_unit.

    Returns the list of render-unit dicts in ordinal order.
    """
    # (label, asset_type, audio_policy, add_syncnet)
    specs = [
        ("H001", "lipsync_video", "HERO_SYNC_LOCKED", True),
        ("B001", "generated_video", "BROLL_FLEX", False),
        ("H002", "lipsync_video", "HERO_SYNC_LOCKED", True),
        ("G001", "local_graphic", "SILENT_GRAPHIC", False),
    ]

    span_data_list = []
    unit_specs_list = []
    for i, (label, asset_type, audio_policy, add_syncnet) in enumerate(specs):
        start_ms, end_ms = i * 4000, (i + 1) * 4000
        span_data_list.append({"label": label, "start_ms": start_ms, "end_ms": end_ms})

        unit_data = {
            "asset_type": asset_type,
            "audio_policy": audio_policy,
            "final_audio_source": "none" if audio_policy == "SILENT_GRAPHIC" else "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "_add_syncnet": add_syncnet,
        }
        if audio_policy not in ("SILENT_GRAPHIC",):
            unit_data["model"] = "seedance_2_0"
        # S07/R7: B-roll semantic contract requires these fields
        if audio_policy in ("BROLL_FLEX", "BROLL_SYNCED_ACTION"):
            unit_data.update({
                "visual_function": "demonstrate",
                "narrative_claim": "test claim",
                "information_to_show": "test info",
                "viewer_takeaway": "test takeaway",
                "required_action": "test action",
                "distinctness_requirement": "test distinctness",
                "semantic_acceptance_criteria": "test criteria",
                "concept_key": "test_concept",
            })
        unit_specs_list.append(unit_data)

    if seed_roles:
        seed_visual_roles(prod_id, db, span_data_list, unit_specs_list)

    spans = commit_timeline_spans(prod_id, span_data_list, db_path=db)

    add_syncnet_flags = []
    all_unit_data = []
    for span, unit_data in zip(spans, unit_specs_list):
        add_syncnet_flags.append(unit_data.pop("_add_syncnet"))
        unit_data["span_id"] = span["id"]
        all_unit_data.append(unit_data)

    units = plan_render_units(prod_id, all_unit_data, db_path=db)

    # Artifact + QA for every unit (incl. local_graphic).
    for unit in units:
        f = tmp_path / f"{unit['id']}.mp4"
        f.write_bytes(b"fake video " * 100)
        art = register_artifact(prod_id, f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)
        run_render_unit_qa(prod_id, unit["id"], {
            "file_exists": True, "dimensions_ok": True,
            "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

    # Mark valid + hero SyncNet/compensated in one committed transaction.
    with _db.transaction(db) as conn:
        for unit, add_syncnet in zip(units, add_syncnet_flags):
            conn.execute("UPDATE render_units SET status='valid' WHERE id=?", (unit["id"],))
            audio_policy = unit.get("audio_policy", "")
            if add_syncnet and audio_policy in ("HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"):
                comp = tmp_path / f"{unit['id']}_comp.mp4"
                comp.write_bytes(b"compensated video " * 100)
                conn.execute(
                    """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation,
                       external_job_id, idempotency_key, status, submitted_at, completed_at)
                       VALUES (?, ?, ?, 'higgsfield', 'generate_video', 'ext_job', ?, 'completed',
                       datetime('now'), datetime('now'))""",
                    (f"pj_{unit['id']}", prod_id, unit["id"], f"idemp_{unit['id']}_{uuid.uuid4().hex[:8]}"),
                )
                conn.execute(
                    "UPDATE provider_jobs SET compensated_artifact_path=? WHERE id=?",
                    (str(comp), f"pj_{unit['id']}"),
                )
                conn.execute(
                    """INSERT INTO validations (id, production_id, subject_type, subject_id,
                       validator_name, status, evidence_json, created_at)
                       VALUES (?, ?, ?, ?, 'syncnet_offset', 'pass', ?, datetime('now'))""",
                    (f"val_syncnet_{unit['id']}_{uuid.uuid4().hex[:8]}",
                     prod_id, "render_unit", unit["id"],
                     json.dumps({"offset_ms": 20.0, "confidence": 2.5})),
                )

    # S15-T003: seed passing post-render semantic-role QA evidence for every unit
    # from its current DB visual_role so publish-grade batches satisfy the
    # semantic-role gate (units with no role are skipped).
    seed_semantic_role_qa(prod_id, db, units)

    return units


def _unit_visual_role(db, unit_id, role):
    """Set (or clear when role is None) a render_unit's visual_role directly."""
    with _db.transaction(db) as conn:
        conn.execute("UPDATE render_units SET visual_role=? WHERE id=?", (role, unit_id))


# ---------------------------------------------------------------------------
# 1. Valid publish-grade H->B->H->G batch with valid visual_role passes
# ---------------------------------------------------------------------------

def test_publish_grade_batch_with_visual_roles_passes(prod, db, tmp_path):
    """A contract-compliant publish-grade batch carrying valid visual_roles passes."""
    units = _make_publish_batch(prod["id"], db, tmp_path, seed_roles=True)

    # Every unit received a propagated visual_role.
    assert all(u["visual_role"] for u in units)
    assert {u["visual_role"] for u in units} <= ALLOWED_VISUAL_ROLES

    result = validate_assembly_inputs(prod["id"], db_path=db)
    assert result["validation_passed"] is True
    assert result["visual_role_publish_grade"] is True


# ---------------------------------------------------------------------------
# 2. Missing visual_role fails with a visual_role-specific error (not shot-mix)
# ---------------------------------------------------------------------------

def test_missing_visual_role_fails_visual_role_error(prod, db, tmp_path):
    """One publish-grade unit missing visual_role fails BLOCKED_VISUAL_ROLE_MISSING,
    not BLOCKED_SHOT_MIX_CONTRACT (shot-mix structure is still valid)."""
    units = _make_publish_batch(prod["id"], db, tmp_path, seed_roles=True)
    hero = next(u for u in units if u["label"] == "H002")
    _unit_visual_role(db, hero["id"], None)

    with pytest.raises(AssemblyError) as exc_info:
        validate_assembly_inputs(prod["id"], db_path=db)

    msg = str(exc_info.value)
    assert "BLOCKED_VISUAL_ROLE_MISSING" in msg
    assert hero["id"] in msg
    # Must NOT be masked by the shot-mix gate (which runs first).
    assert "BLOCKED_SHOT_MIX_CONTRACT" not in msg


# ---------------------------------------------------------------------------
# 3. Invalid visual_role fails with a visual_role-specific error (not shot-mix)
# ---------------------------------------------------------------------------

def test_invalid_visual_role_fails_visual_role_error(prod, db, tmp_path):
    """A unit with an out-of-enum visual_role fails BLOCKED_VISUAL_ROLE_INVALID,
    not BLOCKED_SHOT_MIX_CONTRACT."""
    units = _make_publish_batch(prod["id"], db, tmp_path, seed_roles=True)
    graphic = next(u for u in units if u["label"] == "G001")
    _unit_visual_role(db, graphic["id"], "definitely_not_a_real_role")

    with pytest.raises(AssemblyError) as exc_info:
        validate_assembly_inputs(prod["id"], db_path=db)

    msg = str(exc_info.value)
    assert "BLOCKED_VISUAL_ROLE_INVALID" in msg
    assert "definitely_not_a_real_role" in msg
    assert "BLOCKED_SHOT_MIX_CONTRACT" not in msg


# ---------------------------------------------------------------------------
# 4. visual_role propagates creative_beats -> timeline spans -> render_units
# ---------------------------------------------------------------------------

def test_visual_role_propagates_beat_to_unit(prod, db):
    """visual_role on a creative_beat propagates through the span to the unit."""
    save_storyboard(prod["id"], {"beats": [{
        "label": "B001", "shot_type": "hero_lipsync", "visual_role": "hero_hook",
        "narration_text": "Hook line.",
    }]}, stage_run_id=None, db_path=db)
    beat_id = get_creative_beats(prod["id"], db_path=db)[0]["id"]

    span = commit_timeline_spans(prod["id"], [{
        "label": "S001", "start_ms": 0, "end_ms": 4000, "creative_beat_id": beat_id,
    }], db_path=db)[0]
    plan_render_units(prod["id"], [{
        "span_id": span["id"], "asset_type": "lipsync_video",
        "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0",
    }], db_path=db)

    conn = _db.connect(db)
    row = conn.execute(
        "SELECT visual_role FROM render_units WHERE production_id=?", (prod["id"],)
    ).fetchone()
    conn.close()
    assert row["visual_role"] == "hero_hook"


# ---------------------------------------------------------------------------
# 5. visual_role is NOT inferred from label text
# ---------------------------------------------------------------------------

def test_visual_role_not_inferred_from_label(prod, db):
    """The unit's visual_role is the explicit creative_beat value, not derived
    from the unit/beat label (a label that reads like a hero still yields the
    beat's declared b-roll role)."""
    save_storyboard(prod["id"], {"beats": [{
        "label": "HERO_OPENING",            # label suggests hero...
        "shot_type": "broll",
        "visual_role": "broll_metaphor",    # ...but the editorial role is b-roll
        "narration_text": "Metaphor beat.",
    }]}, stage_run_id=None, db_path=db)
    beat_id = get_creative_beats(prod["id"], db_path=db)[0]["id"]

    span = commit_timeline_spans(prod["id"], [{
        "label": "HERO_OPENING", "start_ms": 0, "end_ms": 4000, "creative_beat_id": beat_id,
    }], db_path=db)[0]
    plan_render_units(prod["id"], [{
        "span_id": span["id"], "asset_type": "generated_video",
        "audio_policy": "BROLL_FLEX", "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "visual_function": "demonstrate", "narrative_claim": "c",
        "information_to_show": "i", "viewer_takeaway": "t",
        "required_action": "a", "distinctness_requirement": "d",
        "semantic_acceptance_criteria": "s", "concept_key": "k",
    }], db_path=db)

    conn = _db.connect(db)
    row = conn.execute(
        "SELECT visual_role FROM render_units WHERE production_id=?", (prod["id"],)
    ).fetchone()
    conn.close()
    # The declared editorial role wins; the hero-ish label is ignored.
    assert row["visual_role"] == "broll_metaphor"


# ---------------------------------------------------------------------------
# 6. Non-publish (test_local / diagnostic_legacy) handling is explicit
# ---------------------------------------------------------------------------

def test_non_publish_contracts_marked_not_publish_grade():
    """test_local and diagnostic_legacy contracts are explicitly non-publish."""
    assert get_contract("test_local").publish_grade is False
    assert get_contract("diagnostic_legacy").publish_grade is False
    assert get_contract("short_educational").publish_grade is True


def test_gate_skips_visual_role_for_non_publish():
    """validate_visual_roles is a no-op when publish_grade is False, even if
    every unit is missing visual_role. This is the explicit exemption."""
    units_no_role = [{"id": "u1", "label": "H001"}, {"id": "u2", "label": "B001"}]
    # No raise for non-publish:
    validate_visual_roles(units_no_role, publish_grade=False)
    # Publish-grade still blocks:
    with pytest.raises(AssemblyError, match="BLOCKED_VISUAL_ROLE_MISSING"):
        validate_visual_roles(units_no_role, publish_grade=True)


def test_test_local_production_skips_visual_role_gate(db, tmp_path):
    """A test_local production (video_type='test_local') with a structurally
    valid publish batch but NO visual_role does not fail on visual_role — the
    gate is skipped because the resolved contract is non-publish."""
    test_prod = _db.ensure_production(
        "s15_visual_role_testlocal", video_type="test_local", db_path=db
    )
    _make_publish_batch(test_prod["id"], db, tmp_path, seed_roles=False)

    result = validate_assembly_inputs(test_prod["id"], db_path=db)
    assert result["validation_passed"] is True
    assert result["visual_role_publish_grade"] is False


def test_publish_grade_production_without_roles_blocks(db, tmp_path):
    """Contrast: the same structurally valid batch on a publish-grade
    production (default short_educational) without visual_role IS blocked."""
    pub_prod = _db.ensure_production("s15_visual_role_pubnorole", db_path=db)
    _make_publish_batch(pub_prod["id"], db, tmp_path, seed_roles=False)

    with pytest.raises(AssemblyError) as exc_info:
        validate_assembly_inputs(pub_prod["id"], db_path=db)
    assert "BLOCKED_VISUAL_ROLE_MISSING" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Storage + reference data
# ---------------------------------------------------------------------------

def test_visual_role_saved_to_creative_beats(prod, db):
    """visual_role is persisted on creative_beats at storyboard save."""
    save_storyboard(prod["id"], {"beats": [
        {"label": "B001", "shot_type": "hero_lipsync", "visual_role": "hero_trust",
         "narration_text": "Trust beat."},
        {"label": "B002", "shot_type": "broll", "visual_role": "broll_evidence",
         "narration_text": "Evidence beat."},
        {"label": "B003", "shot_type": "graphic", "visual_role": "graphic_framework",
         "narration_text": "Framework beat."},
    ]}, stage_run_id=None, db_path=db)

    beats = get_creative_beats(prod["id"], db_path=db)
    assert [b["visual_role"] for b in beats] == [
        "hero_trust", "broll_evidence", "graphic_framework",
    ]


def test_visual_role_is_optional_at_save(prod, db):
    """visual_role is OPTIONAL at storyboard save (enforced at the assembly gate,
    not here) so legacy authoring flows keep working."""
    doc = save_storyboard(prod["id"], {"beats": [{
        "label": "B001", "shot_type": "broll", "narration_text": "Legacy beat.",
    }]}, stage_run_id=None, db_path=db)
    assert doc is not None
    beats = get_creative_beats(prod["id"], db_path=db)
    assert len(beats) == 1
    assert beats[0]["visual_role"] is None


def test_visual_roles_enum_table_populated(db):
    """The visual_roles reference table is seeded with the allowed roles."""
    conn = _db.connect(db)
    roles = conn.execute("SELECT role, category FROM visual_roles ORDER BY role").fetchall()
    conn.close()

    expected = [
        ("broll_emotional_reset", "broll"),
        ("broll_evidence", "broll"),
        ("broll_metaphor", "broll"),
        ("graphic_comparison", "graphic"),
        ("graphic_data", "graphic"),
        ("graphic_framework", "graphic"),
        ("graphic_process", "graphic"),
        ("hero_cta", "hero"),
        ("hero_hook", "hero"),
        ("hero_trust", "hero"),
    ]
    assert [(r["role"], r["category"]) for r in roles] == expected
