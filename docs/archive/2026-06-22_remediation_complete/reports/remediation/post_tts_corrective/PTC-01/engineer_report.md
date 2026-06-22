# PTC-01 Engineer Report — Production Storyboard Superset Contract

## Status: COMPLETE ✅

## Summary

Fixed `compile_plan(production_storyboard, ...)` KeyError by making the production storyboard a superset contract that carries all creative fields through reconciliation.

## Root Cause

`compile_beat()` in `compile_media_prompts.py` accesses `beat["shot_type"]`, `beat["asset_type"]`, and `beat.get("segment_id")` directly. The reconcile engine was constructing production beats from scratch with only timing/treatment/coverage fields, discarding the creative storyboard's downstream-required fields.

## Changes Made

### 1. `scripts/reconcile_production_storyboard.py`
- Added `_CREATIVE_CARRY_FIELDS` tuple defining all fields to propagate (shot_type, segment_id, visual_brief, subject, action, camera, setting, continuity_anchor, asset_type, model_tier, lipsync_required, reference_images, prompt_class, crop_safety, etc.)
- Added `_base_from_creative(beat)` helper that copies all carry fields from the creative beat
- Added `_normalize_graphics(beat)` adapter that converts singular `graphic` dict to canonical `graphics` list (all graphics included, `required` field respected by consumers)
- All production beat construction paths (normal, split children, needs_repair) now start from `_base_from_creative(beat)` then overlay reconciled fields

### 2. `schemas/production_storyboard.schema.json`
- Added `shot_type` and `segment_id` as required properties on production_beat
- Added all creative carry-through fields as documented properties (visual_brief, subject, action, camera, setting, continuity_anchor, asset_type, etc.)
- Added `graphic_entry` definition with required/layout/text/timing + display_slot/display_interval
- Added `coverage_slot` pattern property (B\d{3}-s\d+)

### 3. `scripts/production_storyboard.py` (validator)
- Added invariant checks: beat must have non-empty `shot_type` and `segment_id`

### 4. Test helpers updated for new contract
- `tests/test_reconcile_storyboard.py` — added `segment_id` to `_beat` helper
- `tests/test_production_storyboard_schema.py` — added `shot_type` and `segment_id` to `_make_beat` helper
- `tests/test_post_tts_e2e.py` — added `segment_id` to `_beat` helper
- `tests/test_production_storyboard_review.py` — added `shot_type` and `segment_id` to `_beat` helper

### 5. New test file: `tests/test_production_contract.py`
Six tests validating the contract:
1. `test_production_beat_has_shot_type` ✅
2. `test_production_beat_has_segment_id` ✅
3. `test_split_children_inherit_creative_fields` ✅
4. `test_canonical_graphics_list` ✅
5. `test_compile_plan_consumes_production_storyboard` ✅ (serialized JSON roundtrip)
6. `test_missing_shot_type_fails_validation` ✅

## Verification

```
tests/test_production_contract.py: 6 passed
tests/test_reconcile_storyboard.py: 8 passed
tests/test_production_storyboard_schema.py: 10 passed
Full suite: 435 passed, 0 failed
```

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | compile_plan runs without KeyError | ✅ verified via serialized JSON roundtrip test |
| 2 | Production beats carry shot_type, segment_id, all compiler fields | ✅ |
| 3 | Canonical graphics list; required:false respected | ✅ |
| 4 | Schema updated, validator enforces shot_type/segment_id | ✅ |
| 5 | All 6 new tests pass | ✅ |
| 6 | No regressions in full suite (435 passed) | ✅ |
