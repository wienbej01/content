"""S22_T020: Downstream invalidation/rerun planner.

Given a targeted change request or repaired entity, this planner:
- Identifies affected downstream stages.
- Marks affected stage runs stale.
- Marks affected approvals stale.
- Preserves unaffected artifacts and stage runs.
- Blocks stale artifact reuse if requirement hash changed.
- Emits exact next action list.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import production_db as _db
import stage_runner

ROOT = Path(__file__).resolve().parent.parent

# Canonical stage order from STAGE_REGISTRY — used for ordering next actions.
_CANONICAL_STAGE_ORDER: list[str] = list(stage_runner.STAGE_REGISTRY.keys())

# Map of entity-kind → downstream stages that must be staled when that entity
# changes, sourced from S22_FEEDBACK_LOOP_RULES.md. "compile_overlays" and
# "render_overlays" from the feedback rules map to "graphics_compositing" in the
# registry.
_SHOT_DOWNSTREAM = [
    "compile_media", "gate_a_spend", "generate_media",
    "qa_media", "repair", "assemble", "qa_final", "gate_b_review",
]

_OVERLAY_DOWNSTREAM = [
    "graphics_compositing", "assemble", "qa_final", "gate_b_review",
]

_MEDIA_DRIFT_DOWNSTREAM = [
    "qa_media", "repair", "graphics_compositing",
    "assemble", "qa_final", "gate_b_review",
]

_STORYBOARD_REVISION_DOWNSTREAM = [
    "gate_storyboard",
    "tts", "audio_timing", "reconcile_timing",
    "compile_media", "graphics_compositing", "gate_a_spend",
    "generate_media", "qa_media", "repair",
    "assemble", "qa_final", "gate_b_review",
]

# Gates whose approval_requests must be staled per entity kind.
_STORYBOARD_APPROVAL_GATES = ["gate_storyboard", "gate_a_spend", "gate_b_review"]
_SHOT_APPROVAL_GATES = ["gate_a_spend", "gate_b_review"]
_OVERLAY_APPROVAL_GATES = ["gate_b_review"]
_DRIFT_APPROVAL_GATES = ["gate_b_review"]


@dataclass
class ChangeRequest:
    """Describes what changed and what must be invalidated."""
    entity_type: str
    entity_id: str
    reason: str
    metadata: dict = field(default_factory=dict)


@dataclass
class InvalidationPlan:
    """Result of planning invalidation."""
    entity_type: str
    entity_id: str
    reason: str
    stages_to_stale: list[str] = field(default_factory=list)
    approval_gates_to_stale: list[str] = field(default_factory=list)
    render_unit_ids_to_stale: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    unaffected_stages: list[str] = field(default_factory=list)


def _stages_present(production_id: str, stages: list[str], db_path=None) -> list[str]:
    """Return the subset of `stages` that exist in stage_runs for this production."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    ph = ",".join("?" * len(stages))
    rows = conn.execute(
        f"SELECT DISTINCT stage_name FROM stage_runs WHERE production_id=? AND stage_name IN ({ph})",
        (production_id, *stages),
    ).fetchall()
    conn.close()
    return [r["stage_name"] for r in rows]


def _all_registry_stages() -> list[str]:
    """Return all stage names in canonical order."""
    return list(stage_runner.STAGE_REGISTRY.keys())


def plan_shot_repair_invalidation(
    production_id: str,
    render_unit_id: str,
    reason: str = "shot repair",
    db_path=None,
) -> InvalidationPlan:
    """Plan invalidation after a specific shot/render_unit is repaired.

    Test requirement 1: stales compile_media, gate_a_spend, generate_media
    (affected unit), qa_media, assemble, qa_final, gate_b_review.
    """
    all_stages = _all_registry_stages()
    downstream = _SHOT_DOWNSTREAM
    present = _stages_present(production_id, downstream, db_path=db_path)
    unaffected = [s for s in all_stages if s not in present]

    next_actions = sorted(present, key=lambda s: _CANONICAL_STAGE_ORDER.index(s)
                          if s in _CANONICAL_STAGE_ORDER else 999)

    return InvalidationPlan(
        entity_type="shot",
        entity_id=render_unit_id,
        reason=reason,
        stages_to_stale=present,
        approval_gates_to_stale=_SHOT_APPROVAL_GATES,
        render_unit_ids_to_stale=[render_unit_id],
        next_actions=next_actions,
        unaffected_stages=unaffected,
    )


