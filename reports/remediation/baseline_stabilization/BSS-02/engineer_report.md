# BSS-02 — Engineer Report

**Ticket:** Make Storyboard and Media-Plan Compilation Fail Closed  
**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Changes Made

### `scripts/produce.py`

**`step_storyboard_create()`** — reordered to check errors before writing:
- Moved `errors`/`warnings` extraction before any file write
- If errors nonempty: writes `storyboard_errors.json` (diagnostic), raises `RuntimeError`
- If no errors: writes `storyboard.json` as before
- Existing `storyboard.json` is never overwritten on failure

**`step_compile_media_plan()`** — same pattern:
- If `compile_plan()` returns errors: writes `media_plan_errors.json`, raises `RuntimeError`
- If no errors: writes `media_plan.json` as before

## Tests Added

`tests/test_produce_fail_closed.py` — 5 tests:

| Test | Verifies |
|------|----------|
| `test_storyboard_errors_block_step` | RuntimeError raised, no storyboard.json, diagnostic written |
| `test_storyboard_valid_writes_json` | Happy path writes storyboard.json |
| `test_existing_storyboard_not_overwritten_on_error` | Pre-existing valid artifact preserved |
| `test_compile_errors_block_step` | RuntimeError raised, no media_plan.json, diagnostic written |
| `test_compile_valid_writes_json` | Happy path writes media_plan.json |

## Validation

```
$ python3 -m pytest tests/test_produce_fail_closed.py -v
5 passed in 0.02s

$ python3 -m pytest -q
362 passed in 98.51s
```

## Acceptance Criteria

1. ✅ Nonempty storyboard errors raise RuntimeError before writing storyboard.json
2. ✅ Nonempty compile errors raise RuntimeError before writing media_plan.json
3. ✅ Diagnostic artifacts (`storyboard_errors.json`, `media_plan_errors.json`) written on failure
4. ✅ Existing valid artifacts not overwritten on failure
5. ✅ All 5 new tests pass; full suite (362) passes
