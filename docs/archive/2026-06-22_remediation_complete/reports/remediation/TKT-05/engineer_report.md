# TKT-05 Engineer Report — Seedance Min/Max Duration Without Desync

## Summary

Removed the silent clamp in `slice_continuous_lipsync.py` that truncated over-max hero speech spans to 10s (losing up to 13.9s of spoken audio). Replaced with a hard `ValueError` rejection. Added early-catch in `compile_media_prompts.py` so over-max hero beats are rejected at compile time before expensive slice generation.

## Changes

### `scripts/slice_continuous_lipsync.py`
- Removed hardcoded `LIPSYNC_MIN = 4` / `LIPSYNC_MAX = 10` constants.
- Added `_load_lipsync_limits()` that reads `constraints.json → lipsync_render_rules.{min,max}_clip_duration_sec`.
- Removed `padded = min(padded, LIPSYNC_MAX)` (the silent clamp on line 67).
- Added `ValueError` with actionable message naming beat_id, actual span, and max when `padded > LIPSYNC_MAX`.
- Added `padded_from_sec` / `padded_to_sec` to `audio_slice` provenance for sub-minimum beats that get padded.
- Bumped `producer_version` to `"1.2"`.

### `scripts/compile_media_prompts.py`
- Added early rejection in `compile_beat()`: if a `hero_lipsync` beat's `est_duration_sec` exceeds `max_clip_duration_sec`, it is rejected with an actionable error at compile time.

### `tests/test_compile_media_prompts.py`
- Updated `test_compiles_clean` filter to also exclude the new early-catch error message (existing B047 at 10.4s now correctly caught earlier).

### `tests/test_audio_slicing.py` (new)
5 tests covering all acceptance criteria.

## Acceptance Criteria Verification

```
$ grep -n 'min.*LIPSYNC_MAX\|min.*max_clip\|clamp' scripts/slice_continuous_lipsync.py
(no output — no clamp logic exists)

$ python3 -m pytest tests/test_audio_slicing.py -v
5 passed

$ python3 -m pytest -q 2>&1 | tail -5
4 failed, 323 passed  (failures are pre-existing test_review.py issues)
```

## Files Modified
- `scripts/slice_continuous_lipsync.py`
- `scripts/compile_media_prompts.py`
- `tests/test_compile_media_prompts.py`
- `tests/test_audio_slicing.py` (new)
- `reports/remediation/TKT-05/engineer_report.md` (this file)
