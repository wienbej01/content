#!/usr/bin/env python3
"""Eval: source_slice_sha256 must exist in schema and be populated before provider submission.

Expected to FAIL before implementation (Sprint 00 baseline).
"""
import json
import os
import sqlite3
import pathlib
import re

DB = os.environ.get("PRODUCTION_DB_PATH", "db/production.db")
PROD = "prod_2f9bb58c0508465fb51ac6b4578bba92"
OUTPUT = pathlib.Path("reports/karpathy_loop/sprint_01/S01_T001/eval_result_before.json")

checks = []
issues = []

def add_check(name, passed, detail, threshold=""):
    checks.append({"check": name, "pass": bool(passed), "detail": str(detail), "threshold": threshold})
    return bool(passed)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# 1. SCHEMA_HAS_SOURCE_SLICE_SHA256
cols = conn.execute("PRAGMA table_info(render_units)").fetchall()
col_names = [c[1] for c in cols]
has_slice_sha256 = "source_slice_sha256" in col_names
add_check("SCHEMA_HAS_SOURCE_SLICE_SHA256", has_slice_sha256,
          f"source_slice_sha256 in render_units: {has_slice_sha256}",
          "column must exist")

# 2. SCHEMA_HAS_SOURCE_SLICE_PATH
has_slice_path = "source_slice_path" in col_names
add_check("SCHEMA_HAS_SOURCE_SLICE_PATH", has_slice_path,
          f"source_slice_path in render_units: {has_slice_path}",
          "column must exist")

if not has_slice_sha256:
    issues.append({"class": "F-PROV-001", "severity": "major",
        "description": "render_units table missing source_slice_sha256 column",
        "detail": "Cannot prove slice-to-provider provenance without column"})
if not has_slice_path:
    issues.append({"class": "F-PROV-001", "severity": "minor",
        "description": "render_units table missing source_slice_path column",
        "detail": "Can be derived from artifact URI but first-class column preferred"})

# 3. VALID_HERO_UNITS_HAVE_SLICE_HASH (only if column exists)
if has_slice_sha256:
    rows = conn.execute(f"""
        SELECT id, label, source_slice_sha256, active_artifact_id, status
        FROM render_units
        WHERE production_id=? AND status='valid' AND lipsync_required=1
    """, (PROD,)).fetchall()
    missing_hash = [(r["label"], r["id"]) for r in rows if not r["source_slice_sha256"]]
    populated = len(rows) - len(missing_hash)
    add_check("VALID_HERO_UNITS_HAVE_SLICE_HASH", len(missing_hash) == 0,
              f"{len(rows)} valid HERO units; {populated} with hash, {len(missing_hash)} without",
              "all valid HERO units have source_slice_sha256")
    if missing_hash:
        for label, rid in missing_hash:
            issues.append({"class": "F-PROV-001", "severity": "major",
                "description": f"Valid HERO unit {label} ({rid[:20]}...) has no source_slice_sha256",
                "detail": "Missing slice hash breaks provider provenance chain"})
else:
    add_check("VALID_HERO_UNITS_HAVE_SLICE_HASH", False,
              "column does not exist — cannot verify",
              "all valid HERO units have source_slice_sha256")
    issues.append({"class": "F-PROV-001", "severity": "critical",
        "description": "Cannot check hero unit slice hashes — column source_slice_sha256 does not exist",
        "detail": "Schema must be migrated first"})

# 4. SUBMIT_GATE_EXISTS — check media_service.py for source_slice_sha256 gate
media_service = pathlib.Path("scripts/media_service.py")
if media_service.exists():
    code = media_service.read_text()
    has_gate = "source_slice_sha256" in code
    add_check("SUBMIT_GATE_EXISTS", has_gate,
              f"media_service.py references source_slice_sha256: {has_gate}",
              "submit_provider_job must check source_slice_sha256 before submission")
    if not has_gate:
        issues.append({"class": "F-QA-001", "severity": "major",
            "description": "submit_provider_job does not check source_slice_sha256 before provider submission",
            "detail": "No provenance gate exists"})
else:
    add_check("SUBMIT_GATE_EXISTS", False, "media_service.py not found", "gate must exist")

# 5. TESTS_EXIST
test_dir = pathlib.Path("tests")
test_files = [str(f) for f in test_dir.glob("test_source_slice*")] if test_dir.exists() else []
has_tests = len(test_files) > 0
add_check("TESTS_EXIST", has_tests,
          f"test_source_slice* files: {test_files if test_files else 'NONE'}",
          "at least one test_source_slice* file exists")
if not has_tests:
    issues.append({"class": "F-QA-002", "severity": "major",
        "description": "No test_source_slice* test files exist",
        "detail": "Missing tests for source-slice provenance gate"})

conn.close()

# 6. TESTS_PASS — placeholder for post-implementation run
add_check("TESTS_PASS", False,
          "Tests not run yet (pre-implementation eval)",
          "python3 -m pytest tests/test_source_slice*.py -q")

all_pass = all(c["pass"] for c in checks)
summary = {
    "eval_id": "S01_T001_source_slice_ledger",
    "subject": "render_units schema + media_service.py submit gate",
    "production_id": PROD,
    "timestamp": "2026-06-23T23:30:00+08:00",
    "overall_pass": all_pass,
    "total_checks": len(checks),
    "checks_passed": sum(1 for c in checks if c["pass"]),
    "checks_failed": sum(1 for c in checks if not c["pass"]),
    "checks": checks,
    "issues": issues,
    "expected_to_fail": True,
    "summary": {"pass": sum(1 for c in checks if c["pass"]),
                 "fail": sum(1 for c in checks if not c["pass"]),
                 "total": len(checks)}
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(summary, indent=2))

print(f"Source Slice Ledger Eval: {summary['checks_passed']}/{summary['total_checks']} checks passed")
for c in checks:
    status = "PASS" if c["pass"] else "FAIL"
    print(f"  [{status}] {c['check']}: {c['detail']}")
print(f"\nIssues: {len(issues)}")
for iss in issues:
    print(f"  {iss['class']} [{iss['severity']}]: {iss['description']}")
