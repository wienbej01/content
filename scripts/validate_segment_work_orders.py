#!/usr/bin/env python3
"""validate_segment_work_orders.py — Validates segment work orders in canonical storyboards.

Enforces business rules beyond JSON Schema:
- Every approved script segment (referenced by narrative_beats) must have a work order.
- Narration text in work order must match the narrative_beat's exact narration.
- Segments referencing B-roll shots must have non-empty broll_alignment_instruction.
- Segments referencing overlays must have non-empty graphic_alignment_instruction.
- QA acceptance criteria must be a non-empty array.
- Work order shot_ids must reference existing shots.
- Work order overlay_ids must reference existing overlays.
- Conclusion segments (act >= 5) must have non-empty conclusion_alignment_instruction.

This is a validation-only module. No LLM calls, no creative generation, no DB writes.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "storyboard_v2"

CONCLUSION_ACT_MIN = 5


def is_canonical(data):
    return "storyboard_contract_version" in data


def validate_work_orders(storyboard):
    """Validate segment work orders against business rules.

    Args:
        storyboard: Parsed canonical storyboard JSON dict.

    Returns:
        List of error dicts: {"path": str, "severity": str, "message": str}.
    """
    errors = []

    if not is_canonical(storyboard):
        return errors

    narrative_beats = storyboard.get("narrative_beats", [])
    shots = {s.get("shot_id"): s for s in storyboard.get("shots", [])}
    overlays = {o.get("overlay_id"): o for o in storyboard.get("overlays", [])}
    work_orders = storyboard.get("segment_work_orders", [])

    # Index work orders by segment_id
    work_order_by_segment = {}
    for idx, wo in enumerate(work_orders):
        sid = wo.get("segment_id")
        if sid:
            if sid in work_order_by_segment:
                errors.append({
                    "path": f"segment_work_orders[{idx}].segment_id",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_DUPLICATE_WORK_ORDER: segment_id '{sid}' "
                        f"has multiple work orders."
                    ),
                })
            work_order_by_segment[sid] = wo

    # Index narrative_beats by segment_id
    beats_by_segment = {}
    for beat in narrative_beats:
        sid = beat.get("segment_id")
        if sid:
            if sid not in beats_by_segment:
                beats_by_segment[sid] = []
            beats_by_segment[sid].append(beat)

    # Check 1: Every segment in narrative_beats must have a work order
    for sid in beats_by_segment:
        if sid not in work_order_by_segment:
            errors.append({
                "path": f"segment_work_orders",
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MISSING_WORK_ORDER: segment_id '{sid}' appears in "
                    f"narrative_beats but has no segment_work_order entry."
                ),
            })

    # Check per-work-order fields
    for idx, wo in enumerate(work_orders):
        sid = wo.get("segment_id", f"<index {idx}>")
        beats_for_segment = beats_by_segment.get(sid, [])

        # Check 2: Narration text must match
        if beats_for_segment:
            beat_narration = beats_for_segment[0].get("narration_text", "")
            wo_narration = wo.get("narration_text_exact", "")
            if wo_narration != beat_narration:
                errors.append({
                    "path": f"segment_work_orders[{idx}].narration_text_exact",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_NARRATION_MISMATCH: segment_id '{sid}' narration "
                        f"text mismatch. Work order has '{wo_narration[:60]}...', "
                        f"narrative_beat has '{beat_narration[:60]}...'."
                    ),
                })

        # Check shot references and B-roll instruction
        shot_ids = wo.get("shot_ids", [])
        has_broll_shots = False
        for shot_ref in shot_ids:
            if shot_ref not in shots:
                errors.append({
                    "path": f"segment_work_orders[{idx}].shot_ids",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_UNKNOWN_SHOT_REF: segment_id '{sid}' work order "
                        f"references shot_id '{shot_ref}' which does not exist "
                        f"in the storyboard shots array."
                    ),
                })
            else:
                visual_role = shots[shot_ref].get("visual_role", "")
                if visual_role.startswith("broll"):
                    has_broll_shots = True

        # Check 4: Missing B-roll instruction for segments with B-roll shots
        if has_broll_shots:
            broll_instruction = wo.get("broll_alignment_instruction", "")
            if not broll_instruction.strip():
                errors.append({
                    "path": f"segment_work_orders[{idx}].broll_alignment_instruction",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_MISSING_BROLL_INSTRUCTION: segment_id '{sid}' "
                        f"references B-roll shots but "
                        f"broll_alignment_instruction is empty."
                    ),
                })

        # Check overlay references
        overlay_ids = wo.get("overlay_ids", [])
        has_overlays = False
        for overlay_ref in overlay_ids:
            if overlay_ref not in overlays:
                errors.append({
                    "path": f"segment_work_orders[{idx}].overlay_ids",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_UNKNOWN_OVERLAY_REF: segment_id '{sid}' work order "
                        f"references overlay_id '{overlay_ref}' which does not exist "
                        f"in the storyboard overlays array."
                    ),
                })
            else:
                has_overlays = True

        # Check 5: Missing graphic instruction for segments with overlays
        if has_overlays:
            graphic_instruction = wo.get("graphic_alignment_instruction", "")
            if not graphic_instruction.strip():
                errors.append({
                    "path": f"segment_work_orders[{idx}].graphic_alignment_instruction",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_MISSING_GRAPHIC_INSTRUCTION: segment_id '{sid}' "
                        f"references overlays but "
                        f"graphic_alignment_instruction is empty."
                    ),
                })

        # Check 6: QA acceptance criteria must be non-empty
        qa = wo.get("qa_acceptance_criteria", [])
        if not qa or len(qa) == 0:
            errors.append({
                "path": f"segment_work_orders[{idx}].qa_acceptance_criteria",
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_EMPTY_QA_CRITERIA: segment_id '{sid}' has empty "
                    f"qa_acceptance_criteria."
                ),
            })

        # Check 9: Conclusion segment must have non-empty conclusion_alignment_instruction
        is_conclusion = any(
            beat.get("act", 0) >= CONCLUSION_ACT_MIN
            for beat in beats_for_segment
        )
        if is_conclusion:
            conclusion_instruction = wo.get("conclusion_alignment_instruction", "")
            if not conclusion_instruction.strip():
                errors.append({
                    "path": f"segment_work_orders[{idx}].conclusion_alignment_instruction",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_MISSING_CONCLUSION_INSTRUCTION: segment_id '{sid}' "
                        f"is a conclusion segment (act >= {CONCLUSION_ACT_MIN}) but "
                        f"conclusion_alignment_instruction is empty."
                    ),
                })

    return errors


def load_fixture(name):
    path = _FIXTURE_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text())


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_segment_work_orders.py <storyboard.json>", file=sys.stderr)
        sys.exit(2)
    data = json.loads(Path(sys.argv[1]).read_text())
    errors = validate_work_orders(data)
    if errors:
        for e in errors:
            print(f"WORK_ORDER ERROR: [{e['severity']}] {e['path']}: {e['message']}")
    else:
        print("WORK_ORDER VALIDATION: PASS")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
