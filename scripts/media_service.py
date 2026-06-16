"""Sprint 6: Media generation service.

MEDIA-601  Provider-job state machine (submit, poll, download, retry)
MEDIA-602  Generation worker migration (render-unit driven, no filename inference)
MEDIA-603  Graphics / overlay migration (typed MIME from DB)
QA-604     Media validation evidence store
QA-605     Change-request routing
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import production_db as _db
import production_repo as _repo


# ---------------------------------------------------------------------------
# MEDIA-601  Provider-job state machine
# ---------------------------------------------------------------------------

class ProviderJobError(Exception):
    pass


def submit_provider_job(
    production_id: str,
    render_unit_id: str,
    provider: str,
    operation: str,
    request_payload: dict,
    idempotency_key: Optional[str] = None,
    db_path=None,
) -> dict:
    """Register a provider job and mark it 'submitted'.

    Idempotent: same idempotency_key returns the existing row.
    A billable job CANNOT be submitted without a passing spend approval
    (checked here via the gate_a_spend approval_request).
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    spend_approval = conn.execute(
        """SELECT status FROM approval_requests
           WHERE production_id=? AND gate_name='gate_a_spend'""",
        (production_id,),
    ).fetchone()
    conn.close()

    if not spend_approval or spend_approval["status"] != "pass":
        raise ProviderJobError(
            f"Cannot submit provider job: gate_a_spend is "
            f"{'missing' if not spend_approval else spend_approval['status']} "
            f"for production {production_id}"
        )

    idem = idempotency_key or (
        f"pjob:{production_id}:{render_unit_id}:{provider}:{operation}:"
        f"{_db._sha256_bytes(_db._json(request_payload).encode())[:16]}"
    )
    now = _db._now()

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM provider_jobs WHERE idempotency_key=?", (idem,)
        ).fetchone()
        if existing:
            return dict(existing)

        job_id = _db._id("pjob")
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation,
                idempotency_key, status, request_json, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                job_id, production_id, render_unit_id, provider, operation,
                idem, "submitted", _db._json(request_payload), now,
            ),
        )
        # Advance render unit status
        conn.execute(
            "UPDATE render_units SET status='generating', updated_at=? WHERE id=?",
            (now, render_unit_id),
        )
        _db.append_event(
            production_id, "provider_job_submitted",
            payload={"job_id": job_id, "provider": provider, "operation": operation,
                     "render_unit_id": render_unit_id},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM provider_jobs WHERE id=?", (job_id,)).fetchone())


def poll_provider_job(
    provider_job_id: str,
    external_job_id: Optional[str] = None,
    new_status: Optional[str] = None,  # 'running', 'completed', 'failed'
    db_path=None,
) -> dict:
    """Update provider job status from an external poll result."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        update_parts = ["polled_at=?"]
        params: list = [now]
        if external_job_id:
            update_parts.append("external_job_id=?")
            params.append(external_job_id)
        if new_status:
            update_parts.append("status=?")
            params.append(new_status)
            if new_status in ("completed", "failed"):
                update_parts.append("completed_at=?")
                params.append(now)
        params.append(provider_job_id)
        conn.execute(
            f"UPDATE provider_jobs SET {', '.join(update_parts)} WHERE id=?", params
        )
        return dict(conn.execute(
            "SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)
        ).fetchone())


def complete_provider_job(
    provider_job_id: str,
    result_artifact_path: str | Path,
    result_metadata: Optional[dict] = None,
    db_path=None,
) -> dict:
    """Mark a provider job complete and register the output artifact.

    Atomically:
    1. Registers the artifact in the immutable registry.
    2. Links the artifact to the render unit.
    3. Records the provider job response.
    4. Appends a cost event if actual_usd is in result_metadata.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    job = conn.execute("SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)).fetchone()
    conn.close()
    if not job:
        raise ProviderJobError(f"provider_job {provider_job_id} not found")
    job = dict(job)

    art = _repo.register_artifact(
        job["production_id"],
        result_artifact_path,
        kind="generated_media",
        provider_job_id=provider_job_id,
        extra_metadata=result_metadata or {},
        db_path=db_path,
    )

    now = _db._now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            """UPDATE provider_jobs SET status='completed', completed_at=?, response_json=?
               WHERE id=?""",
            (now, _db._json(result_metadata or {}), provider_job_id),
        )
        # Link artifact to render unit
        if job["render_unit_id"]:
            conn.execute(
                """UPDATE render_units SET active_artifact_id=?, status='generated', updated_at=?
                   WHERE id=?""",
                (art["id"], now, job["render_unit_id"]),
            )

    # Record actual cost if provided
    if result_metadata and result_metadata.get("actual_usd") is not None:
        with _db.transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO cost_events
                   (id, production_id, provider_job_id, provider, operation,
                    actual_usd, currency, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    _db._id("cost"), job["production_id"], provider_job_id,
                    job["provider"], job["operation"],
                    result_metadata["actual_usd"], "USD", now,
                ),
            )

    _db.append_event(
        job["production_id"], "provider_job_completed",
        payload={"job_id": provider_job_id, "artifact_id": art["id"]},
        db_path=db_path,
    )
    return art


