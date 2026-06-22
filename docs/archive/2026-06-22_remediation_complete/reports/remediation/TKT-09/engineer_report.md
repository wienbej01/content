# TKT-09 Engineer Report — Assembly Hardening

## Summary

Implemented all 4 changes to `scripts/assemble.py` and added 3 new tests to `tests/test_assemble.py`.

## Changes Made

### Change 1: Remove tpad for generated-video beats

In the `continuous_voiceover` path, the unconditional `tpad=stop_mode=clone:stop_duration=1` that silently extended all clips with 1s of frozen frames is now conditional:

- **Generated-video beats** (`audio_policy` in `["keep_lipsync", "strip"]` or any `.mp4/.mov/.mkv/.webm` file): NO tpad. If the clip is more than 0.25s shorter than the required beat duration (from timing map), assembly raises `RuntimeError` with the beat ID and shortfall.
- **Still images** (`.png/.jpg/.jpeg/.webp`): tpad still permitted (hold is intentional for stills).

### Change 2: Pre-concat visual bed duration check

After concatenating all segments into `cont_visual.mp4` and before overlaying audio, the visual bed duration is probed and compared to `total_nar_dur`. If `abs(visual_bed_dur - total_nar_dur) > 0.25s`, assembly raises `RuntimeError` with measured vs expected durations. No mux occurs.

### Change 3: Post-mux stream-integrity gate

After the mux produces `cont_joined.mp4`, its duration is probed. If `abs(joined_vid_dur - total_nar_dur) > 0.25s`, the broken output is deleted and `RuntimeError` is raised.

### Change 4: No `-shortest` in continuous voiceover path

Verified: the only `-shortest` in `assemble.py` is in the lower-third overlay path (segment-by-segment mode) where it correctly terminates a `-loop 1` overlay image. There is no `-shortest` in the continuous voiceover path. No change needed.

## Tests Added

| Test | Validates |
|------|-----------|
| `test_short_visual_long_audio_fails_before_mux` | 1 beat needs 10s, clip is 3s → RuntimeError before final file |
| `test_visual_bed_mismatch_fails` | 2 beats need 10s each, clips are 2s each → RuntimeError before mux |
| `test_valid_continuous_fixture_assembles` | Clips match durations → assembles with abs(video-audio) ≤ 0.25s |

All fixtures generated with FFmpeg (no paid APIs). Tiny 320x180 clips for speed.

## Verification Output

### Assembly against production manifest
```
$ python3 scripts/assemble.py Videos/Projects/using_ai_to_help_memory_retention_short/manifest.json --formats 16x9 2>&1; echo "Exit: $?"
ERROR: Beat B001 clip too short: clip=7.082s, required=13.994s (shortfall=6.912s). Regenerate a longer clip or split into multiple shots.
Exit: 2
```

Assembly correctly fails **before mux** with a named beat deficit. No new final file produced.

### test_assemble.py (all pass)
```
tests/test_assemble.py::test_outputs_exist PASSED                        [  5%]
tests/test_assemble.py::test_duration_sane PASSED                        [ 11%]
tests/test_assemble.py::test_resolution PASSED                           [ 17%]
tests/test_assemble.py::test_audio_present PASSED                        [ 23%]
tests/test_assemble.py::test_volume_range PASSED                         [ 29%]
tests/test_assemble.py::test_no_long_silence PASSED                      [ 35%]
tests/test_assemble.py::test_pacing_aligned PASSED                       [ 41%]
tests/test_assemble.py::test_lipsync_span_uses_baked_audio PASSED        [ 47%]
tests/test_assemble.py::test_no_narration_overlay_on_lipsync_span PASSED [ 52%]
tests/test_assemble.py::test_voiceover_spans_still_overlay_narration PASSED [ 58%]
tests/test_assemble.py::test_trim_to_speech_length PASSED                [ 64%]
tests/test_assemble.py::test_provenance_mismatch_fails_assembly PASSED   [ 70%]
tests/test_assemble.py::test_segment_timing_within_quarter_second PASSED [ 76%]
tests/test_assemble.py::test_continuous_mode_accepts_lipsync_as_muted PASSED [ 82%]
tests/test_assemble.py::test_short_visual_long_audio_fails_before_mux PASSED [ 88%]
tests/test_assemble.py::test_visual_bed_mismatch_fails PASSED            [ 94%]
tests/test_assemble.py::test_valid_continuous_fixture_assembles PASSED   [100%]

============================= 17 passed in 19.47s ==============================
```

### Full test suite
```
4 failed, 296 passed in 86.28s (0:01:26)
```

The 4 failures are pre-existing in `tests/test_review.py` (unrelated `review_loop()` API change). Zero regressions from TKT-09.

## Beat Deficits in Production Manifest

The real manifest has these shortfalls (all generated-video beats are 10s or less but need much more):

| Beat | Clip Duration | Required | Shortfall |
|------|--------------|----------|-----------|
| B001 | 7.08s | 13.99s | 6.91s |
| B005 | ~10s | 21.60s | ~11.6s |
| B007 | ~10s | 11.09s | ~1.1s |
| B008 | ~10s | 23.89s | ~13.9s |
| B009 | ~10s | 23.42s | ~13.4s |
| B010 | ~10s | 12.66s | ~2.7s |

These clips were rendered to Seedance's 10s max — the timing map requires much longer spans. Resolution: either split these beats into multiple shots or re-render to video models supporting longer durations.

## Acceptance Criteria Status

1. ✅ Production manifest fails before mux with named beat deficits (exit code 2)
2. ✅ Valid fixture assembles with abs(video-audio) ≤ 0.25s
3. ✅ All 17 assembly tests pass; no existing tests regressed
