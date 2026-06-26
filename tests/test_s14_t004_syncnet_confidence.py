"""Tests for S14_T004: SyncNet confidence and offset threshold gate.

Validates that:
- Hero units with SyncNet confidence below policy threshold fail
- Hero units with SyncNet offset above policy threshold fail
- Hero units with good SyncNet confidence and offset pass
- Hero framing selects correct policy (close/medium/wide)
- Missing offset_ms in evidence raises error
- Malformed evidence_json raises error
- Non-hero units bypass SyncNet confidence check
- Missing hero_framing defaults to close_hero policy
"""

import os
import sys
import uuid
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact, link_artifact_to_render_unit,
)
from media_service import run_render_unit_qa
from assemble_db import validate_assembly_inputs, AssemblyError
from visual_role_fixtures import seed_visual_roles, seed_semantic_role_qa


@pytest.fixture
def db(tmp_path):
    """Create test database."""
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    """Create test production."""
    return _db.ensure_production("s14_t004_test", db_path=db)


def _make_hero_render_unit(
    prod_id: str,
    db: str,
    tmp_path: Path,
    label: str = "H001",
    audio_policy: str = "HERO_SYNC_LOCKED",
    hero_framing: str = "close",
    offset_ms: float = 25.0,
    confidence: float = 2.5,
):
    """Helper: create hero render unit with SyncNet validation.

    Returns the render unit dict.
    """
    # Create timeline span
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )

    # Create render unit with hero_framing
    unit_params = [{
        "span_id": spans[0]["id"],
        "asset_type": "lipsync_video",
        "audio_policy": audio_policy,
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "model": "seedance_2_0",
    }]

    if hero_framing:
        unit_params[0]["hero_framing"] = hero_framing

    units = plan_render_units(prod_id, unit_params, db_path=db)
    unit = units[0]

    # Create fake video artifact
    fake_video = tmp_path / f"{label}_provider.mp4"
    fake_video.write_bytes(b"fake provider video" * 100)
    art = register_artifact(prod_id, fake_video, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    # Run QA
    run_render_unit_qa(prod_id, unit["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
    }, db_path=db)

    # Create provider_job with compensated artifact
    with _db.transaction(db) as conn:
        job_id = f"pj_{uuid.uuid4().hex[:8]}"
        comp_path = tmp_path / f"{label}_compensated.mp4"
        comp_path.write_bytes(b"compensated hero video" * 100)
        conn.execute(
            """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path, submitted_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (job_id, prod_id, unit["id"], "seedance", "generate_lipsync", "completed",
             f"idemp_{job_id}", str(comp_path))
        )

        # Add SyncNet validation
        val_id = f"val_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (val_id, prod_id, "render_unit", unit["id"], "syncnet_offset", "pass",
             json.dumps({"offset_ms": offset_ms, "confidence": confidence}), _db._now())
        )

    return unit


def _make_contract_compliant_batch(
    prod_id: str,
    db: str,
    tmp_path: Path,
    hero_under_test_params: dict | None = None,
):
    """Helper: create a contract-compliant batch of render units.

    Creates a batch that satisfies the short_educational shot-mix contract:
    - >=2 hero/lipsync units
    - >=1 b-roll unit
    - >=1 graphic unit
    - Opening segment is hero
    - No consecutive hero segments (max_consecutive_hero=1)

    Args:
        prod_id: Production ID
        db: Database path
        tmp_path: Temporary path for artifacts
        hero_under_test_params: Optional dict with parameters for the hero unit under test:
            - label: Unit label (default="H002")
            - hero_framing: Framing type (default="close")
            - offset_ms: SyncNet offset (default=20.0)
            - confidence: SyncNet confidence (default=2.5)
            - audio_policy: Audio policy (default="HERO_SYNC_LOCKED")

    Returns:
        Dict mapping labels to render unit dicts, including the 'hero_under_test' unit.
    """
    # Default params for hero under test
    if hero_under_test_params is None:
        hero_under_test_params = {}

    hero_test_label = hero_under_test_params.get("label", "H002")
    hero_test_framing = hero_under_test_params.get("hero_framing", "close")
    hero_test_offset = hero_under_test_params.get("offset_ms", 20.0)
    hero_test_confidence = hero_under_test_params.get("confidence", 2.5)
    hero_test_audio_policy = hero_under_test_params.get("audio_policy", "HERO_SYNC_LOCKED")

    # Phase 1: Define all units in contract-compliant order
    # Structure: H001 (opening hero), [broll/graphic], H002 (hero under test), [graphic], [optional more]
    unit_specs = []

    # H001 - Opening hero (always first, always hero)
    unit_specs.append({
        "label": "H001",
        "asset_type": "lipsync_video",
        "audio_policy": "HERO_SYNC_LOCKED",
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "model": "seedance_2_0",
        "hero_framing": "close",
        "start_ms": 0,
        "end_ms": 4000,
        "add_syncnet": True,
        "offset_ms": 20.0,
        "confidence": 2.5,
    })

    # B001 - B-roll (prevents consecutive heroes)
    unit_specs.append({
        "label": "B001",
        "asset_type": "generated_video",
        "audio_policy": "BROLL_FLEX",
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "start_ms": 4000,
        "end_ms": 8000,
        "add_syncnet": False,
    })

    # H002 - Hero under test (with custom params)
    unit_specs.append({
        "label": hero_test_label,
        "asset_type": "lipsync_video",
        "audio_policy": hero_test_audio_policy,
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "model": "seedance_2_0",
        "hero_framing": hero_test_framing,
        "start_ms": 8000,
        "end_ms": 12000,
        "add_syncnet": True,
        "offset_ms": hero_test_offset,
        "confidence": hero_test_confidence,
    })

    # G001 - Graphic (satisfies graphic requirement)
    unit_specs.append({
        "label": "G001",
        "asset_type": "local_graphic",
        "audio_policy": "SILENT_GRAPHIC",
        "final_audio_source": "none",
        "provider_audio_usage": "diagnostic_only",
        "start_ms": 12000,
        "end_ms": 16000,
        "add_syncnet": False,
    })

    # Phase 2: Collect all span data
    span_data_list = []
    unit_specs_list = []

    for spec in unit_specs:
        span_data = {
            "label": spec["label"],
            "start_ms": spec["start_ms"],
            "end_ms": spec["end_ms"],
        }
        span_data_list.append(span_data)

        unit_data = {
            "asset_type": spec["asset_type"],
            "audio_policy": spec["audio_policy"],
            "final_audio_source": spec["final_audio_source"],
            "provider_audio_usage": spec["provider_audio_usage"],
            "_add_syncnet": spec["add_syncnet"],
            "_offset_ms": spec.get("offset_ms"),
            "_confidence": spec.get("confidence"),
        }

        # Add optional fields
        if "model" in spec:
            unit_data["model"] = spec["model"]
        if "hero_framing" in spec:
            unit_data["hero_framing"] = spec["hero_framing"]

        # S07/R7: B-roll semantic contract requires these fields
        audio_policy = spec.get("audio_policy", "")
        if audio_policy in ["BROLL_FLEX", "BROLL_SYNCED_ACTION"]:
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

    # S15-T002: seed creative_beats with visual_role and link each span to its
    # beat so plan_render_units propagates visual_role onto every render unit.
    seed_visual_roles(prod_id, db, span_data_list, unit_specs_list)

    # Phase 3: Commit all spans in batch
    spans = commit_timeline_spans(prod_id, span_data_list, db_path=db)

    # Phase 4: Prepare unit_data with span_ids
    all_unit_data = []
    for span, unit_data in zip(spans, unit_specs_list):
        unit_data["span_id"] = span["id"]
        all_unit_data.append(unit_data)

    # Phase 5: Plan all render units in batch
    units = plan_render_units(prod_id, all_unit_data, db_path=db)

    # Phase 6: Create artifacts and link them (all units, incl. local_graphic)
    for unit, spec_data in zip(units, unit_specs):
        # Create artifact file
        f = tmp_path / f"{unit['id']}_provider.mp4"
        f.write_bytes(b"fake video " * 100)

        art = register_artifact(prod_id, f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    # Phase 7: Mark all units as valid and add SyncNet validations
    with _db.transaction(db) as conn:
        for unit, spec_data in zip(units, unit_specs_list):
            conn.execute(
                "UPDATE render_units SET status='valid' WHERE id=?",
                (unit["id"],),
            )

            # Add SyncNet validation for hero units
            if spec_data.get("_add_syncnet"):
                audio_policy = spec_data.get("audio_policy", "")
                if audio_policy in ["HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"]:
                    # Create compensated artifact
                    comp_dir = tmp_path / "compensated"
                    comp_dir.mkdir(exist_ok=True)
                    comp_file = comp_dir / f"{unit['id']}.mp4"
                    comp_file.write_bytes(b"compensated video " * 100)

                    # Add provider job with compensated artifact
                    conn.execute(
                        """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation,
                           external_job_id, idempotency_key, status, submitted_at, completed_at)
                           VALUES (?, ?, ?, 'higgsfield', 'generate_video', 'ext_job_1', ?, 'completed', datetime('now'), datetime('now'))""",
                        (f"pj_{unit['id']}", prod_id, unit["id"], f"idemp_{unit['id']}_{uuid.uuid4().hex[:8]}"),
                    )
                    conn.execute(
                        "UPDATE provider_jobs SET compensated_artifact_path=? WHERE id=?",
                        (str(comp_file), f"pj_{unit['id']}"),
                    )

                    # Add SyncNet validation
                    syncnet_evidence = json.dumps({
                        "offset_ms": spec_data.get("_offset_ms", 20.0),
                        "confidence": spec_data.get("_confidence", 2.5),
                    })
                    conn.execute(
                        """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                        (f"val_syncnet_{unit['id']}_{uuid.uuid4().hex[:8]}", prod_id, "render_unit", unit["id"], "syncnet_offset", "pass", syncnet_evidence),
                    )

    # S15-T003: seed passing post-render semantic-role QA evidence per unit
    # (current DB visual_role) so publish-grade batches satisfy the semantic gate.
    seed_semantic_role_qa(prod_id, db, units)

    # Return dict mapping labels to units, with special key for hero under test
    result = {unit_specs[i]["label"]: units[i] for i in range(len(units))}
    result["hero_under_test"] = units[2]  # H002 is the hero under test
    return result


