# TKT-005 Validation Report

**Ticket**: Operator CLI: link reused footage artifacts
**Commit**: `6d5d396`
**Validator**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Acceptance Gates

| Gate | Expected | Result | Evidence |
|------|----------|--------|----------|
| G1 | All 4 scenarios pass via subprocess tests | PASS | `test_link_valid_file_to_reused_unit` (exit 0, status=generated), `test_non_reused_unit_rejected` (exit non-zero, DB unchanged), `test_missing_file_rejected` (exit non-zero, DB unchanged), `test_second_link_attempt_rejected` (exit non-zero, first link preserved) |
| G2 | After linking, unit status = generated | PASS | Manual: link via CLI → `status=generated`, `active_artifact_id` matches output. Confirmed `link_artifact_to_render_unit` sets status to `generated`. |
| G3 | Focused suite passes | PASS | 109 invariant + 4 dedicated = all pass |

## Verification Results

| Check | Result |
|-------|--------|
| 4 dedicated tests | ALL PASS |
| 109 focused invariant tests | ALL PASS |
| Valid file → link succeeds, status=generated | PASS |
| Non-reused unit → rejected, DB unchanged | PASS |
| Missing file → rejected, DB unchanged | PASS |
| Second link → rejected, first link preserved | PASS |
| commit 6d5d396: only produce_db.py + test file changed | PASS |

## Audit findings disposition

**FINDING-1 (LOW)**: Non-atomic `register_artifact` + `link_artifact_to_render_unit` — **non-blocking**. The two calls execute in separate DB transactions. If the link step fails after registration, an orphan artifact row exists. Mitigated by: single-user CLI, idempotent `register_artifact` (UNIQUE constraint on `(production_id, uri, sha256)`), and low operational impact. This is a pre-existing pattern in the codebase.

## Residual risks

- Duration tolerance set to 10% as noted in execution log — ticket does not specify exact value, this is a reasonable default.
- Path resolution uses `Path(file_path).resolve()` — absolute path, no traversal risk. No directory whitelisting; operator is trusted.

## State transition

TKT-005 accepted. Moving from `ready_for_validation_with_findings` → `completed_tickets`. Next eligible: TKT-006 (Wave 0, ROUTINE, ready_for_audit).
