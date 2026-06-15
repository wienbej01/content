# TKT-07 Audit Report

**Auditor:** Kiro subagent  
**Date:** 2026-06-14  
**Verdict:** REVISE (1 residual casing bug)

---

## 1. `scripts/qa_media.py` — Status Casing

| Check | Result | Notes |
|-------|--------|-------|
| Main loop emits uppercase | ✅ PASS | Line 428: `"FAIL" if entry["issues"] else "PASS"` |
| Coverage deficit emits uppercase | ✅ PASS | Line 447: `entry["status"] = "FAIL"` |
| Aggregate consistency guard | ✅ PASS | Line 451: uses `.upper() == "PASS"` — catches any casing |
| Early-exit: MISSING (line 356) | ❌ **REVISE** | Emits lowercase `"fail"` |
| Early-exit: UNREADABLE (line 364) | ❌ **REVISE** | Emits lowercase `"fail"` |

**Impact:** The aggregate boolean is unaffected (the guard at line 451 normalizes via `.upper()`). However:
- `main()` CLI output at lines 474–475 uses exact `== "FAIL"` / `== "PASS"` — a beat with lowercase `"fail"` won't be counted in the `failed` tally (display bug).
- External consumers reading the JSON report would see inconsistent casing.
- The TKT-07 spec explicitly requires uppercase everywhere.

**Fix:** Change lines 356 and 364 from `"fail"` → `"FAIL"`.

---

## 2. Coverage Deficit Check

| Check | Result | Notes |
|-------|--------|-------|
| Compares actual clip duration vs timing-map | ✅ PASS | Lines 439–448 |
| Threshold: deficit > 0.25s | ✅ PASS | Line 441 |
| Timing map loading: graceful if absent | ✅ PASS | `_load_timing_map` returns None if file missing; line 435 guards with `if timing_map:` |
| Missing beat IDs handled gracefully | ✅ PASS | Line 438: `if bid and bid in tm_lookup and entry.get("duration")` — unknown beat IDs silently skip |
| Skips appropriate beat types | ✅ PASS | `local_graphic`/`still_kenburns` beats are excluded from `results` at lines 317–323 (never reach coverage check) |

---

## 3. Aggregate Consistency Guard

| Check | Result | Notes |
|-------|--------|-------|
| No path to return `passed=True` with a FAIL row | ✅ PASS | Line 451–453: `row_pass = all(r.get("status","").upper() == "PASS" for r in results)` then `if row_pass != all_pass: all_pass = False` — any mismatch forces False |
| `run_qa()` signature | ✅ PASS | Returns `(results, all_pass)` at line 455 |

---

## 4. `scripts/produce.py` — `step_qa_media` (line 306)

| Check | Result | Notes |
|-------|--------|-------|
| Uses `passed` boolean from `run_qa()` | ✅ PASS | Line 309: destructures `results, passed` |
| Case-insensitive fail counting | ✅ PASS | Line 310: `.upper() == "FAIL"` |
| Double-guard: `if fail_count > 0 or not passed` | ✅ PASS | Line 314: blocks on either condition |
| Report uses both signals | ✅ PASS | Line 311: `"passed": passed and fail_count == 0` |

No path exists to reach Gate B with broken media.

---

## 5. `tests/test_qa_media.py`

| Test | Result | Notes |
|------|--------|-------|
| `test_lowercase_fail_counts_as_failure` | ✅ PASS | Line 213–222: injects lowercase `"fail"`, verifies produce.py's `.upper() == "FAIL"` finds it |
| `test_coverage_deficit_fails_beat` | ✅ PASS | Lines 226–251: 3s clip vs 10s timing requirement → COVERAGE_DEFICIT |
| `test_coverage_sufficient_passes` | ✅ PASS | Lines 254–275: 10s clip vs 9.5s requirement → PASS |
| `test_aggregate_cannot_disagree_with_rows` | ✅ PASS | Lines 278–292: wrong dims → FAIL row → aggregate False |
| All 20 tests pass | ✅ PASS | `python3 -m pytest tests/test_qa_media.py -v` → 20 passed in 13.28s |

**Note on `test_lowercase_fail_counts_as_failure`:** This test validates the `produce.py` aggregation pattern (`.upper()` comparison) with synthetic data. It does NOT test that `qa_media.py` itself never emits lowercase — which is the residual bug above.

---

## 6. Backward Compatibility

| Check | Result |
|-------|--------|
| No overbroad refactors | ✅ PASS — changes are surgical |
| Existing tests unbroken | ✅ PASS — all 20 pass |
| `run_qa()` API unchanged | ✅ PASS — same `(results, passed)` return |

---

## Summary

The TKT-07 fix correctly addresses:
1. ✅ Coverage deficit check (new, working, tested)
2. ✅ Aggregate consistency guard (prevents `passed=True` with failed rows)
3. ✅ `produce.py` case-insensitive comparison (belt-and-suspenders)

**Remaining issue:** Two early-exit paths in `qa_media.py` still emit lowercase `"fail"` (lines 356, 364). While functionally safe due to the aggregate guard and produce.py's `.upper()` comparison, this violates the TKT-07 spec ("status values emitted must be uppercase everywhere") and causes a display bug in `main()` CLI output.

---

## Verdict: REVISE

**Required fix:** `scripts/qa_media.py` lines 356 and 364 — change `"fail"` → `"FAIL"`.
