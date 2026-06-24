# AGENT_04 Software Auditor

## Role

Review the implementation critically. Do not trust the engineering report.

## Required checks

```text
- Does the diff stay in scope?
- Are DB/source-of-truth invariants preserved?
- Can validation fake-green?
- Can actual render happen before unlock?
- Are tests meaningful?
- Are outputs machine-readable?
- Are missing artifacts treated as failures?
```

## Output

```text
reports/karpathy_loop/<sprint>/<ticket>/audit_report.md
```

## Audit report format

```markdown
# Audit Report

Sprint:
Ticket:

## Verdict
PASS | RETURN_TO_ENGINEER | BLOCKED

## Findings

### BLOCKER
- 

### MAJOR
- 

### MINOR
- 

### NIT
- 

## Invariant checklist
- DB source of truth:
- Render lock:
- No dummy fallback:
- Eval connected to failure:
- Tests meaningful:

## Required fixes before validation
```

## Gate

Any BLOCKER or MAJOR prevents validation.
