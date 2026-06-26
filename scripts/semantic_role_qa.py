"""S15-T003: Post-render semantic-role QA evidence (DB-native).

A render unit's editorial ``visual_role`` (S15-T002) declares WHY a shot is on
screen. This module records the post-render QA evidence that proves the RENDERED
content actually satisfies that declared role, and exposes the ``validator_name``
the assembly gate (S15-T003) keys on.

Evidence is stored in the existing ``validations`` table — there is no parallel
manifest-only path and no new table. Each evidence row is bound to the
``render_unit`` id (``subject_id``) AND records the ``visual_role`` it was
evaluated against, so the gate can prove the QA result corresponds to the unit's
CURRENT declared role — not a stale, label-inferred, or mismatched one.

Scope of THIS ticket: validate the evidence contract and gate behaviour using
deterministic evidence. Actual frame/content analysis is a later ticket
(S15-T004 frame-sampling utility) and will call :func:`record_semantic_role_qa`
with real verdicts. No provider render is involved here.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import production_db as _db

# Single source of truth for the validator_name that binds semantic-role QA
# evidence in the `validations` table. The assembly gate (assemble_db) imports
# this constant so record- and validate-side never drift apart.
SEMANTIC_ROLE_QA_VALIDATOR = "semantic_role_qa"

_VALID_STATUSES = ("pass", "fail")


def record_semantic_role_qa(
    production_id,
    render_unit_id,
    visual_role,
    status,
    *,
    category=None,
    reason=None,
    details=None,
    stage_run_id=None,
    db_path=None,
):
    """Record post-render semantic-role QA evidence for a render unit.

    Args:
        production_id: Production id.
        render_unit_id: The render unit whose rendered content was evaluated.
            The evidence is bound to this id (``validations.subject_id``); the
            gate looks up evidence per-unit, so evidence on the wrong unit never
            satisfies the unit that needs it.
        visual_role: The editorial visual_role the verdict was evaluated against.
            Required and non-empty — the gate binds evidence to this role and
            rejects evidence whose role does not match the unit's current role.
        status: ``'pass'`` or ``'fail'``.
        category: Optional role category (``'hero'``/``'broll'``/``'graphic'``)
            included for readability only.
        reason: Optional human-readable reason (semantically expected on a fail).
        details: Optional dict of extra deterministic evidence fields.
        stage_run_id: Optional originating stage run.
        db_path: Production DB path.

    Returns the created validation row as a dict.

    Raises:
        ValueError: on an invalid status, an empty visual_role, or an unknown
            render_unit. The recorder fails closed rather than persist ambiguous
            evidence; it never silently records a row that could masquerade as
            proof.
    """
    if not visual_role or not isinstance(visual_role, str):
        raise ValueError(
            "BLOCKED_SEMANTIC_ROLE_QA_EVIDENCE_INVALID: visual_role is required to "
            "bind semantic-role QA evidence to a render unit."
        )
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"BLOCKED_SEMANTIC_ROLE_QA_EVIDENCE_INVALID: status must be one of "
            f"{list(_VALID_STATUSES)}, got {status!r}."
        )

    evidence = {
        "render_unit_id": render_unit_id,
        "visual_role": visual_role,
        "result": status,
    }
    if category:
        evidence["category"] = category
    if reason:
        evidence["reason"] = reason
    if details:
        evidence["details"] = details

    now = _db._now()
    with _db.transaction(db_path) as conn:
        # Fail closed if the subject unit does not exist — never bind semantic
        # evidence to a phantom render_unit id.
        row = conn.execute(
            "SELECT 1 FROM render_units WHERE id=?", (render_unit_id,)
        ).fetchone()
        if row is None:
            raise ValueError(
                f"BLOCKED_SEMANTIC_ROLE_QA_EVIDENCE_INVALID: render_unit "
                f"{render_unit_id} does not exist; cannot bind semantic-role QA "
                f"evidence to it."
            )

        val_id = _db._id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_by_stage_run_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                val_id, production_id, "render_unit", render_unit_id,
                SEMANTIC_ROLE_QA_VALIDATOR, status, _db._json(evidence),
                stage_run_id, now,
            ),
        )
        _db.append_event(
            production_id, "semantic_role_qa_recorded",
            payload={
                "validation_id": val_id,
                "render_unit_id": render_unit_id,
                "visual_role": visual_role,
                "status": status,
            },
            conn=conn,
        )
        return dict(
            conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone()
        )
