"""Tests for Sprint 15: Shot-mix contract validation (S15-T001).

Tests format-level shot-mix contract enforcement to prevent wrong editorial
structure from passing assembly.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact, link_artifact_to_render_unit,
)
from assemble_db import validate_assembly_inputs, AssemblyError
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
    return _db.ensure_production("s15_test", db_path=db)


def _make_units_batch(prod_id, db, tmp_path, unit_specs):
    """Helper: create multiple render units in a single transaction and mark them all valid.

    Args:
        prod_id: Production ID
        db: Database path
        tmp_path: Temporary path for artifacts
        unit_specs: List of (label, asset_type, audio_policy, shot_type, ordinal, add_syncnet) tuples

    Returns:
        List of render unit dicts
    """
    # Phase 1: Collect all span data and unit data
    span_data_list = []
    unit_specs_list = []

    for i, spec in enumerate(unit_specs):
        label, asset_type, audio_policy, shot_type, ordinal, add_syncnet = spec

        # Calculate sequential time ranges (4 seconds each)
        start_ms = i * 4000
        end_ms = (i + 1) * 4000

        span_data = {"label": label, "start_ms": start_ms, "end_ms": end_ms}
        if ordinal is not None:
            span_data["ordinal"] = ordinal

        span_data_list.append(span_data)

        unit_data = {
            "asset_type": asset_type,
            "audio_policy": audio_policy,
            "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "_label": label,
            "_add_syncnet": add_syncnet,
        }

        if shot_type is not None:
            unit_data["shot_type"] = shot_type

        # S07/R7: B-roll semantic contract requires these fields
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

    # Phase 2: Commit all spans in a single batch call (avoids stale marking)
    spans = commit_timeline_spans(prod_id, span_data_list, db_path=db)

    # Phase 3: Prepare unit_data with span_ids
    all_unit_data = []
    for i, (span, unit_data) in enumerate(zip(spans, unit_specs_list)):
        label = unit_data.pop("_label")
        add_syncnet = unit_data.pop("_add_syncnet")
        unit_data["span_id"] = span["id"]
        all_unit_data.append(unit_data)
        unit_specs_list[i] = (label, add_syncnet, unit_data)

    # Phase 4: Plan all render units in a single batch call
    units = plan_render_units(prod_id, all_unit_data, db_path=db)

    # Phase 5: Create artifacts and link them
    for unit, (label, _, _) in zip(units, unit_specs_list):
        # Create artifact file
        f = tmp_path / f"{label}.mp4"
        f.write_bytes(b"fake video " * 100)

        art = register_artifact(prod_id, f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    # Phase 6: Mark all units as valid and add SyncNet validations in a single transaction
    import json
    import uuid
    with _db.transaction(db) as conn:
        for unit, (label, add_syncnet, _) in zip(units, unit_specs_list):
            conn.execute(
                "UPDATE render_units SET status='valid' WHERE id=?",
                (unit["id"],),
            )

            # S14: Add SyncNet validation for hero units if requested
            if add_syncnet:
                audio_policy = unit.get("audio_policy", "")
                if audio_policy in ["HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"]:
                    # Create fake compensated artifact file
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
                        "offset_ms": 10.0,
                        "confidence": 2.5,
                    })
                    conn.execute(
                        """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                        (f"val_syncnet_{unit['id']}_{uuid.uuid4().hex[:8]}", prod_id, "render_unit", unit["id"], "syncnet_offset", "pass", syncnet_evidence),
                    )

    # S15-T003: seed passing post-render semantic-role QA evidence for every unit
    # (read from its current DB visual_role) so publish-grade batches satisfy the
    # semantic-role gate. Units without a role are skipped.
    seed_semantic_role_qa(prod_id, db, units)

    return units


