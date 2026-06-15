# PTC-05 Engineer Report — Correct Split Narration and Graphics Validation

**Date:** 2026-06-14
**Status:** ✅ Complete

## Defects Fixed

### 1. Narration Mutation False Positives on Split Beats

**Root cause:** The narration check compared each production child beat's `narration_text` against the full creative parent's `narration_text`. Split children only contain a fragment, so every split child was flagged as a mutation.

**Fix:** Group production beats by `source_beat_id`, sort by `split_index`, concatenate their `narration_text`, then compare the concatenated word sequence against the creative parent. Canonical comparison normalizes whitespace (splits on whitespace, compares word lists).

### 2. Graphics `required: false` Treated as Required

**Root cause:** The graphics check flagged any production beat whose creative source had a `graphic` object, regardless of the `required` field's value.

**Fix:** Only flag missing graphics when the creative graphic has `required: true` (or no `required` field, defaulting to required). Check is now at the source-group level: at least one child of the source must carry the graphic.

## Files Changed

- `scripts/review_production_storyboard.py` — Rewrote narration and graphics validation logic
- `tests/test_split_narration_graphics.py` — New, 8 tests

## Validation

```
$ python3 -m pytest tests/test_split_narration_graphics.py tests/test_production_storyboard_review.py -v
14 passed

$ python3 -m pytest -q
463 passed in 100.20s
```

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Valid split children pass narration immutability (group-level concat) | ✅ |
| 2 | Missing/mutated/reordered narration fails | ✅ |
| 3 | required:false graphics not flagged | ✅ |
| 4 | Required graphics that survive split pass; lost ones fail | ✅ |
| 5 | All 8 tests pass | ✅ |
| 6 | No false missing-graphic or false narration-mutation errors | ✅ |