class TestSyncNetConfidenceGate:
    """Tests for SyncNet confidence threshold enforcement."""

    def test_hero_unit_with_low_confidence_fails(self, prod, db, tmp_path):
        """Hero unit with SyncNet confidence below policy threshold should fail."""
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H001",
            hero_framing="close",
            offset_ms=25.0,
            confidence=1.5,  # Below 2.0 threshold for close_hero
        )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        assert "BLOCKED_HERO_SYNCNET_LOW_CONFIDENCE" in str(exc_info.value)
        assert "confidence" in str(exc_info.value).lower()
        assert unit["id"] in str(exc_info.value)

    def test_hero_unit_with_high_offset_fails(self, prod, db, tmp_path):
        """Hero unit with SyncNet offset above policy threshold should fail."""
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H002",
            hero_framing="close",
            offset_ms=50.0,  # Above 30ms threshold for close_hero
            confidence=2.5,
        )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        assert "BLOCKED_HERO_SYNCNET_BELOW_THRESHOLD" in str(exc_info.value)
        assert "offset" in str(exc_info.value).lower() or "threshold" in str(exc_info.value).lower()
        assert unit["id"] in str(exc_info.value)

    def test_hero_unit_with_good_syncnet_passes(self, prod, db, tmp_path):
        """Hero unit with good SyncNet confidence and offset should pass."""
        _make_contract_compliant_batch(
            prod["id"], db, tmp_path,
            hero_under_test_params={
                "label": "H002",
                "hero_framing": "close",
                "offset_ms": 20.0,  # Within 30ms threshold
                "confidence": 2.5,  # Above 2.0 threshold
            },
        )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True


