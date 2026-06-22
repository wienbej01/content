# UCI-06 Engineer Report — Phantom Sub-Frame Beat Guard

**Status:** ✅ Complete  
**Date:** 2026-06-15  
**Ticket:** UCI-06 (P2 from forensic audit)

## Problem

Beats B003b/B005c received ~0.01s durations from TTS timing — less than one video frame (1/24s = 0.0417s). Sub-frame clips are not renderable and pollute the timeline if emitted as standalone clips.

## Fix Applied

### 1. `docs/channel_universe/constraints.json`
Added `min_beat_duration_sec: 0.1` to `lipsync_render_rules`. This is the single source of truth; the reconciler reads it at runtime.

### 2. `scripts/reconcile_production_storyboard.py`
- Added `MIN_BEAT_SEC_DEFAULT = 0.1` constant (fallback if constraints.json missing).
- `_load_constraints()` now reads `min_beat_duration_sec` from constraints.json.
- New function `_merge_phantom_beats(beats, min_beat_sec)`:
  - Any beat with `audio_duration_sec < min_beat_sec` is merged into its **previous** neighbor (or next, if it's the first beat).
  - Narration text is appended to the target beat.
  - Timing is extended to cover the phantom's interval.
  - Coverage plan is rebuilt for the target.
  - Each merge emits a `PHANTOM_BEAT: {id} {dur}s merged into {target}` log entry in the issues list.
- Called after beat assembly, before building the final production storyboard dict.

### 3. `tests/conftest_constants.py`
Exposed `MIN_BEAT_SEC` from constraints and added `min_beat_sec` to `TEST_CONSTRAINTS`.

### 4. `tests/test_uci06_phantom_beat.py` (5 tests)
| Test | Validates |
|------|-----------|
| `test_phantom_beat_merged_into_previous` | 0.01s beat after normal → merged into previous |
| `test_phantom_first_beat_merged_into_next` | 0.01s as first beat → merged into next |
| `test_normal_beat_not_merged` | 5s beat untouched |
| `test_phantom_logged` | PHANTOM_BEAT log entry contains both beat IDs |
| `test_no_subframe_clip_emitted` | No beat in output has duration < MIN_BEAT_SEC |

## Validation

```
tests/test_uci06_phantom_beat.py: 5 passed
tests/test_reconcile_storyboard.py: 8 passed
Full suite: 619 passed, 1 failed (pre-existing clip_db e2e issue, unrelated)
```

## Acceptance Criteria Checklist

- [x] Sub-frame (<0.1s) beats merged into neighbor, never emitted standalone
- [x] Merge preserves narration text (appended)
- [x] Merge is logged with beat IDs (not silent)
- [x] Normal beats untouched
- [x] After reconciliation no clip < MIN_BEAT_SEC
- [x] All new tests pass; full suite green (pre-existing failure only)
