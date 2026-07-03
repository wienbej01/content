#!/usr/bin/env python3
"""claim_inventory_validator.py — Validates claim inventory against schema and business rules.

Enforces:
- Schema-level types and required fields.
- Source-backed claims (fact, statistic, study, person, date) must have source_id.
- Opinion/original_argument claims pass without source_id.
- Unique claim_id within the inventory.
- Overlay/shot claim_refs resolve to valid claim_id values.
- Script segment refs resolve to valid segment_id values.
- allowed_visual_treatment is a recognized value.

This is a validation-only module. No creative generation, no LLM calls, no DB writes.
"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "claim_inventory.schema.json"
_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "claim_inventory"

ALLOWED_SOURCE_BACKED_TYPES = {
    "fact", "reference", "source_quote", "statistic",
    "study", "person", "date", "narrative_premise",
    "definition", "comparison", "analogy", "conclusion",
}

OPINION_TYPES = {"opinion", "original_argument"}


def load_schema():
    if SCHEMA_PATH.exists():
        return json.loads(SCHEMA_PATH.read_text())
    return None


def validate_claim_schema(inventory_dict):
    """Validate claim_inventory wrapper against JSON Schema.

    inventory_dict must have {"claims": [...]}.
    Returns list of jsonschema.ValidationError objects.
    """
    if not _HAS_JSONSCHEMA:
        raise RuntimeError("jsonschema library not installed")
    schema = load_schema()
    if schema is None:
        raise RuntimeError(f"Schema not found at {SCHEMA_PATH}")
    validator = jsonschema.Draft7Validator(schema)
    return list(validator.iter_errors(inventory_dict))


def validate_claim_business_rules(inventory_dict, known_segment_ids=None):
    """Enforce business rules that JSON Schema cannot express.

    Returns list of error dicts: {"path": str, "severity": str, "message": str}.
    """
    errors = []
    claims = inventory_dict.get("claims", [])

    seen_ids = set()
    all_claim_ids = set()

    for idx, claim in enumerate(claims):
        cid = claim.get("claim_id", f"<index {idx}>")
        ctype = claim.get("claim_type", "")
        citation = claim.get("citation_status", "")
        source_id = claim.get("source_id")
        segments = claim.get("script_segment_refs", [])

        all_claim_ids.add(cid)

        # Duplicate claim ID check
        if cid in seen_ids:
            errors.append({
                "path": f"claims[{idx}].claim_id",
                "severity": "BLOCKER",
                "message": f"BLOCKED_DUPLICATE_CLAIM_ID: claim_id '{cid}' appears more than once",
            })
        seen_ids.add(cid)

        # Source-backed type must have source_id
        if ctype in ALLOWED_SOURCE_BACKED_TYPES and citation != "unsupported_opinion":
            if not source_id:
                errors.append({
                    "path": f"claims[{idx}].source_id",
                    "severity": "BLOCKER",
                    "message": (
                        f"BLOCKED_UNSUPPORTED_CLAIM: claim_type '{ctype}' requires source_id. "
                        f"claim_id='{cid}' has no source."
                    ),
                })

        # Opinion type without citation must still be explicitly typed opinion
        if ctype in OPINION_TYPES and citation != "unsupported_opinion":
            pass  # Opinion types may still have sources; not an error

        # Non-opinion type with unsupported_opinion citation - check if source is missing
        if ctype not in OPINION_TYPES and citation == "unsupported_opinion":
            if not source_id:
                errors.append({
                    "path": f"claims[{idx}].citation_status",
                    "severity": "MAJOR",
                    "message": (
                        f"claim_type '{ctype}' should not use citation_status 'unsupported_opinion'. "
                        f"claim_id='{cid}' — change to 'source_backed' or mark type as opinion/original_argument."
                    ),
                })

        # Unsupported visual treatment
        allowed_treatments = {
            "literal_evidence", "metaphorical", "stat_display",
            "diagram", "source_label", "quote_card", "comparison",
            "emotional_reset", "no_visual_needed",
        }
        treatment = claim.get("allowed_visual_treatment")
        if treatment and treatment not in allowed_treatments:
            errors.append({
                "path": f"claims[{idx}].allowed_visual_treatment",
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_VISUAL_TREATMENT: '{treatment}' is not a valid visual treatment. "
                    f"claim_id='{cid}'. Allowed: {sorted(allowed_treatments)}"
                ),
            })

        # Script segment refs check
        if segments and known_segment_ids is not None:
            for seg_ref in segments:
                if seg_ref not in known_segment_ids:
                    errors.append({
                        "path": f"claims[{idx}].script_segment_refs",
                        "severity": "BLOCKER",
                        "message": (
                            f"BLOCKED_NONEXISTENT_SEGMENT: script_segment_ref '{seg_ref}' "
                            f"does not exist in known_segment_ids. claim_id='{cid}'."
                        ),
                    })

    return errors


def validate_claim_refs_resolve(claims, external_claim_refs, context_label="external_refs"):
    """Check that claim refs in shots, overlays, or segment work orders exist.

    Args:
        claims: list of claim dicts (must have "claim_id").
        external_claim_refs: iterable of claim_id strings found in shot/overlay refs.
        context_label: label for error path.

    Returns list of error dicts.
    """
    errors = []
    valid_ids = {c.get("claim_id") for c in claims}
    for ref in external_claim_refs:
        if ref not in valid_ids:
            errors.append({
                "path": context_label,
                "severity": "BLOCKER",
                "message": (
                    f"BLOCKED_UNRESOLVED_CLAIM_REF: claim_ref '{ref}' does not "
                    f"match any claim_id in the inventory. Valid claim_ids: {sorted(valid_ids)}"
                ),
            })
    return errors


def validate_all(inventory_dict, known_segment_ids=None, external_claim_refs=None):
    """Run all validations: schema + business rules + cross-refs.

    Returns (schema_errors, business_errors, ref_errors).
    """
    schema_errors = validate_claim_schema(inventory_dict)
    business_errors = validate_claim_business_rules(inventory_dict, known_segment_ids)
    ref_errors = []
    if external_claim_refs is not None:
        claims = inventory_dict.get("claims", [])
        ref_errors = validate_claim_refs_resolve(claims, external_claim_refs)
    return schema_errors, business_errors, ref_errors


def load_fixture(name):
    path = _FIXTURE_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 claim_inventory_validator.py <inventory.json> [known_segments.json]", file=sys.stderr)
        sys.exit(2)
    data = json.loads(Path(sys.argv[1]).read_text())
    known_segs = None
    if len(sys.argv) > 2:
        known_segs = set(json.loads(Path(sys.argv[2]).read_text()))
    schema_errs, biz_errs, ref_errs = validate_all(data, known_seg_ids=known_segs)
    if schema_errs:
        for e in schema_errs:
            print(f"SCHEMA ERROR: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
    if biz_errs:
        for e in biz_errs:
            print(f"BUSINESS ERROR: [{e['severity']}] {e['path']}: {e['message']}")
    if ref_errs:
        for e in ref_errs:
            print(f"REF ERROR: [{e['severity']}] {e['path']}: {e['message']}")
    exit_code = 1 if schema_errs or biz_errs or ref_errs else 0
    sys.exit(exit_code)
