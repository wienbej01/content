"""S15-T003: Post-render semantic-role QA contract tests.

Goal of the ticket: a rendered unit must not pass publish-grade assembly merely
because its ``asset_type``, label, or PLANNED ``visual_role`` says it is b-roll /
graphic / hero. The RENDERED content must be proven to satisfy the declared
editorial visual_role via post-render semantic-role QA evidence.

This ticket validates the evidence contract and the assembly-gate behaviour using
deterministic evidence (no real frame analysis — that is S15_T004, which will
call ``record_semantic_role_qa`` with real verdicts). The evidence:

* lives in the existing ``validations`` table (no parallel manifest path);
* is bound to the render_unit id (``subject_id``) — evidence on the wrong unit
  never satisfies the unit that needs it;
* records the ``visual_role`` it was evaluated against — the gate rejects
  evidence whose role does not match the unit's CURRENT visual_role;
* is never inferred from label text or ``asset_type``.

Gate ordering is preserved: S13 compensated/audio-island -> S14 SyncNet/lipsync
-> S15_T001 shot-mix -> S15_T002 visual_role -> S15_T003 semantic-role QA. Every
negative test below uses an otherwise-valid H->B->H->G publish-grade fixture so
it reaches the semantic-role QA gate rather than failing at an earlier gate.
"""
from __future__ import annotations

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
from assemble_db import (
    validate_assembly_inputs, AssemblyError, ALLOWED_VISUAL_ROLES,
)
from shot_mix_contract import get_contract
from semantic_role_qa import (
    SEMANTIC_ROLE_QA_VALIDATOR, record_semantic_role_qa,
)
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
    # video_type=None -> resolves to the publish-grade short_educational contract.
    return _db.ensure_production("s15_t003_semantic_role_qa", db_path=db)


# ---------------------------------------------------------------------------
# Contract-compliant publish-grade batch (H001 -> B001 -> H002 -> G001)
# Adapts the proven _make_publish_batch pattern from test_visual_role_contract.
# ---------------------------------------------------------------------------

_SPECS = [
    # (label, asset_type, audio_policy, add_syncnet)
    ("H001", "lipsync_video", "HERO_SYNC_LOCKED", True),
    ("B001", "generated_video", "BROLL_FLEX", False),
    ("H002", "lipsync_video", "HERO_SYNC_LOCKED", True),
    ("G001", "local_graphic", "SILENT_GRAPHIC", False),
]


def _compliant_batch(prod_id, db, tmp_path, *, seed_roles=True, seed_semantic_qa=True):
    """Build an otherwise-valid publish-grade H->B->H->G batch.

    Every unit has an artifact + passing QA; heroes carry per-segment SyncNet +
    compensated artifacts. ``seed_roles`` propagates a valid visual_role onto
    every unit (S15_T002); ``seed_semantic_qa`` records passing post-render
    semantic-role QA evidence per unit (S15_T003). Returns the unit list.
    """
    span_data_list = []
    unit_specs_list = []
    for i, (label, asset_type, audio_policy, add_syncnet) in enumerate(_SPECS):
        start_ms, end_ms = i * 4000, (i + 1) * 4000
        span_data_list.append({"label": label, "start_ms": start_ms, "end_ms": end_ms})
        unit_data = {
            "asset_type": asset_type,
            "audio_policy": audio_policy,
            "final_audio_source": "none" if audio_policy == "SILENT_GRAPHIC" else "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "_add_syncnet": add_syncnet,
        }
        if audio_policy != "SILENT_GRAPHIC":
            unit_data["model"] = "seedance_2_0"
        if audio_policy in ("BROLL_FLEX", "BROLL_SYNCED_ACTION"):
            unit_data.update({
                "visual_function": "demonstrate", "narrative_claim": "test claim",
                "information_to_show": "test info", "viewer_takeaway": "test takeaway",
                "required_action": "test action", "distinctness_requirement": "test distinctness",
                "semantic_acceptance_criteria": "test criteria", "concept_key": "test_concept",
            })
        unit_specs_list.append(unit_data)

    if seed_roles:
        seed_visual_roles(prod_id, db, span_data_list, unit_specs_list)

    spans = commit_timeline_spans(prod_id, span_data_list, db_path=db)

    add_flags = []
    all_unit_data = []
    for span, unit_data in zip(spans, unit_specs_list):
        add_flags.append(unit_data.pop("_add_syncnet"))
        unit_data["span_id"] = span["id"]
        all_unit_data.append(unit_data)
    units = plan_render_units(prod_id, all_unit_data, db_path=db)

    for unit in units:
        f = tmp_path / f"{unit['id']}.mp4"
        f.write_bytes(b"fake video " * 100)
        art = register_artifact(prod_id, f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)
        run_render_unit_qa(prod_id, unit["id"], {
            "file_exists": True, "dimensions_ok": True,
            "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

    with _db.transaction(db) as conn:
        for unit, add_syncnet in zip(units, add_flags):
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
                     '{"offset_ms":20.0,"confidence":2.5}'),
                )

    if seed_semantic_qa:
        seed_semantic_role_qa(prod_id, db, units)

    return units


