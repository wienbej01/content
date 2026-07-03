"""S22_T019 - Compliance Feedback Ingestion.

Converts storyboard, media, overlay, and final QA compliance findings into
targeted DB feedback/change requests tied to storyboard and render entities.

Uses existing production_repo.record_validation and production_repo.record_change_request
infrastructure. Creates `validations` records for every finding and `change_requests`
for BLOCKER/MAJOR severity findings.

Duplicate open requests for the same unresolved issue are idempotent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import production_db as _db

ALLOWED_ENTITY_TYPES = {"claim", "narrative_beat", "shot", "overlay", "render_unit", "artifact"}
ALLOWED_SEVERITIES = {"BLOCKER", "MAJOR", "MINOR", "NOTE"}
ALLOWED_REPAIR_ACTIONS = {
    "trim_in_assembly",
    "pad_or_extend",
    "regenerate_same_prompt",
    "sonnet_repair_storyboard",
    "rerender_overlay",
    "human_review_required",
    "reject_unfixable",
}

_TARGET_STAGE_MAP = {
    "trim_in_assembly": "assemble",
    "pad_or_extend": "assemble",
    "regenerate_same_prompt": "generate_media",
    "sonnet_repair_storyboard": "storyboard_repair",
    "rerender_overlay": "render_overlays",
    "human_review_required": "gate_storyboard",
    "reject_unfixable": "gate_b_review",
}


class FeedbackIngestionError(ValueError):
    pass


def _entity_to_subject(entity_type: str, entity_id: str) -> tuple:
    if entity_type == "claim":
        return ("storyboard", entity_id)
    if entity_type == "narrative_beat":
        return ("storyboard", entity_id)
    if entity_type == "shot":
        return ("render_unit", entity_id)
    if entity_type == "overlay":
        return ("render_unit", entity_id)
    return (entity_type, entity_id)


def _find_existing_open_request(
    production_id: str,
    subject_type: str,
    subject_id: str,
    rule_id: str,
    conn,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """SELECT * FROM change_requests
           WHERE production_id=? AND subject_type=? AND subject_id=?
             AND status='open' AND failure_evidence_json LIKE ?
           ORDER BY created_at DESC LIMIT 1""",
        (production_id, subject_type, subject_id, f'%"rule_id":"{rule_id}"%'),
    ).fetchone()
    return dict(row) if row else None


def ingest_compliance_finding(
    production_id: str,
    entity_type: str,
    entity_id: str,
    severity: str,
    rule_id: str,
    source_stage: str,
    finding_message: str,
    recommended_action: str,
    repair_owner: Optional[str] = None,
    downstream_stages_impacted: Optional[List[str]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    db_path=None,
) -> Dict[str, Any]:
    if not entity_type:
        raise FeedbackIngestionError("BLOCKED_FEEDBACK_UNROUTED: entity_type is required")
    if not entity_id:
        raise FeedbackIngestionError("BLOCKED_FEEDBACK_UNROUTED: entity_id is required")
    if not recommended_action:
        raise FeedbackIngestionError("BLOCKED_FEEDBACK_UNROUTED: recommended_action is required")
    if not severity:
        raise FeedbackIngestionError("BLOCKED_FEEDBACK_UNROUTED: severity is required")

    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise FeedbackIngestionError(
            f"BLOCKED_FEEDBACK_UNROUTED: unknown entity_type {entity_type!r}"
        )
    if severity not in ALLOWED_SEVERITIES:
        raise FeedbackIngestionError(
            f"BLOCKED_FEEDBACK_UNROUTED: unknown severity {severity!r}"
        )
    if recommended_action not in ALLOWED_REPAIR_ACTIONS:
        raise FeedbackIngestionError(
            f"BLOCKED_FEEDBACK_UNROUTED: unknown recommended_action {recommended_action!r}"
        )

    subject_type, subject_id = _entity_to_subject(entity_type, entity_id)

    evidence_full = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "severity": severity,
        "rule_id": rule_id,
        "source_stage": source_stage,
        "finding_message": finding_message,
        "recommended_action": recommended_action,
        "repair_owner": repair_owner,
        "downstream_stages_impacted": downstream_stages_impacted or [],
    }
    if evidence:
        evidence_full["extra"] = evidence

    now = _db._now()
    result = {"finding": evidence_full}

    with _db.transaction(db_path) as conn:
        val_id = _db._id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                val_id,
                production_id,
                subject_type,
                subject_id,
                source_stage,
                "pass" if severity in ("MINOR", "NOTE") else "fail",
                _db._json(evidence_full),
                now,
            ),
        )
        result["validation"] = dict(
            conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone()
        )

        if severity in ("BLOCKER", "MAJOR"):
            existing = _find_existing_open_request(
                production_id, subject_type, subject_id, rule_id, conn
            )
            if existing:
                result["change_request"] = existing
                result["change_request_action"] = "existing"
            else:
                target_stage = _TARGET_STAGE_MAP.get(recommended_action, "qa_media")

                cr_id = _db._id("cr")
                conn.execute(
                    """INSERT INTO change_requests
                       (id, production_id, subject_type, subject_id, change_type,
                        requested_by_stage, target_stage, reason, status,
                        failure_evidence_json, repair_routing_stage, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cr_id,
                        production_id,
                        subject_type,
                        subject_id,
                        "repair",
                        source_stage,
                        target_stage,
                        finding_message,
                        "open",
                        _db._json(evidence_full),
                        target_stage,
                        now,
                    ),
                )
                result["change_request"] = dict(
                    conn.execute(
                        "SELECT * FROM change_requests WHERE id=?", (cr_id,)
                    ).fetchone()
                )
                result["change_request_action"] = "created"

                _db.append_event(
                    production_id,
                    "feedback_change_requested",
                    payload={"change_request_id": cr_id, "finding": evidence_full},
                    conn=conn,
                )
        else:
            result["change_request"] = None
            result["change_request_action"] = "skipped"

    return result


def ingest_compliance_findings(
    production_id: str,
    findings: List[Dict[str, Any]],
    db_path=None,
) -> List[Dict[str, Any]]:
    results = []
    for finding in findings:
        result = ingest_compliance_finding(
            production_id=production_id,
            entity_type=finding["entity_type"],
            entity_id=finding["entity_id"],
            severity=finding["severity"],
            rule_id=finding.get("rule_id", "UNKNOWN"),
            source_stage=finding.get("source_stage", "unknown"),
            finding_message=finding.get("finding_message", ""),
            recommended_action=finding["recommended_action"],
            repair_owner=finding.get("repair_owner"),
            downstream_stages_impacted=finding.get("downstream_stages_impacted", []),
            evidence=finding.get("evidence"),
            db_path=db_path,
        )
        results.append(result)
    return results
