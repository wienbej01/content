# UCI-01 Validation Report — Manifest Keyed by clip_id

**Date:** 2026-06-15  
**Validator:** kiro-cli (read-only)  
**Verdict:** PASS

## Test Results

### Targeted suite: `tests/test_uci01_manifest_clipid.py` + `tests/test_manifest_builder.py`

```
17 passed in 0.86s
```

| Test | Validates |
|------|-----------|
| `TestSlotExpansion::test_slot_expanded_plan_builds_distinct_segments` | B003×3 → 3 segments, unique clip_ids |
| `TestSplitChildren::test_split_children_build_distinct_segments` | B011a/B011b → 2 segments, correct clip_ids |
| `TestDuplicateClipId::test_duplicate_clip_id_fails` | Duplicate clip_id → hard error |
| `TestSegmentFields::test_segment_carries_clip_id_and_source` | clip_id + source_beat_id fields present |
| `TestPerClipTiming::test_per_clip_timing_from_plan` | Uses required_start/end_sec, ignores timing_map parent |
| `TestSegmentOrdering::test_segments_ordered_by_start` | Reverse-ordered input → sorted output |
| `TestManifestBuilder::test_duplicate_clip_id_fails` | duplicate clip_id enforcement |
| `TestBSS04Hardening::*` (4 tests) | Music, allow-missing, format routing |

### Full suite

```
609 passed in 132.86s
```

No regressions. All existing manifest, assembly, QA, budget, gate, and storyboard tests pass.

## Acceptance Criteria Verified

1. ✅ No duplicate-beat_id check — removed, confirmed by grep.
2. ✅ Duplicate-clip_id check added and exercised.
3. ✅ Slot-expanded (B003×3) and split (B011a/B011b) plans build distinct segments.
4. ✅ Per-clip timing from `required_start_sec`/`required_end_sec`, not `beat_timing_map`.
5. ✅ Segments carry `clip_id` + `source_beat_id`, ordered by `timing_in`.
6. ✅ Golden-truth gate preserved.
7. ✅ 609/609 tests green — zero regression.
