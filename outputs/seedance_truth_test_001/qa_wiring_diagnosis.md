# Seedance QA Wiring Diagnosis

verdict: QA_BUG_WITH_REVIEW_REQUIRED
paid_renders_triggered: no
publish_grade_final_created: no

## What Happened

The truth test reported:

- S000: `lipsync_drift_609ms`
- S002: `lipsync_drift_158ms`

Those values were not SyncNet mouth/audio offsets. They were duration/reference deltas:

- S000 embedded provider audio duration: 8080 ms
- S000 reference slice duration: 7471 ms
- S000 delta: 609 ms
- S002 embedded provider audio duration: 6060 ms
- S002 reference slice duration: 5902 ms
- S002 delta: 158 ms

The old QA path in `scripts/media_service.py` called `qa_lipsync.detect_lipsync_drift_ms(...)`. That helper measures stream duration relationships, including embedded-audio duration against expected/reference duration. The result was stored in `lipsync_drift_ms`, which made a duration mismatch look like mouth/audio drift.

## Answers

### Why did it report duration delta as `lipsync_drift`?

Because `_qa_hero_lipsync` treated the return value from `qa_lipsync.detect_lipsync_drift_ms(...)` as lipsync drift. That function is duration-based, not face-track or SyncNet-based.

### Is this field actually SyncNet offset, duration mismatch, or generic sync failure?

For the failed truth-test report, it was duration mismatch. It was not SyncNet offset.

### Does the current implementation run real SyncNet/face tracking?

No. `scripts/evals/eval_lipsync.py` is a fallback `mouth_motion_proxy` based on audio-envelope vs visual frame-difference correlation. Its output is provisional and reports `face_track_found: false`.

### If no face is detected, does it fail closed correctly?

After the local fix, yes. Low-confidence/no-face proxy output returns `needs_human_av_review` instead of a hard numeric drift failure.

### Is duration mismatch being conflated with mouth/audio offset?

It was conflated before the fix. The local fix records `duration_mismatch_ms` separately and only populates `lipsync_drift_ms` when the lipsync evaluator returns a supported hard fail.

### Is reference audio required for provider-synced hero QA, or should embedded provider audio be authoritative?

For Seedance/provider-lipsync hero clips, embedded provider audio/video sync is the primary A/V artifact. The reference slice is required for provenance and content/timing checks, but reference duration mismatch alone is not proof of mouth/audio drift.

### Where should `compensated_artifact_path` be populated?

It should be populated on the `provider_jobs` row by the compensated hero remux/compensation step before DB-native assembly. The existing helper path is `scripts/evals/remux_compensated_hero.py`, and assembly reads `provider_jobs.compensated_artifact_path`.

### Why is `compensated_artifact_path = null` for both Seedance hero clips?

No compensated remux/registration step ran after the paid provider artifacts were downloaded. QA failed before assembly, and the provider job rows stayed at `compensated_artifact_path = null`.

### Did SyncNet run against the correct media pair?

No real SyncNet run is present in the current evidence. The after-fix local diagnostic ran `eval_lipsync.py` against the provider MP4s with embedded provider audio. It returned `needs_human_av_review` for both clips because it has no face track and confidence below policy minimum.

## Local Fix Applied

- Separated `duration_mismatch_ms` from `lipsync_drift_ms`.
- Switched hero lipsync QA to call `eval_lipsync.analyze_video(...)` for lipsync evidence instead of duration-only drift detection.
- Made low-confidence/no-face proxy evidence produce `NEEDS_HUMAN_AV_REVIEW`.
- Added repair classification `hero_lipsync_needs_human_review`, mapped to `block_for_manual_review`.
- Added regression tests proving duration mismatch is not mislabeled as lipsync drift.

## Current State

The original drift values were invalid as mouth/audio drift claims. The current evidence does not prove real provider lipsync failure, and it also does not prove the clips are acceptable. The valid state is `NEEDS_HUMAN_AV_REVIEW`.
