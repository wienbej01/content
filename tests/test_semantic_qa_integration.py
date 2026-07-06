"""TKT-202: Integration tests for semantic QA dispatch in media_service.py.

Tests:
1. Fixture backend + generated_video records semantic_role_qa pass evidence
2. Fixture backend evidence satisfies assembly semantic gate
3. SEMANTIC_QA_BACKEND=none records fail-closed evidence (INV-3)
4. YT_TEST_MODE=1 keeps existing auto-pass behavior unchanged
5. qa_media_contract return is unaffected by semantic QA
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
import semantic_role_qa as sqa
import assemble_db
from production_repo import register_artifact, plan_render_units, link_artifact_to_render_unit


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("tkt202_integration", db_path=db)


@pytest.fixture
def test_video(tmp_path):
    video_path = tmp_path / "test_broll.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=3:r=30",
        "-pix_fmt", "yuv420p", str(video_path),
    ], capture_output=True, timeout=30)
    if not video_path.exists():
        pytest.skip("ffmpeg not available")
    return video_path


def _create_generated_video_unit(prod_id, video_path, db, label="B001",
                                  visual_role="broll_evidence"):
    """Helper: create a generated_video render unit with linked artifact."""
    art = register_artifact(prod_id, video_path, "generated_video", db_path=db)

    span_id = _db._id("span")
    with _db.transaction(db) as conn:
        conn.execute(
            """INSERT INTO timeline_spans
               (id, production_id, ordinal, label, start_ms, end_ms, duration_ms, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            (span_id, prod_id, 0, label, 0, 4000, 4000, "active"),
        )

    units = plan_render_units(prod_id, [{
        "span_id": span_id,
        "asset_type": "generated_video",
        "audio_policy": "BROLL_FLEX",
        "final_audio_source": "master_narration",
        "provider_audio_usage": "diagnostic_only",
        "model": "seedance_2_0",
        "visual_role": visual_role,
        "narrative_claim": "Test claim about productivity",
        "semantic_acceptance_criteria": "Shows a person working at a desk",
        "visual_function": "demonstrate",
        "information_to_show": "A desk with a person working",
        "viewer_takeaway": "Working at a desk is productive",
        "required_action": "person typing at desk",
        "distinctness_requirement": "standard office desk scene",
        "concept_key": "desk_work_productivity",
        "concept_hash": "desk_work_productivity",
    }], db_path=db)
    unit = units[0]

    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    with _db.transaction(db) as conn:
        conn.execute(
            "UPDATE render_units SET status='valid', label=?, visual_role=? WHERE id=?",
            (label, visual_role, unit["id"]),
        )

    return {"unit_id": unit["id"], "artifact_uri": art["uri"]}


