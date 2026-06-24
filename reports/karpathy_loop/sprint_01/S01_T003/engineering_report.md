# Engineering Report: S01_T003 Lipsync Eval Harness

## Changes made

### 1. `scripts/evals/eval_lipsync.py` (NEW)
Lipsync eval entrypoint with fallback mouth-motion proxy:
- **Method**: `mouth_motion_proxy` — cross-correlates audio envelope vs visual frame-difference signal
- **Audio**: Extracts via ffmpeg, computes RMS energy envelope (50ms windows)
- **Video**: Extracts low-res grayscale frames (160x90) via ffmpeg raw pipe, computes frame-diff signal
- **Correlation**: numpy cross-correlation to find timing offset
- **Output**: Full JSON with offset_ms, confidence, thresholds, status
- **Missing video**: Returns `blocked` status, not crash

### 2. `tests/test_eval_lipsync.py` (NEW)
12 tests across 5 test classes:
| Test | Verifies |
|------|----------|
| test_eval_outputs_valid_json | Eval writes JSON for existing MP4 |
| test_eval_returns_expected_structure | All required fields present |
| test_eval_face_track_false_without_cv | face_track_found=False |
| test_missing_video_returns_blocked | Blocked JSON, not traceback |
| test_cli_missing_video_returns_nonzero | CLI exit code >0 |
| test_extract_audio_envelope_from_fixture | Audio signal extracted |
| test_extract_audio_from_nonexistent_video | Missing → None |
| test_compute_visual_activity_from_fixture | Visual signal extracted |
| test_compute_visual_activity_nonexistent | Missing → None |
| test_correlation_with_synthetic_signals | Correlation returns data |
| test_correlation_offset_detection | Shifted signals detected |
| test_cli_with_fixture | Full CLI end-to-end |

## Bad fixture result
```
Lipsync eval for prod_2f9bb58c0508465fb51ac6b4578bba92
  Method: mouth_motion_proxy
  Status: fail
  Offset: -4950.00ms
  Confidence: 0.1369
```

The large offset and low confidence are expected: the video has talking head,
phone b-roll, and static graphic segments. Visual activity doesn't correlate
with audio envelope across mixed-content video. Without face tracking, this
is diagnostic-only.

## Files changed
```
A scripts/evals/eval_lipsync.py   (280 lines)
A tests/test_eval_lipsync.py      (175 lines)
```

## Test results
```
12 passed in 4.30s
```

## Render lock verification
YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1
No provider render calls. ffmpeg usage: local-only audio/frame extraction.
