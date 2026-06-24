# Eval Design: S00_T001 Fixture Integrity Diagnostic

## Purpose
Verify that the bad-run fixture has been correctly captured and is analyzable.
This is a diagnostic eval — it does not need to fail; it measures whether the
fixture capture succeeded and records quantitative baseline properties.

## Eval type
Diagnostic fixture integrity check.
- Not a pass/fail on video quality
- Not a lipsync measurement
- Not a DB query (DB queries are in the forensic report)
- Deterministic, local-only, no provider calls

## Subject
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4

## Checks performed
1. FILE_EXISTS — fixture file is present and non-empty
2. SHA256_MATCH — fixture SHA256 matches expected value from forensic capture
3. FFMPEG_READABLE — ffprobe can parse the file without error
4. VIDEO_STREAM — H.264, 1920x1080, 24fps, duration ~22.8-23.0s
5. AUDIO_STREAM — AAC, stereo, 96kHz, duration >= video duration
6. RENDER_LOCK — env vars YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1
7. SCENE_DURATION — video duration is 22.8-23.0 seconds
8. FRAME_COUNT — ~548 frames at 24fps

## Thresholds
- FILE_EXISTS: file must exist, size > 5MB
- SHA256_MATCH: must equal `35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386`
- FFMPEG_READABLE: exit code 0, JSON parseable
- VIDEO_STREAM: codec=h264, width=1920, height=1080, fps=24/1
- AUDIO_STREAM: codec=aac, sample_rate=96000, channels=2
- RENDER_LOCK: all 3 env vars set to "1"
- SCENE_DURATION: duration between 22.0 and 24.0 seconds
- FRAME_COUNT: 540-560 frames

## Deterministic command
```bash
python3 reports/karpathy_loop/sprint_00/S00_T001/eval_fixture_integrity.py
```

## Expected output
Machine-readable JSON written to reports/karpathy_loop/sprint_00/S00_T001/eval_result_before.json

## Expected behavior on bad fixture
All checks should PASS. This is a diagnostic eval confirming the fixture
capture is valid. The fixture IS the bad run; the eval confirms it was
captured correctly so that downstream evals (lipsync, timing, etc.) have
a valid subject.