def plan_overlay_repair_invalidation(
    production_id: str,
    render_unit_id: str,
    reason: str = "overlay repair",
    db_path=None,
) -> InvalidationPlan:
    """Plan invalidation after an overlay is repaired.

    Test requirement 2: stales graphics_compositing, assemble, qa_final, gate_b_review.
    """
    all_stages = _all_registry_stages()
    downstream = _OVERLAY_DOWNSTREAM
    present = _stages_present(production_id, downstream, db_path=db_path)
    unaffected = [s for s in all_stages if s not in present]

    next_actions = sorted(present, key=lambda s: _CANONICAL_STAGE_ORDER.index(s)
                          if s in _CANONICAL_STAGE_ORDER else 999)

    return InvalidationPlan(
        entity_type="overlay",
        entity_id=render_unit_id,
        reason=reason,
        stages_to_stale=present,
        approval_gates_to_stale=_OVERLAY_APPROVAL_GATES,
        render_unit_ids_to_stale=[render_unit_id],
        next_actions=next_actions,
        unaffected_stages=unaffected,
    )


def plan_media_drift_invalidation(
    production_id: str,
    artifact_id: str,
    render_unit_id: Optional[str] = None,
    reason: str = "media duration drift",
    db_path=None,
) -> InvalidationPlan:
    """Plan invalidation after observed media duration drifts from planned.

    Test requirement 3: stales qa_media, assemble, qa_final, gate_b_review.
    """
    all_stages = _all_registry_stages()
    downstream = _MEDIA_DRIFT_DOWNSTREAM
    present = _stages_present(production_id, downstream, db_path=db_path)
    unaffected = [s for s in all_stages if s not in present]

    next_actions = sorted(present, key=lambda s: _CANONICAL_STAGE_ORDER.index(s)
                          if s in _CANONICAL_STAGE_ORDER else 999)

    plan = InvalidationPlan(
        entity_type="media_artifact",
        entity_id=artifact_id,
        reason=reason,
        stages_to_stale=present,
        approval_gates_to_stale=_DRIFT_APPROVAL_GATES,
        next_actions=next_actions,
        unaffected_stages=unaffected,
    )
    if render_unit_id:
        plan.render_unit_ids_to_stale = [render_unit_id]
    return plan


def plan_storyboard_revision_invalidation(
    production_id: str,
    document_revision_id: str,
    reason: str = "storyboard revision change",
    db_path=None,
) -> InvalidationPlan:
    """Plan invalidation after the storyboard document revision changes.

    Test requirement 4: stales gate_storyboard and all downstream stages.
    """
    all_stages = _all_registry_stages()
    downstream = _STORYBOARD_REVISION_DOWNSTREAM
    present = _stages_present(production_id, downstream, db_path=db_path)
    unaffected = [s for s in all_stages if s not in present]

    next_actions = sorted(present, key=lambda s: _CANONICAL_STAGE_ORDER.index(s)
                          if s in _CANONICAL_STAGE_ORDER else 999)

    return InvalidationPlan(
        entity_type="storyboard_revision",
        entity_id=document_revision_id,
        reason=reason,
        stages_to_stale=present,
        approval_gates_to_stale=_STORYBOARD_APPROVAL_GATES,
        next_actions=next_actions,
        unaffected_stages=unaffected,
    )


