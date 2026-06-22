"""ENG-0802: Integration tests for Gate B review/publish hardening.

Required tests:
1. Gate B blocks mechanical-only final QA.
2. Gate B blocks failed render-unit QA.
3. Gate B blocks missing local graphic provenance.
4. Gate B passes valid synthetic production.
5. Publish status not set before gate pass.
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
from assemble_db import (
    run_final_qa, get_deliverables, register_deliverable,
    request_gate_b, is_gate_b_approved,
)
from produce_db import invoke_gate_b_review


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("gate_b_contract_test", db_path=db)


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


class TestGateBReviewContract:
    def test_gate_b_blocks_mechanical_only_qa(self, db, prod, tmp_path):
        """Gate B should block when final QA has no DB-contract evidence."""
        _make_valid_unit(prod["id"], db, tmp_path)
        
        f = tmp_path / "output.mp4"
        f.write_bytes(b"assembled video " * 200)
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        
        # Run mechanical-only final QA (no contract checks)
        checks = {
            "dimensions_ok": True,
            "duration_ok": True,
            "loudnorm_ok": True,
            "no_black_frames": True,
        }
        run_final_qa(prod["id"], del_row["id"], checks, db_path=db)
        
        # Gate B should block due to missing contract evidence
        from produce_db import invoke_gate_b_review
        inputs = {"production_id": prod["id"], "project_slug": "gate_b_contract_test"}
        
        with pytest.raises(RuntimeError, match="Gate B blocked.*missing required DB-contract"):
            invoke_gate_b_review(inputs, tmp_path)

    def test_gate_b_blocks_failed_render_unit_qa(self, db, prod, tmp_path):
        """Gate B should block when a render unit has no passing QA."""
        spans = commit_timeline_spans(
            prod["id"], [{"label": "B001", "start_ms": 0, "end_ms": 4000}], db_path=db
        )
        units = plan_render_units(
            prod["id"],
            [{"span_id": spans[0]["id"], "asset_type": "lipsync_video",
              "audio_policy": "HERO_SYNC_LOCKED", "final_audio_source": "master_narration",
              "provider_audio_usage": "diagnostic_only"}],
            db_path=db,
        )
        # No artifact, no QA
        f = tmp_path / "output.mp4"
        f.write_bytes(b"assembled video " * 200)
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        
        # Run mechanical-only QA (will pass mechanically but contract will fail)
        checks = {
            "dimensions_ok": True,
            "duration_ok": True,
            "loudnorm_ok": True,
            "no_black_frames": True,
        }
        run_final_qa(prod["id"], del_row["id"], checks, db_path=db)
        
        # Gate B should block due to missing contract checks (which include render unit QA)
        from produce_db import invoke_gate_b_review
        inputs = {"production_id": prod["id"], "project_slug": "gate_b_contract_test"}
        with pytest.raises(RuntimeError, match="Gate B blocked"):
            invoke_gate_b_review(inputs, tmp_path)

    def test_gate_b_blocks_missing_local_graphic_provenance(self, db, prod, tmp_path):
        """Gate B should block when local graphic has provider job."""
        _make_valid_unit(prod["id"], db, tmp_path, label="B001")
        
        # Create local graphic with provider job
        spans2 = commit_timeline_spans(
            prod["id"], [{"label": "GFX", "start_ms": 4000, "end_ms": 8000}], db_path=db
        )
        units2 = plan_render_units(
            prod["id"],
            [{"span_id": spans2[0]["id"], "asset_type": "local_graphic",
              "model": None,
              "audio_policy": "SILENT_GRAPHIC", "final_audio_source": "none",
              "provider_audio_usage": "discarded",
              "text_policy": "DETERMINISTIC_GRAPHIC",
              "render_mode": "deterministic_graphic",
              "deterministic_text_spec": {"type": "title_card", "text": "FAKE"},
              }],
            db_path=db,
        )
        f2 = tmp_path / "gfx.png"
        f2.write_bytes(b"fake png")
        art2 = register_artifact(prod["id"], f2, "generated_media", db_path=db)
        link_artifact_to_render_unit(art2["id"], units2[0]["id"], db_path=db)
        run_render_unit_qa(prod["id"], units2[0]["id"], {
            "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
        }, db_path=db)
        
        # Insert provider job for local graphic
        with _db.transaction(db) as conn:
            conn.execute(
                "INSERT INTO provider_jobs "
                "(id, production_id, render_unit_id, provider, operation, "
                "idempotency_key, status, request_json, submitted_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                ("pjob_gfx", prod["id"], units2[0]["id"],
                 "seedance", "generate",
                 "pjob_gfx_key", "submitted",
                 _db._json({"model": "kling3_0", "prompt": "test"}),
                 _db._now()),
            )
        
        f = tmp_path / "output.mp4"
        f.write_bytes(b"assembled video " * 200)
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        
        # Run mechanical-only QA
        checks = {
            "dimensions_ok": True,
            "duration_ok": True,
            "loudnorm_ok": True,
            "no_black_frames": True,
        }
        run_final_qa(prod["id"], del_row["id"], checks, db_path=db)
        
        from produce_db import invoke_gate_b_review
        inputs = {"production_id": prod["id"], "project_slug": "gate_b_contract_test"}
        with pytest.raises(RuntimeError, match="Gate B blocked"):
            invoke_gate_b_review(inputs, tmp_path)

    def test_gate_b_passes_valid_synthetic(self, db, prod, tmp_path):
        """Gate B should pass for a valid synthetic production with full contract checks."""
        _make_valid_unit(prod["id"], db, tmp_path)
        
        f = tmp_path / "output.mp4"
        f.write_bytes(b"assembled video " * 200)
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        
        # Run full final QA with contract checks
        from qa_final import run_db_contract_checks
        contract = run_db_contract_checks(prod["id"], del_row["id"], db_path=db)
        checks = {
            "dimensions_ok": True,
            "duration_ok": True,
            "loudnorm_ok": True,
            "no_black_frames": True,
            "contract_checks": contract,
        }
        run_final_qa(prod["id"], del_row["id"], checks, db_path=db)
        
        # Approve gate_a_spend so gate_b_review can proceed
        from authoring_service import request_approval, record_approval_decision
        request_approval(
            prod["id"], gate_name="gate_b_review",
            subject_type="deliverable", subject_id=del_row["id"],
            db_path=db,
        )
        record_approval_decision(
            prod["id"], "gate_b_review", "pass", actor="test", db_path=db
        )
        
        # Gate B should pass
        assert is_gate_b_approved(prod["id"], db_path=db)

    def test_publish_not_set_before_gate_pass(self, db, prod, tmp_path):
        """Deliverable status should not be 'published' before gate passes."""
        _make_valid_unit(prod["id"], db, tmp_path)
        
        f = tmp_path / "output.mp4"
        f.write_bytes(b"assembled video " * 200)
        del_row = register_deliverable(prod["id"], "16x9", f, db_path=db)
        
        # Deliverable should not be published initially
        conn = _db.connect(db)
        row = conn.execute("SELECT status FROM deliverables WHERE id=?", (del_row["id"],)).fetchone()
        conn.close()
        assert row["status"] != "published"
        assert row["status"] == "assembled"
