"""TKT-203: Tests for semantic repair loop prompt-revision feedback.

Test matrix:
1. Unit: verdict-driven prompt revision (revise_prompt)
2. Boundary: third semantic failure → manual-review block
3. Contract: repair lifecycle prompt revision + metadata lineage persisted
"""
import json
import os
from pathlib import Path

import pytest

import production_db as _db
from media_service import (
    run_repair_lifecycle,
    revise_prompt,
    classify_validation_failure,
    choose_repair_action,
    VALIDATION_FAILURE_CLASSIFICATIONS,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    row = _db.ensure_production("tkt203_test", db_path=db)
    with _db.transaction(db) as conn:
        conn.execute(
            "INSERT INTO approval_requests(id, production_id, gate_name, status, requested_at) "
            "VALUES(?,?,?,?,?)",
            ("ar_tkt203", row["id"], "gate_a_spend", "pass", _db._now()),
        )
    return row["id"]


def _create_render_unit(conn, prod_id, unit_id, label="B001", metadata=None):
    conn.execute(
        """INSERT INTO render_units
           (id, production_id, label, asset_type, audio_policy,
            lipsync_required, required_start_ms, required_end_ms,
            required_duration_ms, ordinal, status, render_mode,
            visual_role, narrative_claim,
            source_slice_sha256, metadata_json, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (unit_id, prod_id, label, "generated_video", "BROLL_FLEX", 0,
         0, 5000, 5000, 1, "needs_repair", "generated_video",
         "broll_evidence", "Test narrative claim",
         "a" * 64,
         json.dumps(metadata) if metadata else "{}",
         _db._now(), _db._now()),
    )


def _record_validation(conn, prod_id, unit_id, validator_name, status,
                        evidence, val_id=None):
    vid = val_id or f"val_{validator_name}_{unit_id}"
    conn.execute(
        "INSERT INTO validations(id, production_id, subject_id, subject_type, "
        "validator_name, status, evidence_json, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (vid, prod_id, unit_id, "render_unit",
         validator_name, status, json.dumps(evidence), _db._now()),
    )


_SAMPLE_VERDICT = {
    "claim_supported": False,
    "must_show_present": ["document"],
    "must_avoid_violations": ["person not at desk"],
    "described_content": "A person sitting on a couch with a phone",
    "confidence": 0.65,
}


# =========================================================================
# Unit tests — revise_prompt
# =========================================================================

class TestRevisePrompt:
    """Deterministic prompt revision from semantic QA verdict."""

    def test_revise_adds_correctives(self):
        original = "A cinematic shot showing a person working at a desk"
        revised = revise_prompt(original, _SAMPLE_VERDICT)
        assert "Previous render showed" in revised
        assert "couch" in revised
        assert "Must avoid" in revised or "CORRECTIVE" in revised

    def test_original_preserved_in_output(self):
        original = "Person working at desk with laptop"
        revised = revise_prompt(original, _SAMPLE_VERDICT)
        assert original in revised

    def test_empty_verdict_returns_original(self):
        original = "A calm office scene"
        revised = revise_prompt(original, {})
        assert revised == original

    def test_empty_original_produces_correctives(self):
        revised = revise_prompt("", _SAMPLE_VERDICT)
        assert revised != ""
        assert "CORRECTIVE" in revised

    def test_no_violations_omits_avoid(self):
        verdict = {
            "claim_supported": True,
            "must_show_present": ["desk"],
            "must_avoid_violations": [],
            "described_content": "A desk with a laptop",
            "confidence": 0.95,
        }
        revised = revise_prompt("Desk scene", verdict)
        assert "Previous render showed" in revised
        assert "Must avoid" not in revised

    def test_no_described_content_still_revises(self):
        verdict = {
            "claim_supported": False,
            "must_show_present": [],
            "must_avoid_violations": ["readable text"],
            "described_content": "",
            "confidence": 0.3,
        }
        revised = revise_prompt("Office scene", verdict)
        assert "Must avoid" in revised


# =========================================================================
# Unit tests — classification and action
# =========================================================================

class TestSemanticMismatchClassification:
    """semantic_mismatch in classification and action decision table."""

    def test_semantic_mismatch_in_classifications(self):
        assert "semantic_mismatch" in VALIDATION_FAILURE_CLASSIFICATIONS

    def test_classify_from_validator_name(self):
        ev = {"validator_name": "semantic_role_qa", "result": "fail"}
        assert classify_validation_failure(ev) == "semantic_mismatch"

    def test_classify_from_semantic_qa_flag(self):
        ev = {"semantic_qa_failure": True, "file_exists": True, "sha_match": True}
        assert classify_validation_failure(ev) == "semantic_mismatch"

    def test_choose_repair_action_semantic_mismatch(self):
        ru = {"asset_type": "generated_video"}
        assert choose_repair_action(ru, "semantic_mismatch") == "regenerate_provider_video"


# =========================================================================
# Integration tests — repair lifecycle with semantic QA failures
# =========================================================================

class TestRepairLifecycleSemantic:
    """run_repair_lifecycle with semantic_role_qa fail evidence."""

    def test_semantic_failure_triggers_repair(self, db, prod):
        """A unit with passing qa_media_contract but failing semantic_role_qa
        triggers prompt-revision repair."""
        unit_id = "ru_sem_001"
        meta = {
            "provider_visual_prompt": "A person working productively at a desk",
            "prompt": "A person working productively at a desk",
        }
        with _db.transaction(db) as conn:
            _create_render_unit(conn, prod, unit_id, metadata=meta)
            # qa_media_contract passes
            _record_validation(conn, prod, unit_id, "qa_media_contract",
                               "pass", {"file_exists": True, "sha_match": True,
                                        "dimensions_ok": True, "duration_ok": True,
                                        "render_method": "generated_video"})
            # semantic_role_qa fails
            _record_validation(conn, prod, unit_id, "semantic_role_qa",
                               "fail", {
                                   "visual_role": "broll_evidence",
                                   "result": "fail",
                                   "details": {
                                       "backend": "fixture",
                                       "verdict": _SAMPLE_VERDICT,
                                   },
                               })

        outcome = run_repair_lifecycle(prod, unit_id, db_path=db)

        assert outcome["failure_class"] == "semantic_mismatch"
        assert outcome["action"] == "regenerate_provider_video"
        assert outcome.get("prompt_revised") is True
        assert outcome.get("attempt") == 1
        assert outcome.get("change_request_id") is not None

    def test_revision_lineage_stored_in_metadata(self, db, prod):
        """Prompt revision lineage is persisted in render unit metadata."""
        unit_id = "ru_sem_002"
        original_prompt = "Person at desk with laptop"
        meta = {"provider_visual_prompt": original_prompt}
        with _db.transaction(db) as conn:
            _create_render_unit(conn, prod, unit_id, metadata=meta)
            _record_validation(conn, prod, unit_id, "qa_media_contract",
                               "pass", {"file_exists": True, "sha_match": True,
                                        "dimensions_ok": True, "duration_ok": True,
                                        "render_method": "generated_video"})
            _record_validation(conn, prod, unit_id, "semantic_role_qa",
                               "fail", {
                                   "visual_role": "broll_evidence",
                                   "result": "fail",
                                   "details": {"verdict": _SAMPLE_VERDICT},
                               })

        run_repair_lifecycle(prod, unit_id, db_path=db)

        conn = _db.connect(db)
        ru = conn.execute("SELECT metadata_json FROM render_units WHERE id=?",
                          (unit_id,)).fetchone()
        conn.close()
        assert ru is not None

        meta_after = json.loads(ru["metadata_json"])
        assert meta_after.get("semantic_repair_attempts") == 1

        lineage = meta_after.get("prompt_revision_lineage", [])
        assert len(lineage) == 1
        entry = lineage[0]
        assert entry["attempt"] == 1
        assert entry["original_prompt"] == original_prompt
        assert entry["revised_prompt"] != original_prompt
        assert "verdict" in entry
        assert entry["validator"] == "semantic_role_qa"

    def test_third_attempt_blocked(self, db, prod):
        """Third semantic QA failure (2 prior repairs) blocks with manual review."""
        unit_id = "ru_sem_003"
        meta = {
            "provider_visual_prompt": "Original prompt",
            "prompt": "Original prompt",
            "semantic_repair_attempts": 2,
            "prompt_revision_lineage": [
                {"attempt": 1, "original_prompt": "A", "revised_prompt": "B"},
                {"attempt": 2, "original_prompt": "B", "revised_prompt": "C"},
            ],
        }
        with _db.transaction(db) as conn:
            _create_render_unit(conn, prod, unit_id, metadata=meta)
            _record_validation(conn, prod, unit_id, "qa_media_contract",
                               "pass", {"file_exists": True, "sha_match": True,
                                        "dimensions_ok": True, "duration_ok": True,
                                        "render_method": "generated_video"})
            _record_validation(conn, prod, unit_id, "semantic_role_qa",
                               "fail", {
                                   "visual_role": "broll_evidence",
                                   "result": "fail",
                                   "details": {"verdict": _SAMPLE_VERDICT},
                               })

        with pytest.raises(RuntimeError, match="attempts exhausted"):
            run_repair_lifecycle(prod, unit_id, db_path=db)

    def test_second_attempt_proceeds(self, db, prod):
        """Second repair (1 prior attempt) still proceeds."""
        unit_id = "ru_sem_004"
        meta = {
            "provider_visual_prompt": "Prompt v1",
            "prompt": "Prompt v1",
            "semantic_repair_attempts": 1,
            "prompt_revision_lineage": [
                {"attempt": 1, "original_prompt": "Original", "revised_prompt": "Prompt v1"},
            ],
        }
        with _db.transaction(db) as conn:
            _create_render_unit(conn, prod, unit_id, metadata=meta)
            _record_validation(conn, prod, unit_id, "qa_media_contract",
                               "pass", {"file_exists": True, "sha_match": True,
                                        "dimensions_ok": True, "duration_ok": True,
                                        "render_method": "generated_video"})
            _record_validation(conn, prod, unit_id, "semantic_role_qa",
                               "fail", {
                                   "visual_role": "broll_evidence",
                                   "result": "fail",
                                   "details": {"verdict": _SAMPLE_VERDICT},
                               })

        outcome = run_repair_lifecycle(prod, unit_id, db_path=db)

        assert outcome["failure_class"] == "semantic_mismatch"
        assert outcome["attempt"] == 2
        assert outcome["prompt_revised"] is True

        conn = _db.connect(db)
        ru = conn.execute("SELECT metadata_json FROM render_units WHERE id=?",
                          (unit_id,)).fetchone()
        conn.close()
        meta_after = json.loads(ru["metadata_json"])
        assert meta_after["semantic_repair_attempts"] == 2
        assert len(meta_after["prompt_revision_lineage"]) == 2

    def test_attempt_counter_not_present_starts_at_zero(self, db, prod):
        """No prior semantic_repair_attempts defaults to 0 — first repair proceeds."""
        unit_id = "ru_sem_005"
        meta = {"provider_visual_prompt": "No prior repairs"}
        with _db.transaction(db) as conn:
            _create_render_unit(conn, prod, unit_id, metadata=meta)
            _record_validation(conn, prod, unit_id, "qa_media_contract",
                               "pass", {"file_exists": True, "sha_match": True,
                                        "dimensions_ok": True, "duration_ok": True,
                                        "render_method": "generated_video"})
            _record_validation(conn, prod, unit_id, "semantic_role_qa",
                               "fail", {
                                   "visual_role": "broll_evidence",
                                   "result": "fail",
                                   "details": {"verdict": _SAMPLE_VERDICT},
                               })

        outcome = run_repair_lifecycle(prod, unit_id, db_path=db)
        assert outcome["attempt"] == 1
