#!/usr/bin/env python3
"""duration_drift.py — Duration drift resolver for S22_T018.

Resolves discrepancies between planned render-unit duration and observed
artifact duration according to Sonnet-authored shot drift policy.

No creative generation. No paid APIs. No LLM calls.

The resolver is deterministic: same inputs produce the same resolution.
Blocking drifts create change requests targeting the repair routing stage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_DRIFT_POLICIES = frozenset({
    "trim_ok",
    "pad_ok",
    "extend_still_ok",
    "regenerate_required",
    "sonnet_repair_required",
    "human_review_required",
})

VALID_RESOLUTIONS = frozenset({
    "accepted",
    "trim_in_assembly",
    "pad_or_extend",
    "regenerate_same_prompt",
    "sonnet_repair_storyboard",
    "human_review_required",
    "reject_unfixable",
})

Resolution = Literal[
    "accepted",
    "trim_in_assembly",
    "pad_or_extend",
    "regenerate_same_prompt",
    "sonnet_repair_storyboard",
    "human_review_required",
    "reject_unfixable",
]

DURATION_MATCH_TOLERANCE_SEC = 0.1
HERO_LIPSYNC_MAX_DRIFT_SEC = 0.15

POLICIES_NEED_TRIMMING = frozenset({"trim_ok"})
POLICIES_NEED_EXTENSION = frozenset({"extend_still_ok", "pad_ok"})


class DurationDriftError(ValueError):
    pass


@dataclass
class DriftInput:
    render_unit_id: Optional[str] = None
    production_id: Optional[str] = None
    artifact_id: Optional[str] = None
    shot_id: Optional[str] = None

    required_duration_ms: Optional[int] = None
    actual_duration_ms: Optional[int] = None
    min_usable_duration_ms: Optional[int] = None
    max_usable_duration_ms: Optional[int] = None

    duration_drift_policy: Optional[str] = None

    asset_type: Optional[str] = None
    audio_policy: Optional[str] = None

    is_hero_lipsync: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "render_unit_id": self.render_unit_id,
            "production_id": self.production_id,
            "artifact_id": self.artifact_id,
            "shot_id": self.shot_id,
            "required_duration_ms": self.required_duration_ms,
            "actual_duration_ms": self.actual_duration_ms,
            "min_usable_duration_ms": self.min_usable_duration_ms,
            "max_usable_duration_ms": self.max_usable_duration_ms,
            "duration_drift_policy": self.duration_drift_policy,
            "asset_type": self.asset_type,
            "audio_policy": self.audio_policy,
            "is_hero_lipsync": self.is_hero_lipsync,
        }


@dataclass
class DriftResolution:
    resolution: Resolution

    planned_duration_sec: float = 0.0
    actual_duration_sec: float = 0.0
    delta_sec: float = 0.0

    assembly_action: Optional[Literal["trim", "extend", "none"]] = None
    assembly_metadata: Dict[str, Any] = field(default_factory=dict)

    reason: str = ""
    change_request_id: Optional[str] = None
    validation_id: Optional[str] = None

    input_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution": self.resolution,
            "planned_duration_sec": self.planned_duration_sec,
            "actual_duration_sec": self.actual_duration_sec,
            "delta_sec": self.delta_sec,
            "assembly_action": self.assembly_action,
            "assembly_metadata": self.assembly_metadata,
            "reason": self.reason,
            "change_request_id": self.change_request_id,
            "validation_id": self.validation_id,
            "input_snapshot": self.input_snapshot,
        }


def _ms_to_sec(ms: Optional[int]) -> Optional[float]:
    if ms is None:
        return None
    return ms / 1000.0


def resolve_drift(
    inp: DriftInput,
    db_path=None,
    create_change_requests: bool = True,
) -> DriftResolution:
    """Resolve duration drift between planned and actual for one render unit.

    Returns a DriftResolution. Blocking cases create change requests when
    create_change_requests is True and the DB is reachable.

    The caller is responsible for passing production_id, render_unit_id,
    and artifact_id if DB change request creation is desired.
    """
    planned_sec = _ms_to_sec(inp.required_duration_ms)
    actual_sec = _ms_to_sec(inp.actual_duration_ms)
    min_sec = _ms_to_sec(inp.min_usable_duration_ms)
    max_sec = _ms_to_sec(inp.max_usable_duration_ms)

    input_snapshot = inp.to_dict()

    def _make(
        resolution: Resolution,
        reason: str,
        assembly_action: Optional[str] = None,
        assembly_metadata: Optional[Dict[str, Any]] = None,
        change_request_id: Optional[str] = None,
        validation_id: Optional[str] = None,
    ) -> DriftResolution:
        return DriftResolution(
            resolution=resolution,
            planned_duration_sec=planned_sec or 0.0,
            actual_duration_sec=actual_sec or 0.0,
            delta_sec=(actual_sec - planned_sec) if (actual_sec is not None and planned_sec is not None) else 0.0,
            assembly_action=assembly_action,
            assembly_metadata=assembly_metadata or {},
            reason=reason,
            change_request_id=change_request_id,
            validation_id=validation_id,
            input_snapshot=input_snapshot,
        )

    if actual_sec is None:
        return _make(
            "reject_unfixable",
            "BLOCKED_DURATION_DRIFT_UNRESOLVED: actual duration is missing; "
            "artifact must be probed before drift can be resolved.",
        )

    if planned_sec is None:
        return _make(
            "reject_unfixable",
            "BLOCKED_DURATION_DRIFT_UNRESOLVED: required duration is missing; "
            "render unit must declare a planned duration.",
        )

    policy = inp.duration_drift_policy
    if not policy or policy not in ALLOWED_DRIFT_POLICIES:
        return _make(
            "reject_unfixable",
            f"BLOCKED_DURATION_DRIFT_UNRESOLVED: unknown or missing drift policy "
            f"'{policy}'. Must be one of {sorted(ALLOWED_DRIFT_POLICIES)}.",
        )

    delta_sec = actual_sec - planned_sec

    if abs(delta_sec) <= DURATION_MATCH_TOLERANCE_SEC:
        return _make(
            "accepted",
            f"duration within {DURATION_MATCH_TOLERANCE_SEC}s tolerance "
            f"(planned={planned_sec:.3f}s, actual={actual_sec:.3f}s, "
            f"delta={delta_sec:.3f}s).",
        )

    cr_id = None
    val_id = None

    if inp.is_hero_lipsync and abs(delta_sec) > HERO_LIPSYNC_MAX_DRIFT_SEC:
        reason_base = (
            f"BLOCKED_DURATION_DRIFT: hero lipsync shot {inp.shot_id or inp.render_unit_id or '?'} "
            f"has {abs(delta_sec):.3f}s drift (planned={planned_sec:.3f}s, "
            f"actual={actual_sec:.3f}s). Lipsync drift > {HERO_LIPSYNC_MAX_DRIFT_SEC}s "
            f"is not trimmable/paddable."
        )
        if create_change_requests and inp.production_id and inp.render_unit_id:
            cr_id, val_id = _create_blocking_change_request(
                inp, reason_base, db_path=db_path,
            )
        return _make(
            "regenerate_same_prompt",
            reason_base,
            change_request_id=cr_id,
            validation_id=val_id,
        )

    if max_sec is not None and actual_sec > max_sec:
        reason_base = (
            f"BLOCKED_DURATION_DRIFT: actual {actual_sec:.3f}s exceeds "
            f"max_usable_duration_sec={max_sec:.3f}s for shot "
            f"{inp.shot_id or inp.render_unit_id or '?'}."
        )
        if create_change_requests and inp.production_id and inp.render_unit_id:
            cr_id, val_id = _create_blocking_change_request(
                inp, reason_base, db_path=db_path,
            )
        return _make(
            "reject_unfixable",
            reason_base,
            change_request_id=cr_id,
            validation_id=val_id,
        )

    if min_sec is not None and actual_sec < min_sec:
        if policy in POLICIES_NEED_EXTENSION:
            extend_sec = planned_sec - actual_sec
            metadata = {
                "extend_duration_sec": round(extend_sec, 3),
                "extension_type": "freeze_frame" if policy == "extend_still_ok" else "pad",
            }
            return _make(
                "accepted",
                f"actual {actual_sec:.3f}s below planned {planned_sec:.3f}s; "
                f"extension allowed by policy '{policy}' (extend={extend_sec:.3f}s).",
                assembly_action="extend",
                assembly_metadata=metadata,
            )
        reason_base = (
            f"BLOCKED_DURATION_DRIFT: actual {actual_sec:.3f}s below "
            f"min_usable_duration_sec={min_sec:.3f}s for shot "
            f"{inp.shot_id or inp.render_unit_id or '?'}. Policy '{policy}' does not "
            f"allow extension."
        )
        if create_change_requests and inp.production_id and inp.render_unit_id:
            cr_id, val_id = _create_blocking_change_request(
                inp, reason_base, db_path=db_path,
            )
        return _make(
            "reject_unfixable",
            reason_base,
            change_request_id=cr_id,
            validation_id=val_id,
        )

    if delta_sec > 0:
        if policy in POLICIES_NEED_TRIMMING:
            trim_sec = delta_sec
            metadata = {
                "trim_duration_sec": round(trim_sec, 3),
                "trim_from_end": True,
            }
            return _make(
                "accepted",
                f"actual {actual_sec:.3f}s exceeds planned {planned_sec:.3f}s by "
                f"{trim_sec:.3f}s; trimming allowed by policy '{policy}'.",
                assembly_action="trim",
                assembly_metadata=metadata,
            )
        if policy == "regenerate_required":
            return _make("regenerate_same_prompt",
                         f"actual {actual_sec:.3f}s > planned {planned_sec:.3f}s; "
                         f"policy '{policy}' requires regeneration.")
        if policy == "sonnet_repair_required":
            return _make("sonnet_repair_storyboard",
                         f"actual {actual_sec:.3f}s > planned {planned_sec:.3f}s; "
                         f"policy '{policy}' requires Sonnet storyboard repair.")
        if policy == "human_review_required":
            return _make("human_review_required",
                         f"actual {actual_sec:.3f}s > planned {planned_sec:.3f}s; "
                         f"policy '{policy}' requires human review.")

    if delta_sec < 0:
        if policy in POLICIES_NEED_EXTENSION:
            extend_sec = abs(delta_sec)
            metadata = {
                "extend_duration_sec": round(extend_sec, 3),
                "extension_type": "freeze_frame" if policy == "extend_still_ok" else "pad",
            }
            return _make(
                "accepted",
                f"actual {actual_sec:.3f}s below planned {planned_sec:.3f}s by "
                f"{extend_sec:.3f}s; extension allowed by policy '{policy}'.",
                assembly_action="extend",
                assembly_metadata=metadata,
            )
        if policy == "regenerate_required":
            return _make("regenerate_same_prompt",
                         f"actual {actual_sec:.3f}s < planned {planned_sec:.3f}s; "
                         f"policy '{policy}' requires regeneration.")
        if policy == "sonnet_repair_required":
            return _make("sonnet_repair_storyboard",
                         f"actual {actual_sec:.3f}s < planned {planned_sec:.3f}s; "
                         f"policy '{policy}' requires Sonnet storyboard repair.")
        if policy == "human_review_required":
            return _make("human_review_required",
                         f"actual {actual_sec:.3f}s < planned {planned_sec:.3f}s; "
                         f"policy '{policy}' requires human review.")

    return _make(
        "reject_unfixable",
        f"BLOCKED_DURATION_DRIFT_UNRESOLVED: policy '{policy}' with delta "
        f"{delta_sec:.3f}s produced no matching resolution. "
        f"planned={planned_sec:.3f}s, actual={actual_sec:.3f}s.",
    )


def _create_blocking_change_request(
    inp: DriftInput,
    reason: str,
    db_path=None,
) -> tuple[Optional[str], Optional[str]]:
    cr_id = None
    val_id = None
    try:
        from production_repo import record_change_request, record_validation

        cr = record_change_request(
            production_id=inp.production_id,
            subject_type="render_unit",
            subject_id=inp.render_unit_id,
            change_type="duration_drift_blocked",
            requested_by_stage="feedback_route",
            target_stage="generate_media",
            reason=reason,
            status="open",
            failure_evidence={
                "drift_input": inp.to_dict(),
            },
            repair_routing_stage="generate_media",
            db_path=db_path,
        )
        cr_id = cr["id"]

        val = record_validation(
            production_id=inp.production_id,
            subject_type="render_unit",
            subject_id=inp.render_unit_id,
            validator_name="duration_drift_resolver",
            status="fail",
            evidence={
                "reason": reason,
                "drift_input": inp.to_dict(),
            },
            db_path=db_path,
        )
        val_id = val["id"]
    except Exception:
        pass
    return cr_id, val_id


def resolve_batch(
    inputs: List[DriftInput],
    db_path=None,
    create_change_requests: bool = True,
) -> List[DriftResolution]:
    results = []
    for inp in inputs:
        result = resolve_drift(
            inp,
            db_path=db_path,
            create_change_requests=create_change_requests,
        )
        results.append(result)
    return results


def resolution_manifest_entry(resolution: DriftResolution, segment_id: str = "") -> Dict[str, Any]:
    """Produce an assembly-manifest entry from a drift resolution.

    Provides explicit trim/pad instructions for the assembly stage to consume.
    """
    entry: Dict[str, Any] = {
        "drift_resolution": resolution.resolution,
        "reason": resolution.reason,
    }
    if resolution.assembly_action == "trim":
        entry["trim"] = {
            "action": "trim_from_end",
            "trim_duration_sec": resolution.assembly_metadata.get("trim_duration_sec"),
            "planned_duration_sec": resolution.planned_duration_sec,
            "actual_duration_sec": resolution.actual_duration_sec,
        }
    elif resolution.assembly_action == "extend":
        entry["extend"] = {
            "action": "freeze_last_frame",
            "extend_duration_sec": resolution.assembly_metadata.get("extend_duration_sec"),
            "planned_duration_sec": resolution.planned_duration_sec,
            "actual_duration_sec": resolution.actual_duration_sec,
        }
    return entry
