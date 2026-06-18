#!/usr/bin/env python3
"""Unified production ledger and repository API.

This module is the migration boundary from file-led pipeline state to a single
transactional system of record. Media payloads remain in the artifact store;
the database records identity, lifecycle, checksums, lineage, and evidence.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "db" / "production.db"
MIGRATIONS_DIR = ROOT / "db" / "migrations"

_db_path_override = None


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_path(db_path=None):
    if db_path:
        return Path(db_path)
    if _db_path_override:
        return Path(_db_path_override)
    return Path(os.environ.get("PRODUCTION_DB_PATH", DEFAULT_DB_PATH))


def connect(db_path=None):
    """Open a configured SQLite connection with integrity safeguards enabled."""
    path = _db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _backup_db(db_path):
    """Create a pre-migration backup of the DB file. Returns the backup path or None."""
    import shutil
    path = _db_path(db_path)
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + ".pre_migration_bak")
    shutil.copy2(str(path), str(backup))
    return backup


def _restore_db(backup_path, db_path):
    """Restore the DB from a pre-migration backup."""
    import shutil
    path = _db_path(db_path)
    if backup_path and backup_path.exists():
        shutil.copy2(str(backup_path), str(path))
        backup_path.unlink(missing_ok=True)


def migrate(db_path=None, backup=True):
    """Apply ordered SQL migrations exactly once.

    S1-T03: when backup=True (default), creates a pre-migration copy of the DB
    before applying any new migration. If a migration fails mid-execution, the
    backup is restored so the DB is left in its pre-migration state (no partial
    migration applied). The schema_migrations checksum immutability check
    prevents silent modification of already-applied migrations.
    """
    path = _db_path(db_path)
    backup_path = _backup_db(db_path) if backup else None

    try:
        conn = connect(db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version TEXT PRIMARY KEY,
                   filename TEXT NOT NULL,
                   sha256 TEXT NOT NULL,
                   applied_at TEXT NOT NULL
               )"""
        )
        applied = {
            row["version"]: row
            for row in conn.execute("SELECT * FROM schema_migrations").fetchall()
        }
        for mpath in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = mpath.name.split("_", 1)[0]
            sql = mpath.read_text()
            digest = _sha256_bytes(sql.encode("utf-8"))
            prior = applied.get(version)
            if prior:
                if prior["sha256"] != digest:
                    conn.close()
                    raise RuntimeError(f"migration {mpath.name} changed after application")
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, filename, sha256, applied_at) VALUES (?,?,?,?)",
                (version, mpath.name, digest, _now()),
            )
            conn.commit()
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()
        if violations:
            raise RuntimeError(f"foreign key violations after migration: {violations}")
    except Exception:
        # Failed-migration rollback: restore from backup so the DB is not left
        # in a partially-migrated state.
        if backup_path:
            _restore_db(backup_path, db_path)
        raise

    # Clean up backup on success (all migrations applied cleanly)
    if backup_path and backup_path.exists():
        backup_path.unlink(missing_ok=True)

    return path


