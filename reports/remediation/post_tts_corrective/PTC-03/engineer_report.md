# PTC-03 Engineer Report — Deterministic Rerouting for Unsplittable Hero Beats

**Date:** 2026-06-14
**Status:** ✅ COMPLETE — all acceptance criteria met

## Summary

Implemented deterministic rerouting for hero_lipsync beats that exceed the 10s model limit but cannot be split (single-sentence narration or no legal measured silence boundaries). The visual treatment changes from `hero_lipsync` to `hero_cutaway`; narration is preserved byte-for-byte as continuous voiceover.

## Changes Made

### `scripts/reconcile_production_storyboard.py`
- Added `reroute_unsplittable_hero()` function: transforms treatment, sets `audio_policy=strip`, generates b-roll slot coverage plan (each slot ≤ 6s), clears `needs_repair`, records reroute provenance
- `_load_constraints()` now reads `reroute_policy` from constraints.json
- Wired rerouting into two reconcile paths:
  1. Single-sentence beats (no sentence boundary for split)
  2. Multi-sentence beats where no measured silence boundary produces legal sub-intervals

### `docs/channel_universe/constraints.json`
- Added `reroute_policy` block:
  ```json
  "reroute_policy": {
    "unsplittable_hero_target": "hero_cutaway",
    "broll_slot_max_sec": 6.0,
    "allowed_targets": ["hero_cutaway", "broll", "local_graphic"]
  }
  ```

### `tests/test_reroute.py` (new — 7 tests)
All 7 tests pass.

### Updated existing tests
- `tests/test_reconcile_storyboard.py::test_no_word_split` — now asserts reroute behavior
- `tests/test_post_tts_e2e.py::TestNoLegalSilenceSplitGoesToIssues::test_unsplittable_goes_to_issues` — now asserts reroute
- `tests/test_audio_alignment.py::test_reconcile_no_measured_boundary_marks_repair` — now asserts reroute

## Audited Project Results

```
B001     src=B001 dur=13.994s treat=hero_cutaway   repair=False slots=3 reroute=True
B008a    src=B008 dur=8.441s  treat=hero_lipsync   repair=None  slots=1 (split OK)
B008b    src=B008 dur=6.681s  treat=hero_lipsync   repair=None  slots=1 (split OK)
B008c    src=B008 dur=8.767s  treat=hero_lipsync   repair=None  slots=1 (split OK)
B009     src=B009 dur=23.422s treat=hero_cutaway   repair=False slots=4 reroute=True

needs_repair beats: NONE
```

- **B001** (13.994s, single sentence): rerouted → 3 b-roll slots ≤ 6s each
- **B008** (23.889s, 3 sentences): split at measured silence → 3 legal hero clips (8.4s, 6.7s, 8.8s)
- **B009** (23.422s, single sentence): rerouted → 4 b-roll slots ≤ 6s each

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | B001, B008, B009 become model-legal without narration/TTS changes | ✅ |
| 2 | Every rerouted slot within model limit | ✅ (all slots ≤ 6.0s) |
| 3 | No needs_repair beat remains in accepted output | ✅ (0 remaining) |
| 4 | Narration preserved byte-for-byte | ✅ |
| 5 | All 7 tests pass | ✅ |

## Test Results

```
tests/test_reroute.py — 7 passed in 0.31s
Full suite — 449 passed in 100.35s
```

## Design Notes

- B-roll slot boundaries use even division (no word-alignment needed — the visual just changes while continuous narration plays underneath, no lipsync to desync)
- `audio_policy: strip` ensures assembly uses the continuous master VO, not baked lipsync audio
- `model_max_duration_sec: null` removes the validator constraint (irrelevant for b-roll slots)
- Graphics are preserved through reroute
- Reroute provenance is recorded for downstream traceability
