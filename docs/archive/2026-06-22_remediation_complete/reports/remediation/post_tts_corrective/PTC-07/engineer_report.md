# PTC-07 Engineer Report — Expand Coverage Slots into Media-Plan Assets

**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Summary

The media-plan compiler (`scripts/compile_media_prompts.py`) now expands each `coverage_plan` slot into its own independently-costed media-plan asset with full lineage traceability.

## Implementation

Added `_expand_coverage_slots(entry, beat_input, constraints, routing)` in `compile_media_prompts.py`:

- When a beat has a `coverage_plan` with >1 slot, each slot becomes a separate media-plan asset
- Each expanded asset carries:
  - `media_plan_asset_id` (stable, derived from slot_id)
  - `source_beat_id` → `production_beat_id` → `coverage_slot_id` → `media_plan_asset_id` lineage
  - Exact `required_start_sec`, `required_end_sec`, `required_duration_sec` from the slot
  - Per-slot cost (1 clip per generated slot; 0 for local_graphic)
  - Unique `output_path`: `assets/media/{segment_id}/{beat_id}_{slot_id}.mp4`
- `local_graphic` slots (by asset_type or model) cost $0
- Total plan cost reflects ALL expanded slots
- **Backward compat:** beats without `coverage_plan` (creative storyboards) produce one asset as before — no lineage fields injected

## Lineage chain

```
source_beat_id (creative) → production_beat_id (= beat_id) → coverage_slot_id → media_plan_asset_id
```

## Acceptance criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Each coverage slot becomes one media-plan asset with full lineage | ✅ |
| 2 | B003/B005/B007 produce 4/4/2 assets respectively | ✅ |
| 3 | Total budget reflects all generated slots | ✅ |
| 4 | Unique output paths per slot | ✅ |
| 5 | Backward compat: creative storyboard → one asset per beat | ✅ |
| 6 | All 8 tests pass | ✅ (9 tests, including backward compat) |

## Test results

```
tests/test_slot_expansion.py: 9 passed
tests/test_compile_media_prompts.py: 14 passed
Full suite: 482 passed
```

## Files modified

- `scripts/compile_media_prompts.py` — added `_expand_coverage_slots()`, integrated into `compile_plan()`
- `tests/test_slot_expansion.py` — new (9 tests)
