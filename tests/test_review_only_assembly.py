import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from assemble_db import AssemblyError, build_assembly_inputs
from media_service import run_render_unit_qa
from production_repo import (
    commit_timeline_spans,
    link_artifact_to_render_unit,
    plan_render_units,
    register_artifact,
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
    return _db.ensure_production("review_only_assembly", db_path=db)


def _make_hero(prod_id, db, tmp_path, *, qa_pass=False, human_review=False, syncnet=False):
    spans = commit_timeline_spans(
        prod_id,
        [{"label": "S000", "start_ms": 0, "end_ms": 4000}],
        db_path=db,
    )
    units = plan_render_units(
        prod_id,
        [{
            "span_id": spans[0]["id"],
            "asset_type": "lipsync_video",
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "model": "seedance_2_0",
        }],
        db_path=db,
    )
    unit = units[0]

    video = tmp_path / "S000.mp4"
    video.write_bytes(b"fake video" * 100)
    art = register_artifact(prod_id, video, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    run_render_unit_qa(
        prod_id,
        unit["id"],
        {
            "file_exists": True,
            "dimensions_ok": qa_pass,
            "duration_ok": True,
            "audio_policy_ok": True,
        },
        db_path=db,
    )

    comp = tmp_path / "S000_compensated.mp4"
    comp.write_bytes(b"provider synced audio" * 100)
    job_id = f"pjob_{uuid.uuid4().hex[:8]}"
    with _db.transaction(db) as conn:
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation, status,
                idempotency_key, compensated_artifact_path)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                job_id,
                prod_id,
                unit["id"],
                "higgsfield",
                "generate_video",
                "completed",
                f"idemp_{job_id}",
                str(comp),
            ),
        )
        if human_review:
            conn.execute(
                """INSERT INTO validations
                   (id, production_id, subject_type, subject_id, validator_name,
                    status, evidence_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    f"val_{uuid.uuid4().hex[:8]}",
                    prod_id,
                    "render_unit",
                    unit["id"],
                    "human_av_review_pass_review_only",
                    "pass",
                    _db._json({
                        "status": "REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS",
                        "review_result": "PASS",
                        "automated_syncnet_pass": False,
                    }),
                    _db._now(),
                ),
            )
        if syncnet:
            conn.execute(
                """INSERT INTO validations
                   (id, production_id, subject_type, subject_id, validator_name,
                    status, evidence_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    f"val_{uuid.uuid4().hex[:8]}",
                    prod_id,
                    "provider_job",
                    job_id,
                    "syncnet_offset",
                    "pass",
                    _db._json({"offset_ms": 10, "confidence": 0.95}),
                    _db._now(),
                ),
            )
    return unit


