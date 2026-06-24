# Eval Design: S00_T002 Video Forensic Summary

## Purpose
Create a machine-readable quantitative summary of all video defects identified
during forensic analysis. This is a diagnostic eval — it extracts measurable
properties from the fixture and compares them against expected thresholds.

## Subject
fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4

## Eval type
Diagnostic video forensic summary — local, deterministic, no provider calls.

## Checks performed
1. DURATION_CHECK — total duration is ~22.9s (22.0-24.0s range)
2. SCENE_COUNT — exactly 4 scenes detected
3. MAX_STATIC_HOLD — 7.125s black hold detected (should exceed 5s warning threshold)
4. LIPSYNC_OFFSET — provisional only, recorded as null (evaluator not available)
5. HERO_TALKING_HEAD — 2 hero segments present
6. AUDIO_CONTINUITY — no silence gaps detected
7. AUDIO_VIDEO_DURATION_DIFF — 67ms mismatch (warning if > 41.7ms = 1 frame)

## Deterministic command
```bash
python3 reports/karpathy_loop/sprint_00/S00_T002/eval_video_forensic.py
```

## Expected output
reports/karpathy_loop/sprint_00/S00_T002/video_forensic_summary.json

## Thresholds
- DURATION_CHECK: 22.0-24.0s
- SCENE_COUNT: 4 (exact)
- MAX_STATIC_HOLD: < 5.0s for PASS, >= 5.0s triggers F-GFX-001
- LIPSYNC_OFFSET: null (provisional — requires SyncNet)
- AV_DURATION_DIFF: < 0.042s (1 frame at 24fps) for PASS
