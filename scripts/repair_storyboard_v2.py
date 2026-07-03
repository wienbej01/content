#!/usr/bin/env python3
"""S22_T010 — Bounded Sonnet 5 repair loop for canonical storyboard entities.

Accepts a canonical storyboard, validation errors, and affected entity IDs. Sends
only the affected entities plus minimal adjacent context to Sonnet 5 for targeted
repair. Validates that narration is preserved and unaffected entities are not modified.

Usage:
  python3 scripts/repair_storyboard_v2.py \
    --storyboard canonical_storyboard.json \
    --validation-errors validation_errors.json \
    --entity-ids SH002 OV001 \
    --output repaired_storyboard.json \
    [--max-attempts 2] [--dry-run]
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
PROMPTS_DIR = ROOT / "docs" / "prompts"

from llm_call import llm_call as _llm_call

REQUIRED_SONNET5_PROFILE = "storyboard_director_sonnet5"
REPAIR_TASK = "storyboard_repair"
DEFAULT_MAX_ATTEMPTS = 2

BLOCKED_REPAIR_EXHAUSTED = "BLOCKED_REPAIR_EXHAUSTED"
BLOCKED_NARRATION_MUTATION = "BLOCKED_SCRIPT_NARRATION_MUTATION"
BLOCKED_UNAFFECTED_REWRITE = "BLOCKED_UNAFFECTED_REWRITE"
BLOCKED_NON_SONNET = "BLOCKED_CREATIVE_FALLBACK_FORBIDDEN"
BLOCKED_SONNET_UNAVAILABLE = "BLOCKED_SONNET5_UNAVAILABLE"

ENTITY_COLLECTIONS = (
    "claim_inventory",
    "narrative_beats",
    "shots",
    "overlays",
    "segment_work_orders",
)

ENTITY_ID_FIELDS = {
    "claim_inventory": "claim_id",
    "narrative_beats": "beat_id",
    "shots": "shot_id",
    "overlays": "overlay_id",
    "segment_work_orders": "segment_id",
}

IMMUTABLE_NARRATION_FIELDS = {
    "narrative_beats": "narration_text",
    "segment_work_orders": "narration_text_exact",
}


def _compute_sha256(data):
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_prompt_template():
    path = PROMPTS_DIR / "STORYBOARD_SONNET5_REPAIR.md"
    if not path.exists():
        raise FileNotFoundError(f"Repair prompt template not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def extract_affected_entities(storyboard, entity_ids):
    affected = {}
    for collection_name in ENTITY_COLLECTIONS:
        items = storyboard.get(collection_name, [])
        id_field = ENTITY_ID_FIELDS[collection_name]
        matched = [item for item in items if item.get(id_field) in entity_ids]
        if matched:
            affected[collection_name] = copy.deepcopy(matched)
    return affected


def _all_entity_ids(storyboard):
    ids = set()
    for collection_name in ENTITY_COLLECTIONS:
        id_field = ENTITY_ID_FIELDS[collection_name]
        for item in storyboard.get(collection_name, []):
            eid = item.get(id_field)
            if eid:
                ids.add(eid)
    return ids


def extract_adjacent_entities(storyboard, affected_ids):
    adjacent = {}
    for collection_name in ENTITY_COLLECTIONS:
        items = storyboard.get(collection_name, [])
        id_field = ENTITY_ID_FIELDS[collection_name]
        matched_ids = {item[id_field] for item in extract_affected_entities(
            storyboard, affected_ids).get(collection_name, [])}

        adjacent_items = []
        for i, item in enumerate(items):
            if item.get(id_field) in matched_ids:
                if i > 0 and items[i - 1][id_field] not in matched_ids:
                    adjacent_items.append(copy.deepcopy(items[i - 1]))
                if i < len(items) - 1 and items[i + 1][id_field] not in matched_ids:
                    adjacent_items.append(copy.deepcopy(items[i + 1]))

        if adjacent_items:
            adjacent[collection_name] = adjacent_items

    return adjacent


def build_repair_prompt(storyboard, validation_errors, affected_entities, adjacent_entities):
    template = _load_prompt_template()

    errors_json = json.dumps(validation_errors, indent=2, ensure_ascii=False)
    affected_json = json.dumps(affected_entities, indent=2, ensure_ascii=False)
    adjacent_json = json.dumps(adjacent_entities, indent=2, ensure_ascii=False)
    storyboard_sha = _compute_sha256(storyboard)

    prompt = template.replace("{validation_errors_json}", errors_json)
    prompt = prompt.replace("{affected_entities_json}", affected_json)
    prompt = prompt.replace("{adjacent_entities_json}", adjacent_json)
    prompt = prompt.replace("{storyboard_sha256}", storyboard_sha)

    idx = prompt.find("## OUTPUT FORMAT")
    if idx == -1:
        idx = len(prompt)

    prefix = prompt[:idx].rstrip()
    schema_suffix = prompt[idx:]

    instructions = (
        "\n\n## REPAIR INSTRUCTIONS\n"
        "Fix ONLY the entities listed in AFFECTED ENTITIES above.\n"
        "You MUST NOT modify any entity not listed in VALIDATION ERRORS.\n"
        f"Current repair round: {1}. "
        "Preserve narration text byte-for-byte.\n"
    )

    return prefix + instructions + "\n" + schema_suffix


def validate_narration_immutability(original_storyboard, repaired_storyboard, affected_ids):
    errors = []
    for collection_name in ENTITY_COLLECTIONS:
        if collection_name not in IMMUTABLE_NARRATION_FIELDS:
            continue
        nar_field = IMMUTABLE_NARRATION_FIELDS[collection_name]
        id_field = ENTITY_ID_FIELDS[collection_name]
        orig_items = {item[id_field]: item
                      for item in original_storyboard.get(collection_name, [])}
        repaired_items = {item[id_field]: item
                          for item in repaired_storyboard.get(collection_name, [])}

        for eid, orig in orig_items.items():
            repaired = repaired_items.get(eid)
            if repaired is None:
                continue
            orig_narration = orig.get(nar_field, "")
            repaired_narration = repaired.get(nar_field, "")
            if orig_narration != repaired_narration:
                errors.append({
                    "severity": "BLOCKER",
                    "code": BLOCKED_NARRATION_MUTATION,
                    "entity_id": eid,
                    "collection": collection_name,
                    "field": nar_field,
                    "message": (
                        f"{BLOCKED_NARRATION_MUTATION}: narration mutated in "
                        f"{collection_name} '{eid}'. Field '{nar_field}' changed."
                    ),
                })
    return errors


def validate_unaffected_preserved(original_storyboard, repaired_storyboard, affected_ids):
    errors = []
    all_ids = _all_entity_ids(original_storyboard)
    unaffected_ids = all_ids - set(affected_ids)

    for collection_name in ENTITY_COLLECTIONS:
        id_field = ENTITY_ID_FIELDS[collection_name]
        orig_items = {item[id_field]: item
                      for item in original_storyboard.get(collection_name, [])}
        repaired_items = {item[id_field]: item
                          for item in repaired_storyboard.get(collection_name, [])}

        for eid in unaffected_ids:
            orig = orig_items.get(eid)
            repaired = repaired_items.get(eid)
            if orig is None or repaired is None:
                if orig != repaired:
                    errors.append({
                        "severity": "BLOCKER",
                        "code": BLOCKED_UNAFFECTED_REWRITE,
                        "entity_id": eid,
                        "collection": collection_name,
                        "message": (
                            f"{BLOCKED_UNAFFECTED_REWRITE}: unaffected entity "
                            f"'{eid}' in '{collection_name}' was removed or altered."
                        ),
                    })
                continue

            if json.dumps(orig, sort_keys=True) != json.dumps(repaired, sort_keys=True):
                changed_fields = []
                for key in set(list(orig.keys()) + list(repaired.keys())):
                    if orig.get(key) != repaired.get(key):
                        changed_fields.append(key)
                errors.append({
                    "severity": "BLOCKER",
                    "code": BLOCKED_UNAFFECTED_REWRITE,
                    "entity_id": eid,
                    "collection": collection_name,
                    "changed_fields": changed_fields,
                    "message": (
                        f"{BLOCKED_UNAFFECTED_REWRITE}: unaffected entity "
                        f"'{eid}' in '{collection_name}' was modified. "
                        f"Changed fields: {changed_fields}."
                    ),
                })
    return errors


def parse_stub_repair_response(data):
    if isinstance(data, dict) and "repair_summary" in data:
        if "repaired_entities" in data:
            return data
        repaired = {}
        for collection_name in ENTITY_COLLECTIONS:
            if collection_name in data:
                repaired[collection_name] = data[collection_name]
        return {"repair_summary": data.get("repair_summary", []),
                "repaired_entities": repaired}
    if isinstance(data, list):
        return {"repair_summary": [], "repaired_entities": data}
    return None


def apply_repair(original_storyboard, repair_data):
    storyboard = copy.deepcopy(original_storyboard)

    entities_map = repair_data.get("repaired_entities", {})
    if isinstance(entities_map, list):
        return storyboard

    for collection_name in ENTITY_COLLECTIONS:
        if collection_name not in entities_map:
            continue
        repaired_items = entities_map[collection_name]
        if not isinstance(repaired_items, list):
            continue
        id_field = ENTITY_ID_FIELDS[collection_name]
        orig_items = storyboard.get(collection_name, [])
        repaired_by_id = {item[id_field]: item for item in repaired_items}

        merged = []
        for item in orig_items:
            eid = item.get(id_field)
            if eid in repaired_by_id:
                merged.append(repaired_by_id[eid])
            else:
                merged.append(item)
        storyboard[collection_name] = merged

    return storyboard


def compute_changed_fields(original_storyboard, repaired_storyboard, affected_ids):
    log_entries = []
    for collection_name in ENTITY_COLLECTIONS:
        id_field = ENTITY_ID_FIELDS[collection_name]
        orig_items = {item[id_field]: item
                      for item in original_storyboard.get(collection_name, [])}
        repaired_items = {item[id_field]: item
                          for item in repaired_storyboard.get(collection_name, [])}

        for eid in affected_ids:
            orig = orig_items.get(eid)
            repaired = repaired_items.get(eid)
            if orig is None or repaired is None:
                continue

            changed = []
            for key in set(list(orig.keys()) + list(repaired.keys())):
                if orig.get(key) != repaired.get(key):
                    changed.append(key)

            if changed:
                log_entries.append({
                    "entity_id": eid,
                    "collection": collection_name,
                    "changed_fields": changed,
                })
    return log_entries


def repair_canonical_storyboard(canonical_storyboard, validation_errors,
                                affected_entity_ids, max_attempts=DEFAULT_MAX_ATTEMPTS,
                                dry_run=False, llm_fn=None, revalidator_fn=None,
                                verbose=False):
    storyboard = copy.deepcopy(canonical_storyboard)
    repair_log = []
    block_chain = []

    storyboard_sha_before = _compute_sha256(storyboard)

    for attempt in range(1, max_attempts + 1):
        affected = extract_affected_entities(storyboard, affected_entity_ids)
        adjacent = extract_adjacent_entities(storyboard, affected_entity_ids)
        prompt = build_repair_prompt(storyboard, validation_errors, affected, adjacent)

        if dry_run:
            repair_log.append({
                "attempt": attempt,
                "status": "DRY_RUN",
                "prompt_chars": len(prompt),
                "affected_entity_ids": affected_entity_ids,
                "prompt_preview": prompt[:500],
            })
            return {
                "status": "DRY_RUN",
                "storyboard": storyboard,
                "repair_log": repair_log,
                "block_chain": block_chain,
            }

        try:
            if llm_fn:
                data, raw_text, profile_name, model = llm_fn(prompt)
            else:
                data, raw_text, profile_name, model = _llm_call(
                    task=REPAIR_TASK,
                    prompt=prompt,
                    model_profile=REQUIRED_SONNET5_PROFILE,
                    expect_json=True,
                    timeout=300,
                )
        except RuntimeError as e:
            msg = str(e)
            if "BLOCKED_SONNET5_UNAVAILABLE" in msg:
                return {
                    "status": "BLOCKED",
                    "error_code": BLOCKED_SONNET_UNAVAILABLE,
                    "error": msg,
                    "repair_log": repair_log,
                }
            if "BLOCKED_CREATIVE_FALLBACK" in msg or "not permitted" in msg:
                return {
                    "status": "BLOCKED",
                    "error_code": BLOCKED_NON_SONNET,
                    "error": msg,
                    "repair_log": repair_log,
                }
            repair_log.append({
                "attempt": attempt,
                "status": "LLM_ERROR",
                "error": str(e),
            })
            continue

        parsed = parse_stub_repair_response(data)
        if parsed is None:
            repair_log.append({
                "attempt": attempt,
                "status": "UNPARSEABLE_RESPONSE",
            })
            continue

        repaired_storyboard = apply_repair(storyboard, parsed)

        repair_summary = parsed.get("repair_summary", [])
        changed = compute_changed_fields(storyboard, repaired_storyboard,
                                         affected_entity_ids)

        repair_log.append({
            "attempt": attempt,
            "status": "REPAIR_ATTEMPTED",
            "model": model,
            "repair_summary": repair_summary,
            "changed_fields": changed,
        })

        narr_errors = validate_narration_immutability(
            storyboard, repaired_storyboard, affected_entity_ids)
        if narr_errors:
            for e in narr_errors:
                block_chain.append({
                    "attempt": attempt,
                    "type": "NARRATION_MUTATION",
                    "error": e,
                })
            repair_log.append({
                "attempt": attempt,
                "status": "BLOCKED_NARRATION_MUTATION",
                "errors": narr_errors,
            })
            return {
                "status": "BLOCKED",
                "error_code": BLOCKED_NARRATION_MUTATION,
                "storyboard": storyboard,
                "repair_log": repair_log,
                "block_chain": block_chain,
            }

        unaffected_errors = validate_unaffected_preserved(
            storyboard, repaired_storyboard, affected_entity_ids)
        if unaffected_errors:
            for e in unaffected_errors:
                block_chain.append({
                    "attempt": attempt,
                    "type": "UNAFFECTED_REWRITE",
                    "error": e,
                })
            repair_log.append({
                "attempt": attempt,
                "status": "BLOCKED_UNAFFECTED_REWRITE",
                "errors": unaffected_errors,
            })
            return {
                "status": "BLOCKED",
                "error_code": BLOCKED_UNAFFECTED_REWRITE,
                "storyboard": storyboard,
                "repair_log": repair_log,
                "block_chain": block_chain,
            }

        storyboard = repaired_storyboard

        if revalidator_fn:
            remaining_errors = revalidator_fn(storyboard)
            if not remaining_errors:
                storyboard_sha_after = _compute_sha256(storyboard)
                return {
                    "status": "SUCCESS",
                    "storyboard": storyboard,
                    "repair_log": repair_log,
                    "block_chain": block_chain,
                    "storyboard_sha256_before": storyboard_sha_before,
                    "storyboard_sha256_after": storyboard_sha_after,
                }
            validation_errors = remaining_errors
        else:
            storyboard_sha_after = _compute_sha256(storyboard)
            return {
                "status": "SUCCESS",
                "storyboard": storyboard,
                "repair_log": repair_log,
                "block_chain": block_chain,
                "storyboard_sha256_before": storyboard_sha_before,
                "storyboard_sha256_after": storyboard_sha_after,
            }

    storyboard_sha_after = _compute_sha256(storyboard)
    return {
        "status": "BLOCKED",
        "error_code": BLOCKED_REPAIR_EXHAUSTED,
        "storyboard": storyboard,
        "repair_log": repair_log,
        "block_chain": block_chain,
        "storyboard_sha256_before": storyboard_sha_before,
        "storyboard_sha256_after": storyboard_sha_after,
        "message": (
            f"{BLOCKED_REPAIR_EXHAUSTED}: repair did not resolve all "
            f"validation errors after {max_attempts} attempts."
        ),
    }


def _default_revalidator(storyboard):
    from validate_storyboard_v2 import validate_semantic_alignment
    return validate_semantic_alignment(storyboard)


def main():
    parser = argparse.ArgumentParser(
        description="S22_T010 — Bounded Sonnet 5 repair loop for canonical storyboards.")
    parser.add_argument("--storyboard", type=Path, required=True,
                        help="Canonical storyboard JSON file.")
    parser.add_argument("--validation-errors", type=Path, required=True,
                        help="JSON file with validation errors array.")
    parser.add_argument("--entity-ids", nargs="+", required=True,
                        help="Affected entity IDs to repair.")
    parser.add_argument("--output", "-o", type=Path, required=True,
                        help="Output repaired storyboard JSON file.")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS,
                        help=f"Maximum repair attempts (default: {DEFAULT_MAX_ATTEMPTS}).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build prompt without invoking Kilo.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--revalidate", action="store_true",
                        help="Re-validate storyboard after each repair attempt.")
    args = parser.parse_args()

    if not args.storyboard.exists():
        print(f"ERROR: Storyboard not found: {args.storyboard}", file=sys.stderr)
        sys.exit(1)
    if not args.validation_errors.exists():
        print(f"ERROR: Validation errors file not found: {args.validation_errors}", file=sys.stderr)
        sys.exit(1)

    storyboard = json.loads(args.storyboard.read_text())
    validation_errors = json.loads(args.validation_errors.read_text())

    revalidator_fn = _default_revalidator if args.revalidate else None

    result = repair_canonical_storyboard(
        canonical_storyboard=storyboard,
        validation_errors=validation_errors,
        affected_entity_ids=args.entity_ids,
        max_attempts=args.max_attempts,
        dry_run=args.dry_run,
        revalidator_fn=revalidator_fn,
        verbose=args.verbose,
    )

    status = result["status"]
    print(f"  Sonnet repair loop: {status}")

    for entry in result.get("repair_log", []):
        att = entry.get("attempt", "?")
        st = entry.get("status", "?")
        if st == "DRY_RUN":
            print(f"    [attempt {att}] DRY_RUN — prompt {entry.get('prompt_chars')} chars")
        elif st == "REPAIR_ATTEMPTED":
            changed = entry.get("changed_fields", [])
            print(f"    [attempt {att}] {st} — {len(changed)} entities changed")
        else:
            print(f"    [attempt {att}] {st}")

    if status == "BLOCKED":
        for bc in result.get("block_chain", []):
            print(f"    BLOCKED: {bc.get('type')} — {bc.get('error', {}).get('message', '')}")
        print(f"    {result.get('error_code')}: {result.get('message', '')}")

    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "status": result["status"],
            "storyboard": result.get("storyboard"),
            "repair_log": result.get("repair_log", []),
        }
        if result.get("storyboard_sha256_before"):
            output["storyboard_sha256_before"] = result["storyboard_sha256_before"]
            output["storyboard_sha256_after"] = result["storyboard_sha256_after"]
        if result.get("error_code"):
            output["error_code"] = result["error_code"]
            output["message"] = result.get("message", "")
        args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"\n  Output: {args.output}")

    return 0 if status not in ("BLOCKED",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