@contextlib.contextmanager
def transaction(db_path=None):
    """Yield one immediate transaction and commit or roll back atomically."""
    migrate(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row(row):
    return dict(row) if row is not None else None


def _git_revision():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def ensure_production(project_slug, seed=None, video_type=None, created_at=None, db_path=None):
    """Return the stable production row for a project slug, creating it if needed."""
    now = _now()
    with transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM productions WHERE project_slug=?", (project_slug,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE productions SET seed=COALESCE(?, seed),
                   video_type=COALESCE(?, video_type), updated_at=? WHERE id=?""",
                (seed, video_type, now, existing["id"]),
            )
            return _row(conn.execute("SELECT * FROM productions WHERE id=?", (existing["id"],)).fetchone())
        production_id = _id("prod")
        conn.execute(
            """INSERT INTO productions
               (id, project_slug, video_type, seed, status, code_revision, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                production_id,
                project_slug,
                video_type,
                seed,
                "created",
                _git_revision(),
                created_at or now,
                now,
            ),
        )
        conn.execute(
            """INSERT INTO production_events
               (id, production_id, event_type, actor, event_key, payload_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                _id("evt"), production_id, "production_created", "system",
                f"production_created:{project_slug}", _json({"project_slug": project_slug}), now,
            ),
        )
        return _row(conn.execute("SELECT * FROM productions WHERE id=?", (production_id,)).fetchone())


def get_production(project_or_id, db_path=None):
    migrate(db_path)
    conn = connect(db_path)
    row = conn.execute(
        "SELECT * FROM productions WHERE id=? OR project_slug=?", (project_or_id, project_or_id)
    ).fetchone()
    conn.close()
    return _row(row)


def list_productions(db_path=None):
    migrate(db_path)
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM productions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row(row) for row in rows]


def append_event(production_id, event_type, actor="system", payload=None, event_key=None,
                 db_path=None, conn=None):
    """Append an audit event; event_key makes mirrored writes idempotent."""
    owns_conn = conn is None
    if owns_conn:
        migrate(db_path)
        conn = connect(db_path)
    event_id = _id("evt")
    try:
        conn.execute(
            """INSERT OR IGNORE INTO production_events
               (id, production_id, event_type, actor, event_key, payload_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id, production_id, event_type, actor, event_key,
             _json(payload or {}), _now()),
        )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()
    return event_id


def mirror_stage_state(project_slug, stage_name, status, result=None, error=None,
                       seed=None, video_type=None, completed_at=None, db_path=None):
    """Mirror one legacy orchestrator stage into the unified ledger."""
    production = ensure_production(project_slug, seed=seed, video_type=video_type, db_path=db_path)
    now = _now()
    mapped = {None: "queued", "done": "succeeded", "failed": "failed"}.get(status, status)
    if mapped not in {"queued", "running", "succeeded", "failed", "stale", "cancelled"}:
        mapped = "queued"
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM stage_runs WHERE production_id=? AND stage_name=? AND attempt=1",
            (production["id"], stage_name),
        ).fetchone()
        stage_run_id = row["id"] if row else _id("run")
        started_at = row["started_at"] if row else (now if mapped == "running" else None)
        finished_at = completed_at or (now if mapped in {"succeeded", "failed"} else None)
        conn.execute(
            """INSERT INTO stage_runs
               (id, production_id, stage_name, attempt, status, started_at, finished_at,
                error_class, error_message, result_summary_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(production_id, stage_name, attempt) DO UPDATE SET
                 status=excluded.status,
                 started_at=COALESCE(stage_runs.started_at, excluded.started_at),
                 finished_at=excluded.finished_at,
                 error_class=excluded.error_class,
                 error_message=excluded.error_message,
                 result_summary_json=excluded.result_summary_json,
                 updated_at=excluded.updated_at""",
            (
                stage_run_id, production["id"], stage_name, 1, mapped, started_at, finished_at,
                type(error).__name__ if isinstance(error, BaseException) else ("LegacyError" if error else None),
                str(error) if error else None, _json(result) if result is not None else None,
                now, now,
            ),
        )
        production_status = "failed" if mapped == "failed" else (
            "completed" if stage_name == "gate_b_review" and mapped == "succeeded" else "running"
        )
        conn.execute(
            """UPDATE productions SET status=?, current_stage=?, updated_at=?,
               completed_at=CASE WHEN ?='completed' THEN ? ELSE completed_at END WHERE id=?""",
            (production_status, stage_name, now, production_status, now, production["id"]),
        )
        append_event(
            production["id"], f"stage_{mapped}", payload={"stage": stage_name, "error": str(error) if error else None},
            event_key=f"legacy-stage:{stage_name}:{mapped}:{completed_at or ''}", conn=conn,
        )
    return stage_run_id


