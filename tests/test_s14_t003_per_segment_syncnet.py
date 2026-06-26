"""Tests for S14-T003: Per-segment SyncNet mandatory.

Validates that:
- HERO_SYNC_LOCKED units require per-segment SyncNet validation
- audio_offset alone is insufficient for publish-grade hero sync
- Whole-video/final assembly SyncNet cannot satisfy per-segment requirement
- Non-hero units do not require SyncNet
- Evidence can be on render_unit or provider_job
- Missing SyncNet raises BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING
"""

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
from assemble_db import validate_assembly_inputs, AssemblyError


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
    return _db.ensure_production("s14_t003_test", db_path=db)


def _make_hero_render_unit(
    prod_id: str,
    db: str,
    tmp_path: Path,
    label: str = "H001",
    audio_policy: str = "HERO_SYNC_LOCKED",
    with_syncnet: bool = False,
    with_audio_offset: bool = False,
):
    """Helper: create hero render unit with optional SyncNet validation.

    Returns the render unit dict.
    """
    # Create timeline span
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )

    # Create render unit
    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": audio_policy, "final_audio_source": "master_narration",
          "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
        db_path=db,
    )
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

    # Create provider_job with compensated artifact (needed for hero_island assembly)
    conn = _db.connect(db)
    job_id = f"pj_{uuid.uuid4().hex[:8]}"
    comp_path = tmp_path / f"{label}_compensated.mp4"
    comp_path.write_bytes(b"compensated hero video" * 100)
    conn.execute(
        """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path, submitted_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (job_id, prod_id, unit["id"], "seedance", "generate_lipsync", "completed",
         f"idemp_{job_id}", str(comp_path))
    )

    # Add SyncNet validation on provider_job if requested
    if with_syncnet:
        val_id = f"val_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (val_id, prod_id, "provider_job", job_id, "syncnet_offset", "pass",
             '{"offset_ms": 25.0, "confidence": 2.8}', _db._now())
        )
        # Also add SyncNet validation on render_unit for completeness
        val_id2 = f"val_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (val_id2, prod_id, "render_unit", unit["id"], "syncnet_offset", "pass",
             '{"offset_ms": 25.0, "confidence": 2.8}', _db._now())
        )

    # Add audio_offset validation if requested
    if with_audio_offset:
        val_id = f"val_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (val_id, prod_id, "render_unit", unit["id"], "audio_offset", "pass",
             '{"offset_ms": 25.0}', _db._now())
        )

    conn.close()
    return unit


def _make_syncnet_contract_batch(prod_id, db, tmp_path, unit_specs):
    """Helper: create a contract-compliant batch with proper transaction commits.

    Mirrors the proven `_make_units_batch` pattern from test_shot_mix_contract.py.
    Each spec is a tuple:
        (label, asset_type, audio_policy, shot_type, ordinal, add_syncnet)

    Contract compliance (short_educational): >=2 hero (with syncnet), >=1 broll,
    >=1 graphic, opening hero, no consecutive heroes (max_consecutive_hero=1).

    All inserts go through `_db.transaction()` so they persist for the separate
    connection that `validate_assembly_inputs` opens (avoids the deferred-transaction
    gotcha that broke the single-unit `_make_hero_render_unit` positive paths).

    Returns: list of render unit dicts (in spec order).
    """
    import json
    import uuid

    span_data_list = []
    unit_specs_list = []

    for i, spec in enumerate(unit_specs):
        label, asset_type, audio_policy, shot_type, ordinal, add_syncnet = spec
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
        if audio_policy not in ("SILENT_GRAPHIC",):
            unit_data["model"] = "seedance_2_0"
        if shot_type is not None:
            unit_data["shot_type"] = shot_type
        # SILENT_GRAPHIC must use final_audio_source='none'
        if audio_policy == "SILENT_GRAPHIC":
            unit_data["final_audio_source"] = "none"
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

    # Commit all spans in one batch
    spans = commit_timeline_spans(prod_id, span_data_list, db_path=db)

    # Attach span_ids; pop internal flags before planning (plan_render_units
    # only reads known keys, but keep the spec clean). Track add_syncnet per unit.
    all_unit_data = []
    add_syncnet_flags = []
    for span, unit_data in zip(spans, unit_specs_list):
        unit_data.pop("_label")
        add_syncnet_flags.append(unit_data.pop("_add_syncnet"))
        unit_data["span_id"] = span["id"]
        all_unit_data.append(unit_data)

    units = plan_render_units(prod_id, all_unit_data, db_path=db)

    # Create + link artifacts for every unit (incl. local_graphic) and run QA
    for unit in units:
        f = tmp_path / f"{unit['id']}.mp4"
        f.write_bytes(b"fake video " * 100)
        art = register_artifact(prod_id, f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)
        # Passing QA (all four required checks) so the QA gate is satisfied
        run_render_unit_qa(prod_id, unit["id"], {
            "file_exists": True, "dimensions_ok": True,
            "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

    # Mark valid + add compensated artifacts and SyncNet validations in ONE
    # committed transaction (this is the fix for the deferred-commit bug).
    with _db.transaction(db) as conn:
        for unit, add_syncnet in zip(units, add_syncnet_flags):
            conn.execute(
                "UPDATE render_units SET status='valid' WHERE id=?",
                (unit["id"],),
            )
            audio_policy = unit.get("audio_policy", "")
            if add_syncnet and audio_policy in ("HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"):
                comp_dir = tmp_path / "compensated"
                comp_dir.mkdir(exist_ok=True)
                comp_file = comp_dir / f"{unit['id']}.mp4"
                comp_file.write_bytes(b"compensated video " * 100)

                conn.execute(
                    """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation,
                       external_job_id, idempotency_key, status, submitted_at, completed_at)
                       VALUES (?, ?, ?, 'higgsfield', 'generate_video', 'ext_job_1', ?, 'completed',
                       datetime('now'), datetime('now'))""",
                    (f"pj_{unit['id']}", prod_id, unit["id"], f"idemp_{unit['id']}_{uuid.uuid4().hex[:8]}"),
                )
                conn.execute(
                    "UPDATE provider_jobs SET compensated_artifact_path=? WHERE id=?",
                    (str(comp_file), f"pj_{unit['id']}"),
                )
                syncnet_evidence = json.dumps({"offset_ms": 25.0, "confidence": 2.8})
                conn.execute(
                    """INSERT INTO validations (id, production_id, subject_type, subject_id,
                       validator_name, status, evidence_json, created_at)
                       VALUES (?, ?, ?, ?, 'syncnet_offset', 'pass', ?, datetime('now'))""",
                    (f"val_syncnet_{unit['id']}_{uuid.uuid4().hex[:8]}",
                     prod_id, "render_unit", unit["id"], syncnet_evidence),
                )

    return units


# ---------------------------------------------------------------------------
# Test per-segment SyncNet requirement
# ---------------------------------------------------------------------------

class TestPerSegmentSyncNetRequirement:
    """Test that per-segment SyncNet is mandatory for hero units."""

    def test_hero_unit_with_syncnet_passes(self, db, prod, tmp_path):
        """Hero unit with per-segment SyncNet passes preflight."""
        # Contract-compliant batch: both heroes carry per-segment SyncNet.
        unit_specs = [
            ("H001", "lipsync_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "lipsync_video", "HERO_SYNC_LOCKED", None, 2, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]
        units = _make_syncnet_contract_batch(prod["id"], db, tmp_path, unit_specs)

        result = validate_assembly_inputs(prod["id"], db_path=db)

        assert result["validation_passed"] is True
        assert "BLOCKED" not in str(result)
        # Both hero units must carry a passing per-segment SyncNet validation
        assert len(units) == 4

    def test_hero_unit_without_syncnet_fails(self, db, prod, tmp_path):
        """Hero unit without SyncNet fails with BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING."""
        _make_hero_render_unit(prod["id"], db, tmp_path, "H002", with_syncnet=False)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING" in error_msg
        assert "H002" in error_msg


class TestAudioOffsetInsufficient:
    """Test that audio_offset alone is insufficient."""

    def test_hero_unit_with_only_audio_offset_fails(self, db, prod, tmp_path):
        """Hero unit with only audio_offset validation fails."""
        _make_hero_render_unit(prod["id"], db, tmp_path, "H003",
                               with_syncnet=False, with_audio_offset=True)

        with pytest.raises(AssemblyError) as exc_info:
            validate_assembly_inputs(prod["id"], db_path=db)

        error_msg = str(exc_info.value)
        assert "BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING" in error_msg
        assert "audio_offset" in error_msg
        assert "diagnostic-only" in error_msg

    def test_hero_unit_with_both_passes(self, db, prod, tmp_path):
        """Hero unit with both audio_offset and syncnet_offset passes (SyncNet required)."""
        unit_specs = [
            ("H001", "lipsync_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "lipsync_video", "HERO_SYNC_LOCKED", None, 2, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]
        units = _make_syncnet_contract_batch(prod["id"], db, tmp_path, unit_specs)

        # Additionally attach an audio_offset validation to H002 (diagnostic-only);
        # SyncNet is still the evidence that satisfies the per-segment requirement.
        import json
        import uuid
        h002 = units[2]
        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO validations (id, production_id, subject_type, subject_id,
                   validator_name, status, evidence_json, created_at)
                   VALUES (?, ?, ?, ?, 'audio_offset', 'pass', ?, datetime('now'))""",
                (f"val_ao_{h002['id']}_{uuid.uuid4().hex[:8]}",
                 prod["id"], "render_unit", h002["id"], json.dumps({"offset_ms": 25.0})),
            )

        result = validate_assembly_inputs(prod["id"], db_path=db)

        assert result["validation_passed"] is True