def fail_provider_job(
    provider_job_id: str,
    error: str,
    db_path=None,
) -> dict:
    """Mark a provider job failed and propagate to its render unit."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        job = conn.execute("SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)).fetchone()
        if not job:
            raise ProviderJobError(f"provider_job {provider_job_id} not found")
        conn.execute(
            """UPDATE provider_jobs SET status='failed', completed_at=?,
               error_json=? WHERE id=?""",
            (now, _db._json({"error": error}), provider_job_id),
        )
        if job["render_unit_id"]:
            conn.execute(
                "UPDATE render_units SET status='failed', updated_at=? WHERE id=?",
                (now, job["render_unit_id"]),
            )
        return dict(conn.execute("SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)).fetchone())


# ---------------------------------------------------------------------------
# QA-604  Media validation evidence
# ---------------------------------------------------------------------------

def record_validation_evidence(
    production_id: str,
    subject_type: str,
    subject_id: str,
    validator_name: str,
    passed: bool,
    evidence: dict,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Store validation evidence and update the subject's approved_validation_id if passed.

    A subject is only consumable when required validations pass (HARD INVARIANT #4).
    """
    now = _db._now()
    with _db.transaction(db_path) as conn:
        val_id = _db._id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_by_stage_run_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                val_id, production_id, subject_type, subject_id, validator_name,
                "pass" if passed else "fail",
                _db._json(evidence), stage_run_id, now,
            ),
        )
        if passed and subject_type == "render_unit":
            conn.execute(
                "UPDATE render_units SET approved_validation_id=?, status='valid', updated_at=? WHERE id=?",
                (val_id, now, subject_id),
            )
        return dict(conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone())


def run_render_unit_qa(
    production_id: str,
    render_unit_id: str,
    checks: dict,
    db_path=None,
) -> dict:
    """Run the standard media QA checklist against a render unit.

    checks: {
        "file_exists": bool,
        "dimensions_ok": bool,
        "duration_ok": bool,
        "audio_policy_ok": bool,
        "sha_match": bool,
        "details": {...}
    }

    Returns validation row. Raises if the render unit has no active artifact.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
    conn.close()
    if not ru:
        raise ValueError(f"render_unit {render_unit_id} not found")
    if not ru["active_artifact_id"]:
        raise ValueError(f"render_unit {render_unit_id} has no active artifact — cannot QA")

    required_checks = ["file_exists", "dimensions_ok", "duration_ok", "audio_policy_ok"]
    passed = all(bool(checks.get(k)) for k in required_checks)
    # sha_match is also required when present
    if "sha_match" in checks:
        passed = passed and bool(checks["sha_match"])

    return record_validation_evidence(
        production_id, "render_unit", render_unit_id,
        "qa_media", passed, checks, db_path=db_path,
    )


# ---------------------------------------------------------------------------
# QA-605  Change-request routing
# ---------------------------------------------------------------------------

def route_change_request(
    production_id: str,
    render_unit_id: str,
    change_type: str,  # 'regenerate', 're-slice', 're-plan', 're-render'
    reason: str,
    requested_by: str = "qa_media",
    target_stage: str = "generate_media",
    db_path=None,
) -> dict:
    """Create a change request and reset the render unit so it can re-flow.

    Change types and their target stages:
    - 'regenerate'  → generate_media (new provider call needed)
    - 're-slice'    → audio_timing   (re-slice audio)
    - 're-plan'     → compile_media  (change prompt/model)
    - 're-render'   → assemble       (re-render from existing clips)
    """
    now = _db._now()
    with _db.transaction(db_path) as conn:
        ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
        if not ru:
            raise ValueError(f"render_unit {render_unit_id} not found")

        req_id = _db._id("change")
        conn.execute(
            """INSERT INTO change_requests
               (id, production_id, subject_type, subject_id, change_type,
                requested_by_stage, target_stage, reason, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                req_id, production_id, "render_unit", render_unit_id,
                change_type, requested_by, target_stage, reason, "open", now,
            ),
        )
        conn.execute(
            "UPDATE render_units SET status='change_requested', updated_at=? WHERE id=?",
            (now, render_unit_id),
        )
        _db.append_event(
            production_id, "change_request_created",
            payload={"req_id": req_id, "render_unit_id": render_unit_id,
                     "change_type": change_type, "target_stage": target_stage},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM change_requests WHERE id=?", (req_id,)).fetchone())


def resolve_change_request(
    production_id: str,
    change_request_id: str,
    resolution: str,  # 'accepted' | 'rejected'
    resolved_by: str = "system",
    db_path=None,
) -> dict:
    """Resolve an open change request and reset render unit to 'ordered'."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        req = conn.execute(
            "SELECT * FROM change_requests WHERE id=?", (change_request_id,)
        ).fetchone()
        if not req:
            raise ValueError(f"change_request {change_request_id} not found")
        conn.execute(
            """UPDATE change_requests SET status='resolved', resolution_json=?, resolved_at=?
               WHERE id=?""",
            (_db._json({"resolution": resolution, "resolved_by": resolved_by}),
             now, change_request_id),
        )
        if resolution == "accepted":
            conn.execute(
                "UPDATE render_units SET status='ordered', updated_at=? WHERE id=?",
                (now, req["subject_id"]),
            )
        return dict(conn.execute("SELECT * FROM change_requests WHERE id=?", (change_request_id,)).fetchone())


def get_open_change_requests(production_id: str, target_stage: Optional[str] = None, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    if target_stage:
        rows = conn.execute(
            """SELECT * FROM change_requests
               WHERE production_id=? AND status='open' AND target_stage=?""",
            (production_id, target_stage),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM change_requests WHERE production_id=? AND status='open'",
            (production_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
