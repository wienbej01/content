"""ENG-0703: Tests for assembly timeline heuristic validation.

Required tests:
1. 48 seconds of consecutive identical local graphic spans fails preflight.
2. 10-second valid local graphic passes.
3. Identical consecutive render unit IDs fail preflight.
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
from render_graphics import render_local_graphic_render_unit


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("timeline_heuristic_test", db_path=db)


def _make_local_graphic_unit(prod_id, db, tmp_path, label="GFX", start_ms=0, end_ms=5000,
                              render_func=False):
    """Create a valid local_graphic render unit with all QA passing."""
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": start_ms, "end_ms": end_ms}],
        db_path=db,
    )
    dts = {"type": "title_card", "text": f"TEXT {label}", "headline": f"TEXT {label}"}
    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "local_graphic",
          "model": None,
          "audio_policy": "SILENT_GRAPHIC",
          "final_audio_source": "none",
          "provider_audio_usage": "discarded",
          "text_policy": "DETERMINISTIC_GRAPHIC",
          "render_mode": "deterministic_graphic",
          "deterministic_text_spec": dts,
          }],
        db_path=db,
    )

    if render_func:
        # Use the actual render function to create the artifact
        result_path = render_local_graphic_render_unit(db, prod_id, units[0]["id"])
        assert Path(result_path).exists()
    else:
        # Create a synthetic artifact file
        f = tmp_path / f"{label}.png"
        f.write_bytes(b"fake png")
        art = register_artifact(prod_id, f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)

    # Pass QA
    run_render_unit_qa(prod_id, units[0]["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
    }, db_path=db)
    return units[0]


def _make_valid_unit(prod_id, db, tmp_path, label="B001", start_ms=0, end_ms=4000):
    """Create a complete valid non-graphic render unit."""
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


class TestTimelineHeuristics:
    def test_consecutive_identical_local_graphic_fails(self, db, prod, tmp_path):
        """Two consecutive local_graphic units with the same label should fail,
        simulating repeated looped graphics."""
        # Create spans in one batch so they're not superseded
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "GFX_REPEAT", "start_ms": 0, "end_ms": 5000},
             {"label": "GFX_REPEAT", "start_ms": 5000, "end_ms": 10000}],
            db_path=db,
        )
        # Both spans mapped to the same graphic content (same deterministic_text_spec)
        dts = {"type": "title_card", "text": "SAME TEXT", "headline": "SAME TEXT"}
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "local_graphic",
              "model": None,
              "audio_policy": "SILENT_GRAPHIC",
              "final_audio_source": "none",
              "provider_audio_usage": "discarded",
              "text_policy": "DETERMINISTIC_GRAPHIC",
              "render_mode": "deterministic_graphic",
              "deterministic_text_spec": dts,
              "label": "GFX_REPEAT",
              },
             {"span_id": spans[1]["id"], "asset_type": "local_graphic",
              "model": None,
              "audio_policy": "SILENT_GRAPHIC",
              "final_audio_source": "none",
              "provider_audio_usage": "discarded",
              "text_policy": "DETERMINISTIC_GRAPHIC",
              "render_mode": "deterministic_graphic",
              "deterministic_text_spec": dts,
              "label": "GFX_REPEAT",
              }],
            db_path=db,
        )
        for u in units:
            f = tmp_path / f"{u['id']}.png"
            f.write_bytes(b"fake png")
            art = register_artifact(prod["id"], f, "generated_media", db_path=db)
            link_artifact_to_render_unit(art["id"], u["id"], db_path=db)
            run_render_unit_qa(prod["id"], u["id"], {
                "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
            }, db_path=db)

        with pytest.raises(AssemblyError, match="BLOCKED.*identical consecutive local_graphic"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_ten_second_local_graphic_passes(self, db, prod, tmp_path):
        """A valid local_graphic under 15s should pass."""
        # Two consecutive local_graphic with DIFFERENT IDs should be fine
        _make_local_graphic_unit(prod["id"], db, tmp_path, label="GFX1",
                                  start_ms=0, end_ms=10000)
        _make_local_graphic_unit(prod["id"], db, tmp_path, label="GFX2",
                                  start_ms=10000, end_ms=20000)
        evidence = validate_assembly_inputs(prod["id"], db_path=db)
        assert evidence["validation_passed"] is True

    def test_micro_cut_fails(self, db, prod, tmp_path):
        """A render unit with duration < 1 second should fail."""
        # Create spans in one batch to avoid staleness
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "B001", "start_ms": 0, "end_ms": 4000},
             {"label": "B002", "start_ms": 4000, "end_ms": 4500}],
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
        with pytest.raises(AssemblyError, match="BLOCKED.*micro-cut"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_long_local_graphic_without_hold_fails(self, db, prod, tmp_path):
        """A local_graphic > 15s without 'hold' label should fail."""
        _make_local_graphic_unit(prod["id"], db, tmp_path, label="LONG_GFX",
                                  start_ms=0, end_ms=20000)
        with pytest.raises(AssemblyError, match="BLOCKED.*exceeds.*without.*hold"):
            validate_assembly_inputs(prod["id"], db_path=db)

    def test_long_local_graphic_with_hold_passes(self, db, prod, tmp_path):
        """A local_graphic > 15s with 'hold' in label should pass."""
        spans = commit_timeline_spans(
            prod["id"],
            [{"label": "hold_intro_title", "start_ms": 0, "end_ms": 20000}],
            db_path=db,
        )
        dts = {"type": "title_card", "text": "HOLD TEXT", "headline": "HOLD TEXT"}
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "local_graphic",
              "model": None,
              "audio_policy": "SILENT_GRAPHIC",
              "final_audio_source": "none",
              "provider_audio_usage": "discarded",
              "text_policy": "DETERMINISTIC_GRAPHIC",
              "render_mode": "deterministic_graphic",
              "deterministic_text_spec": dts,
              }],
            db_path=db,
        )
        f = tmp_path / "hold.png"
        f.write_bytes(b"fake png")
        art = register_artifact(prod["id"], f, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
        run_render_unit_qa(prod["id"], units[0]["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)
        evidence = validate_assembly_inputs(prod["id"], db_path=db)
        assert evidence["validation_passed"] is True
