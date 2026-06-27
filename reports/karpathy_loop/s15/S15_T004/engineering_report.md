# Engineering Report — S15_T004 (Frame sampling utility)

**Ticket**: S15_T004 — Frame sampling utility
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Author**: Software Engineer (Claude Code)
**Date**: 2026-06-27
**Branch**: `forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`

---

## Purpose

Build a deterministic local frame-sampling utility that extracts representative frames from rendered video units for later semantic-role QA inspection. This provides the evidence input that S15_T003's semantic-role QA recorder/gate can consume in later tickets.

Scope of this ticket: **frame sampling only**. No semantic judgment, no AI vision providers, no paid renders. The utility extracts frames and records metadata — it does NOT create semantic_role_qa pass/fail evidence (that is for later tickets).

## Design

### Frame extraction strategies

Two deterministic strategies:

1. **`start_middle_end`**: Fixed 3 frames at 25%, 50%, 75% of video duration
   - Avoids exact edges (0%, 100%) to handle fade-in/fade-out
   - Requires `count=3`

2. **`evenly_spaced`**: Configurable frame count (1-20) distributed evenly
   - Avoids exact edges (first/last 5% of video)
   - For `count=1`, extracts the middle frame (50%)

### Determinism

Same video + same config → same frames at same timestamps:
- Timestamps are calculated as float seconds from video start
- Output paths include timestamps: `frame_000_0.750s.jpg`
- No random sampling, no heuristics, no AI involvement

### Error handling

All failures raise `FrameSamplingError` with explicit `BLOCKED_FRAME_SAMPLING_*` prefixes:
- `BLOCKED_FRAME_SAMPLING_VIDEO_MISSING`: video file not found
- `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT`: ffprobe/ffmpeg failed
- `BLOCKED_FRAME_SAMPLING_VIDEO_INVALID`: duration <= 0
- `BLOCKED_FRAME_SAMPLING_INVALID`: bad strategy/count
- `BLOCKED_FRAME_SAMPLING_UNIT_NOT_FOUND`: render_unit not in DB
- `BLOCKED_FRAME_SAMPLING_NO_ARTIFACT`: render_unit has no active artifact

### Integration with render_units

The primary entry point `sample_frames_for_render_unit()`:
- Looks up render_unit from DB
- Joins with artifacts table via `active_artifact_id`
- Extracts frames to `output_base_dir/production_id/render_unit_id/`
- Returns metadata dict with:
  - `render_unit_id`, `production_id`, `artifact_uri`
  - `visual_role` (from render_unit, if set)
  - `strategy`, `count`, `duration_sec`
  - `frames`: list of `{frame_index, path, timestamp_sec}`
  - `sampled_at`: ISO timestamp

### No semantic_role_qa evidence created

Frame sampling is **evidence input only**. Calling `sample_frames_for_render_unit()`:
- Does NOT call `record_semantic_role_qa()`
- Does NOT insert into `validations` table
- Does NOT make pass/fail judgments about visual role

The test `test_frame_sampling_does_not_create_qa_evidence` verifies this invariant.

## Files changed (S15_T004)

### Production code

| File | Change | Why |
|------|--------|-----|
| `scripts/frame_sampling.py` (NEW) | Frame sampling utility with two strategies, determinism guarantees, and clear error handling. | Core S15_T004 deliverable. |

### Tests

| File | Change |
|------|--------|
| `tests/test_frame_sampling.py` (NEW) | 13 tests covering frame extraction, determinism, error handling, render_unit integration, and the invariant that no semantic_role_qa evidence is created. |

## Dependencies

### Required
- Python 3.13 (ffmpeg/ffprobe on PATH)
- `production_db` (for render_unit/artifact lookups)
- `production_repo.artifacts` (for render_unit fixture in tests)

### Not used
- No AI vision providers (OpenCV, CLIP, etc.)
- No paid Higgsfield/ElevenLabs calls
- No external image analysis
- No `semantic_role_qa` module dependency (sampling is input-only)

## Test results

### New tests
```
tests/test_frame_sampling.py: 13/13 passed
```

Breakdown:
- 4/4 frame extraction tests (start_middle_end, evenly_spaced, single, determinism)
- 4/4 error handling tests (missing video, invalid strategy, invalid count, strategy/count mismatch)
- 3/3 render_unit integration tests (valid unit, missing unit, no artifact)
- 1/1 invariant test (no semantic_role_qa evidence created)
- 1/1 import sanity test (existing tests still load)

### Required S15 regression tests
```
tests/test_semantic_role_qa.py: 16/16 passed
tests/test_visual_role_contract.py: 12/12 passed
tests/test_shot_mix_contract.py: 12/12 passed
tests/test_s14_t004_syncnet_confidence.py: 9/9 passed
tests/test_s14_t003_per_segment_syncnet.py: 6/6 passed
tests/test_lipsync_policy.py + tests/test_hero_framing.py: 73/73 passed
tests/test_s13_t005_integration_regression.py: 14 passed, 1 skipped
tests/test_audio_continuity.py: 18/18 passed

Total: 160 passed, 1 skipped (same as S15_T003 acceptance baseline)
```

**Zero regressions**: All S15_T001/S15_T002/S15_T003 and S13/S14 tests remain green.

## Why these are NOT violations of the hard rules

- **One ticket only**: Only frame sampling implemented; no semantic judgment (S15_T005)
- **No paid renders**: ffmpeg only, no provider calls
- **No external AI vision**: No OpenCV, CLIP, or cloud vision APIs
- **No gate weakening**: All S13/S14/S15_T001/S15_T002/S15_T003 gates unchanged and tested green
- **No fake-green path**: Frame sampling does NOT create semantic_role_qa evidence
- **No parallel manifest**: Frames go to local deterministic paths, not a new manifest table
- **No silent fallback**: All errors raise explicit `BLOCKED_FRAME_SAMPLING_*` exceptions
- **Deterministic**: Same input → same output (verified by test)

## Limitations / residual risks

- **No real semantic analysis**: By design — frame sampling only. Later tickets will consume these frames for actual visual role verification.
- **No black-area/motion/duplicate metrics**: S15_T004 ticket only asked for frame sampling; those metrics are for later tickets if needed.
- **ffmpeg dependency**: Requires ffmpeg/ffprobe on PATH (already true for this repo).

## Next steps (S15_T005)

S15_T005 (Enforce shot-mix preflight) may use `sample_frames_for_render_unit()` to:
- Extract frames from render units before assembly
- Verify shot composition matches declared visual roles
- Call `record_semantic_role_qa()` with real pass/fail verdicts based on frame analysis

S15_T004 delivers the frame sampling foundation; S15_T005 will build the semantic analysis on top.