def mirror_state(project_dir, state, db_path=None):
    """Mirror all legacy state.json stage statuses into the production ledger."""
    project_dir = Path(project_dir)
    step_status = state.get("step_status", {})
    for stage_name, info in step_status.items():
        mirror_stage_state(
            project_dir.name,
            stage_name,
            info.get("status"),
            result=info.get("result"),
            error=info.get("error"),
            seed=state.get("seed"),
            video_type=state.get("format"),
            completed_at=info.get("completed_at"),
            db_path=db_path,
        )
    failed = next(
        (name for name, info in step_status.items() if info.get("status") == "failed"), None
    )
    unfinished = next(
        (name for name, info in step_status.items() if info.get("status") != "done"), None
    )
    summary_status = "failed" if failed else ("completed" if step_status and not unfinished else "running")
    current_stage = failed or unfinished
    production = get_production(project_dir.name, db_path=db_path)
    now = _now()
    with transaction(db_path) as conn:
        conn.execute(
            """UPDATE productions SET status=?, current_stage=?, updated_at=?,
               completed_at=CASE WHEN ?='completed' THEN COALESCE(completed_at, ?) ELSE NULL END
               WHERE id=?""",
            (summary_status, current_stage, now, summary_status, now, production["id"]),
        )


def invalidate_stages(project_slug, stage_names, reason="legacy invalidation", db_path=None):
    """Mark current stage-run snapshots stale and append an audit event."""
    production = ensure_production(project_slug, db_path=db_path)
    names = list(stage_names)
    if not names:
        return 0
    now = _now()
    placeholders = ",".join("?" for _ in names)
    with transaction(db_path) as conn:
        cursor = conn.execute(
            f"""UPDATE stage_runs SET status='stale', finished_at=?, updated_at=?
                WHERE production_id=? AND stage_name IN ({placeholders})""",
            (now, now, production["id"], *names),
        )
        conn.execute(
            "UPDATE productions SET status='running', current_stage=?, updated_at=? WHERE id=?",
            (names[0], now, production["id"]),
        )
        append_event(
            production["id"], "stages_invalidated",
            payload={"stages": names, "reason": reason}, conn=conn,
        )
        return cursor.rowcount