def _add_minimum_review_only_shotmix(prod_id, db, tmp_path):
    spans = commit_timeline_spans(
        prod_id,
        [
            {"label": "S000", "start_ms": 0, "end_ms": 4000},
            {"label": "S001", "start_ms": 4000, "end_ms": 8000},
            {"label": "S002", "start_ms": 8000, "end_ms": 12000},
            {"label": "S003", "start_ms": 12000, "end_ms": 16000},
        ],
        db_path=db,
    )
    specs = [
        {
            "span_id": spans[0]["id"],
            "asset_type": "lipsync_video",
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "model": "seedance_2_0",
        },
        {
            "span_id": spans[1]["id"],
            "asset_type": "generated_video",
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "NO_VISIBLE_TEXT",
            "model": "kling3_0",
            "visual_function": "illustrate",
            "narrative_claim": "A manager protects reflection time",
            "information_to_show": "A notebook and calendar blocks in a meeting room",
            "viewer_takeaway": "Deep work is protected by deliberate pauses",
            "required_action": "Manager pauses over a notebook before responding",
            "distinctness_requirement": "Grounded corporate setting, not sci-fi",
            "semantic_acceptance_criteria": "Shows real office objects tied to the narration",
            "concept_key": "manager_reflection_pause",
            "concept_hash": "manager_reflection_pause",
        },
        {
            "span_id": spans[2]["id"],
            "asset_type": "lipsync_video",
            "audio_policy": "HERO_SYNC_LOCKED",
            "final_audio_source": "master_narration",
            "provider_audio_usage": "diagnostic_only",
            "model": "seedance_2_0",
        },
        {
            "span_id": spans[3]["id"],
            "asset_type": "local_graphic",
            "audio_policy": "SILENT_GRAPHIC",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "model": None,
        },
    ]
    units = plan_render_units(prod_id, specs, db_path=db)
    for idx, unit in enumerate(units):
        suffix = "png" if unit["asset_type"] == "local_graphic" else "mp4"
        media = tmp_path / f"{unit['label']}.{suffix}"
        media.write_bytes(b"fake media" * 100)
        art = register_artifact(prod_id, media, "generated_media", db_path=db)
        link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)
        qa_pass = unit["asset_type"] not in {"lipsync_video"}
        run_render_unit_qa(
            prod_id,
            unit["id"],
            {
                "file_exists": True,
                "dimensions_ok": qa_pass,
                "duration_ok": True,
                "audio_policy_ok": True,
            },
            db_path=db,
        )
        if unit["asset_type"] == "lipsync_video":
            comp = tmp_path / f"{unit['label']}_compensated.mp4"
            comp.write_bytes(b"provider synced audio" * 100)
            job_id = f"pjob_{idx}_{uuid.uuid4().hex[:8]}"
            human_val_id = f"val_{uuid.uuid4().hex[:8]}"
            with _db.transaction(db) as conn:
                conn.execute(
                    """INSERT INTO provider_jobs
                       (id, production_id, render_unit_id, provider, operation, status,
                        idempotency_key, compensated_artifact_path)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        job_id,
                        prod_id,
                        unit["id"],
                        "higgsfield",
                        "generate_video",
                        "completed",
                        f"idemp_{job_id}",
                        str(comp),
                    ),
                )
                conn.execute(
                    """INSERT INTO validations
                       (id, production_id, subject_type, subject_id, validator_name,
                        status, evidence_json, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        human_val_id,
                        prod_id,
                        "render_unit",
                        unit["id"],
                        "human_av_review_pass_review_only",
                        "pass",
                        _db._json({
                            "status": "REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS",
                            "review_result": "PASS",
                            "automated_syncnet_pass": False,
                        }),
                        _db._now(),
                    ),
                )
                conn.execute(
                    "UPDATE render_units SET status='valid', approved_validation_id=? WHERE id=?",
                    (human_val_id, unit["id"]),
                )
    return units


def test_review_only_assembly_accepts_human_av_without_syncnet(db, prod, tmp_path):
    _add_minimum_review_only_shotmix(prod["id"], db, tmp_path)

    result = build_assembly_inputs(prod["id"], db_path=db, review_only=True)

    assert result["preflight"]["assembly_mode"] == "review_only"
    assert result["preflight"]["publish_grade_syncnet_required"] is False
    assert result["preflight"]["review_only_label"] == (
        "REVIEW_ONLY_HUMAN_AV_ACCEPTED_NOT_AUTOMATED_SYNCNET_PASS"
    )


def test_publish_grade_still_blocks_without_syncnet(db, prod, tmp_path):
    _make_hero(prod["id"], db, tmp_path, qa_pass=True, human_review=True, syncnet=False)

    with pytest.raises(AssemblyError, match="BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING"):
        build_assembly_inputs(prod["id"], db_path=db)


def test_review_only_human_av_is_not_publish_syncnet(db, prod, tmp_path):
    _make_hero(prod["id"], db, tmp_path, qa_pass=False, human_review=True, syncnet=False)

    with pytest.raises(AssemblyError, match="no passing QA"):
        build_assembly_inputs(prod["id"], db_path=db)