class TestHeroFramingPolicySelection:
    """Tests for hero framing to policy name mapping."""

    def test_medium_framing_uses_medium_policy(self, prod, db, tmp_path):
        """Hero unit with medium framing should use medium_hero policy (40ms threshold)."""
        _make_contract_compliant_batch(
            prod["id"], db, tmp_path,
            hero_under_test_params={
                "label": "H002",
                "hero_framing": "medium",
                "offset_ms": 35.0,  # OK for medium (40ms), would FAIL for close (30ms)
                "confidence": 2.5,
            },
        )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True

    def test_wide_framing_uses_medium_policy(self, prod, db, tmp_path):
        """Hero unit with wide framing should use medium_hero policy (wide maps to medium)."""
        _make_contract_compliant_batch(
            prod["id"], db, tmp_path,
            hero_under_test_params={
                "label": "H002",
                "hero_framing": "wide",
                "offset_ms": 35.0,  # OK for medium (40ms)
                "confidence": 2.5,
            },
        )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True

    def test_missing_framing_defaults_to_close(self, prod, db, tmp_path):
        """Hero unit with missing hero_framing should default to close_hero policy."""
        # Use contract-compliant batch but manually remove hero_framing from hero_under_test
        units = _make_contract_compliant_batch(
            prod["id"], db, tmp_path,
            hero_under_test_params={
                "label": "H002",
                # NO hero_framing specified - should default to close_hero
                "offset_ms": 25.0,  # OK for close (30ms)
                "confidence": 2.5,
            },
        )

        # Manually remove hero_framing from the hero_under_test unit to test default behavior
        hero_under_test = units["hero_under_test"]
        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE render_units SET hero_framing=NULL WHERE id=?",
                (hero_under_test["id"],),
            )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True