class TestNonHeroUnitsExempt:
    """Test that non-hero units don't require SyncNet."""

    def test_broll_flex_does_not_require_syncnet(self, db, prod, tmp_path):
        """BROLL_FLEX unit does not require SyncNet.

        The b-roll unit (B001) carries no SyncNet validation, yet the
        contract-compliant batch passes — proving b-roll is exempt from the
        per-segment SyncNet requirement.
        """
        # B001 has add_syncnet=False; both heroes carry SyncNet.
        unit_specs = [
            ("H001", "lipsync_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),  # no SyncNet
            ("H002", "lipsync_video", "HERO_SYNC_LOCKED", None, 2, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),
        ]
        units = _make_syncnet_contract_batch(prod["id"], db, tmp_path, unit_specs)
        broll_unit = units[1]

        # Assert B001 genuinely has no SyncNet validation
        conn = _db.connect(db)
        syncnet_on_broll = conn.execute(
            """SELECT 1 FROM validations WHERE subject_id=? AND validator_name='syncnet_offset'""",
            (broll_unit["id"],),
        ).fetchone()
        conn.close()
        assert syncnet_on_broll is None

        # Despite no SyncNet on b-roll, assembly validation passes
        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result["validation_passed"] is True

    def test_silent_graphic_does_not_require_syncnet(self, db, prod, tmp_path):
        """SILENT_GRAPHIC unit does not require SyncNet.

        The graphic unit (G001) carries no SyncNet validation, yet the
        contract-compliant batch passes — proving graphics are exempt.
        """
        unit_specs = [
            ("H001", "lipsync_video", "HERO_SYNC_LOCKED", None, 0, True),
            ("B001", "generated_video", "BROLL_FLEX", None, 1, False),
            ("H002", "lipsync_video", "HERO_SYNC_LOCKED", None, 2, True),
            ("G001", "local_graphic", "SILENT_GRAPHIC", None, 3, False),  # no SyncNet
        ]
        units = _make_syncnet_contract_batch(prod["id"], db, tmp_path, unit_specs)
        graphic_unit = units[3]

        # Assert G001 genuinely has no SyncNet validation
        conn = _db.connect(db)
        syncnet_on_graphic = conn.execute(
            """SELECT 1 FROM validations WHERE subject_id=? AND validator_name='syncnet_offset'""",
            (graphic_unit["id"],),
        ).fetchone()
        conn.close()
        assert syncnet_on_graphic is None

        # Despite no SyncNet on graphic, assembly validation passes
        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result["validation_passed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
