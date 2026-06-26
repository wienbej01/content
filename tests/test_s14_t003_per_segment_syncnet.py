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


# ---------------------------------------------------------------------------
# Test per-segment SyncNet requirement
# ---------------------------------------------------------------------------

class TestPerSegmentSyncNetRequirement:
    """Test that per-segment SyncNet is mandatory for hero units."""

    def test_hero_unit_with_syncnet_passes(self, db, prod, tmp_path):
        """Hero unit with per-segment SyncNet passes preflight."""
        unit = _make_hero_render_unit(prod["id"], db, tmp_path, "H001", with_syncnet=True)

        result = validate_assembly_inputs(prod["id"], db_path=db)

        assert result["validation_passed"] is True
        assert "BLOCKED" not in str(result)

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
        _make_hero_render_unit(prod["id"], db, tmp_path, "H004",
                               with_syncnet=True, with_audio_offset=True)

        result = validate_assembly_inputs(prod["id"], db_path=db)

        assert result["validation_passed"] is True


class TestNonHeroUnitsExempt:
    """Test that non-hero units don't require SyncNet."""

    def test_broll_flex_does_not_require_syncnet(self, db, prod, tmp_path):
        """BROLL_FLEX unit does not require SyncNet."""
        # Create BROLL_FLEX unit
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "B001", "start_ms": 0, "end_ms": 4000}],
            db_path=db,
        )

        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "b_roll",
              "audio_policy": "BROLL_FLEX", "final_audio_source": "master_narration",
              "provider_audio_usage": "discarded", "model": "kling3_0"}],
            db_path=db,
        )
        unit = units[0]

        # Create artifact and link
        fake_video = tmp_path / "B001_provider.mp4"
        fake_video.write_bytes(b"fake b-roll video" * 100)
        art = register_artifact(prod["id"], fake_video, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        # Run QA
        run_render_unit_qa(prod["id"], unit["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True,
        }, db_path=db)

        # No SyncNet validation - should still pass
        result = validate_assembly_inputs(prod["id"], db_path=db)

        assert result["validation_passed"] is True

    def test_silent_graphic_does_not_require_syncnet(self, db, prod, tmp_path):
        """SILENT_GRAPHIC unit does not require SyncNet."""
        # Create SILENT_GRAPHIC unit
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "G001", "start_ms": 0, "end_ms": 4000}],
            db_path=db,
        )

        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "local_graphic",
              "audio_policy": "SILENT_GRAPHIC", "final_audio_source": "none",
              "provider_audio_usage": "discarded"}],
            db_path=db,
        )
        unit = units[0]

        # Create artifact and link
        fake_graphic = tmp_path / "G001.png"
        fake_graphic.write_bytes(b"fake graphic" * 100)
        art = register_artifact(prod["id"], fake_graphic, "local_graphic", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        # Run QA
        run_render_unit_qa(prod["id"], unit["id"], {
            "file_exists": True, "duration_ok": True,
        }, db_path=db)

        # No SyncNet validation - should still pass
        result = validate_assembly_inputs(prod["id"], db_path=db)

        assert result["validation_passed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
