#!/usr/bin/env python3
"""validate_timing_drift_policy.py — Timing/drift contract validator for canonical storyboards.

Validates that every canonical shot carries sufficient timing policy for
downstream handling of real provider duration drift.

This is a validation-only module. No LLM calls, no creative generation, no DB writes.
No drift resolution is implemented here.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "storyboard_v2"

ALLOWED_DRIFT_POLICIES = {
    "trim_ok", "pad_ok", "extend_still_ok",
    "regenerate_required", "sonnet_repair_required", "human_review_required",
}

POLICIES_THAT_HANDLE_TRIMMING = {"trim_ok", "regenerate_required", "human_review_required"}
POLICIES_THAT_HANDLE_EXTENSION = {"extend_still_ok", "regenerate_required", "human_review_required"}


def is_canonical(data):
    return "storyboard_contract_version" in data


def _has_any_policy(policy, allowed_set):
    return any(allowed in policy for allowed in allowed_set)


def validate_timing_policy(storyboard):
    errors = []

    if not is_canonical(storyboard):
        return errors

    shots = storyboard.get("shots", [])

    for idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id", f"<index {idx}>")
        visual_role = (shot.get("visual_role") or "").lower()

        planned = shot.get("planned_duration_sec")
        min_dur = shot.get("min_usable_duration_sec")
        max_dur = shot.get("max_usable_duration_sec")
        drift_policy = shot.get("duration_drift_policy")
        fit_policy = shot.get("assembly_fit_policy")

        if planned is None:
            errors.append({
                "path": f"shots[{idx}].planned_duration_sec",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MISSING_PLANNED_DURATION: shot '{shot_id}' "
                    f"is missing planned_duration_sec. Every shot must specify "
                    f"a planned duration."
                ),
            })

        if min_dur is None:
            errors.append({
                "path": f"shots[{idx}].min_usable_duration_sec",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MISSING_MIN_DURATION: shot '{shot_id}' "
                    f"is missing min_usable_duration_sec. Every shot must specify "
                    f"a minimum usable duration."
                ),
            })

        if max_dur is None:
            errors.append({
                "path": f"shots[{idx}].max_usable_duration_sec",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MISSING_MAX_DURATION: shot '{shot_id}' "
                    f"is missing max_usable_duration_sec. Every shot must specify "
                    f"a maximum usable duration."
                ),
            })

        if planned is not None and min_dur is not None and planned < min_dur:
            errors.append({
                "path": f"shots[{idx}].min_usable_duration_sec",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MIN_EXCEEDS_PLANNED: shot '{shot_id}' "
                    f"min_usable_duration_sec ({min_dur}) is greater than "
                    f"planned_duration_sec ({planned}). "
                    f"Constraint: min_usable_duration_sec <= planned_duration_sec."
                ),
            })

        if planned is not None and max_dur is not None and planned > max_dur:
            errors.append({
                "path": f"shots[{idx}].max_usable_duration_sec",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_PLANNED_EXCEEDS_MAX: shot '{shot_id}' "
                    f"planned_duration_sec ({planned}) exceeds "
                    f"max_usable_duration_sec ({max_dur}). "
                    f"Constraint: planned_duration_sec <= max_usable_duration_sec."
                ),
            })

        if drift_policy is None:
            errors.append({
                "path": f"shots[{idx}].duration_drift_policy",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MISSING_DRIFT_POLICY: shot '{shot_id}' "
                    f"is missing duration_drift_policy. Every shot must specify "
                    f"a drift policy."
                ),
            })
        elif drift_policy not in ALLOWED_DRIFT_POLICIES:
            errors.append({
                "path": f"shots[{idx}].duration_drift_policy",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_UNKNOWN_DRIFT_POLICY: shot '{shot_id}' "
                    f"has unknown duration_drift_policy '{drift_policy}'. "
                    f"Allowed: {sorted(ALLOWED_DRIFT_POLICIES)}."
                ),
            })

        if fit_policy is None:
            errors.append({
                "path": f"shots[{idx}].assembly_fit_policy",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_MISSING_FIT_POLICY: shot '{shot_id}' "
                    f"is missing assembly_fit_policy. Every shot must specify "
                    f"an assembly fit policy."
                ),
            })

        if visual_role == "hero_lipsync" and drift_policy == "pad_ok":
            errors.append({
                "path": f"shots[{idx}].duration_drift_policy",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_HERO_LIPSYNC_PAD_ONLY: shot '{shot_id}' "
                    f"is hero_lipsync with duration_drift_policy='pad_ok' only. "
                    f"Hero/lipsync shots cannot use weak pad-only policies; "
                    f"they must be trimmable, extendable, or trigger regeneration."
                ),
            })

        is_broll = visual_role.startswith("broll") or visual_role == "still_kenburns"
        if is_broll and drift_policy is not None and drift_policy not in POLICIES_THAT_HANDLE_TRIMMING:
            errors.append({
                "path": f"shots[{idx}].duration_drift_policy",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_BROLL_MISSING_TRIM_POLICY: B-roll shot '{shot_id}' "
                    f"has duration_drift_policy='{drift_policy}' which does not "
                    f"include trim behavior. Generated B-roll must state trim behavior "
                    f"via trim_ok, regenerate_required, or human_review_required."
                ),
            })

        is_local_graphic = visual_role.startswith("graphic") or visual_role in ("kinetic_text", "ui_insert")
        if is_local_graphic and drift_policy is not None and drift_policy not in POLICIES_THAT_HANDLE_EXTENSION:
            errors.append({
                "path": f"shots[{idx}].duration_drift_policy",
                "entity_id": shot_id,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_GRAPHIC_MISSING_EXTENSION_POLICY: local graphic shot '{shot_id}' "
                    f"has duration_drift_policy='{drift_policy}' which does not include "
                    f"extension behavior. Local graphics must state whether extension is allowed "
                    f"via extend_still_ok, regenerate_required, or human_review_required."
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
        print("Usage: python3 validate_timing_drift_policy.py <storyboard.json> [--output-json out.json]",
              file=sys.stderr)
        sys.exit(2)

    data = json.loads(Path(sys.argv[1]).read_text())
    errors = validate_timing_policy(data)
    output_json = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--output-json":
        output_json = sys.argv[3]

    result = {
        "task": "timing_drift_policy_validation",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "error_count": len(errors),
    }

    if output_json:
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(output_json).write_text(json.dumps(result, indent=2))

    if errors:
        for e in errors:
            print(f"TIMING ERROR: [{e['severity']}] {e['entity_id']}: {e['message']}")
        sys.exit(1)
    else:
        print("TIMING DRIFT POLICY: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
