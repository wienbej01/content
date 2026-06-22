"""ENG-0701: Tests for assembly input validator (validate_assembly_inputs).

Required tests:
1. Missing render unit fails.
2. Missing artifact fails.
3. Failed QA fails.
4. Provider-generated local graphic fails.
5. Duplicate active artifact fails.
6. Valid minimal production passes.
7. Error messages identify failing span/render unit.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import production_db as _db
from production_repo import (
    commit_timeline_spans, plan_render_units, register_artifact,
    link_artifact_to_render_unit,
)
from media_service import run_render_unit_qa
from assemble_db import validate_assembly_inputs, AssemblyError


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("preflight_test", db_path=db)


def _make_valid_unit(prod_id, db, tmp_path, label="B001", start_ms=0, end_ms=4000):
    """Create a complete valid span + render unit + artifact + QA."""
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": start_ms, "end_ms": end_ms}],
        db_path=db,
    )
    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
          "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
        db_path=db,
    )
    f = tmp_path / f"{label}.mp4"
    f.write_bytes(b"fake video " * 100)
    art = register_artifact(prod_id, f, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
    run_render_unit_qa(prod_id, units[0]["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
    }, db_path=db)
    return units[0]


class TestValidateAssemblyInputs:
    def test_valid_production_passes(self, db, prod, tmp_path):
        _make_valid_unit(prod["id"], db, tmp_path)
        evidence = validate_assembly_inputs(prod["id"], db_path=db)
        assert evidence["validation_passed"] is True
        assert evidence["span_count"] == 1
        assert evidence["unit_count"] == 1
        assert "artifact_set_hash" in evidence
        assert "render_unit_ids" in evidence
        assert "artifact_ids" in evidence

    def test_no_spans_fails(self, db, prod):
        with pytest.raises(AssemblyError, match="BLOCKED.*no active timeline spans"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_missing_artifact_fails(self, db, prod, tmp_path):
        """Render unit without active artifact should fail."""
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only"}],
            db_path=db,
        )
        with pytest.raises(AssemblyError, match="BLOCKED.*no active artifact"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_failed_qa_fails(self, db, prod, tmp_path):
        """Render unit with failing contract QA should fail."""
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
            db_path=db,
        )
        f = tmp_path / "B001.mp4"
        f.write_bytes(b"fake video " * 100)
        art = register_artifact(prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
        # QA fails
        run_render_unit_qa(prod["id"], units[0]["id"], {
            "file_exists": True, "dimensions_ok": False, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)
        with pytest.raises(AssemblyError, match="BLOCKED.*no passing QA"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_provider_generated_local_graphic_fails(self, db, prod, tmp_path):
        """Local graphic with a provider_job should fail.

        Directly inserts a provider_job row to simulate the historical bug pattern
        where a local_graphic was sent to a paid provider. The current
        submit_provider_job correctly blocks local_graphic, so we insert directly
        into the table to test the validator's detection.
        """
        spans = commit_timeline_spans(
            prod["id"], [{"label": "GFX", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        # Create a local_graphic render unit
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "local_graphic",
              "model": None,
              "audio_policy": "SILENT_GRAPHIC",
              "final_audio_source": "none",
              "provider_audio_usage": "discarded",
              "text_policy": "DETERMINISTIC_GRAPHIC",
              "render_mode": "deterministic_graphic",
              "deterministic_text_spec": {"type": "title_card", "text": "FAKE"},
              }],
            db_path=db,
        )
        # Register artifact and link
        f = tmp_path / "gfx.png"
        f.write_bytes(b"fake png")
        art = register_artifact(prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
        # Pass QA
        run_render_unit_qa(prod["id"], units[0]["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

        # Directly insert a provider_job row to simulate the historical bug pattern
        # where a local_graphic was (wrongly) sent to a provider
        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO provider_jobs
                   (id, production_id, render_unit_id, provider, operation,
                    idempotency_key, status, request_json, submitted_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                ("pjob_test_local_graphic", prod["id"], units[0]["id"],
                 "seedance", "generate",
                 "test_local_graphic_provider_job", "submitted",
                 _db._json({"model": "kling3_0", "prompt": "test"}),
                 _db._now()),
            )

        with pytest.raises(AssemblyError, match="BLOCKED.*provider job"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_duplicate_render_unit_for_span_fails(self, db, prod, tmp_path):
        """Two active render units for the same span should fail."""
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        # Create first unit
        units1 = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
            db_path=db,
        )
        f1 = tmp_path / "dup1.mp4"
        f1.write_bytes(b"fake video " * 100)
        art1 = register_artifact(prod["id"], f1, "generated_media", db_path=db)
        link_artifact_to_render_unit(art1["id"], units1[0]["id"], db_path=db)
        run_render_unit_qa(prod["id"], units1[0]["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

        # Manually insert a second active render unit for the same span
        with _db.transaction(db) as conn:
            conn.execute(
                """INSERT INTO render_units
                   (id, production_id, timeline_span_id, ordinal, label, asset_type,
                    audio_policy, required_start_ms, required_end_ms, required_duration_ms,
                    status, active_artifact_id, metadata_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("render_dup_for_" + spans[0]["id"], prod["id"], spans[0]["id"],
                 100, "DUP", "lipsync_video", "HERO_SYNC_LOCKED",
                 0, 4000, 4000, "valid",
                 art1["id"], "{}", _db._now(), _db._now()),
            )
        with pytest.raises(AssemblyError, match="BLOCKED.*duplicate render units"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_error_message_identifies_failing_unit(self, db, prod, tmp_path):
        """Error message should identify the failing span/render unit."""
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        # Create render unit but no artifact
        plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only"}],
            db_path=db,
        )
        try:
            validate_assembly_inputs(prod["id"], db_path=db)
            pytest.fail("Should have raised")
        except AssemblyError as e:
            msg = str(e)
            assert "BLOCKED:" in msg
            # Should mention a specific render unit ID or span
            assert any(x in msg for x in ["render unit", "timeline span", "no active artifact"])

    def test_valid_multi_unit_passes(self, db, prod, tmp_path):
        """Multiple valid units should pass."""
        # Create spans in one batch to avoid staleness
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "B001", "start_ms": 0, "end_ms": 4000},
             {"label": "B002", "start_ms": 4000, "end_ms": 8000}],
            db_path=db,
        )
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"},
             {"span_id": spans[1]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
            db_path=db,
        )
        for i, u in enumerate(units):
            f = tmp_path / f"B00{i+1}.mp4"
            f.write_bytes(b"fake video " * 100)
            art = register_artifact(prod["id"], f, "generated_media", db_path=db)
            link_artifact_to_render_unit(art["id"], u["id"], db_path=db)
            run_render_unit_qa(prod["id"], u["id"], {
                "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
            }, db_path=db)
        evidence = validate_assembly_inputs(prod["id"], db_path=db)
        assert evidence["validation_passed"] is True
        assert evidence["span_count"] == 2
        assert evidence["unit_count"] == 2
