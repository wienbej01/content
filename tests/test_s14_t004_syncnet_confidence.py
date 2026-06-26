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
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H003",
            hero_framing="close",
            offset_ms=20.0,  # Within 30ms threshold
            confidence=2.5,  # Above 2.0 threshold
        )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True


class TestHeroFramingPolicySelection:
    """Tests for hero framing to policy name mapping."""

    def test_medium_framing_uses_medium_policy(self, prod, db, tmp_path):
        """Hero unit with medium framing should use medium_hero policy (40ms threshold)."""
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H004",
            hero_framing="medium",
            offset_ms=35.0,  # OK for medium (40ms), would FAIL for close (30ms)
            confidence=2.5,
        )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True

    def test_wide_framing_uses_medium_policy(self, prod, db, tmp_path):
        """Hero unit with wide framing should use medium_hero policy (wide maps to medium)."""
        unit = _make_hero_render_unit(
            prod["id"], db, tmp_path,
            label="H005",
            hero_framing="wide",
            offset_ms=35.0,  # OK for medium (40ms)
            confidence=2.5,
        )

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True

    def test_missing_framing_defaults_to_close(self, prod, db, tmp_path):
        """Hero unit with missing hero_framing should default to close_hero policy."""
        # Create unit with NO hero_framing
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "H006", "start_ms": 0, "end_ms": 4000}],
            db_path=db,
        )

        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],  # NO hero_framing
            db_path=db,
        )
        unit = units[0]

        # Create fake video artifact
        fake_video = tmp_path / "H006_provider.mp4"
        fake_video.write_bytes(b"fake provider video" * 100)
        art = register_artifact(prod["id"], fake_video, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        # Run QA
        run_render_unit_qa(prod["id"], unit["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

        # Create provider_job with compensated artifact
        with _db.transaction(db) as conn:
            job_id = f"pj_{uuid.uuid4().hex[:8]}"
            comp_path = tmp_path / "H006_compensated.mp4"
            comp_path.write_bytes(b"compensated hero video" * 100)
            conn.execute(
                """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path, submitted_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (job_id, prod["id"], unit["id"], "seedance", "generate_lipsync", "completed",
                 f"idemp_{job_id}", str(comp_path))
            )

            # Add SyncNet validation with offset that's OK for close (25ms)
            val_id = f"val_{uuid.uuid4().hex[:8]}"
            conn.execute(
                """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (val_id, prod["id"], "render_unit", unit["id"], "syncnet_offset", "pass",
                 json.dumps({"offset_ms": 25.0, "confidence": 2.5}), _db._now())
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
        """Non-hero units (BROLL_FLEX) should bypass SyncNet confidence check."""
        # Create B-roll render unit
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "B001", "start_ms": 0, "end_ms": 4000}],
            db_path=db,
        )

        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "broll_video",
              "audio_policy": "BROLL_FLEX", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only"}],
            db_path=db,
        )
        unit = units[0]

        # Create fake video artifact
        fake_video = tmp_path / "B001_broll.mp4"
        fake_video.write_bytes(b"fake broll video" * 100)
        art = register_artifact(prod["id"], fake_video, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

        # Run QA
        run_render_unit_qa(prod["id"], unit["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

        result = validate_assembly_inputs(prod["id"], db_path=db)
        assert result is not None
        assert result.get("validation_passed") is True
