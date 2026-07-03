#!/usr/bin/env python3
"""storyboard_v2_validator.py — Validator helpers for the canonical SSOT storyboard schema.

Provides schema validation plus Sonnet-5 authority checks that JSON Schema alone
cannot enforce. These are validation-only; no creative generation is introduced.
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
SCHEMA_PATH = ROOT / "schemas" / "storyboard_v2.schema.json"
_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "storyboard_v2"

ALLOWED_SONNET5_MODEL_PATTERNS = ["sonnet", "claude-sonnet"]
NON_CANONICAL_FALLBACK_STR = "BLOCKED_NON_SONNET_AUTHOR"


def load_schema():
    if SCHEMA_PATH.exists():
        return json.loads(SCHEMA_PATH.read_text())
    return None


def validate_against_schema(data):
    if not _HAS_JSONSCHEMA:
        raise RuntimeError("jsonschema library not installed")
    schema = load_schema()
    if schema is None:
        raise RuntimeError(f"Schema not found at {SCHEMA_PATH}")
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    return errors


def validate_sonnet5_authority(data):
    """Check that the authoring model references a Sonnet 5 profile.

    Returns list of error dicts: {"path": str, "message": str}.
    JSON Schema validates presence but model-string inspection requires code.
    """
    errors = []
    profile = (data.get("authoring_model_profile") or "").lower()
    model = (data.get("authoring_model") or "").lower()

    is_sonnet = any(p in profile for p in ALLOWED_SONNET5_MODEL_PATTERNS)
    is_sonnet |= any(p in model for p in ALLOWED_SONNET5_MODEL_PATTERNS)

    if not is_sonnet:
        errors.append({
            "path": "authoring_model_profile",
            "severity": "BLOCKER",
            "message": (
                f"{NON_CANONICAL_FALLBACK_STR}: authoring_model_profile='{data.get('authoring_model_profile')}' "
                f"and authoring_model='{data.get('authoring_model')}' do not reference Sonnet 5. "
                "Runtime storyboard authorship requires Sonnet 5 through Kilo."
            )
        })
    return errors


def is_canonical(data):
    return "storyboard_contract_version" in data


def compatibility_path_for_legacy(data):
    """Check whether a legacy (non-canonical) document is usable.

    Legacy docs pass their own legacy schema check (else branch).
    Consumers should prefer canonical docs but can accept legacy.
    """
    if is_canonical(data):
        return None
    if data.get("schema_version") == "2.0":
        return {"compatibility": "legacy_v2_beat", "action": "accept_as_legacy"}
    return {"compatibility": "unknown", "action": "reject"}


def validate_all(data):
    """Combined validation: schema + Sonnet-5 authority.

    Returns (schema_errors, authority_errors).
    """
    schema_errors = validate_against_schema(data)
    author_errors = validate_sonnet5_authority(data) if is_canonical(data) else []
    return schema_errors, author_errors


def load_fixture(name):
    path = _FIXTURE_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 storyboard_v2_validator.py <storyboard.json>", file=sys.stderr)
        sys.exit(2)
    data = json.loads(Path(sys.argv[1]).read_text())
    schema_errs, author_errs = validate_all(data)
    if schema_errs:
        for e in schema_errs:
            print(f"SCHEMA ERROR: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
    if author_errs:
        for e in author_errs:
            print(f"AUTHORITY ERROR: {e['message']}")
    exit_code = 1 if schema_errs or author_errs else 0
    sys.exit(exit_code)
