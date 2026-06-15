# PTC-06 Engineer Report — Enforce Exact Coverage Slot Geometry

**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Defect

Coverage validation summed `required_duration_sec` across slots without proving boundary continuity. Slots with correct total duration but shifted/gapped/overlapping boundaries passed validation incorrectly.

## Changes

### `scripts/production_storyboard.py`

- Added constants: `LEGAL_ASSET_TYPES`, `LEGAL_MODELS`, `LEGAL_AUDIO_POLICIES`
- Added function `validate_coverage_geometry(beat) -> list[str]` implementing ordered-boundary geometry checks:
  1. First slot `required_start_sec` == beat `audio_start_sec` (±1 frame)
  2. Last slot `required_end_sec` == beat `audio_end_sec` (±1 frame)
  3. Consecutive slots: `slot[i].required_end_sec == slot[i+1].required_start_sec` (±1 frame)
  4. Each slot: `required_duration_sec == required_end_sec - required_start_sec` (±0.001s)
  5. Unique slot IDs (checks both `slot_id` and `coverage_slot` fields)
  6. Legal `asset_type`, `model`, `audio_policy` values
  7. Every slot must have a visual `asset_type` (no audio-only)
  8. Reversed boundaries (end < start) caught explicitly
- Replaced old Invariant 9 (duration-sum check) with `validate_coverage_geometry()` call

### `tests/test_coverage_geometry.py` (new, 10 tests)

| # | Test | Validates |
|---|------|-----------|
| 1 | test_contiguous_slots_pass | [0-5, 5-10] for 10s beat passes |
| 2 | test_gap_fails | 1s gap detected |
| 3 | test_overlap_fails | 1s overlap detected |
| 4 | test_first_slot_must_start_at_beat_start | Start misalignment caught |
| 5 | test_last_slot_must_end_at_beat_end | End misalignment caught |
| 6 | test_equal_duration_but_shifted_fails | **Key bug**: sum=10 but boundaries shifted |
| 7 | test_duration_mismatch_fails | Internal duration inconsistency |
| 8 | test_duplicate_slot_id_fails | Duplicate IDs rejected |
| 9 | test_reversed_boundaries_fails | end < start rejected |
| 10 | test_audio_only_slot_fails | Missing visual asset_type rejected |

### `tests/test_production_storyboard_schema.py`

- Updated `test_incomplete_coverage_rejected` assertion to match new error format (same defect still caught via "last slot" boundary check)

## Verification

```
$ python3 -m pytest tests/test_coverage_geometry.py tests/test_production_storyboard_schema.py -v
20 passed in 0.02s

$ python3 -m pytest -q
473 passed in 100.27s
```

## Acceptance Criteria Met

1. ✅ Coverage validated by ordered boundaries, not duration sums
2. ✅ Gaps, overlaps, shifted-but-equal-sum, duplicates, reversed all fail
3. ✅ Contiguous complete slots pass
4. ✅ All 10 new tests pass
5. ✅ No regressions (473 tests pass)