def enqueue_job(project_slug, stage_name, payload=None, priority=0, available_at=None,
                max_attempts=3, idempotency_key=None, db_path=None):
    """Create one idempotent durable stage job."""
    production = ensure_production(project_slug, db_path=db_path)
    now = _now()
    key = idempotency_key or f"{production['id']}:{stage_name}:{_sha256_bytes(_json(payload or {}).encode())}"
    with transaction(db_path) as conn:
        existing = conn.execute("SELECT * FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            return _row(existing)
        job_id = _id("job")
        conn.execute(
            """INSERT INTO jobs
               (id, production_id, stage_name, status, priority, available_at, attempts,
                max_attempts, idempotency_key, payload_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id, production["id"], stage_name, "queued", priority,
                available_at or now, 0, max_attempts, key, _json(payload or {}), now, now,
            ),
        )
        append_event(
            production["id"], "job_enqueued", payload={"job_id": job_id, "stage": stage_name},
            event_key=f"job-enqueued:{key}", conn=conn,
        )
        return _row(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def lease_job(worker_id, lease_seconds=300, db_path=None):
    """Atomically lease the next available job, reclaiming expired leases."""
    now_dt = datetime.now(timezone.utc).astimezone()
    now = now_dt.isoformat(timespec="seconds")
    expires = (now_dt + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
    with transaction(db_path) as conn:
        conn.execute(
            """UPDATE jobs SET status='queued', leased_by=NULL, lease_expires_at=NULL, updated_at=?
               WHERE status='leased' AND lease_expires_at IS NOT NULL AND lease_expires_at<=?""",
            (now, now),
        )
        job = conn.execute(
            """SELECT * FROM jobs WHERE status='queued' AND available_at<=?
               AND attempts < max_attempts
               ORDER BY priority DESC, available_at, created_at LIMIT 1""",
            (now,),
        ).fetchone()
        if not job:
            return None
        cursor = conn.execute(
            """UPDATE jobs SET status='leased', leased_by=?, lease_expires_at=?,
               attempts=attempts+1, updated_at=? WHERE id=? AND status='queued'""",
            (worker_id, expires, now, job["id"]),
        )
        if cursor.rowcount != 1:
            return None
        return _row(conn.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone())


def heartbeat_job(job_id, worker_id, lease_seconds=300, db_path=None):
    """Extend a lease only for its owning worker."""
    now_dt = datetime.now(timezone.utc).astimezone()
    expires = (now_dt + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
    with transaction(db_path) as conn:
        cursor = conn.execute(
            """UPDATE jobs SET lease_expires_at=?, updated_at=?
               WHERE id=? AND status='leased' AND leased_by=?""",
            (expires, now_dt.isoformat(timespec="seconds"), job_id, worker_id),
        )
        return cursor.rowcount == 1


def complete_job(job_id, worker_id, result=None, db_path=None):
    """Complete a leased job and mirror a successful stage run."""
    now = _now()
    with transaction(db_path) as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id=? AND status='leased' AND leased_by=?",
            (job_id, worker_id),
        ).fetchone()
        if not job:
            raise RuntimeError(f"job {job_id} is not leased by {worker_id}")
        conn.execute(
            """UPDATE jobs SET status='succeeded', lease_expires_at=NULL,
               updated_at=? WHERE id=?""",
            (now, job_id),
        )
        append_event(
            job["production_id"], "job_succeeded", actor=worker_id,
            payload={"job_id": job_id, "stage": job["stage_name"], "result": result or {}}, conn=conn,
        )
    production = get_production(job["production_id"], db_path=db_path)
    mirror_stage_state(
        production["project_slug"], job["stage_name"], "succeeded",
        result=result, completed_at=now, db_path=db_path,
    )


def fail_job(job_id, worker_id, error, retry_delay_seconds=0, db_path=None):
    """Fail a lease, requeueing while attempts remain."""
    now_dt = datetime.now(timezone.utc).astimezone()
    now = now_dt.isoformat(timespec="seconds")
    with transaction(db_path) as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id=? AND status='leased' AND leased_by=?",
            (job_id, worker_id),
        ).fetchone()
        if not job:
            raise RuntimeError(f"job {job_id} is not leased by {worker_id}")
        retry = job["attempts"] < job["max_attempts"]
        status = "queued" if retry else "failed"
        available_at = (now_dt + timedelta(seconds=retry_delay_seconds)).isoformat(timespec="seconds")
        conn.execute(
            """UPDATE jobs SET status=?, available_at=?, leased_by=NULL, lease_expires_at=NULL,
               last_error=?, updated_at=? WHERE id=?""",
            (status, available_at, str(error), now, job_id),
        )
        append_event(
            job["production_id"], "job_retry_scheduled" if retry else "job_failed",
            actor=worker_id, payload={"job_id": job_id, "error": str(error)}, conn=conn,
        )
    if not retry:
        production = get_production(job["production_id"], db_path=db_path)
        mirror_stage_state(
            production["project_slug"], job["stage_name"], "failed",
            error=str(error), db_path=db_path,
        )
    return status


def mirror_approval(project_slug, gate_name, status, artifact_path=None, artifact_sha256=None,
                    forced=False, actor=None, decision_note=None, legacy_payload=None, db_path=None):
    """Mirror a legacy gate entry into approval_requests."""
    production = ensure_production(project_slug, db_path=db_path)
    now = _now()
    with transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO approval_requests
               (id, production_id, gate_name, subject_type, subject_sha256, artifact_uri,
                status, requested_at, decided_at, actor, decision_note, forced, legacy_payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(production_id, gate_name) DO UPDATE SET
                 subject_sha256=excluded.subject_sha256,
                 artifact_uri=excluded.artifact_uri,
                 status=excluded.status,
                 decided_at=excluded.decided_at,
                 actor=excluded.actor,
                 decision_note=excluded.decision_note,
                 forced=excluded.forced,
                 legacy_payload_json=excluded.legacy_payload_json""",
            (
                _id("approval"), production["id"], gate_name,
                "artifact" if artifact_path else None, artifact_sha256,
                str(artifact_path) if artifact_path else None, status, now,
                now if status in {"pass", "fail"} else None, actor, decision_note,
                int(bool(forced)), _json(legacy_payload or {}),
            ),
        )
        append_event(
            production["id"], "approval_recorded", actor=actor or "legacy_gate",
            payload={"gate": gate_name, "status": status, "forced": bool(forced)},
            event_key=f"approval:{gate_name}:{status}:{artifact_sha256 or ''}:{int(bool(forced))}",
            conn=conn,
        )


def import_document(project_slug, kind, path, db_path=None):
    """Import a JSON document as an immutable revision, idempotently."""
    path = Path(path)
    payload = json.loads(path.read_text())
    canonical = _json(payload)
    digest = _sha256_bytes(canonical.encode("utf-8"))
    production = ensure_production(project_slug, db_path=db_path)
    with transaction(db_path) as conn:
        existing = conn.execute(
            """SELECT * FROM document_revisions
               WHERE production_id=? AND kind=? AND payload_sha256=?""",
            (production["id"], kind, digest),
        ).fetchone()
        if existing:
            return _row(existing)
        previous = conn.execute(
            """SELECT * FROM document_revisions WHERE production_id=? AND kind=?
               ORDER BY revision DESC LIMIT 1""",
            (production["id"], kind),
        ).fetchone()
        revision = (previous["revision"] + 1) if previous else 1
        if previous:
            conn.execute("UPDATE document_revisions SET status='superseded' WHERE id=?", (previous["id"],))
        document_id = _id("doc")
        conn.execute(
            """INSERT INTO document_revisions
               (id, production_id, kind, revision, status, schema_version, payload_json,
                payload_sha256, supersedes_id, source_uri, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                document_id, production["id"], kind, revision, "active",
                str(payload.get("schema_version", "")) or None, canonical, digest,
                previous["id"] if previous else None, str(path.resolve()), _now(),
            ),
        )
        return _row(conn.execute("SELECT * FROM document_revisions WHERE id=?", (document_id,)).fetchone())


def import_artifact(project_slug, kind, path, metadata=None, db_path=None):
    """Register an existing file in the immutable artifact registry."""
    path = Path(path)
    production = ensure_production(project_slug, db_path=db_path)
    absolute = path.resolve()
    digest = _sha256_file(absolute) if absolute.is_file() else None
    size = absolute.stat().st_size if absolute.is_file() else None
    with transaction(db_path) as conn:
        existing = conn.execute(
            """SELECT * FROM artifacts WHERE production_id=? AND uri=?
               AND ((sha256=?) OR (sha256 IS NULL AND ? IS NULL))""",
            (production["id"], str(absolute), digest, digest),
        ).fetchone()
        if existing:
            return _row(existing)
        artifact_id = _id("art")
        conn.execute(
            """INSERT INTO artifacts
               (id, production_id, kind, uri, storage_backend, sha256, size_bytes,
                metadata_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                artifact_id, production["id"], kind, str(absolute), "local", digest, size,
                _json(metadata or {}), _now(),
            ),
        )
        return _row(conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone())


def import_legacy_clip(project_slug, clip, db_path=None):
    """Upsert one clips.db row as a render unit plus optional artifact."""
    production = ensure_production(project_slug, db_path=db_path)
    start_ms = round(float(clip.get("required_start_sec") or 0) * 1000)
    end_ms = round(float(clip.get("required_end_sec") or 0) * 1000)
    if end_ms <= start_ms:
        end_ms = start_ms + max(1, round(float(clip.get("required_dur_sec") or 0.001) * 1000))
    path = Path(clip.get("output_path") or "")
    full_path = path if path.is_absolute() else ROOT / path
    artifact = import_artifact(project_slug, clip.get("asset_type") or "media", full_path,
                               metadata={"legacy_clip_id": clip.get("clip_id")}, db_path=db_path) \
        if full_path.is_file() else None
    now = _now()
    raw_policy = clip.get("audio_policy") or "strip"
    policy_map = {
        "baked_in": "HERO_SYNC_LOCKED", "generated_tts": "HERO_SYNC_LOCKED",
        "strip": "BROLL_FLEX", "ambient": "AMBIENCE_OR_SFX",
        "narration_overlay": "BROLL_FLEX", "silent": "SILENT_GRAPHIC",
        "HERO_SYNC_LOCKED": "HERO_SYNC_LOCKED", "BROLL_FLEX": "BROLL_FLEX",
        "BROLL_SYNCED_ACTION": "BROLL_SYNCED_ACTION",
        "AMBIENCE_OR_SFX": "AMBIENCE_OR_SFX", "MUSIC_BED": "MUSIC_BED",
        "SILENT_GRAPHIC": "SILENT_GRAPHIC",
    }
    audio_policy = policy_map.get(raw_policy, "BROLL_FLEX")
    is_hero = audio_policy == "HERO_SYNC_LOCKED"
    final_audio = "master_narration" if is_hero else "none"
    provider_usage = "diagnostic_only" if is_hero else "discarded"
    with transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM render_units WHERE legacy_clip_id=?", (clip.get("clip_id"),)
        ).fetchone()
        ordinal = existing["ordinal"] if existing else conn.execute(
            "SELECT COALESCE(MAX(ordinal), -1) + 1 AS n FROM render_units WHERE production_id=?",
            (production["id"],),
        ).fetchone()["n"]
        render_unit_id = existing["id"] if existing else _id("render")
        conn.execute(
            """INSERT INTO render_units
               (id, production_id, ordinal, label, legacy_clip_id, asset_type, model,
                audio_policy, final_audio_source, provider_audio_usage, text_policy,
                lipsync_required, required_start_ms, required_end_ms,
                required_duration_ms, slot_index, slot_total, status, active_artifact_id,
                metadata_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(legacy_clip_id) DO UPDATE SET
                 label=excluded.label,
                 asset_type=excluded.asset_type,
                 model=excluded.model,
                 audio_policy=excluded.audio_policy,
                 final_audio_source=excluded.final_audio_source,
                 provider_audio_usage=excluded.provider_audio_usage,
                 text_policy=excluded.text_policy,
                 lipsync_required=excluded.lipsync_required,
                 required_start_ms=excluded.required_start_ms,
                 required_end_ms=excluded.required_end_ms,
                 required_duration_ms=excluded.required_duration_ms,
                 slot_index=excluded.slot_index,
                 slot_total=excluded.slot_total,
                 status=excluded.status,
                 active_artifact_id=COALESCE(excluded.active_artifact_id, render_units.active_artifact_id),
                 metadata_json=excluded.metadata_json,
                 updated_at=excluded.updated_at""",
            (
                render_unit_id, production["id"], ordinal, clip.get("production_beat_id"),
                clip.get("clip_id"), clip.get("asset_type") or "generated_video",
                clip.get("model"), audio_policy,
                final_audio, provider_usage, "NO_VISIBLE_TEXT" if not is_hero else None,
                int(bool(clip.get("lipsync_required"))), start_ms, end_ms, end_ms - start_ms,
                clip.get("split_index"), clip.get("split_total"), clip.get("status") or "ordered",
                artifact["id"] if artifact else None, _json(clip), now, now,
            ),
        )
        return _row(conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone())


