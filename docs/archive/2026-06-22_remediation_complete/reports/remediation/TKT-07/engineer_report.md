# TKT-07 Engineer Report — Media QA Upgrade and Aggregation Fix

## Files Changed

### `scripts/qa_media.py`
- **Status normalization** (line ~280): Changed `entry["status"] = "fail"/"pass"` → `"FAIL"/"PASS"` (uppercase constant).
- **`_load_timing_map()` helper** (inserted before `run_qa`): Loads `beat_timing_map.json` from `ROOT/Videos/Projects/{project_id}/narration/` or base-relative. Returns None if absent (no breakage for projects without timing maps).
- **Coverage-deficit check** (after per-beat loop): For each beat with a timing-map entry, compares `actual_duration` vs `required_duration = end - start`. If deficit > 0.25s, adds `COVERAGE_DEFICIT` FAIL issue.
- **Aggregate consistency guard** (end of `run_qa`): Verifies `all_pass` boolean agrees with `all(status == "PASS" for r in results)`. If they disagree, forces `all_pass = False`.
- **`main()` print summary** (line ~310): Updated status comparisons to uppercase.

### `scripts/produce.py`
- **`step_qa_media()`** (line ~210): Changed `r.get("status") == "FAIL"` → `r.get("status", "").upper() == "FAIL"` (case-insensitive). Also checks `not passed` from `run_qa()` return.

### `tests/test_qa_media.py`
- Updated existing assertions from lowercase `"pass"`/`"fail"` to uppercase `"PASS"`/`"FAIL"`.
- **4 new tests added:**
  1. `test_lowercase_fail_counts_as_failure` — verifies produce.py aggregation logic catches lowercase `"fail"`
  2. `test_coverage_deficit_fails_beat` — 3s clip with 10s timing requirement → COVERAGE_DEFICIT FAIL
  3. `test_coverage_sufficient_passes` — 10s clip with 9.5s requirement → PASS
  4. `test_aggregate_cannot_disagree_with_rows` — wrong-dimension clip → row FAIL → aggregate False

## Behavior Added

1. **Casing contract**: `qa_media.py` now emits only uppercase `"FAIL"` / `"PASS"` in all results.
2. **Defensive aggregation**: `produce.py` uses `.upper()` comparison so even mixed-case status values cannot slip through.
3. **Coverage-deficit detection**: When a timing map exists, each beat's rendered visual duration is compared to its allocated time. Deficit > 0.25s = hard FAIL.
4. **Aggregate consistency**: If any row is FAIL but `all_pass` was somehow True (defensive), it forces False.

## Tests Added

| Test | Validates |
|------|-----------|
| `test_lowercase_fail_counts_as_failure` | Produce.py aggregation handles lowercase |
| `test_coverage_deficit_fails_beat` | 3s clip, 10s required → COVERAGE_DEFICIT FAIL |
| `test_coverage_sufficient_passes` | 10s clip, 9.5s required → PASS (no false positive) |
| `test_aggregate_cannot_disagree_with_rows` | Row FAIL → aggregate must be False |

## Commands Executed

```
$ python3 -m pytest tests/test_qa_media.py -v
20 passed in 13.22s

$ python3 -m pytest -q 2>&1 | tail -5
FAILED tests/test_review.py::test_all_pass_aggregates_pass - assert (False)
FAILED tests/test_review.py::test_audience_veto_blocks - AssertionError
FAILED tests/test_review.py::test_feedback_loop_revises_then_passes - ValueError
FAILED tests/test_review.py::test_loop_escalates_after_max_rounds - TypeError
4 failed, 287 passed in 81.11s
```

The 4 failures in `test_review.py` are **pre-existing** (unrelated to this ticket — they concern `review_loop()` API changes).

## Known Risks

- **Coverage check is optional**: Only activates when `beat_timing_map.json` exists. Projects without a timing map won't get this validation (by design — avoids breaking older projects).
- **Tolerance threshold**: 0.25s deficit tolerance is tight enough to catch the 4–15s deficits in B003/B005/B007/B008/B009 but won't fire on sub-frame rounding differences.
- **`_load_timing_map` pathing**: Relies on `project_id` matching the directory name (enforced by `_enforce_project_id` in produce.py).

## Revision — 2026-06-14

**Finding:** Two lowercase `"fail"` literals remained in the MISSING and UNREADABLE early-exit paths (lines 355–356, 363–364). These were missed in the initial fix and would not be counted by `main()`'s `sum(... == "FAIL")` logic (lines 474–475), causing silent under-reporting of failures.

**Fix applied:**
- Line 356: `entry["status"] = "fail"` → `entry["status"] = "FAIL"` (MISSING path)
- Line 364: `entry["status"] = "fail"` → `entry["status"] = "FAIL"` (UNREADABLE path)

**Not changed:** The `_record(pid, "media_qa", "pass" if ...)` call on line 503 uses lowercase intentionally — it records to the gate ledger which has its own convention separate from beat-level QA status.

**Verification:**
```
$ grep -n '"fail"\|"pass"' scripts/qa_media.py | grep -v '#'
503:            _record(pid, "media_qa", "pass" if all_pass else "fail",
# ↑ gate-ledger only — no beat-level lowercase remains

$ python3 -m pytest tests/test_qa_media.py -v
20 passed in 13.21s
```
