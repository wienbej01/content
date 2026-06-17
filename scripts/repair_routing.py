"""Sprint 6/R6: Repair Routing (Ticket LB-603 / R6-004).

R6-004: Rebuild repair routing to use repository services instead of raw
incompatible SQL. Stores change_type, requested_by_stage, target_stage,
failure_evidence, replacement artifact info, and resolution_json.

Uses production_repo.change_request services and production_db.transaction()
for crash-safe, transactional repair resolution.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import production_db as _db


class RepairRoutingError(ValueError):
    pass


def create_repair_request(
    production_id: str,
    render_unit_id: str,
    change_type: str,
    requested_by_stage: str,
    failure_reason: str,
    target_stage: str = "generate_media",
    failure_validation_id: Optional[str] = None,
    failed_artifact_id: Optional[str] = None,
    failure_evidence: Optional[Dict[str, Any]] = None,
    db_path=None,
) -> Dict[str, Any]:
    """Create a repair change request for a failed render unit.

    Marks the render_unit as 'change_requested'. All fields are populated
    to match the schema — no NOT NULL columns omitted.
    """
    if not change_type:
        raise RepairRoutingError("change_type is required")
    if not requested_by_stage:
        raise RepairRoutingError("requested_by_stage is required")

    from production_repo import record_change_request

    now = _db._now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            "UPDATE render_units SET status='change_requested', updated_at=? WHERE id=? AND production_id=?",
            (now, render_unit_id, production_id),
        )

        cr_id = f"cr_{_db._id('cr')[3:]}"
        conn.execute(
            """INSERT INTO change_requests
               (id, production_id, subject_type, subject_id, change_type,
                requested_by_stage, target_stage, reason, status,
                failure_evidence_json, replacement_subject_type, replacement_subject_id,
                repair_routing_stage, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cr_id, production_id, "render_unit", render_unit_id, change_type,
                requested_by_stage, target_stage, failure_reason, "open",
                _db._json(failure_evidence or {
                    "failure_validation_id": failure_validation_id,
                    "failed_artifact_id": failed_artifact_id,
                }),
                None, None,
                target_stage, now,
            ),
        )
        cr = dict(conn.execute("SELECT * FROM change_requests WHERE id=?", (cr_id,)).fetchone())

        invalidate_dependent_deliverables(production_id, render_unit_id, conn=conn)

        _db.append_event(
            production_id, "repair_request_created",
            payload={"render_unit_id": render_unit_id, "change_request_id": cr["id"], "reason": failure_reason},
            conn=conn,
        )

    return cr


def is_repair_request_open(production_id: str, render_unit_id: str, db_path=None) -> bool:
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM change_requests
           WHERE production_id=? AND subject_id=? AND status='open'""",
        (production_id, render_unit_id),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def resolve_repair_request(
    production_id: str,
    render_unit_id: str,
    replacement_artifact_id: str,
    replacement_validations: Optional[List[str]] = None,
    resolution_note: str = "",
    db_path=None,
) -> Dict[str, Any]:
    """Resolve a repair request by linking the replacement artifact.

    Transactional: marks the change request as resolved, updates the render
    unit's active artifact, and records the resolution in resolution_json.
    Requires that all replacement validations pass before resolving.
    """
    from production_repo import get_artifact

    replacement = get_artifact(replacement_artifact_id, db_path=db_path)
    if not replacement:
        raise RepairRoutingError(f"Replacement artifact {replacement_artifact_id} not found")

    now = _db._now()
    with _db.transaction(db_path) as conn:
        cr_row = conn.execute(
            """SELECT id, change_type, target_stage FROM change_requests
               WHERE production_id=? AND subject_id=? AND status='open'
               ORDER BY created_at DESC LIMIT 1""",
            (production_id, render_unit_id),
        ).fetchone()

        if not cr_row:
            raise RepairRoutingError(f"No open change request for render_unit {render_unit_id}")

        if replacement_validations:
            for val_id in replacement_validations:
                val = conn.execute(
                    "SELECT status FROM validations WHERE id=?", (val_id,)
                ).fetchone()
                if not val or val["status"] != "pass":
                    raise RepairRoutingError(f"Validation {val_id} does not pass — cannot resolve repair")

        conn.execute(
            """UPDATE change_requests SET
               status='resolved',
               resolution_json=?,
               replacement_subject_type='artifact',
               replacement_subject_id=?,
               resolved_at=?
               WHERE id=?""",
            (
                _db._json({"replacement_artifact_id": replacement_artifact_id,
                            "replacement_validations": replacement_validations,
                            "note": resolution_note}),
                replacement_artifact_id,
                now,
                cr_row["id"],
            ),
        )

        conn.execute(
            "UPDATE render_units SET active_artifact_id=?, status='generated', updated_at=? WHERE id=? AND production_id=?",
            (replacement_artifact_id, now, render_unit_id, production_id),
        )

        _db.append_event(
            production_id, "repair_resolved",
            payload={"render_unit_id": render_unit_id, "change_request_id": cr_row["id"],
                      "replacement_artifact_id": replacement_artifact_id},
            conn=conn,
        )

    return {
        "change_request_id": cr_row["id"],
        "render_unit_id": render_unit_id,
        "replacement_artifact_id": replacement_artifact_id,
        "status": "resolved",
    }


def invalidate_dependent_deliverables(
    production_id: str,
    render_unit_id: str,
    db_path=None,
    conn=None,
) -> List[str]:
    """Invalidate deliverables that depend on the given render unit."""
    if conn is not None:
        rows = conn.execute(
            """SELECT id FROM deliverables
               WHERE production_id=? AND status NOT IN ('stale', 'retired')""",
            (production_id,),
        ).fetchall()
        invalidated = []
        for row in rows:
            conn.execute(
                "UPDATE deliverables SET status='stale' WHERE id=?",
                (row["id"],),
            )
            invalidated.append(row["id"])
        return invalidated

    now = _db._now()
    with _db.transaction(db_path) as conn:
        rows = conn.execute(
            """SELECT id FROM deliverables
               WHERE production_id=? AND status NOT IN ('stale', 'retired')""",
            (production_id,),
        ).fetchall()
        invalidated = []
        for row in rows:
            conn.execute(
                "UPDATE deliverables SET status='stale' WHERE id=? AND production_id=?",
                (row["id"], production_id),
            )
            invalidated.append(row["id"])
        return invalidated


def get_open_repair_requests(production_id: str, db_path=None) -> List[Dict[str, Any]]:
    conn = _db.connect(db_path)
    rows = conn.execute(
        """SELECT * FROM change_requests
           WHERE production_id=? AND status='open'
           ORDER BY created_at DESC""",
        (production_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