# ---------------------------------------------------------------------------
# Small DB helpers for negative-test surgery
# ---------------------------------------------------------------------------

def _clear_semantic_qa(db, unit_id):
    """Remove all semantic_role_qa evidence for a unit."""
    with _db.transaction(db) as conn:
        conn.execute(
            "DELETE FROM validations WHERE subject_type='render_unit' AND subject_id=? "
            "AND validator_name=?",
            (unit_id, SEMANTIC_ROLE_QA_VALIDATOR),
        )


def _set_unit_visual_role(db, unit_id, role):
    """Set (or clear when role is None) a render_unit's current visual_role."""
    with _db.transaction(db) as conn:
        conn.execute("UPDATE render_units SET visual_role=? WHERE id=?", (role, unit_id))


def _semantic_qa_rows(db, unit_id):
    conn = _db.connect(db)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT status, evidence_json FROM validations WHERE subject_type='render_unit' "
            "AND subject_id=? AND validator_name=? ORDER BY created_at",
            (unit_id, SEMANTIC_ROLE_QA_VALIDATOR),
        ).fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. Valid publish-grade batch with passing semantic-role QA passes
# ---------------------------------------------------------------------------

class TestSemanticRoleQAGate:
    """End-to-end gate behaviour through validate_assembly_inputs."""

    def test_valid_publish_batch_with_semantic_qa_passes(self, prod, db, tmp_path):
        """A contract-compliant publish-grade batch carrying valid visual_roles
        AND passing semantic-role QA evidence passes the assembly gate."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        # Every unit has a valid role and a passing semantic-role QA row bound to it.
        assert all(u["visual_role"] for u in units)
        assert {u["visual_role"] for u in units} <= ALLOWED_VISUAL_ROLES
        for u in units:
            rows = _semantic_qa_rows(db, u["id"])
            assert rows, f"unit {u['id']} missing semantic-role QA evidence"
            assert rows[-1]["status"] == "pass"

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result["validation_passed"] is True
        assert result["semantic_role_qa_publish_grade"] is True

    # -----------------------------------------------------------------
    # 2. Missing semantic-role QA -> BLOCKED_SEMANTIC_ROLE_QA_MISSING
    # -----------------------------------------------------------------

    def test_missing_semantic_qa_fails_semantic_error(self, prod, db, tmp_path):
        """A publish-grade unit with visual_role but NO semantic-role QA evidence
        fails BLOCKED_SEMANTIC_ROLE_QA_MISSING — never masked by shot-mix or
        visual_role (the batch is otherwise valid)."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "B001")
        # All other units keep their passing QA; only the target lacks evidence.
        _clear_semantic_qa(db, target["id"])

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" in msg
        assert target["id"] in msg
        # Must NOT be masked by an earlier gate.
        assert "BLOCKED_SHOT_MIX_CONTRACT" not in msg
        assert "BLOCKED_VISUAL_ROLE" not in msg

    # -----------------------------------------------------------------
    # 3. Failed semantic-role QA -> BLOCKED_SEMANTIC_ROLE_QA_FAILED
    # -----------------------------------------------------------------

    def test_failed_semantic_qa_fails_semantic_error(self, prod, db, tmp_path):
        """A failing semantic-role QA verdict (e.g. b-roll showing a talking head)
        fails BLOCKED_SEMANTIC_ROLE_QA_FAILED, carrying its reason."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "B001")
        role = target["visual_role"]
        # Replace target's evidence with a single explicit FAIL verdict.
        _clear_semantic_qa(db, target["id"])
        record_semantic_role_qa(
            prod["id"], target["id"], role, "fail",
            category="broll", reason="b-roll clip shows a talking head, not evidence",
            db_path=db,
        )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_SEMANTIC_ROLE_QA_FAILED" in msg
        assert target["id"] in msg
        assert role in msg
        assert "talking head" in msg
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" not in msg

    # -----------------------------------------------------------------
    # 4. Evidence for the wrong visual_role fails
    # -----------------------------------------------------------------

    def test_evidence_for_wrong_visual_role_fails(self, prod, db, tmp_path):
        """Evidence whose recorded visual_role does not match the unit's CURRENT
        role does not satisfy the gate (stale / mismatched evidence)."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "G001")
        current_role = target["visual_role"]  # graphic_framework
        # Re-record target's evidence against a DIFFERENT role than it currently holds.
        _clear_semantic_qa(db, target["id"])
        record_semantic_role_qa(
            prod["id"], target["id"], "broll_evidence", "pass", db_path=db,
        )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" in msg
        assert target["id"] in msg
        assert current_role in msg  # the gate reports the current role that is unsatisfied
        assert "BLOCKED_VISUAL_ROLE" not in msg

    # -----------------------------------------------------------------
    # 5. Evidence attached to the wrong render_unit fails
    # -----------------------------------------------------------------

    def test_evidence_attached_to_wrong_render_unit_fails(self, prod, db, tmp_path):
        """Evidence bound to a different render_unit id does not satisfy the unit
        that needs it — the gate looks evidence up per subject_id."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "G001")
        other = next(u for u in units if u["label"] == "B001")
        target_role = target["visual_role"]
        # Move target's evidence onto another unit (mis-filed binding).
        _clear_semantic_qa(db, target["id"])
        record_semantic_role_qa(
            prod["id"], other["id"], target_role, "pass", db_path=db,
        )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" in msg
        assert target["id"] in msg
        # The other unit's evidence must not leak to the target.
        assert other["id"] != target["id"]

    # -----------------------------------------------------------------
    # 6. Labels alone do not satisfy semantic-role QA
    # -----------------------------------------------------------------

    def test_labels_alone_do_not_satisfy(self, prod, db, tmp_path):
        """A unit whose label literally names its visual_role still fails without
        QA evidence — the gate never infers satisfaction from label text."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "B001")
        # Strip this unit's QA; keep everyone else's so the gate reaches it.
        _clear_semantic_qa(db, target["id"])
        # Make the label scream the intended role; it must not matter.
        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE render_units SET label=? WHERE id=?",
                ("BROLL_EVIDENCE_DEMONSTRATES_CLAIM", target["id"]),
            )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" in msg
        assert target["id"] in msg
        assert "asset_type" in msg or "label" in msg  # gate explains labels cannot substitute

    # -----------------------------------------------------------------
    # 7. asset_type alone does not satisfy semantic-role QA
    # -----------------------------------------------------------------

    def test_asset_type_alone_does_not_satisfy(self, prod, db, tmp_path):
        """A local_graphic unit with no semantic-role QA still fails — asset_type
        cannot substitute for post-render semantic-role QA."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "G001")
        assert target["asset_type"] == "local_graphic"
        # Strip only this graphic's QA so the gate reaches it (not an earlier unit).
        _clear_semantic_qa(db, target["id"])

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" in msg
        assert target["id"] in msg
        assert "asset_type" in msg

    # -----------------------------------------------------------------
    # 8. test_local / diagnostic_legacy are explicitly non-publish (exempt)
    # -----------------------------------------------------------------

    def test_non_publish_contracts_are_not_publish_grade(self):
        """test_local and diagnostic_legacy are explicitly non-publish and so skip
        the semantic-role QA gate; short_educational is publish-grade."""
        assert get_contract("test_local").publish_grade is False
        assert get_contract("diagnostic_legacy").publish_grade is False
        assert get_contract("short_educational").publish_grade is True

    def test_test_local_production_skips_semantic_role_qa_gate(self, db, tmp_path):
        """A test_local production with a valid batch but NO semantic-role QA (and
        no visual_role) does not fail on semantic-role QA — the gate is skipped
        because the resolved contract is non-publish. It cannot be mistaken for
        publish-grade."""
        test_prod = _db.ensure_production(
            "s15_t003_testlocal", video_type="test_local", db_path=db
        )
        _compliant_batch(test_prod["id"], db, tmp_path, seed_roles=False, seed_semantic_qa=False)

        result = validate_assembly_inputs(test_prod["id"], db_path=db)
        assert result["validation_passed"] is True
        assert result["semantic_role_qa_publish_grade"] is False

    def test_publish_grade_production_without_semantic_qa_blocks(self, db, tmp_path):
        """Contrast: the same structurally valid batch on a publish-grade
        production WITHOUT semantic-role QA IS blocked (fail closed)."""
        pub_prod = _db.ensure_production("s15_t003_pub_nosemqag", db_path=db)
        _compliant_batch(pub_prod["id"], db, tmp_path, seed_semantic_qa=False)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(pub_prod["id"], db_path=db)
        assert "BLOCKED_SEMANTIC_ROLE_QA_MISSING" in str(exc_info.value)

    # -----------------------------------------------------------------
    # 9. S15_T002 visual_role gate still runs FIRST (no weakening)
    # -----------------------------------------------------------------

    def test_missing_visual_role_fails_visual_role_not_semantic(self, prod, db, tmp_path):
        """A publish-grade unit missing visual_role fails BLOCKED_VISUAL_ROLE_MISSING
        at the S15_T002 gate — BEFORE the semantic-role QA gate. Ordering preserved."""
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = next(u for u in units if u["label"] == "H002")
        _set_unit_visual_role(db, target["id"], None)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        msg = str(exc_info.value)
        assert "BLOCKED_VISUAL_ROLE_MISSING" in msg
        # The semantic-role gate must not run (and cannot mask) the visual_role failure.
        assert "BLOCKED_SEMANTIC_ROLE_QA" not in msg

    # -----------------------------------------------------------------
    # 10. Earlier gates (shot-mix / SyncNet) still catch earlier failures
    # -----------------------------------------------------------------

    def test_shot_mix_failure_not_masked_by_semantic_gate(self, db, tmp_path):
        """A shot-mix-invalid publish batch fails BLOCKED_SHOT_MIX_CONTRACT at the
        S15_T001 gate — BEFORE the semantic-role QA gate."""
        pub_prod = _db.ensure_production("s15_t003_shotmix", db_path=db)
        # Only 1 hero, no b-roll, no graphic -> violates shot-mix contract.
        span = commit_timeline_spans(pub_prod["id"], [{
            "label": "H001", "start_ms": 0, "end_ms": 4000,
        }], db_path=db)
        unit = plan_render_units(pub_prod["id"], [{
            "span_id": span[0]["id"], "asset_type": "lipsync_video",
            "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0",
            "visual_role": "hero_trust",
        }], db_path=db)[0]
        f = tmp_path / f"{unit['id']}.mp4"
        f.write_bytes(b"fake video " * 100)
        art = register_artifact(pub_prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)
        run_render_unit_qa(pub_prod["id"], unit["id"], {
            "file_exists": True, "dimensions_ok": True,
            "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)
        comp = tmp_path / f"{unit['id']}_comp.mp4"
        comp.write_bytes(b"compensated video " * 100)
        with _db.transaction(db) as conn:
            conn.execute("UPDATE render_units SET status='valid' WHERE id=?", (unit["id"],))
            conn.execute(
                """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation,
                   external_job_id, idempotency_key, status, submitted_at, completed_at)
                   VALUES (?, ?, ?, 'higgsfield', 'generate_video', 'ext_job', ?, 'completed',
                   datetime('now'), datetime('now'))""",
                (f"pj_{unit['id']}", pub_prod["id"], unit["id"], f"idemp_{unit['id']}"),
            )
            conn.execute(
                "UPDATE provider_jobs SET compensated_artifact_path=? WHERE id=?",
                (str(comp), f"pj_{unit['id']}"),
            )
            conn.execute(
                """INSERT INTO validations (id, production_id, subject_type, subject_id,
                   validator_name, status, evidence_json, created_at)
                   VALUES (?, ?, ?, ?, 'syncnet_offset', 'pass', ?, datetime('now'))""",
                (f"val_syncnet_{unit['id']}", pub_prod["id"], "render_unit", unit["id"],
                 '{"offset_ms":20.0,"confidence":2.5}'),
            )
        record_semantic_role_qa(pub_prod["id"], unit["id"], "hero_trust", "pass", db_path=db)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(pub_prod["id"], db_path=db)
        msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in msg
        assert "BLOCKED_SEMANTIC_ROLE_QA" not in msg


# ---------------------------------------------------------------------------
# Evidence-contract unit tests (record_semantic_role_qa + validate helper)
# ---------------------------------------------------------------------------

class TestSemanticRoleQAEvidenceContract:
    """Direct tests of the evidence recorder and its fail-closed invariants."""

    def test_record_requires_non_empty_visual_role(self, prod, db, tmp_path):
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = units[0]
        with pytest.raises(ValueError, match="SEMANTIC_ROLE_QA_EVIDENCE_INVALID"):
            record_semantic_role_qa(prod["id"], target["id"], "", "pass", db_path=db)

    def test_record_requires_valid_status(self, prod, db, tmp_path):
        units = _compliant_batch(prod["id"], db, tmp_path)
        target = units[0]
        with pytest.raises(ValueError, match="SEMANTIC_ROLE_QA_EVIDENCE_INVALID"):
            record_semantic_role_qa(
                prod["id"], target["id"], target["visual_role"], "maybe", db_path=db,
            )

    def test_record_rejects_unknown_render_unit(self, prod, db, tmp_path):
        _compliant_batch(prod["id"], db, tmp_path)
        with pytest.raises(ValueError, match="SEMANTIC_ROLE_QA_EVIDENCE_INVALID"):
            record_semantic_role_qa(
                prod["id"], "ru_does_not_exist", "hero_trust", "pass", db_path=db,
            )

    def test_evidence_bound_to_unit_and_role(self, prod, db, tmp_path):
        """Recorded evidence is stored under validator_name='semantic_role_qa',
        subject_id == the render_unit, and carries the evaluated visual_role."""
        units = _compliant_batch(prod["id"], db, tmp_path, seed_semantic_qa=False)
        target = next(u for u in units if u["label"] == "B001")
        row = record_semantic_role_qa(
            prod["id"], target["id"], "broll_evidence", "pass",
            category="broll", reason="demonstrates claim", db_path=db,
        )
        assert row["validator_name"] == SEMANTIC_ROLE_QA_VALIDATOR
        assert row["subject_type"] == "render_unit"
        assert row["subject_id"] == target["id"]
        import json
        ev = json.loads(row["evidence_json"])
        assert ev["visual_role"] == "broll_evidence"
        assert ev["render_unit_id"] == target["id"]
        assert ev["result"] == "pass"
