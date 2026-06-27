# Loop Decision — S15_T004 (Frame sampling utility)

**Ticket**: S15_T004 — Frame sampling utility
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Date**: 2026-06-27
**Branch**: `forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`

---

## Verdict

**PASS (engineering / audit / validation).** Awaiting final loop decision to mark the ticket DONE.

S15_T004 delivers a deterministic local frame-sampling utility that extracts representative frames from rendered video units for later semantic-role QA inspection. The implementation is minimal, correctly scoped as evidence-input-only, and creates no semantic_role_qa evidence (verified by test).

---

## What was delivered

- **`scripts/frame_sampling.py`** — Frame sampling utility with two strategies:
  - `start_middle_end`: 3 frames at 25%, 50%, 75% (avoids fade edges)
  - `evenly_spaced`: configurable count (1-20) distributed evenly
  - Deterministic: same video + config → same timestamps
  - Fail-closed: all errors raise `BLOCKED_FRAME_SAMPLING_*` exceptions

- **`tests/test_frame_sampling.py`** — 13 tests:
  - 4 frame extraction tests (strategies, determinism)
  - 4 error handling tests (missing video, invalid config)
  - 3 render_unit integration tests
  - 1 invariant test (no semantic_role_qa evidence created)
  - 1 import sanity test

- **Primary entry point**: `sample_frames_for_render_unit()`
  - Looks up render_unit and artifact from DB
  - Extracts frames to `output_base_dir/production_id/render_unit_id/`
  - Returns metadata (render_unit_id, artifact_uri, visual_role, timestamps)

---

## Error signatures

- `BLOCKED_FRAME_SAMPLING_VIDEO_MISSING` — video file not found
- `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT` — ffprobe/ffmpeg failed
- `BLOCKED_FRAME_SAMPLING_VIDEO_INVALID` — duration <= 0
- `BLOCKED_FRAME_SAMPLING_INVALID` — bad strategy or count
- `BLOCKED_FRAME_SAMPLING_FAILED` — extracted 0 frames
- `BLOCKED_FRAME_SAMPLING_UNIT_NOT_FOUND` — render_unit not in DB
- `BLOCKED_FRAME_SAMPLING_NO_ARTIFACT` — render_unit has no artifact

---

## Test results

- Required set: **173 passed, 1 skipped** (skip pre-existing).
- New suite: **13 passed** (test_frame_sampling.py).
- Full suite: **90 failed, 1812 passed, 10 skipped**.
- **Zero frame-sampling failures anywhere** in the full suite → **zero regressions**.
- Failure count identical to the S15_T003-accepted baseline (90); +13 passes are the new tests.

---

## Remaining failures classification

All 90 full-suite failures are **REAL / PRE-EXISTING / OUT OF SCOPE** — earlier-gate debt (S14 SyncNet, S13 compensated, S15_T001 shot-mix on non-compliant fixtures) and unrelated subsystems (audio, canary, DB, e2e). **NO MATERIAL IMPACT** on S15_T004.

---

## Hard-rule compliance

| Rule | Status |
|------|--------|
| One ticket only (no S15_T005) | ✅ |
| No paid renders | ✅ |
| No external AI vision | ✅ |
| No gate weakening | ✅ |
| No fake-green (no semantic_role_qa evidence) | ✅ |
| No silent fallback | ✅ |
| No broad suite cleanup | ✅ |
| Fail-closed with `BLOCKED_*` signatures | ✅ |
| Deterministic | ✅ |

---

## S15_T005 readiness

**NOT STARTED.** S15_T004 is delivered but awaiting final loop decision. S15_T005 (Enforce shot-mix preflight) is the natural next step: it will use `sample_frames_for_render_unit()` to extract frames and then perform semantic analysis to verify shot composition matches declared visual roles. Per instructions, S15_T005 is **not** started in this session.

---

## Residual risks

- No real semantic analysis yet (by design — S15_T005 will analyze the sampled frames and call `record_semantic_role_qa()` with real verdicts).
- No black-area/motion/duplicate metrics (S15_T004 only asked for frame sampling; those metrics can be added in later tickets if needed).

---

## State updates

- `management/LOOP_STATE.md` — S15_T004 ENGINEERING PASS, awaiting final decision.
- `management/TICKET_STATUS.json` — S15_T004 status updated.
