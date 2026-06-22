# TKT-02 Engineer Report — Final MP4 Stream-Integrity Gate

## Files changed

| File | Change |
|------|--------|
| `scripts/qa_final.py` | Rewrote `_video_duration()` to probe v:0 stream duration; added `_container_duration()`, `_video_frame_count()`; added CONTAINER_MISMATCH, TERMINAL_FREEZE, NO_FRAMES checks; tightened default tolerance to 0.25s; always writes report beside video |
| `scripts/produce.py` | Added `step_qa_final` function + inserted `"qa_final"` into STEPS list (position 16/17) + added to STEP_FNS |
| `docs/channel_universe/constraints.json` | Changed `length_tol_sec` and `tail_tol_sec` from 0.5 to 0.25 |
| `tests/test_qa_final.py` | New — 5 tests covering valid pass, short-video/long-audio, no-frames, container mismatch, and the actual defective MP4 |

## Behavior added

1. **`_video_duration(path)`** now probes `v:0` stream duration via `ffprobe -select_streams v:0 -show_entries stream=duration`. Falls back to `nb_frames/fps` if stream duration tag is absent.
2. **`_container_duration(path)`** — new helper probing format-level duration.
3. **`_video_frame_count(path)`** — probes `nb_frames` for v:0.
4. **`run_final_qa()`** now checks:
   - `NO_FRAMES`: frame count is 0 or missing → fail
   - `CONTAINER_MISMATCH`: container_dur - video_dur > 0.25s → fail
   - `LENGTH_MISMATCH`: |video_dur - audio_dur| > 0.25s → fail
   - `TERMINAL_FREEZE`: audio outlasts video by >0.25s → fail (the dominant failure mode)
   - `FROZEN_TAIL`: video outlasts audio by >0.25s → fail
5. **`main()`** always writes `final_qa_report.json` (beside video by default, or explicit `--output`).
6. **`produce.py`** now runs `qa_final` as step 16 (between `assemble` at 15 and `gate_b_review` at 17). If final QA fails, the pipeline halts with an actionable error.

## Tests added

| Test | Validates |
|------|-----------|
| `test_valid_fixture_passes` | Valid 5s video+audio → exit 0, status pass |
| `test_short_video_long_audio_fails` | 3s video / 8s audio → exit 1, TERMINAL_FREEZE/LENGTH_MISMATCH, ~5s mismatch |
| `test_no_frames_fails` | Audio-only file → exit 1, NO_FRAMES |
| `test_container_exceeds_video_fails` | Container > video → exit 1, CONTAINER_MISMATCH |
| `test_existing_defective_mp4_fails` | Actual defective MP4 → video≈83.33s, audio≈146.6s, mismatch≈63.3s |

## Commands executed

### Test run (`python3 -m pytest tests/test_qa_final.py -v`)
```
============================= test session starts ==============================
tests/test_qa_final.py::test_valid_fixture_passes PASSED                 [ 20%]
tests/test_qa_final.py::test_short_video_long_audio_fails PASSED         [ 40%]
tests/test_qa_final.py::test_no_frames_fails PASSED                      [ 60%]
tests/test_qa_final.py::test_container_exceeds_video_fails PASSED        [ 80%]
tests/test_qa_final.py::test_existing_defective_mp4_fails PASSED         [100%]
============================== 5 passed in 5.17s ===============================
```

### Defective MP4 validation (`python3 scripts/qa_final.py Videos/Projects/.../using_ai_to_help_memory_retention_short_16x9.mp4`)
```
  ✗ CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s (delta 63.3s > 0.25s tolerance)
  ✗ LENGTH_MISMATCH: video 83.3s vs audio 146.6s (delta 63.3s > 0.25s tolerance)
  ✗ TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s (audio outlasts video by 63.3s)
EXIT_CODE=1
```

Report output:
```json
{
  "video_duration": 83.33,
  "audio_duration": 146.6,
  "container_duration": 146.6,
  "frame_count": 2000,
  "issues": [
    "CONTAINER_MISMATCH: ...",
    "LENGTH_MISMATCH: ...",
    "TERMINAL_FREEZE: ..."
  ],
  "status": "fail"
}
```

### Full suite (`python3 -m pytest -q`)
```
4 failed, 283 passed in 80.12s
```
The 4 failures are **pre-existing** in `tests/test_review.py` (unrelated `review_loop()` signature mismatch) — not caused by this change.

## Known risks

1. **constraints.json tolerance change** affects all projects globally. Any future assembly that produces a legitimate <0.5s mismatch (but >0.25s) will now be caught. This is intentional — the ticket requires 0.25s.
2. **Stream duration tag absent**: some re-encoded files may not have the `duration` tag on the video stream. The fallback (`nb_frames/fps`) handles this, but if both are missing, `_video_duration()` returns `None` and the length checks are skipped (the NO_FRAMES check still fires if nb_frames is 0).
3. **produce.py step count changed from 16 to 17**: any existing `state.json` files that already completed `assemble` but not `gate_b_review` will correctly pick up `qa_final` as the next step (name-based resume logic).
