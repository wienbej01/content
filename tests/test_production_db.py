"""Tests for the unified production ledger and migration bridge."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as pdb
from import_legacy_production import import_project


def test_migrations_are_repeatable_and_integrity_clean(tmp_path):
    path = tmp_path / "production.db"
    assert pdb.migrate(path) == path
    assert pdb.migrate(path) == path
    integrity, foreign_keys = pdb.integrity_check(path)
    assert integrity == "ok"
    assert foreign_keys == []

    conn = pdb.connect(path)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    conn.close()
    assert {"productions", "stage_runs", "document_revisions", "timeline_spans",
            "render_units", "artifacts", "approval_requests", "outbox_messages"} <= tables


def test_ensure_production_is_stable_by_project_slug(tmp_path):
    path = tmp_path / "production.db"
    first = pdb.ensure_production("episode_1", "seed", "short", db_path=path)
    second = pdb.ensure_production("episode_1", "new seed", "short", db_path=path)
    assert first["id"] == second["id"]
    assert second["seed"] == "new seed"


def test_mirror_state_records_stage_runs_and_failure_blocker(tmp_path):
    path = tmp_path / "production.db"
    project = tmp_path / "episode_2"
    project.mkdir()
    state = {
        "seed": "topic",
        "format": "explainer",
        "step_status": {
            "research": {"status": "done", "result": {"claims": 3}, "completed_at": "2026-01-01T00:00:00"},
            "script_create": {"status": "failed", "error": "writer failed"},
        },
    }
    pdb.mirror_state(project, state, db_path=path)
    production = pdb.get_production("episode_2", db_path=path)
    assert production["status"] == "failed"
    blocked = pdb.blockers("episode_2", db_path=path)
    assert blocked == [{"type": "failed_stage", "owner": "script_create", "detail": "writer failed"}]


def test_mirror_state_failed_stage_wins_over_downstream_pending(tmp_path):
    path = tmp_path / "production.db"
    project = tmp_path / "episode_failed"
    project.mkdir()
    pdb.mirror_state(project, {
        "seed": "topic",
        "format": "short",
        "step_status": {
            "research": {"status": "done"},
            "qa_final": {"status": "failed", "error": "bad stream"},
            "gate_b_review": {"status": None},
        },
    }, db_path=path)
    production = pdb.get_production("episode_failed", db_path=path)
    assert production["status"] == "failed"
    assert production["current_stage"] == "qa_final"


def test_mirror_stage_state_is_idempotent(tmp_path):
    path = tmp_path / "production.db"
    for _ in range(2):
        pdb.mirror_stage_state("episode_3", "research", "done", result={"claims": 2}, db_path=path)
    conn = pdb.connect(path)
    count = conn.execute("SELECT COUNT(*) FROM stage_runs").fetchone()[0]
    event_count = conn.execute(
        "SELECT COUNT(*) FROM production_events WHERE event_type='stage_succeeded'"
    ).fetchone()[0]
    conn.close()
    assert count == 1
    assert event_count == 1


def test_mirror_approval_updates_single_gate_row(tmp_path):
    path = tmp_path / "production.db"
    artifact = tmp_path / "storyboard.json"
    artifact.write_text('{"a": 1}')
    digest = pdb._sha256_file(artifact)
    pdb.mirror_approval("episode_4", "storyboard_review", "pass",
                        artifact_path=artifact, artifact_sha256=digest, db_path=path)
    pdb.mirror_approval("episode_4", "storyboard_review", "stale",
                        artifact_path=artifact, artifact_sha256=digest,
                        decision_note="changed", db_path=path)
    conn = pdb.connect(path)
    rows = conn.execute("SELECT * FROM approval_requests").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["status"] == "stale"
    assert pdb.blockers("episode_4", db_path=path)[0]["type"] == "approval"


def test_import_document_creates_immutable_revisions(tmp_path):
    path = tmp_path / "production.db"
    document = tmp_path / "script.json"
    document.write_text(json.dumps({"schema_version": "1", "segments": [{"text": "one"}]}))
    first = pdb.import_document("episode_5", "script", document, db_path=path)
    again = pdb.import_document("episode_5", "script", document, db_path=path)
    assert first["id"] == again["id"]

    document.write_text(json.dumps({"schema_version": "1", "segments": [{"text": "two"}]}))
    second = pdb.import_document("episode_5", "script", document, db_path=path)
    assert second["revision"] == 2
    conn = pdb.connect(path)
    statuses = [tuple(row) for row in conn.execute(
        "SELECT revision, status FROM document_revisions ORDER BY revision"
    )]
    conn.close()
    assert statuses == [(1, "superseded"), (2, "active")]


def test_import_artifact_creates_immutable_version_when_checksum_changes(tmp_path):
    path = tmp_path / "production.db"
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"first")
    first = pdb.import_artifact("episode_6", "generated_video", media, db_path=path)
    media.write_bytes(b"second")
    second = pdb.import_artifact("episode_6", "generated_video", media, db_path=path)
    assert first["id"] != second["id"]
    assert first["sha256"] != second["sha256"]


def test_import_legacy_clip_creates_render_unit_and_artifact(tmp_path, monkeypatch):
    path = tmp_path / "production.db"
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media")
    clip = {
        "clip_id": "legacy::B001::whole",
        "production_beat_id": "B001",
        "output_path": str(media),
        "asset_type": "generated_video",
        "model": "test",
        "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT",
        "lipsync_required": 0,
        "required_start_sec": 1.0,
        "required_end_sec": 3.5,
        "status": "valid",
    }
    row = pdb.import_legacy_clip("episode_7", clip, db_path=path)
    assert row["legacy_clip_id"] == clip["clip_id"]
    assert row["required_duration_ms"] == 2500
    assert row["active_artifact_id"] is not None


def test_legacy_import_dry_run_and_idempotent_apply(tmp_path):
    project = tmp_path / "legacy_episode"
    project.mkdir()
    (project / "narration").mkdir()
    (project / "state.json").write_text(json.dumps({
        "seed": "legacy seed",
        "format": "short",
        "step_status": {"research": {"status": "done", "completed_at": "2026-01-01"}},
    }))
    (project / "gates.json").write_text(json.dumps({
        "project_id": "legacy_episode",
        "gates": {"script_review": {"status": "pass", "artifact_sha256": None,
                                       "artifact_path": None, "forced": False}},
    }))
    (project / "script.json").write_text(json.dumps({"schema_version": "1", "segments": []}))
    (project / "narration" / "continuous.mp3").write_bytes(b"audio")

    clips_db = tmp_path / "clips.db"
    conn = sqlite3.connect(clips_db)
    conn.execute("CREATE TABLE clips (project_id TEXT, clip_id TEXT)")
    conn.commit()
    conn.close()
    content_db = tmp_path / "content.db"

    dry = import_project(project, clips_db, content_db, db_path=tmp_path / "prod.db", dry_run=True)
    assert dry["documents"] == ["script.json"]
    assert dry["gates"] == 1

    first = import_project(project, clips_db, content_db, db_path=tmp_path / "prod.db")
    second = import_project(project, clips_db, content_db, db_path=tmp_path / "prod.db")
    assert first["production_id"] == second["production_id"]
    conn = pdb.connect(tmp_path / "prod.db")
    assert conn.execute("SELECT COUNT(*) FROM document_revisions").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0] == 1
    conn.close()


def test_cli_create_show_and_check(tmp_path):
    path = tmp_path / "production.db"
    create = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "production_db.py"), "--db", str(path),
         "create", "cli_episode", "--seed", "topic", "--format", "short"],
        capture_output=True, text=True,
    )
    assert create.returncode == 0, create.stderr
    show = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "production_db.py"), "--db", str(path),
         "show", "cli_episode"], capture_output=True, text=True,
    )
    assert show.returncode == 0
    assert json.loads(show.stdout)["project_slug"] == "cli_episode"
    check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "production_db.py"), "--db", str(path), "check"],
        capture_output=True, text=True,
    )
    assert check.returncode == 0
    assert json.loads(check.stdout)["integrity"] == "ok"


def test_gate_ledger_dual_write_and_stale_status(tmp_path, monkeypatch):
    import gates

    gates.PROJECTS_DIR = tmp_path / "Projects"
    artifact = tmp_path / "plan.json"
    artifact.write_text('{"v": 1}')
    gates.record_gate("dual_gate", "media_plan_review", "pass", artifact_path=artifact)
    approval = pdb.connect().execute(
        "SELECT status FROM approval_requests WHERE gate_name='media_plan_review'"
    ).fetchone()
    assert approval["status"] == "pass"

    artifact.write_text('{"v": 2}')
    with pytest.raises(SystemExit):
        gates.require_gates("dual_gate", ["media_plan_review"])
    conn = pdb.connect()
    approval = conn.execute(
        "SELECT status FROM approval_requests WHERE gate_name='media_plan_review'"
    ).fetchone()
    conn.close()
    assert approval["status"] == "stale"


def test_job_queue_is_idempotent_and_lease_owned(tmp_path):
    path = tmp_path / "production.db"
    first = pdb.enqueue_job("queued_episode", "research", payload={"seed": "x"}, db_path=path)
    second = pdb.enqueue_job("queued_episode", "research", payload={"seed": "x"}, db_path=path)
    assert first["id"] == second["id"]

    leased = pdb.lease_job("worker-a", lease_seconds=60, db_path=path)
    assert leased["id"] == first["id"]
    assert leased["attempts"] == 1
    assert pdb.lease_job("worker-b", db_path=path) is None
    assert pdb.heartbeat_job(first["id"], "worker-b", db_path=path) is False
    assert pdb.heartbeat_job(first["id"], "worker-a", db_path=path) is True
    with pytest.raises(RuntimeError):
        pdb.complete_job(first["id"], "worker-b", db_path=path)
    pdb.complete_job(first["id"], "worker-a", result={"claims": 1}, db_path=path)
    production = pdb.get_production("queued_episode", db_path=path)
    assert production["current_stage"] == "research"


def test_failed_job_retries_then_becomes_blocker(tmp_path):
    path = tmp_path / "production.db"
    job = pdb.enqueue_job("retry_episode", "tts", max_attempts=2, db_path=path)
    lease = pdb.lease_job("worker", db_path=path)
    assert lease["id"] == job["id"]
    assert pdb.fail_job(job["id"], "worker", "temporary", db_path=path) == "queued"

    lease = pdb.lease_job("worker", db_path=path)
    assert lease["attempts"] == 2
    assert pdb.fail_job(job["id"], "worker", "permanent", db_path=path) == "failed"
    assert pdb.blockers("retry_episode", db_path=path) == [
        {"type": "failed_stage", "owner": "tts", "detail": "permanent"}
    ]


def test_expired_lease_is_reclaimed(tmp_path):
    path = tmp_path / "production.db"
    job = pdb.enqueue_job("lease_episode", "assemble", db_path=path)
    leased = pdb.lease_job("dead-worker", lease_seconds=-1, db_path=path)
    assert leased["id"] == job["id"]
    reclaimed = pdb.lease_job("new-worker", db_path=path)
    assert reclaimed["id"] == job["id"]
    assert reclaimed["leased_by"] == "new-worker"


def test_invalidate_stages_marks_stage_runs_stale(tmp_path):
    path = tmp_path / "production.db"
    pdb.mirror_stage_state("invalidate_episode", "research", "done", db_path=path)
    pdb.mirror_stage_state("invalidate_episode", "script_create", "done", db_path=path)
    count = pdb.invalidate_stages(
        "invalidate_episode", ["script_create", "storyboard_create"], db_path=path
    )
    assert count == 1
    conn = pdb.connect(path)
    row = conn.execute(
        "SELECT status FROM stage_runs WHERE stage_name='script_create'"
    ).fetchone()
    conn.close()
    assert row["status"] == "stale"


def test_clip_lifecycle_dual_writes_render_validation_and_change(tmp_path):
    import clip_db

    clip_db.init_db()
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"clip-data")
    clip = clip_db.order_clip(
        project_id="clip_dual", source_beat_id="B001", production_beat_id="B001",
        segment_id="S001", asset_type="generated_video", model="test",
        audio_policy="BROLL_FLEX", lipsync_required=False,
        required_start_sec=0, required_end_sec=2,
    )
    conn = clip_db.get_db()
    conn.execute("UPDATE clips SET output_path=? WHERE clip_id=?", (str(media), clip["clip_id"]))
    conn.commit()
    conn.close()
    digest = clip_db._sha256_file(media)
    clip_db.record_generated(clip["clip_id"], 2.0, 1920, 1080, False, digest)
    clip_db.mark_valid(clip["clip_id"])

    conn = pdb.connect()
    render = conn.execute(
        "SELECT * FROM render_units WHERE legacy_clip_id=?", (clip["clip_id"],)
    ).fetchone()
    validations = conn.execute(
        "SELECT * FROM validations WHERE subject_id=?", (render["id"],)
    ).fetchall()
    conn.close()
    assert render["status"] == "valid"
    assert render["active_artifact_id"] is not None
    assert len(validations) == 1 and validations[0]["status"] == "pass"

    clip_db.request_change(clip["clip_id"], "qa_media", "generate_media", "regenerate", "blur")
    assert any(item["type"] == "change_request" for item in pdb.blockers("clip_dual"))
    clip_db.resolve_change(clip["clip_id"], "generate_media", "regenerated")
    conn = pdb.connect()
    assert conn.execute(
        "SELECT status FROM change_requests"
    ).fetchone()["status"] == "resolved"
    conn.close()