class TestSemanticQADispatch:
    """Integration tests for run_contract_media_qa semantic QA dispatch."""

    def test_fixture_backend_records_pass_evidence(self, prod, test_video, db):
        """Fixture backend records semantic_role_qa pass evidence for generated_video."""
        unit = _create_generated_video_unit(prod["id"], test_video, db)

        os.environ["SEMANTIC_QA_BACKEND"] = "fixture"
        # Ensure production mode (not YT_TEST_MODE)
        os.environ.pop("YT_TEST_MODE", None)

        from media_service import run_contract_media_qa
        validation = run_contract_media_qa(db, prod["id"], unit["unit_id"])

        # Verify qa_media_contract validation returned (unchanged dispatch)
        assert validation["validator_name"] == "qa_media_contract"
        assert validation["status"] == "pass"

        # Verify semantic_role_qa pass evidence was recorded
        conn = _db.connect(db)
        sqa_rows = conn.execute(
            """SELECT * FROM validations
               WHERE subject_id=? AND validator_name=?
               ORDER BY created_at DESC""",
            (unit["unit_id"], sqa.SEMANTIC_ROLE_QA_VALIDATOR),
        ).fetchall()
        conn.close()

        assert len(sqa_rows) > 0, "semantic_role_qa evidence must exist"
        assert sqa_rows[0]["status"] == "pass"
        ev = json.loads(sqa_rows[0]["evidence_json"])
        assert ev["visual_role"] == "broll_evidence"
        assert ev["result"] == "pass"
        assert ev["details"]["backend"] == "fixture"

    def test_assembly_semantic_gate_satisfied(self, prod, test_video, db):
        """Fixture backend evidence satisfies assembly validate_semantic_role_qa."""
        unit = _create_generated_video_unit(prod["id"], test_video, db)

        os.environ["SEMANTIC_QA_BACKEND"] = "fixture"
        os.environ.pop("YT_TEST_MODE", None)

        from media_service import run_contract_media_qa
        run_contract_media_qa(db, prod["id"], unit["unit_id"])

        # Verify assembly semantic gate passes
        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT * FROM render_units WHERE id=?", (unit["unit_id"],)
        ).fetchone()
        assert ru is not None

        assemble_db.validate_semantic_role_qa(
            conn, [dict(ru)], publish_grade=True,
        )
        conn.close()

    def test_backend_none_records_fail_evidence(self, prod, test_video, db):
        """SEMANTIC_QA_BACKEND=none records fail-closed evidence in prod mode."""
        unit = _create_generated_video_unit(prod["id"], test_video, db)

        os.environ["SEMANTIC_QA_BACKEND"] = "none"
        os.environ.pop("YT_TEST_MODE", None)

        from media_service import run_contract_media_qa
        validation = run_contract_media_qa(db, prod["id"], unit["unit_id"])

        # qa_media_contract still passes (technical QA is OK)
        assert validation["validator_name"] == "qa_media_contract"

        # semantic_role_qa evidence should be FAIL
        conn = _db.connect(db)
        sqa_rows = conn.execute(
            """SELECT * FROM validations
               WHERE subject_id=? AND validator_name=?
               ORDER BY created_at DESC""",
            (unit["unit_id"], sqa.SEMANTIC_ROLE_QA_VALIDATOR),
        ).fetchall()
        conn.close()

        assert len(sqa_rows) > 0, "semantic_role_qa evidence must exist"
        assert sqa_rows[0]["status"] == "fail"
        ev = json.loads(sqa_rows[0]["evidence_json"])
        assert "none" in ev.get("details", {}).get("backend", "")

    def test_backend_none_prod_mode_fails_assembly(self, prod, test_video, db):
        """backend=none evidence fails assembly semantic gate in production mode."""
        unit = _create_generated_video_unit(prod["id"], test_video, db)

        os.environ["SEMANTIC_QA_BACKEND"] = "none"
        os.environ.pop("YT_TEST_MODE", None)

        from media_service import run_contract_media_qa
        run_contract_media_qa(db, prod["id"], unit["unit_id"])

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT * FROM render_units WHERE id=?", (unit["unit_id"],)
        ).fetchone()

        with pytest.raises(assemble_db.AssemblyError, match="BLOCKED_SEMANTIC_ROLE_QA_FAILED"):
            assemble_db.validate_semantic_role_qa(
                conn, [dict(ru)], publish_grade=True,
            )
        conn.close()

    def test_yt_test_mode_preserves_auto_pass(self, prod, test_video, db):
        """YT_TEST_MODE=1 keeps existing auto-pass behavior unchanged."""
        unit = _create_generated_video_unit(prod["id"], test_video, db)

        os.environ["YT_TEST_MODE"] = "1"
        os.environ.pop("SEMANTIC_QA_BACKEND", None)

        from media_service import run_contract_media_qa
        validation = run_contract_media_qa(db, prod["id"], unit["unit_id"])

        assert validation["validator_name"] == "qa_media_contract"
        assert validation["status"] == "pass"

        # Test-mode auto-pass writes  semantic_role_qa with yt_test_mode method
        conn = _db.connect(db)
        sqa_rows = conn.execute(
            """SELECT * FROM validations
               WHERE subject_id=? AND validator_name=?
               ORDER BY created_at DESC""",
            (unit["unit_id"], sqa.SEMANTIC_ROLE_QA_VALIDATOR),
        ).fetchall()
        conn.close()

        assert len(sqa_rows) > 0
        assert sqa_rows[0]["status"] == "pass"
        ev = json.loads(sqa_rows[0]["evidence_json"])
        assert "yt_test_mode" in ev.get("details", {}).get("method", "")