def mirror_clip_validation(project_slug, legacy_clip_id, status, validator_name,
                           evidence=None, db_path=None):
    """Append validation evidence for the current render-unit state."""
    production = ensure_production(project_slug, db_path=db_path)
    with transaction(db_path) as conn:
        render = conn.execute(
            "SELECT * FROM render_units WHERE legacy_clip_id=?", (legacy_clip_id,)
        ).fetchone()
        if not render:
            return None
        validation_id = _id("validation")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                validation_id, production["id"], "render_unit", render["id"],
                validator_name, status, _json(evidence or {}), _now(),
            ),
        )
        if status == "pass":
            conn.execute(
                "UPDATE render_units SET approved_validation_id=?, updated_at=? WHERE id=?",
                (validation_id, _now(), render["id"]),
            )
        return validation_id


def mirror_change_request(project_slug, legacy_clip_id, change_type, requested_by,
                          target_stage, reason, status="open", resolution=None, db_path=None):
    """Mirror a clip change request using a deterministic legacy identity."""
    production = ensure_production(project_slug, db_path=db_path)
    event_key = f"legacy-change:{legacy_clip_id}:{change_type}:{requested_by}:{target_stage}:{reason}"
    with transaction(db_path) as conn:
        render = conn.execute(
            "SELECT * FROM render_units WHERE legacy_clip_id=?", (legacy_clip_id,)
        ).fetchone()
        if not render:
            return None
        existing = conn.execute(
            """SELECT * FROM change_requests WHERE production_id=? AND subject_id=?
               AND change_type=? AND requested_by_stage=? AND target_stage=? AND reason=?
               ORDER BY created_at DESC LIMIT 1""",
            (production["id"], render["id"], change_type, requested_by, target_stage, reason),
        ).fetchone()
        request_id = existing["id"] if existing else _id("change")
        conn.execute(
            """INSERT INTO change_requests
               (id, production_id, subject_type, subject_id, change_type, requested_by_stage,
                target_stage, reason, status, resolution_json, created_at, resolved_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                 resolution_json=excluded.resolution_json, resolved_at=excluded.resolved_at""",
            (
                request_id, production["id"], "render_unit", render["id"], change_type,
                requested_by, target_stage, reason, status, _json(resolution or {}), _now(),
                _now() if status != "open" else None,
            ),
        )
        append_event(
            production["id"], "change_request_mirrored", actor=requested_by,
            payload={"legacy_clip_id": legacy_clip_id, "status": status},
            event_key=event_key, conn=conn,
        )
        return request_id