class TestShotMixContract:
    """Test shot-mix contract validation."""

    def test_2_hero_1_broll_1_graphic_passes(self, db, prod, tmp_path):
        """Valid shot-mix: 2 hero + 1 broll + 1 graphic passes contract."""
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 2, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]

        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should pass - has 2 hero, 1 broll, 1 graphic
        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result["validation_passed"] is True

    def test_only_hero_and_graphic_fails(self, db, prod, tmp_path):
        """Missing b-roll: only hero + graphic fails with BLOCKED_SHOT_MIX_CONTRACT."""
        # Hero 1, Hero 2, Graphic (missing b-roll)
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 1, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 2, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - missing b-roll
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "broll: expected >= 1, actual 0" in error_msg

    def test_missing_second_hero_fails(self, db, prod, tmp_path):
        """Only 1 hero when 2 required fails with BLOCKED_SHOT_MIX_CONTRACT."""
        # Hero 1 (missing second hero), B-roll, Graphic
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 2, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - only 1 hero when 2 required
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "hero_lipsync: expected >= 2, actual 1" in error_msg

    def test_missing_graphic_fails(self, db, prod, tmp_path):
        """Missing graphic: 2 hero + 1 broll fails with BLOCKED_SHOT_MIX_CONTRACT."""
        # Hero 1, B-roll, Hero 2 (missing graphic)
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 2, True),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - missing graphic
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "graphic: expected >= 1, actual 0" in error_msg

    def test_consecutive_hero_segments_fails(self, db, prod, tmp_path):
        """More than 1 consecutive hero segment fails editorial break rule."""
        # Hero 1, Hero 2 (consecutive - violates max_consecutive_hero=1), B-roll, Hero 3, Graphic
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 1, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 2, False),
            ("H003", "generated_video", "HERO_SYNC_LOCKED", None, 3, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 4, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - 2 consecutive heroes (H001, H002) violate max_consecutive_hero=1
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "consecutive hero" in error_msg

    def test_opening_must_be_hero(self, db, prod, tmp_path):
        """Opening segment must be hero unless explicitly waived."""
        # B-roll first (violates opening_must_be_hero rule), Hero 1, Hero 2, Graphic
        unit_specs = [
            ("B001", "generated_video", "BROLL_FLEX", None, 0, False),
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 1, True),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 2, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - opening segment not hero
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "opening segment must be hero" in error_msg


class TestShotClassification:
    """Test shot type classification logic."""

    def test_hero_lipsync_not_counted_as_broll(self, db, prod, tmp_path):
        """B-roll count excludes HERO_SYNC_LOCKED units even if labelled broll."""
        # Hero 1, Hero 2 with HERO_SYNC_LOCKED audio (should count as hero, not broll), Graphic
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 1, True),  # Hero audio policy, needs SyncNet
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 2, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - missing actual broll (H002 has HERO_SYNC_LOCKED audio)
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "broll: expected >= 1, actual 0" in error_msg

    def test_local_graphic_not_counted_as_broll(self, db, prod, tmp_path):
        """B-roll count excludes local_graphic asset type."""
        # Hero 1, Local graphic (not broll), Hero 2
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 1, False),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 2, True),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail - missing actual broll (local_graphic doesn't count as broll)
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_SHOT_MIX_CONTRACT" in error_msg
        assert "broll: expected >= 1, actual 0" in error_msg


class TestNonPublishGradeProfiles:
    """Test that non-publish profiles are clearly marked."""

    def test_test_local_profile_not_publish_grade(self):
        """Test/test_local profile must not be mistaken for publish-grade."""
        from shot_mix_contract import get_contract

        # Load test_local contract
        contract = get_contract("test_local")

        # Verify it's explicitly marked as non-publish
        assert contract.publish_grade is False
        assert contract.format_name == "Test/Local Profile"
        assert "NOT PUBLISH-GRADE" in contract.description

    def test_diagnostic_legacy_not_publish_grade(self):
        """Diagnostic legacy profile must not be publish-grade."""
        from shot_mix_contract import get_contract

        # Load diagnostic_legacy contract
        contract = get_contract("diagnostic_legacy")

        # Verify it's explicitly marked as non-publish
        assert contract.publish_grade is False


class TestS13S14Regression:
    """Ensure S13/S14 gates still work with shot-mix validation."""

    def test_s13_hero_compensated_artifact_gate_still_enforced(self, db, prod, tmp_path):
        """S13 compensated hero artifact requirement must still be enforced."""
        # Create enough units to pass shot-mix (2 hero, 1 broll, 1 graphic)
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, True),  # Has SyncNet + compensated artifact
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 2, True),  # Has SyncNet + compensated artifact
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Update compensated artifact paths to point to non-existent files
        conn = _db.connect(db)
        conn.execute(
            "UPDATE provider_jobs SET compensated_artifact_path=? WHERE id LIKE 'pj_%'",
            ("/nonexistent/path/compensated.mp4",)
        )
        conn.commit()
        conn.close()

        # Should fail on S13 compensated artifact file check (before shot-mix)
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)
        error_msg = str(exc_info.value)
        # Should fail on compensated artifact file missing, not shot-mix
        assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING" in error_msg

    def test_s14_per_segment_syncnet_still_enforced(self, db, prod, tmp_path):
        """S14 per-segment SyncNet requirement must still be enforced."""
        # Create hero render units WITHOUT SyncNet validation (add_syncnet=False)
        unit_specs = [
            ("H001", "generated_video", "HERO_SYNC_LOCKED", None, 0, False),  # NO SyncNet!
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "generated_video", "HERO_SYNC_LOCKED", None, 2, False),  # NO SyncNet!
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]
        _make_units_batch(prod["id"], db, tmp_path, unit_specs)

        # Should fail on S14 SyncNet check before shot-mix
        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)
        error_msg = str(exc_info.value)
        # Should fail on SyncNet, not shot-mix
        assert "BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING" in error_msg
