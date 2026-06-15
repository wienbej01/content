# UCI-01 Engineer Report — clip_id is the manifest key

**Date:** 2026-06-15  
**Status:** ✅ Complete  
**Engineer:** kiro-agent

---

## Summary

`build_manifest.py` now keys on `clip_id` (the unique physical clip identifier) instead of `beat_id` (a non-unique logical grouping). Slot-expanded plans (B003×3) and split-beat plans (B011a/B011b) now build manifests correctly.

## Changes

### `scripts/build_manifest.py`

1. **Removed** the duplicate-`beat_id` check (false invariant — beat_id is non-unique after slot expansion).
2. **Added** duplicate-`clip_id` check (correct uniqueness invariant).
3. **Per-clip timing**: segments use `required_start_sec`/`required_end_sec` from the plan row, not the parent beat_timing_map. Fallback to timing_map only for legacy plans without per-clip timing.
4. **Segment schema**: each segment now carries `clip_id`, `id` (= clip_id for backward compat), `source_beat_id`, `segment_id`, `media`, `media_sha256`, and per-clip timing.
5. **Legacy fallback**: if a plan row has no `clip_id`, falls back to `beat_id` with a warning.
6. **Ordering**: segments sorted by `timing_in` (required_start_sec) for timeline order.
7. **Preserved**: clip_db golden-truth gate (assert_all_valid), music handling, overlay handling.

### `tests/test_manifest_builder.py`

- Renamed `test_duplicate_beat_fails` → `test_duplicate_clip_id_fails` with updated fixture using `clip_id` field.
- Updated `test_valid_plan_produces_manifest` assertions to verify new fields (`clip_id`, `source_beat_id`).

### `tests/test_uci01_manifest_clipid.py` (new)

| Test | Validates |
|------|-----------|
| `test_slot_expanded_plan_builds_distinct_segments` | B003×3 slots → 3 segments, no duplicate error |
| `test_split_children_build_distinct_segments` | B011a + B011b → 2 segments |
| `test_duplicate_clip_id_fails` | Same clip_id on two rows → error |
| `test_segment_carries_clip_id_and_source` | Each segment has clip_id + source_beat_id |
| `test_per_clip_timing_from_plan` | Timing from required_start/end_sec, not parent beat_timing_map |
| `test_segments_ordered_by_start` | Segments sorted by required_start_sec |

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Slot-expanded + split plans build manifests with one segment per clip, no duplicate-beat_id error | ✅ |
| 2 | clip_id is the uniqueness key; duplicate clip_id fails | ✅ |
| 3 | Per-clip timing from plan row, not stale beat_timing_map | ✅ |
| 4 | Segments carry clip_id + source_beat_id, ordered by start | ✅ |
| 5 | Golden-truth gate preserved | ✅ |
| 6 | All tests pass; full suite green | ✅ |

## Test Results

```
tests/test_uci01_manifest_clipid.py — 6 passed
tests/test_manifest_builder.py — 11 passed
Full suite — 609 passed in 145.59s
```

## Files Modified

- `scripts/build_manifest.py`
- `tests/test_manifest_builder.py`

## Files Created

- `tests/test_uci01_manifest_clipid.py`
- `reports/remediation/uci/UCI-01/engineer_report.md`
