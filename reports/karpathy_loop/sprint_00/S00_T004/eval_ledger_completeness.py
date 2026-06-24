#!/usr/bin/env python3
"""Validate baseline failure ledger completeness for S00_T004."""
import json
import pathlib

LEDGER = pathlib.Path("reports/karpathy_loop/sprint_00/S00_T004/failure_ledger.json")
OUTPUT = pathlib.Path("reports/karpathy_loop/sprint_00/S00_T004/eval_result_before.json")
EXPECTED_CLASSES = {"F-LIP-001", "F-LIP-004", "F-PROV-001", "F-QA-001", "F-QA-002", "F-GFX-001", "F-GFX-002", "F-TEXT-001"}

checks = []
issues = []

def add_check(name, passed, detail, threshold=""):
    checks.append({"check": name, "pass": bool(passed), "detail": str(detail), "threshold": threshold})
    return bool(passed)

# 1. LEDGER_EXISTS
if not LEDGER.exists():
    add_check("LEDGER_EXISTS", False, "file not found", "file must exist")
    json.dumps({"eval_id":"S00_T004_ledger","overall_pass":False,"checks":checks,"issues":issues})
    exit(1)

try:
    data = json.loads(LEDGER.read_text())
    add_check("LEDGER_EXISTS", True, f"valid JSON, {len(data.get('failures',[]))} failures", "file exists and parseable")
except Exception as e:
    add_check("LEDGER_EXISTS", False, str(e), "file must be valid JSON")
    exit(1)

failures = data.get("failures", [])

# 2. ALL_DEFECTS_CAPTURED
observed_classes = set(f["failure_class"] for f in failures)
missing_classes = EXPECTED_CLASSES - observed_classes
extra_classes = observed_classes - EXPECTED_CLASSES
covered = add_check("ALL_DEFECTS_CAPTURED", len(missing_classes) == 0,
                    f"expected={sorted(EXPECTED_CLASSES)} observed={sorted(observed_classes)} "
                    f"missing={sorted(missing_classes)} extra={sorted(extra_classes)}",
                    "all 8 failure classes captured")
if missing_classes:
    for c in sorted(missing_classes):
        issues.append({"class": c, "severity": "major",
            "description": f"Failure class {c} not in canonical ledger",
            "detail": "All observed failures must be captured in the baseline ledger"})

# 3. REQUIRED_FIELDS
required_fields = {"failure_class", "severity", "evidence", "eval_status", "next_ticket"}
missing_fields = {}
for f in failures:
    mf = required_fields - set(f.keys())
    if mf:
        missing_fields[f.get("failure_class", "UNKNOWN")] = sorted(mf)

fields_ok = add_check("REQUIRED_FIELDS", len(missing_fields) == 0,
                      f"{len(failures)} failures; {len(missing_fields)} with missing fields: {missing_fields}",
                      "each failure must have: failure_class, severity, evidence, eval_status, next_ticket")
for fc, mf in missing_fields.items():
    issues.append({"class": fc, "severity": "major",
        "description": f"Missing required fields: {mf}",
        "detail": "Every failure entry requires all 5 fields"})

# 4. NEXT_TICKETS_ASSIGNED
no_ticket = [f for f in failures if not f.get("next_ticket")]
tickets_ok = add_check("NEXT_TICKETS_ASSIGNED", len(no_ticket) == 0,
                       f"{len(no_ticket)} failures without next_ticket",
                       "all failures must point to a future ticket")
for f in no_ticket:
    issues.append({"class": f["failure_class"], "severity": "major",
        "description": f"No next_ticket for {f.get('failure_class')}",
        "detail": "All failures must be assigned to a future ticket"})

# 5. EVAL_STATUS_COVERAGE
statuses = set(f.get("eval_status", "") for f in failures)
has_missing = "missing" in statuses
has_diagnostic = "diagnostic" in statuses
has_failing = "failing" in statuses
status_ok = add_check("EVAL_STATUS_COVERAGE", has_missing and has_diagnostic and has_failing,
                      f"statuses: {statuses} (missing={has_missing}, diag={has_diagnostic}, failing={has_failing})",
                      "at least one of each: missing, diagnostic, failing")
if not (has_missing and has_diagnostic and has_failing):
    issues.append({"class": "F-QA-002", "severity": "minor",
        "description": f"Eval status coverage incomplete: missing={has_missing}, diagnostic={has_diagnostic}, failing={has_failing}",
        "detail": "Ledger should have entries at each eval maturity level"})

# 6. SEVERITY_DISTRIBUTION
severities = set(f.get("severity", "") for f in failures)
has_critical = "critical" in severities
sev_ok = add_check("SEVERITY_DISTRIBUTION", has_critical,
                   f"severities: {severities}",
                   "at least one critical severity entry")

# Assemble
all_pass = all(c["pass"] for c in checks)
summary = {
    "eval_id": "S00_T004_ledger_validation",
    "subject": str(LEDGER),
    "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",
    "timestamp": "2026-06-23T23:25:00+08:00",
    "overall_pass": all_pass,
    "total_checks": len(checks),
    "checks_passed": sum(1 for c in checks if c["pass"]),
    "checks_failed": sum(1 for c in checks if not c["pass"]),
    "checks": checks,
    "issues": issues,
    "failure_count": len(failures),
    "failure_classes": sorted(observed_classes),
    "summary": {"pass": sum(1 for c in checks if c["pass"]),
                 "fail": sum(1 for c in checks if not c["pass"]),
                 "total": len(checks)}
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(summary, indent=2))

print(f"Ledger Validation: {summary['checks_passed']}/{summary['total_checks']} checks passed")
for c in checks:
    status = "PASS" if c["pass"] else "FAIL"
    print(f"  [{status}] {c['check']}: {c['detail']}")
if issues:
    print(f"\nIssues: {len(issues)}")
    for iss in issues:
        print(f"  {iss.get('class','?')} [{iss['severity']}]: {iss['description']}")
