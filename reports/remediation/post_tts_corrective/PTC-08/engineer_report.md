# PTC-08 Engineer Report — Orchestrator Ordering & Strict Adoption

**Date:** 2026-06-14  
**Status:** ✅ Complete

## Changes Made

### 1. Removed creative-storyboard fallback (fail-closed)

`scripts/produce.py` `step_compile_media_plan` now raises `RuntimeError` if `production_storyboard.json` does not exist. The previous behavior (WARNING + fallback to `storyboard.json`) is removed.

### 2. Fixed STEPS ordering: render_graphics before build_manifest

Swapped positions in the STEPS list:
- Before: `...reconcile_duration, build_manifest, render_graphics, assemble...`
- After: `...reconcile_duration, render_graphics, build_manifest, assemble...`

This ensures graphics are rendered before the strict manifest is built.

### 3. Production storyboard review report verified

`step_production_storyboard` (PTC-04) already:
- Runs `review_production_storyboard.py --output review_report.json`
- Checks `blocks_production` field and raises RuntimeError if true

No changes needed — confirmed correct.

### 4. State invalidation updated

Added `review_report.json` to `STEP_ARTIFACTS["production_storyboard"]`:
```python
"production_storyboard": ["production_storyboard.json", "review_report.json"],
```

### 5. Existing tests updated

- `tests/test_downstream_adoption.py`: Replaced `test_compile_falls_back_with_warning` with `test_compile_requires_production_storyboard_strict` (expects RuntimeError)
- `tests/test_produce_resume.py`: Fixed expected invalidation order to reflect render_graphics before build_manifest
- `tests/test_produce_fail_closed.py`: Updated compile tests to use `production_storyboard.json` instead of `storyboard.json`

## New Tests

`tests/test_orchestrator_ordering.py` — 6 tests:

| Test | Validates |
|------|-----------|
| `test_compile_requires_production_storyboard` | RuntimeError when production_storyboard.json missing |
| `test_no_creative_fallback` | No WARNING/fallback code path in source |
| `test_render_graphics_before_manifest` | STEPS ordering |
| `test_production_storyboard_before_compile` | STEPS ordering |
| `test_step_order_full` | Full effective order of 11 key steps |
| `test_review_report_in_step_artifacts` | Artifact map completeness |

## Validation

```
tests/test_orchestrator_ordering.py: 6 passed
tests/test_produce_resume.py + tests/test_downstream_adoption.py: 29 passed
Full suite: 488 passed in 100s
```

## Effective STEPS Order (final)

```
0  research
1  script_create
2  script_review_loop
3  storyboard_create
4  storyboard_review_loop
5  tts
6  build_timing_map
7  production_storyboard
8  compliance_check
9  compile_media_plan
10 slice_lipsync
11 gate_a_budget
12 generate_media
13 qa_media
14 reconcile_duration
15 render_graphics      ← moved before build_manifest
16 build_manifest
17 assemble
18 qa_final
19 build_quality_report
20 gate_b_review
```
