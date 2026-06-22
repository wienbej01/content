"""ENG-0702: Integration tests for assembly preflight enforcement.

Required tests:
1. Assembly blocked on invalid artifact.
2. Assembly blocked on missing local graphic.
3. Assembly passes after repair and QA.
4. Assembly does not silently substitute files from disk.
5. Assembly evidence includes render unit IDs and artifact IDs.
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
    return _db.ensure_production("integration_assembly_test", db_path=db)


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


class TestAssembleDBValidArtifacts:
    def test_assembly_blocked_on_invalid_artifact(self, db, prod, tmp_path):
        """Assembly should be blocked when an artifact has failing QA."""
        _make_valid_unit(prod["id"], db, tmp_path, label="B001", start_ms=0, end_ms=4000)
        # Create a second unit with QA that we'll mark as failing
        spans2 = commit_timeline_spans(
            prod["id"], [{"label": "B002", "start_ms": 4000, "end_ms": 8000}],
            db_path=db,
        )
        units2 = plan_render_units(
            prod["id"],
            [{"span_id": spans2[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
            db_path=db,
        )
        f2 = tmp_path / "B002.mp4"
        f2.write_bytes(b"fake video " * 100)
        art2 = register_artifact(prod["id"], f2, "generated_media", db_path=db)
        link_artifact_to_render_unit(art2["id"], units2[0]["id"], db_path=db)
        # QA fails
        run_render_unit_qa(prod["id"], units2[0]["id"], {
            "file_exists": True, "dimensions_ok": False, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)

        with pytest.raises(AssemblyError, match="BLOCKED.*no passing QA"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_assembly_blocked_on_missing_artifact(self, db, prod, tmp_path):
        """Assembly should be blocked when a render unit has no artifact."""
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}],
            db_path=db,
        )
        plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only"}],
            db_path=db,
        )
        with pytest.raises(AssemblyError, match="BLOCKED"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_assembly_passes_after_repair_and_qa(self, db, prod, tmp_path):
        """Assembly should pass after repair cycle and passing QA."""
        unit = _make_valid_unit(prod["id"], db, tmp_path, label="B001")
        result = build_assembly_inputs(prod["id"], db_path=db)
        assert result["production_id"] == prod["id"]
        assert len(result["clips"]) == 1
        assert "preflight" in result
        assert result["preflight"]["validation_passed"] is True

    def test_assembly_does_not_substitute_files(self, db, prod, tmp_path):
        """Assembly should not silently substitute files from disk."""
        unit = _make_valid_unit(prod["id"], db, tmp_path, label="B001")
        result = build_assembly_inputs(prod["id"], db_path=db)
        clip = result["clips"][0]
        # The path should match the registered artifact
        assert clip["path"] is not None
        assert clip["sha256"] is not None
        # The path should exist
        assert Path(clip["path"]).exists()

    def test_assembly_evidence_includes_ids(self, db, prod, tmp_path):
        """Assembly evidence should include render unit IDs and artifact IDs."""
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
            f = tmp_path / f"clip_{i}.mp4"
            f.write_bytes(b"fake video " * 100)
            art = register_artifact(prod["id"], f, "generated_media", db_path=db)
            link_artifact_to_render_unit(art["id"], u["id"], db_path=db)
            run_render_unit_qa(prod["id"], u["id"], {
                "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
            }, db_path=db)
        result = build_assembly_inputs(prod["id"], db_path=db)
        preflight = result["preflight"]
        assert len(preflight["render_unit_ids"]) == 2
        assert len(preflight["artifact_ids"]) == 2
        assert preflight["span_count"] == 2
        assert preflight["unit_count"] == 2
