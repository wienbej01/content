"""Tests for S13-T002: Enforce compensated hero artifact requirement.

This test suite proves:
1. Core invariant: hero_island units require compensated_artifact_path
2. Missing path blocks assembly with explicit BLOCKED_ error
3. Missing file blocks assembly with explicit BLOCKED_ error
4. Non-hero units are not affected
5. Existing tests still pass
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
from assemble_db import build_assembly_inputs, AssemblyError


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("s13_t002_test", db_path=db)


def _make_hero_render_unit(prod_id, db, tmp_path, label="H001", with_compensated=False, with_syncnet=False):
    """Helper: create hero lipsync render unit with optional compensated artifact.

    Returns the render unit dict.
    """
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )
    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
          "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
        db_path=db,
    )
    unit = units[0]

    # Create fake provider video artifact
    fake_video = tmp_path / f"{label}_provider.mp4"
    fake_video.write_bytes(b"fake provider video" * 100)
    art = register_artifact(prod_id, fake_video, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    # Run QA
    run_render_unit_qa(prod_id, unit["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
    }, db_path=db)

    # Always create a provider_job for hero units (needed for syncnet validation and compensated artifacts)
    conn = _db.connect(db)
    job_id = f"pj_{uuid.uuid4().hex[:8]}"

    if with_compensated:
        comp_path = tmp_path / f"{label}_compensated.mp4"
        comp_path.write_bytes(b"compensated hero video" * 100)
        conn.execute(
            """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, prod_id, unit["id"], "seedance", "generate_lipsync", "completed",
             f"idemp_{job_id}", str(comp_path))
        )
    else:
        conn.execute(
            """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (job_id, prod_id, unit["id"], "seedance", "generate_lipsync", "completed",
             f"idemp_{job_id}")
        )

    # Add SyncNet validation on provider_job if requested
    # Note: Validation must be subject_type='provider_job' and subject_id=job_id
    if with_syncnet:
        val_id = f"val_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (val_id, prod_id, "provider_job", job_id, "syncnet_offset", "pass",
             '{"offset_ms": 10}', _db._now())
        )
    conn.close()

    return unit


def _make_broll_render_unit(prod_id, db, tmp_path, label="B001"):
    """Helper: create b-roll render unit (not hero).

    Returns the render unit dict.
    """
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )
    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "generated_video",
          "audio_policy": "BROLL_FLEX", "final_audio_source": "none",
          "provider_audio_usage": "discarded",
          "visual_function": "explain", "narrative_claim": "test claim",
          "information_to_show": "test info", "viewer_takeaway": "test takeaway",
          "required_action": "action", "distinctness_requirement": "distinct",
          "semantic_acceptance_criteria": "criteria", "concept_key": "test_key"}],
        db_path=db,
    )
    unit = units[0]

    fake_video = tmp_path / f"{label}.mp4"
    fake_video.write_bytes(b"fake b-roll video" * 100)
    art = register_artifact(prod_id, fake_video, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    run_render_unit_qa(prod_id, unit["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True,
    }, db_path=db)

    return unit


class TestCompensatedHeroArtifactCoreInvariant:
    """Prove core invariant: hero_island units require compensated artifacts."""

    def test_hero_with_compensated_passes_validation(self, db, prod, tmp_path):
        """Hero unit WITH compensated artifact path should pass validation."""
        _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=True, with_syncnet=True)

        # This should NOT raise
        inputs = build_assembly_inputs(prod["id"], db_path=db)
        assert inputs["production_id"] == prod["id"]
        assert len(inputs["clips"]) == 1

    def test_hero_without_compensated_blocks_assembly(self, db, prod, tmp_path):
        """Hero unit WITHOUT compensated artifact path should BLOCK assembly."""
        _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=False, with_syncnet=True)

        # This SHOULD raise with explicit BLOCKED_ error
        with pytest.raises(AssemblyError, match="BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_broll_without_compensated_passes_validation(self, db, prod, tmp_path):
        """B-roll unit should NOT require compensated artifact (should pass)."""
        _make_broll_render_unit(prod["id"], db, tmp_path)

        # This should NOT raise (b-roll doesn't need compensated artifact)
        inputs = build_assembly_inputs(prod["id"], db_path=db)
        assert inputs["production_id"] == prod["id"]


class TestCompensatedHeroArtifactErrors:
    """Prove explicit error handling with BLOCKED_ prefix."""

    def test_missing_path_error_message(self, db, prod, tmp_path):
        """Error message must contain BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING."""
        _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=False, with_syncnet=True)

        try:
            build_assembly_inputs(prod["id"], db_path=db)
            assert False, "Should have raised AssemblyError"
        except AssemblyError as e:
            error_msg = str(e)
            assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING" in error_msg
            assert "hero_island" in error_msg
            assert "compensated_artifact_path" in error_msg

    def test_missing_file_error_message(self, db, prod, tmp_path):
        """Error for missing compensated file must contain BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING."""
        unit = _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=False, with_syncnet=True)

        # Add provider_job pointing to non-existent file
        conn = _db.connect(db)
        job_id = f"pj_{uuid.uuid4().hex[:8]}"
        fake_missing_path = tmp_path / "nonexistent_compensated.mp4"
        conn.execute(
            """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, prod["id"], unit["id"], "seedance", "generate_lipsync", "completed",
             f"idemp_{job_id}", str(fake_missing_path))
        )
        conn.close()

        try:
            build_assembly_inputs(prod["id"], db_path=db)
            assert False, "Should have raised AssemblyError"
        except AssemblyError as e:
            error_msg = str(e)
            assert "BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING" in error_msg
            assert "not found" in error_msg
            assert str(fake_missing_path) in error_msg

    def test_error_mentions_unit_id_and_label(self, db, prod, tmp_path):
        """Error message must include unit ID and label for debugging."""
        label = "HERO_TEST_LABEL"
        _make_hero_render_unit(prod["id"], db, tmp_path, label=label, with_compensated=False, with_syncnet=True)

        try:
            build_assembly_inputs(prod["id"], db_path=db)
            assert False, "Should have raised AssemblyError"
        except AssemblyError as e:
            error_msg = str(e)
            assert "render unit" in error_msg
            assert label in error_msg


