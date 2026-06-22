# TKT-13 Engineer Report — Resume and State Invalidation

## Summary

Replaced the append-only `completed_steps` list in `produce.py` with a DAG-based `step_status` dict, added downstream invalidation on `--from-step`, failure propagation, artifact cleanup, and atomic state writes.

## Changes Made

### `scripts/produce.py`

1. **`_save_state`** — Atomic write via `.state.json.tmp` + rename.

2. **`_load_state`** — Backward-compat migration: old `completed_steps` list → `step_status` dict (deduplicates on load).

3. **`STEP_ARTIFACTS` map** — Maps step names to artifact files that should be deleted on invalidation. TTS audio and generated media are explicitly excluded.

4. **`invalidate_from_step(state, step_name, project_dir)`** — New function. Sets step X and all downstream steps to `status: None`. Deletes stale JSON/CSV artifacts. Does NOT delete expensive media (TTS, clips).

5. **`run_pipeline`** — Rewired to:
   - Use `step_status` dict (no more `completed_steps` list)
   - Call `invalidate_from_step` when `--from-step` is provided
   - Propagate failure: if any step is `"failed"`, downstream `"done"` steps are reset to pending
   - Record `"failed"` status with error message on exception
   - No duplicates possible (dict keyed by step name)

## Test Results

```
tests/test_produce_resume.py — 11 passed in 0.03s
Full suite — 313 passed, 4 failed (pre-existing test_review.py failures)
```

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `--from-step tts` invalidates all downstream | ✅ Verified in test |
| Failed rerun doesn't leave pass on downstream | ✅ Verified in test |
| Old state format loads correctly | ✅ Verified in test |
| All new tests pass | ✅ 11/11 |
| No existing behavior broken | ✅ 313 pass, 4 pre-existing failures |
| TTS audio never deleted | ✅ Verified in test |
| Atomic state writes | ✅ Verified in test |
| No paid API calls | ✅ All tests use fixtures only |

## Files Modified/Created

- `scripts/produce.py` — Core changes
- `tests/test_produce_resume.py` — 11 tests (new)
- `reports/remediation/TKT-13/engineer_report.md` — This report
