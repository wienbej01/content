#!/usr/bin/env python3
"""review_storyboard_v2.py — Sonnet 5 creative review gate for canonical storyboards.

Requires Python structural validation to pass first.
Uses Sonnet 5 through Kilo for creative review.

Usage:
  python3 scripts/review_storyboard_v2.py storyboard.json
  python3 scripts/review_storyboard_v2.py storyboard.json --dry-run
  python3 scripts/review_storyboard_v2.py storyboard.json --output review.json
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

SONNET5_PROFILES = {"storyboard_director_sonnet5", "storyboard_sonnet5"}
REVIEW_TASK = "storyboard_creative_review"
REQUIRED_PERSPECTIVES = {"visual_director", "filmmaker", "audience", "technical"}
REQUIRED_PERSPECTIVE_STATUS = {"pass", "fail"}
REQUIRED_OUTPUT_FIELDS = {
    "task", "persona", "storyboard_sha256", "status", "may_proceed",
    "visual_director", "filmmaker", "audience", "technical",
    "sonnet_author_verified", "overall_score",
}
PERSPECTIVE_FIELDS = {"status", "scores", "overall_score", "blocking_issues", "warnings", "recommended_fixes"}


def load_storyboard(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Storyboard must be a JSON object")
    return data


def compute_sha256(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def check_author_is_sonnet5(storyboard):
    profile = storyboard.get("authoring_model_profile", "")
    model = storyboard.get("authoring_model", "")
    if profile not in SONNET5_PROFILES and "sonnet" not in profile.lower():
        return False, (
            f"BLOCKED_NON_SONNET_AUTHOR: Storyboard author profile {profile!r} "
            f"is not Sonnet 5. Only Sonnet-authored storyboards may receive creative approval."
        )
    if not model or "sonnet" not in model.lower():
        return False, (
            f"BLOCKED_NON_SONNET_AUTHOR: Storyboard author model {model!r} "
            f"is not Sonnet 5. Only Sonnet-authored storyboards may receive creative approval."
        )
    return True, None


def run_python_structural_check(storyboard):
    if storyboard.get("schema_version") == "2.0":
        from review_storyboard import review as structural_review, load_constraints
        constraints = load_constraints()
        blocking, warnings, fixes = structural_review(storyboard, constraints)
        if blocking:
            return False, blocking, warnings, fixes
        return True, [], warnings, fixes

    valid, reason = check_canonical_format(storyboard)
    if not valid:
        return False, [reason], [], []
    return True, [], [], []


def check_canonical_format(storyboard):
    if storyboard.get("storyboard_contract_version") is None:
        return False, "Storyboard must have storyboard_contract_version (canonical format)"
    for required in ("claim_inventory", "narrative_beats", "shots", "overlays", "segment_work_orders"):
        if required not in storyboard:
            return False, f"Canonical storyboard missing required field: {required}"
    return True, None


def build_review_prompt(storyboard):
    prompt_path = ROOT / "docs" / "prompts" / "STORYBOARD_SONNET5_CREATIVE_REVIEW.md"
    template = prompt_path.read_text()

    sb_json = json.dumps(storyboard, indent=2)
    sb_sha256 = compute_sha256(storyboard)

    approved_script = {}
    script_revision = storyboard.get("approved_script_revision_id", "")
    if script_revision:
        approved_script = {
            "approved_script_revision_id": script_revision,
            "approved_script_sha256": storyboard.get("approved_script_sha256", ""),
        }

    prompt = (
        template
        .replace("{storyboard_canonical_json}", sb_json)
        .replace("{storyboard_sha256}", sb_sha256)
        .replace("{approved_script_json}", json.dumps(approved_script, indent=2))
    )

    return prompt, sb_sha256


def validate_creative_review_output(data, storyboard_sha256):
    errors = []
    if not isinstance(data, dict):
        return ["Review output must be a JSON object"]

    for field in REQUIRED_OUTPUT_FIELDS:
        if field not in data:
            errors.append(f"Review output missing required field: {field}")

    if data.get("status") not in ("pass", "fail"):
        errors.append(f"Review top-level status must be 'pass' or 'fail', got: {data.get('status')!r}")

    if not isinstance(data.get("may_proceed"), bool):
        errors.append(f"may_proceed must be boolean, got: {type(data.get('may_proceed')).__name__}")

    if data.get("storyboard_sha256") != storyboard_sha256:
        errors.append(
            f"Review storyboard_sha256 mismatch: expected {storyboard_sha256}, "
            f"got {data.get('storyboard_sha256')!r}"
        )

    if not isinstance(data.get("sonnet_author_verified"), bool):
        errors.append(f"sonnet_author_verified must be boolean")

    for perspective in REQUIRED_PERSPECTIVES:
        pdata = data.get(perspective)
        if not isinstance(pdata, dict):
            errors.append(f"Review missing perspective: {perspective}")
            continue
        for f in PERSPECTIVE_FIELDS:
            if f not in pdata:
                errors.append(f"Review perspective {perspective} missing field: {f}")
        if pdata.get("status") not in REQUIRED_PERSPECTIVE_STATUS:
            errors.append(
                f"Review perspective {perspective} status must be 'pass' or 'fail', "
                f"got: {pdata.get('status')!r}"
            )
        if not isinstance(pdata.get("blocking_issues"), list):
            errors.append(f"Review perspective {perspective} blocking_issues must be a list")
        if not isinstance(pdata.get("warnings"), list):
            errors.append(f"Review perspective {perspective} warnings must be a list")
        if not isinstance(pdata.get("recommended_fixes"), list):
            errors.append(f"Review perspective {perspective} recommended_fixes must be a list")

    return errors


def creative_review(storyboard, dry_run=False, stub=None, verbose=False):
    """Run Sonnet 5 creative review gate.

    Returns (passed, report_dict).
    """
    report = {
        "task": REVIEW_TASK,
        "storyboard_path": None,
    }

    err = check_canonical_format(storyboard)
    if err[0] is False:
        report["status"] = "fail"
        report["may_proceed"] = False
        report["blocking_issues"] = [err[1]]
        report["warnings"] = []
        report["recommended_fixes"] = ["Regenerate storyboard in canonical format"]
        return False, report

    is_sonnet5, auth_error = check_author_is_sonnet5(storyboard)
    if not is_sonnet5:
        report["status"] = "fail"
        report["may_proceed"] = False
        report["blocking_issues"] = [auth_error]
        report["warnings"] = []
        report["recommended_fixes"] = [
            "Regenerate storyboard with Sonnet 5 (storyboard_director_sonnet5 profile)"
        ]
        return False, report

    py_valid, py_blocking, py_warnings, py_fixes = run_python_structural_check(storyboard)
    if not py_valid:
        report["status"] = "fail"
        report["may_proceed"] = False
        report["blocking_issues"] = (
            ["BLOCKED_PYTHON_VALIDATION_FAILED: Storyboard failed structural validation. "
             "Creative review cannot proceed until Python validation passes."]
            + py_blocking
        )
        report["warnings"] = py_warnings
        report["recommended_fixes"] = py_fixes
        return False, report

    if dry_run or stub is not None:
        if stub is not None:
            data = stub(storyboard)
            sb_sha256 = compute_sha256(storyboard)
        else:
            report["status"] = "dry_run"
            report["may_proceed"] = None
            report["python_validation"] = {"passed": True, "warnings": py_warnings}
            return None, report
    else:
        from llm_call import llm_call

        prompt, sb_sha256 = build_review_prompt(storyboard)

        if verbose:
            print(f"  prompt chars: {len(prompt)}", file=sys.stderr)
            print(f"  storyboard sha256: {sb_sha256}", file=sys.stderr)

        data, raw_text, profile_name, model = llm_call(
            task=REVIEW_TASK,
            prompt=prompt,
            dry_run=False,
            expect_json=True,
            verbose=verbose,
        )

    validation_errors = validate_creative_review_output(data, sb_sha256)
    if validation_errors:
        report["status"] = "fail"
        report["may_proceed"] = False
        report["blocking_issues"] = (
            ["BLOCKED_MALFORMED_REVIEW: Creative review output is malformed."]
            + validation_errors
        )
        report["warnings"] = []
        report["recommended_fixes"] = ["Re-run creative review with Sonnet 5 to get properly formatted output"]
        report["_raw_review"] = data
        return False, report

    report["status"] = data.get("status", "fail")
    report["may_proceed"] = data.get("may_proceed", False)
    report["overall_score"] = data.get("overall_score")
    report["sonnet_author_verified"] = data.get("sonnet_author_verified", False)
    report["storyboard_sha256"] = data.get("storyboard_sha256")
    report["python_validation"] = {"passed": True, "warnings": py_warnings}

    blocking_issues = []
    warnings = []
    recommended_fixes = []
    entity_ids = set()

    for perspective in REQUIRED_PERSPECTIVES:
        pdata = data.get(perspective, {})
        pstatus = pdata.get("status")
        report[f"{perspective}_status"] = pstatus

        for b in pdata.get("blocking_issues", []):
            issue_text = b if isinstance(b, str) else str(b)
            blocking_issues.append({"perspective": perspective, "issue": issue_text})
            extracted = _extract_entity_ids(issue_text)
            entity_ids.update(extracted)

        for w in pdata.get("warnings", []):
            warnings.append({"perspective": perspective, "warning": w})

        for f in pdata.get("recommended_fixes", []):
            fix_text = f if isinstance(f, str) else str(f)
            recommended_fixes.append({"perspective": perspective, "fix": fix_text})
            extracted = _extract_entity_ids(fix_text)
            entity_ids.update(extracted)

    report["blocking_issues"] = blocking_issues
    report["warnings"] = warnings
    report["recommended_fixes"] = recommended_fixes
    report["affected_entity_ids"] = sorted(entity_ids) if entity_ids else []

    passed = report["may_proceed"] is True
    return passed, report


def _extract_entity_ids(text):
    import re
    ids = set()
    for m in re.finditer(r'\b(SH\d+|NB\d+|OV\d+|C\d+|B\d+)\b', text):
        ids.add(m.group(1))
    return ids


def run_creative_review_on_path(storyboard_path, dry_run=False, stub=None, verbose=False):
    """Load storyboard from path and run creative review gate."""
    storyboard = load_storyboard(storyboard_path)
    passed, report = creative_review(storyboard, dry_run=dry_run, stub=stub, verbose=verbose)
    report["storyboard_path"] = str(storyboard_path)
    return passed, report


def main():
    ap = argparse.ArgumentParser(
        description="Sonnet 5 creative review gate for canonical storyboards (v2 SSOT)."
    )
    ap.add_argument("storyboard", help="Path to canonical storyboard JSON")
    ap.add_argument("--output", "-o", default=None, help="Output JSON report path")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without calling LLM")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    path = Path(args.storyboard)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        passed, report = run_creative_review_on_path(
            path, dry_run=args.dry_run, verbose=args.verbose,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2))
        print(f"  report: {args.output}", file=sys.stderr)

    status = "pass" if passed else ("dry_run" if args.dry_run else "fail")
    blocking = report.get("blocking_issues", [])
    warnings = report.get("warnings", [])

    print(f"  creative_review: {status.upper()}", file=sys.stderr)
    if passed is not None:
        print(f"  may_proceed: {passed}", file=sys.stderr)
    if isinstance(report.get("overall_score"), (int, float)):
        print(f"  overall_score: {report['overall_score']}", file=sys.stderr)
    for w in warnings:
        w_text = w if isinstance(w, str) else w.get("warning", str(w))
        print(f"  ⚠ {w_text}", file=sys.stderr)
    for b in blocking:
        b_text = b if isinstance(b, str) else b.get("issue", str(b))
        print(f"  ✗ BLOCKING: {b_text}", file=sys.stderr)
    if report.get("affected_entity_ids"):
        print(f"  affected entities: {', '.join(report['affected_entity_ids'])}", file=sys.stderr)

    if passed is True:
        sys.exit(0)
    elif args.dry_run:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