class TestCompensatedHeroArtifactRegression:
    """Prove old behavior cannot occur (no silent fallback)."""

    def test_no_silent_fallback_to_raw_provider(self, db, prod, tmp_path):
        """Assembly must NOT silently fall back to raw provider video."""
        _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=False, with_syncnet=True)

        # Must raise explicitly, not continue with raw video
        with pytest.raises(AssemblyError, match="BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_raw_provider_video_blocked_explicitly(self, db, prod, tmp_path):
        """Error message must explicitly state raw provider video cannot be used."""
        _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=False, with_syncnet=True)

        try:
            build_assembly_inputs(prod["id"], db_path=db)
            assert False, "Should have raised AssemblyError"
        except AssemblyError as e:
            error_msg = str(e)
            assert "Raw provider video cannot be used" in error_msg

    def test_multiple_hero_units_all_require_compensated(self, db, prod, tmp_path):
        """Multiple hero units: ALL must have compensated artifacts (block on first missing)."""
        # First hero WITH compensated and SyncNet (should pass these checks)
        _make_hero_render_unit(prod["id"], db, tmp_path, label="H001", with_compensated=True, with_syncnet=True)

        # Second hero WITH SyncNet but WITHOUT compensated (should block)
        _make_hero_render_unit(prod["id"], db, tmp_path, label="H002", with_compensated=False, with_syncnet=True)

        with pytest.raises(AssemblyError, match="BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING"):
            build_assembly_inputs(prod["id"], db_path=db)


class TestCompensatedHeroArtifactFileChecks:
    """Prove file existence is enforced for compensated artifacts."""

    def test_compensated_file_must_exist_on_disk(self, db, prod, tmp_path):
        """Compensated artifact file must exist on disk."""
        unit = _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=False, with_syncnet=True)

        # Add provider_job pointing to non-existent file
        conn = _db.connect(db)
        job_id = f"pj_{uuid.uuid4().hex[:8]}"
        missing_path = tmp_path / "missing_compensated.mp4"
        conn.execute(
            """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, prod["id"], unit["id"], "seedance", "generate_lipsync", "completed",
             f"idemp_{job_id}", str(missing_path))
        )
        conn.close()

        with pytest.raises(AssemblyError, match="BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_valid_compensated_file_passes_validation(self, db, prod, tmp_path):
        """Valid compensated file should pass validation."""
        _make_hero_render_unit(prod["id"], db, tmp_path, with_compensated=True, with_syncnet=True)

        # Verify the compensated file exists
        inputs = build_assembly_inputs(prod["id"], db_path=db)
        assert inputs["production_id"] == prod["id"]

        # Verify at least one clip has compensated path
        hero_clips = [c for c in inputs["clips"] if c.get("compensated_artifact_path")]
        assert len(hero_clips) >= 1
        assert all(Path(c["compensated_artifact_path"]).exists() for c in hero_clips)


class TestCompensatedHeroArtifactScope:
    """Prove enforcement scope is correct (hero units only)."""

    def test_broll_flex_not_affected(self, db, prod, tmp_path):
        """BROLL_FLEX units must not be affected by compensated artifact requirement."""
        _make_broll_render_unit(prod["id"], db, tmp_path, label="B001")

        # Should pass without compensated artifact
        inputs = build_assembly_inputs(prod["id"], db_path=db)
        assert inputs["production_id"] == prod["id"]

    def test_silent_graphic_not_affected(self, db, prod, tmp_path):
        """SILENT_GRAPHIC units must not be affected by compensated artifact requirement."""
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "G001", "start_ms": 0, "end_ms": 3000}],
            db_path=db,
        )
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "local_graphic",
              "audio_policy": "SILENT_GRAPHIC"}],
            db_path=db,
        )

        fake_graphic = tmp_path / "graphic.png"
        fake_graphic.write_bytes(b"fake graphic" * 50)
        art = register_artifact(prod["id"], fake_graphic, "local_graphic", db_path=db)
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)

        run_render_unit_qa(prod["id"], units[0]["id"], {
            "file_exists": True, "dimensions_ok": True,
        }, db_path=db)

        # Should pass without compensated artifact
        inputs = build_assembly_inputs(prod["id"], db_path=db)
        assert inputs["production_id"] == prod["id"]
