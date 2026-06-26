"""Debug test for S14_T003."""

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


def test_debug_syncnet_insertion(tmp_path):
    """Debug test to check if SyncNet validation is being inserted."""
    db = str(tmp_path / "test.db")
    os.environ["PRODUCTION_DB_PATH"] = db
    _db.migrate(db)
    prod_id = "prod_debug"
    prod = _db.ensure_production(prod_id, db_path=db)

    # Create hero render unit with SyncNet
    spans = commit_timeline_spans(
        prod_id,
        [{"label": "H001", "start_ms": 0, "end_ms": 4000}],
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

    # Create fake video artifact
    fake_video = tmp_path / "H001_provider.mp4"
    fake_video.write_bytes(b"fake provider video" * 100)
    art = register_artifact(prod_id, fake_video, "generated_media", db_path=db)
    link_artifact_to_render_unit(art["id"], unit["id"], db_path=db)

    # Run QA
    run_render_unit_qa(prod_id, unit["id"], {
        "file_exists": True, "dimensions_ok": True, "duration_ok": True, "audio_policy_ok": True,
    }, db_path=db)

    # Create provider_job with compensated artifact
    conn = _db.connect(db)
    job_id = f"pj_{uuid.uuid4().hex[:8]}"
    comp_path = tmp_path / "H001_compensated.mp4"
    comp_path.write_bytes(b"compensated hero video" * 100)
    conn.execute(
        """INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, operation, status, idempotency_key, compensated_artifact_path, submitted_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (job_id, prod_id, unit["id"], "seedance", "generate_lipsync", "completed",
         f"idemp_{job_id}", str(comp_path))
    )

    # Add SyncNet validation on render_unit
    val_id = f"val_{uuid.uuid4().hex[:8]}"
    conn.execute(
        """INSERT INTO validations (id, production_id, subject_type, subject_id, validator_name, status, evidence_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (val_id, prod_id, "render_unit", unit["id"], "syncnet_offset", "pass",
         '{"offset_ms": 25.0, "confidence": 2.8}', _db._now())
    )

    # Check if validation was inserted
    check = conn.execute(
        "SELECT * FROM validations WHERE subject_id=? AND validator_name='syncnet_offset'",
        (unit["id"],)
    ).fetchall()

    print(f"Inserted validation: {val_id}")
    print(f"Render unit ID: {unit['id']}")
    print(f"Found {len(check)} validations for syncnet_offset on render_unit")

    # Now check if the query in assemble_db would find it
    syncnet_check = conn.execute(
        """SELECT id, evidence_json FROM validations WHERE
           (subject_id=? OR subject_id IN (SELECT id FROM provider_jobs WHERE render_unit_id=?))
           AND validator_name='syncnet_offset'
           AND status='pass'
           LIMIT 1""", (unit["id"], unit["id"],),
    ).fetchall()

    print(f"Query found {len(syncnet_check)} validations")

    conn.close()
    del os.environ["PRODUCTION_DB_PATH"]
