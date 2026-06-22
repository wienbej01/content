# PST-06 Implementation Report — Downstream Production Storyboard Adoption

**Date:** 2026-06-14
**Status:** ✅ Complete

## Changes Made

### 1. `scripts/produce.py` — STEPS list updated

Added `"production_storyboard"` between `build_timing_map` and `compliance_check`:

```
tts → build_timing_map → production_storyboard → compliance_check → compile_media_plan
```

### 2. `scripts/produce.py` — `step_production_storyboard()` added

Calls `reconcile_production_storyboard.py` (builds production beats from creative + timing map), then `review_production_storyboard.py` (validates reconciliation). Hard-fails on non-zero exit from either subprocess.

### 3. `scripts/produce.py` — `step_compile_media_plan()` prefers production storyboard

Logic: if `production_storyboard.json` exists in the project dir, use it. Otherwise fall back to `storyboard.json` with a printed `⚠ WARNING`.

### 4. `scripts/compile_media_prompts.py` — `source_beat_id` traceability check

After building the plan beat list, if the storyboard has `reconciled_from` or `production` markers, every beat must have `source_beat_id`. Missing entries are added to compile errors.

### 5. `STEP_ARTIFACTS` updated

Added `"production_storyboard": ["production_storyboard.json"]` so invalidation cleans correctly.

## Tests Added

File: `tests/test_downstream_adoption.py` (4 tests)

| Test | Verifies |
|------|----------|
| `test_compile_uses_production_storyboard_when_present` | compile reads production_storyboard.json when both exist |
| `test_compile_falls_back_with_warning` | falls back to creative with WARNING when production missing |
| `test_production_storyboard_step_in_steps_list` | step positioned between build_timing_map and compliance_check |
| `test_production_storyboard_before_compile` | full ordering: tts < build_timing_map < production_storyboard < compliance_check < compile_media_plan |

## Verification

```
$ python3 -m pytest tests/test_downstream_adoption.py -v
4 passed in 0.03s

$ python3 -m pytest -q
416 passed in 99.15s
```

## Acceptance Criteria

1. ✅ `"production_storyboard"` step in STEPS between `build_timing_map` and `compliance_check`
2. ✅ `compile_media_plan` uses production_storyboard.json when present
3. ✅ Falling back to creative storyboard prints a WARNING
4. ✅ All 4 tests pass
