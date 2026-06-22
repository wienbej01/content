# PTC-04 Engineer Report — Repair Loop Integration & Fail-Closed CLI Semantics

**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Changes Made

### 1. Fail-closed CLI: `reconcile_production_storyboard.py`

- Exit non-zero when ANY `needs_repair` beat remains, validation errors exist, or ERROR-level issues found
- Dry-run mode: writes preview then exits 1 if invalid (orchestrator gets signal)
- Production mode: atomic write via diagnostic path — if output is invalid AND a valid file exists, writes to `.invalid.json` and preserves the existing valid artifact

### 2. Fail-closed CLI: `repair_storyboard_beats.py`

- Exit non-zero on: REPAIR_FAILED, MALFORMED LLM output, validation errors, or remaining `needs_repair` beats
- Won't overwrite valid existing file with invalid output (writes to `.repair_failed.json` diagnostic)

### 3. `--output` added to review invocation in `produce.py`

- `review_production_storyboard.py` now invoked with `--output review_report.json`
- Review report is also checked for `blocks_production` flag

### 4. Repair wired into `step_production_storyboard`

New flow:
1. Run reconcile → if exit 0, proceed to review
2. If reconcile exits non-zero: read output (or diagnostic), identify `needs_repair` beats
3. Run `repair_storyboard_beats.py` targeting those beat IDs
4. If repair fails → RuntimeError
5. Promote repaired output, re-validate (remaining needs_repair → RuntimeError)
6. Run review with `--output`; if blocks_production → RuntimeError

### 5. Fingerprint includes repair policy

When repair runs, fingerprint producer is set to `reconcile+repair` with upstream hashes from storyboard + timing map.

## Files Modified

| File | Change |
|------|--------|
| `scripts/reconcile_production_storyboard.py` | Fail-closed exit logic, atomic write, validation gate |
| `scripts/repair_storyboard_beats.py` | Fail-closed exit logic, safe write |
| `scripts/produce.py` | Wire repair loop, add `--output` to review, fingerprint update |
| `tests/test_repair_integration.py` | 6 new tests (created) |

## Test Results

```
tests/test_repair_integration.py::test_reconcile_cli_exits_nonzero_on_unresolved PASSED
tests/test_repair_integration.py::test_reconcile_cli_exits_zero_when_resolved PASSED
tests/test_repair_integration.py::test_review_called_with_output PASSED
tests/test_repair_integration.py::test_repair_wired_in_produce PASSED
tests/test_repair_integration.py::test_invalid_output_not_promoted PASSED
tests/test_repair_integration.py::test_repair_failure_raises PASSED

Full suite: 455 passed in 100.38s
```

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | produce.py invokes repair_storyboard_beats when needs_repair beats remain | ✅ |
| 2 | review invoked with --output | ✅ |
| 3 | reconcile/repair exit non-zero on unresolved/invalid output | ✅ |
| 4 | Invalid output never overwrites valid production storyboard | ✅ |
| 5 | All 6 tests pass | ✅ |