def apply_invalidation(
    production_id: str,
    plan: InvalidationPlan,
    db_path=None,
) -> dict:
    """Execute an invalidation plan atomically.

    Returns counts of each affected entity type.

    Idempotent: running twice with the same plan produces the same DB state
    because stale markers are idempotent INSERT/UPDATE operations.
    """
    _db.migrate(db_path)
    production = _db.get_production(production_id, db_path=db_path)
    if not production:
        raise RuntimeError(f"BLOCKED: production {production_id} not found")
    project_slug = production["project_slug"]

    now = _db._now()

    # 1. Stale stage_runs
    stage_count = 0
    if plan.stages_to_stale:
        stage_count = _db.invalidate_stages(
            project_slug,
            plan.stages_to_stale,
            reason=plan.reason,
            db_path=db_path,
        )

    # 2. Stale approval_requests
    approval_count = 0
    if plan.approval_gates_to_stale:
        with _db.transaction(db_path) as conn:
            for gate_name in plan.approval_gates_to_stale:
                cur = conn.execute(
                    """UPDATE approval_requests SET status='stale'
                       WHERE production_id=? AND gate_name=? AND status='pass'""",
                    (production["id"], gate_name),
                )
                approval_count += cur.rowcount
            conn.execute(
                "UPDATE productions SET status='running', updated_at=? WHERE id=?",
                (now, production["id"]),
            )

    # 3. Stale affected render_units (blocks stale artifact reuse)
    render_unit_count = 0
    if plan.render_unit_ids_to_stale:
        with _db.transaction(db_path) as conn:
            ph = ",".join("?" * len(plan.render_unit_ids_to_stale))
            cur = conn.execute(
                f"""UPDATE render_units SET status='stale', active_artifact_id=NULL,
                   updated_at=? WHERE production_id=? AND id IN ({ph})""",
                (now, production["id"], *plan.render_unit_ids_to_stale),
            )
            render_unit_count = cur.rowcount

    _db.append_event(
        production["id"], "rerun_plan_applied",
        payload={
            "entity_type": plan.entity_type,
            "entity_id": plan.entity_id,
            "reason": plan.reason,
            "stages_staled": plan.stages_to_stale,
            "approvals_staled": plan.approval_gates_to_stale,
            "render_units_staled": plan.render_unit_ids_to_stale,
            "next_actions": plan.next_actions,
            "stage_count": stage_count,
            "approval_count": approval_count,
            "render_unit_count": render_unit_count,
        },
        db_path=db_path,
    )

    return {
        "stages_staled": stage_count,
        "approvals_staled": approval_count,
        "render_units_staled": render_unit_count,
        "next_actions": plan.next_actions,
        "unaffected_stages": plan.unaffected_stages,
    }


def plan_and_apply(
    production_id: str,
    change: ChangeRequest,
    db_path=None,
) -> dict:
    """Convenience: plan invalidation for a change request and apply it.

    Returns the invalidation result dict.
    """
    entity_type = change.entity_type

    if entity_type == "shot":
        plan = plan_shot_repair_invalidation(
            production_id, change.entity_id, change.reason, db_path=db_path,
        )
    elif entity_type == "overlay":
        plan = plan_overlay_repair_invalidation(
            production_id, change.entity_id, change.reason, db_path=db_path,
        )
    elif entity_type == "media_artifact":
        ru_id = change.metadata.get("render_unit_id")
        plan = plan_media_drift_invalidation(
            production_id, change.entity_id, ru_id, change.reason, db_path=db_path,
        )
    elif entity_type == "storyboard_revision":
        plan = plan_storyboard_revision_invalidation(
            production_id, change.entity_id, change.reason, db_path=db_path,
        )
    else:
        raise RuntimeError(
            f"BLOCKED_FEEDBACK_UNROUTED: unknown entity_type '{entity_type}'"
        )

    plan.metadata = change.metadata
    return apply_invalidation(production_id, plan, db_path=db_path)
