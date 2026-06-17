"""Tests for Sprint 7: assemble_db.py
(DB-native assembly, deliverable registry, final QA + Gate B)
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
from authoring_service import request_approval, record_approval_decision
from media_service import run_render_unit_qa
from assemble_db import (
    build_assembly_inputs, AssemblyError,
    register_deliverable, get_deliverables,
    run_final_qa, request_gate_b, is_gate_b_approved,
    export_assembly_manifest,
)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("sprint7_test", db_path=db)


def _make_valid_render_unit(prod_id, db, tmp_path, label="B001"):
    """Helper: span + render unit + artifact + qa_passed."""
    spans = commit_timeline_spans(
        prod_id,
        [{"label": label, "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )
    units = plan_render_units(
        prod_id,
        [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
          "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration", "provider_audio_usage": "diagnostic_only", "model": "seedance_2_0"}],
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


class TestBuildAssemblyInputs:
    def test_builds_from_db(self, db, prod, tmp_path):
        _make_valid_render_unit(prod["id"], db, tmp_path)
        inputs = build_assembly_inputs(prod["id"], db_path=db)
        assert inputs["production_id"] == prod["id"]
        assert len(inputs["clips"]) == 1
        assert inputs["clips"][0]["asset_type"] == "lipsync_video"
        assert inputs["clips"][0]["path"] is not None

    def test_no_spans_raises(self, db, prod):
        with pytest.raises(AssemblyError, match="No active timeline spans"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_non_valid_unit_raises(self, db, prod, tmp_path):
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video", "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration", "provider_audio_usage": "diagnostic_only"}],
            db_path=db,
        )
        # unit status is 'ordered' (not valid) → should block
        with pytest.raises(AssemblyError, match="not valid"):
            build_assembly_inputs(prod["id"], db_path=db)

    def test_clips_in_ordinal_order(self, db, tmp_path):
        # Use separate production to avoid span superseding issue
        p = _db.ensure_production("sprint7_order", db_path=db)
        for i, label in enumerate(["B003", "B001", "B002"]):
            spans = commit_timeline_spans(
                p["id"],
                [{"label": label, "start_ms": i * 4000, "end_ms": (i + 1) * 4000}],
                db_path=db,
            )
            units = plan_render_units(
                p["id"],
                [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
                  "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration", "provider_audio_usage": "diagnostic_only"}],
                db_path=db,
            )
            f = tmp_path / f"clip_{i}.mp4"
            f.write_bytes(b"video")
            art = register_artifact(p["id"], f, "generated_media", db_path=db)
            link_artifact_to_render_unit(art["id"], units[0]["id"], db_path=db)
            run_render_unit_qa(p["id"], units[0]["id"], {
                "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
            }, db_path=db)

        inputs = build_assembly_inputs(p["id"], db_path=db)
        ordinals = [c["ordinal"] for c in inputs["clips"]]
        assert ordinals == sorted(ordinals)


class TestDeliverableRegistry:
    def test_register_deliverable(self, db, prod, tmp_path):
        f = tmp_path / "output_16x9.mp4"
        f.write_bytes(b"assembled video " * 200)
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        assert del_row["variant"] == "16x9"
        assert del_row["status"] == "assembled"

    def test_idempotent_registration(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video data")
        d1 = register_deliverable(prod["id"], "16x9", f, db_path=db)
        d2 = register_deliverable(prod["id"], "16x9", f, db_path=db)
        assert d1["id"] == d2["id"]

    def test_multiple_variants(self, db, prod, tmp_path):
        f16 = tmp_path / "16x9.mp4"
        f16.write_bytes(b"16x9 video")
        f9 = tmp_path / "9x16.mp4"
        f9.write_bytes(b"9x16 video")
        register_deliverable(prod["id"], "16x9", f16, db_path=db)
        register_deliverable(prod["id"], "9x16", f9, db_path=db)
        deliverables = get_deliverables(prod["id"], db_path=db)
        variants = {d["variant"] for d in deliverables}
        assert "16x9" in variants
        assert "9x16" in variants


class TestFinalQA:
    def test_passing_qa_advances_status(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        checks = {
            "dimensions_ok": True, "duration_ok": True,
            "loudnorm_ok": True, "no_black_frames": True,
        }
        val = run_final_qa(prod["id"], del_row["id"], checks, db_path=db)
        assert val["status"] == "pass"
        deliverables = get_deliverables(prod["id"], db_path=db)
        assert deliverables[0]["status"] == "qa_passed"

    def test_failing_qa_marks_qa_failed(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        val = run_final_qa(prod["id"], del_row["id"], {"loudnorm_ok": False}, db_path=db)
        assert val["status"] == "fail"
        deliverables = get_deliverables(prod["id"], db_path=db)
        assert deliverables[0]["status"] == "qa_failed"


class TestGateB:
    def test_gate_b_requires_qa_validation(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        with pytest.raises(ValueError, match="qa_final validation"):
            request_gate_b(prod["id"], del_row["id"], db_path=db)

    def test_gate_b_request_creates_approval(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video data 123")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        run_final_qa(prod["id"], del_row["id"], {
            "dimensions_ok": True, "duration_ok": True,
            "loudnorm_ok": True, "no_black_frames": True,
        }, db_path=db)
        ar = request_gate_b(prod["id"], del_row["id"], db_path=db)
        assert ar["gate_name"] == "gate_b_review"
        assert ar["status"] == "pending"

    def test_gate_b_pass(self, db, prod, tmp_path):
        f = tmp_path / "output.mp4"
        f.write_bytes(b"video data 456")
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        run_final_qa(prod["id"], del_row["id"], {
            "dimensions_ok": True, "duration_ok": True,
            "loudnorm_ok": True, "no_black_frames": True,
        }, db_path=db)
        request_gate_b(prod["id"], del_row["id"], db_path=db)
        record_approval_decision(prod["id"], "gate_b_review", "pass", db_path=db)
        assert is_gate_b_approved(prod["id"], db_path=db)

    def test_gate_b_not_approved_by_default(self, db, prod):
        assert not is_gate_b_approved(prod["id"], db_path=db)


class TestJSONExport:
    def test_export_manifest(self, db, prod, tmp_path):
        import json
        _make_valid_render_unit(prod["id"], db, tmp_path)
        out = tmp_path / "manifest.json"
        export_assembly_manifest(prod["id"], out, db_path=db)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "clips" in data
        assert data["production_id"] == prod["id"]
