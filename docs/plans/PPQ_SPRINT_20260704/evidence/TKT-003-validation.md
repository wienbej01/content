# TKT-003 Validation Report

**Ticket**: Populate visible windows on the main compile path
**Commit**: `82a97d1`
**Validator**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Acceptance Gates

| Gate | Expected | Result | Evidence |
|------|----------|--------|----------|
| G1 | Non-null visible windows on all hero units | PASS | Manual: compiled hero unit produces `visible=[0, 480000]` == speech, ⊆ generation. `test_single_slot_hero_visible_window` + `test_multi_slot_hero_visible_window` (5 assertions each) |
| G2 | Negative tests pass | PASS | `test_visible_outside_generation_rejected` + `test_visible_before_generation_rejected` both raise `PolicyValidationError` with `"Visible interval"` |
| G3 | Focused suite passes | PASS | `YT_TEST_MODE=1 python3 -m pytest ... -q` → 109 passed; `tests/test_hero_visible_window.py -v` → 5 passed |

## Verification Results

| Check | Result |
|-------|--------|
| 5 dedicated tests | ALL PASS |
| 109 focused invariant tests | ALL PASS |
| Baseline (produce_db_orchestrator) | 13 PASS |
| visible == speech on single-slot hero | PASS |
| visible == speech per slot on multi-slot hero | PASS |
| validate_hero_slicing_intervals accepts compiled units | PASS |
| visible > generation end → PolicyValidationError | PASS |
| visible < generation start → PolicyValidationError | PASS |
| commit 82a97d1: only produce_db.py + test file changed | PASS |

## Audit findings disposition

**FINDING-1 (LOW)**: Missing EXECUTION_LOG implement record — **RESOLVED**. Record appended to `EXECUTION_LOG.jsonl`.

## Residual risks

- Visible window always equals speech window (no lead/trail silence buffer). If future logic extends speech beyond generation (e.g., adding trailing padding), visible would exceed generation and fail validation. This is correct behavior per the gate.

## State transition

TKT-003 accepted. Moving from `ready_for_validation_with_findings` → `completed_tickets`. Next eligible ticket per dependency order: TKT-004 (Wave 0, ROUTINE, ready_for_audit).
