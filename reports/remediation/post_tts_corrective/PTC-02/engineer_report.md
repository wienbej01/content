# PTC-02 Engineer Report: Replace Estimated Split Timing with Measured Boundaries

## Status: COMPLETE ✅

## Summary

Word-proportional split timing has been replaced with measured silence-boundary detection. The reconcile engine now requires actual audio evidence to determine split points. When no measured boundary exists, the beat is marked `needs_repair` — no boundary is invented.

## Changes Made

### 1. `scripts/audio_alignment.py` (new)

- `find_legal_split_points(audio_path, beat_start, beat_end, ...)` — detects silence intervals via ffmpeg silencedetect within a beat's time range and returns midpoints as legal split candidates.
- Returns: `{split_points, method, confidence, audio_sha256, silences}`
- Confidence: `'high'` when ≥1 silence found, `'low'` when none.

### 2. `scripts/reconcile_production_storyboard.py` (modified)

- Added import of `find_legal_split_points` from `audio_alignment`.
- Added `_select_split_points()`: greedy algorithm selecting minimum split points that produce all sub-intervals ≤ max_clip.
- Added `_assign_sentences_to_intervals()`: maps sentences to measured intervals using advisory word-proportional midpoints for sentence assignment only.
- **Split logic rewritten:**
  - When `audio_path` is provided: detects silence boundaries → selects valid splits → produces children with `timing_provenance`.
  - When `audio_path` is NOT provided: marks beat as `needs_repair` (dry-runs still work for analysis).
  - When measured boundaries exist but can't produce legal intervals: marks `needs_repair`.
- `_word_proportional_times()` retained as ADVISORY ONLY (docstring updated, output labeled `estimated_split_advisory` in repair beats).

### 3. `tests/test_audio_alignment.py` (new — 7 tests)

All tests use FFmpeg-generated fixtures (sine waves with known silence gaps):

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_silence_boundary_detected` | Split point found near silence gap |
| 2 | `test_boundary_does_not_bisect_speech` | All points fall within silence intervals |
| 3 | `test_low_confidence_when_no_silence` | Continuous tone → confidence='low', empty points |
| 4 | `test_audio_hash_recorded` | audio_sha256 present (64-char hex) |
| 5 | `test_reconcile_uses_measured_split` | Full reconcile with audio → children have timing_provenance |
| 6 | `test_reconcile_no_measured_boundary_marks_repair` | No silence → needs_repair, no invented boundary |
| 7 | `test_word_proportional_not_authoritative` | Split boundary matches measured silence, not word ratio |

### 4. Existing tests updated (5 tests)

Tests that previously assumed word-proportional splitting without audio now assert `needs_repair`:
- `test_reconcile_storyboard.py::test_overlong_hero_split`
- `test_reconcile_storyboard.py::test_narration_preserved_in_split`
- `test_reconcile_storyboard.py::test_graphics_inherited_by_split_children`
- `test_post_tts_e2e.py::TestOverlongHeroSplitToChildren::test_three_sentence_split`
- `test_post_tts_e2e.py::TestRequiredGraphicsAcrossSplitChildren::test_graphics_inherited`
- `test_production_contract.py::TestProductionBeatCarriesCreativeFields::test_split_children_inherit_creative_fields`

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Split boundaries from measured silence detection | ✅ `find_legal_split_points` + `_select_split_points` |
| 2 | Boundaries don't bisect speech (fall in silence) | ✅ Test 2 asserts point ∈ silence interval |
| 3 | Low-confidence/no-silence → needs_repair | ✅ Tests 3, 6 |
| 4 | timing_provenance recorded | ✅ Test 5 checks method, confidence, audio_sha256 |
| 5 | Timing remains contiguous within one frame | ✅ Boundaries list is [start, ...splits, end] — no gaps |
| 6 | All 7 tests pass | ✅ |

## Test Results

```
tests/test_audio_alignment.py: 7 passed
tests/test_reconcile_storyboard.py: 8 passed
Full suite: 442 passed in 100s
```