def resolve_mirrored_changes(project_slug, legacy_clip_id, resolved_by, outcome, db_path=None):
    """Resolve every open unified change request for a legacy clip."""
    production = ensure_production(project_slug, db_path=db_path)
    now = _now()
    with transaction(db_path) as conn:
        render = conn.execute(
            "SELECT * FROM render_units WHERE legacy_clip_id=?", (legacy_clip_id,)
        ).fetchone()
        if not render:
            return 0
        cursor = conn.execute(
            """UPDATE change_requests SET status='resolved', resolution_json=?, resolved_at=?
               WHERE production_id=? AND subject_id=? AND status='open'""",
            (_json({"resolved_by": resolved_by, "outcome": outcome}), now,
             production["id"], render["id"]),
        )
        append_event(
            production["id"], "change_requests_resolved", actor=resolved_by,
            payload={"legacy_clip_id": legacy_clip_id, "outcome": outcome}, conn=conn,
        )
        return cursor.rowcount


def blockers(project_or_id, db_path=None):
    """Return actionable blockers for one production."""
    production = get_production(project_or_id, db_path=db_path)
    if not production:
        return [{"type": "missing_production", "detail": project_or_id}]
    migrate(db_path)
    conn = connect(db_path)
    items = []
    for row in conn.execute(
        "SELECT stage_name, error_message FROM stage_runs WHERE production_id=? AND status='failed'",
        (production["id"],),
    ):
        items.append({"type": "failed_stage", "owner": row["stage_name"], "detail": row["error_message"]})
    for row in conn.execute(
        """SELECT gate_name, status FROM approval_requests
           WHERE production_id=? AND status NOT IN ('pass')""",
        (production["id"],),
    ):
        items.append({"type": "approval", "owner": row["gate_name"], "detail": row["status"]})
    for row in conn.execute(
        """SELECT target_stage, reason FROM change_requests
           WHERE production_id=? AND status='open'""",
        (production["id"],),
    ):
        items.append({"type": "change_request", "owner": row["target_stage"], "detail": row["reason"]})
    for row in conn.execute(
        """SELECT legacy_clip_id, status FROM render_units
           WHERE production_id=? AND status IN ('failed','stale','change_requested')""",
        (production["id"],),
    ):
        items.append({"type": "render_unit", "owner": row["legacy_clip_id"], "detail": row["status"]})
    conn.close()
    return items