class TestEvidenceValidation:
    """Tests for SyncNet evidence JSON validation."""

    def test_missing_offset_ms_fails(self, prod, db, tmp_path):
        """Hero unit with SyncNet validation missing offset_ms should fail."""
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H007",
            hero_framing="close",
        )

        # Manually update validation to remove offset_ms
        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE validations SET evidence_json=? WHERE subject_id=? AND validator_name='syncnet_offset'",
                (json.dumps({"confidence": 2.5}), unit["id"])
            )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        assert "BLOCKED_HERO_SYNCNET_EVIDENCE_MALFORMED" in str(exc_info.value)
        assert "offset_ms" in str(exc_info.value)

    def test_malformed_evidence_json_fails(self, prod, db, tmp_path):
        """Hero unit with malformed evidence_json should fail."""
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H008",
            hero_framing="close",
        )

        # Manually update validation to malformed JSON
        with _db.transaction(db) as conn:
            conn.execute(
                "UPDATE validations SET evidence_json=? WHERE subject_id=? AND validator_name='syncnet_offset'",
                ("not valid json {{{", unit["id"])
            )

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        assert "BLOCKED_HERO_SYNCNET_EVIDENCE_MALFORMED" in str(exc_info.value)


class TestNonHeroUnits:
    """Tests for non-hero unit exemption."""

    def test_broll_flex_bypasses_confidence_check(self, prod, db, tmp_path):
        """Non-hero units (BROLL_FLEX) should bypass SyncNet confidence check.

        This test verifies that b-roll units don't require SyncNet validation.
        The contract-compliant batch includes a b-roll unit (B001) with no SyncNet
        validation, yet the overall batch passes - proving b-roll bypasses the check.
        """
        # Create contract-compliant batch where B001 (b-roll) has no SyncNet validation
        units = _make_contract_compliant_batch(
            prod["id"], db, tmp_path,
            hero_under_test_params={
                "label": "H002",
                "hero_framing": "close",
                "offset_ms": 20.0,
                "confidence": 2.5,
            },
        )

        # Verify the b-roll unit exists and has no SyncNet validation
        broll_unit = units["B001"]
        assert broll_unit is not None
        assert broll_unit.get("audio_policy") == "BROLL_FLEX"

        # The batch passes despite b-roll having no SyncNet validation
        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True
