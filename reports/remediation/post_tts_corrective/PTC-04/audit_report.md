# PTC-04 Audit Report

**Ticket:** PTC-04 — Repair wired into produce.py, review --output added, CLIs fail-closed  
**Auditor:** kiro-cli subagent (read-only)  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Scope

Verify four properties:
1. Repair step wired into `produce.py`
2. Review invocation includes `--output`
3. `reconcile_production_storyboard.py` exits non-zero when beats are unresolved (no audio), zero when resolved (with audio reroute)
4. Invalid output is not promoted over valid existing output (atomic write protection)

---

## Findings

### 1. Repair wired in `produce.py` ✅

`scripts/produce.py` lines 364-368 invoke `repair_storyboard_beats.py` with `--output` when reconcile exits non-zero and `needs_repair` beats are detected. After repair, the repaired output is promoted to the canonical path and re-validated (lines 396-399 check remaining repair beats and raise if any persist).

### 2. Review `--output` ✅

`scripts/produce.py` line 404 passes `--output` to `review_production_storyboard.py`. The review result is written to `review_report.json` in the project directory.

### 3. Fail-closed exit codes ✅

- **Without audio:** Reconcile detects 3 beats (B006, B008, B010) exceeding 10s model max. Marks them `needs_repair=True`. Exit code: **1**.
- **With audio:** All beats resolved via measured-boundary splitting. 14 production beats, 0 unresolved. Exit code: **0**.

Verified via direct CLI invocation against `using_ai_to_help_memory_retention_short` project.

### 4. Atomic write protection ✅

`reconcile_production_storyboard.py` lines 628-633: when `is_invalid` is true and an existing output file exists, the invalid result is written to `.invalid.json` diagnostic path instead. The valid existing file is preserved. Script exits 1.

`repair_storyboard_beats.py` lines 276, 298-305: exits 1 on REPAIR_FAILED or malformed results. Produce.py raises RuntimeError on non-zero repair exit — never promotes partial/failed repair output.

---

## Test Coverage

- `tests/test_repair_integration.py`: 6/6 passed
  - `test_reconcile_cli_exits_nonzero_on_unresolved` ✅
  - `test_reconcile_cli_exits_zero_when_resolved` ✅
  - `test_review_called_with_output` ✅
  - `test_repair_wired_in_produce` ✅
  - `test_invalid_output_not_promoted` ✅
  - `test_repair_failure_raises` ✅

- Full suite: **455 passed** in 100s

---

## Conclusion

All four PTC-04 properties are correctly implemented and tested. No issues found.