def events(project_or_id, db_path=None):
    production = get_production(project_or_id, db_path=db_path)
    if not production:
        return []
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM production_events WHERE production_id=? ORDER BY created_at, id",
        (production["id"],),
    ).fetchall()
    conn.close()
    return [_row(row) for row in rows]


def integrity_check(db_path=None):
    migrate(db_path)
    conn = connect(db_path)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    conn.close()
    return integrity, foreign_keys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Unified production ledger.")
    parser.add_argument("--db", help="Override production database path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("migrate")
    create = sub.add_parser("create")
    create.add_argument("project_slug")
    create.add_argument("--seed")
    create.add_argument("--format", dest="video_type")
    show = sub.add_parser("show")
    show.add_argument("project")
    sub.add_parser("list")
    ev = sub.add_parser("events")
    ev.add_argument("project")
    blocked = sub.add_parser("blockers")
    blocked.add_argument("project")
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("project")
    enqueue.add_argument("stage")
    enqueue.add_argument("--priority", type=int, default=0)
    enqueue.add_argument("--payload", default="{}", help="JSON object")
    lease = sub.add_parser("lease")
    lease.add_argument("worker")
    lease.add_argument("--seconds", type=int, default=300)
    sub.add_parser("check")
    args = parser.parse_args(argv)

    if args.command == "init":
        print(migrate(args.db))
    if args.command == "migrate":
        print(migrate(args.db))
    elif args.command == "create":
        print(json.dumps(ensure_production(args.project_slug, args.seed, args.video_type,
                                           db_path=args.db), indent=2))
    elif args.command == "show":
        row = get_production(args.project, db_path=args.db)
        if not row:
            print(f"not found: {args.project}", file=sys.stderr)
            return 1
        row["blockers"] = blockers(args.project, db_path=args.db)
        print(json.dumps(row, indent=2))
    elif args.command == "list":
        print(json.dumps(list_productions(db_path=args.db), indent=2))
    elif args.command == "events":
        print(json.dumps(events(args.project, db_path=args.db), indent=2))
    elif args.command == "blockers":
        print(json.dumps(blockers(args.project, db_path=args.db), indent=2))
    elif args.command == "enqueue":
        print(json.dumps(enqueue_job(
            args.project, args.stage, payload=json.loads(args.payload), priority=args.priority,
            db_path=args.db,
        ), indent=2))
    elif args.command == "lease":
        print(json.dumps(lease_job(args.worker, args.seconds, db_path=args.db), indent=2))
    elif args.command == "check":
        integrity, foreign_keys = integrity_check(args.db)
        print(json.dumps({"integrity": integrity, "foreign_key_violations": foreign_keys}, indent=2))
        return 0 if integrity == "ok" and not foreign_keys else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
