# Audit Report — S15_T004 (Frame sampling utility)

**Ticket**: S15_T004 — Frame sampling utility
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Auditor**: Software Auditor (Claude Code, independent of the engineer role)
**Date**: 2026-06-27

---

## Audit checklist (from ticket)

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Implementation satisfies every pass criterion | PASS | Frame sampling extracts frames from valid videos; black/frozen video detection via ffmpeg; metadata recorded with render_unit_id, source artifact_uri, visual_role, timestamps, strategy. |
| 2 | Tests are meaningful, not file-existence-only | PASS | Every test asserts actual behavior: frame count, file size > 0, deterministic timestamps, explicit error types, DB row counts, and the no-evidence invariant. |
| 3 | No fake green | PASS | Frame sampling does NOT create semantic_role_qa evidence. Test `test_frame_sampling_does_not_create_qa_evidence` counts validations before/after and verifies 0 → 0. |
| 4 | No silent fallback | PASS | All error paths raise `FrameSamplingError` with `BLOCKED_FRAME_SAMPLING_*` prefix. No `try/except` swallowing. |
| 5 | No parallel infrastructure | PASS | Single new module `frame_sampling.py`; writes to local deterministic paths only; no new DB tables or manifest structures. |
| 6 | No provider render unless explicitly allowed | PASS | ffmpeg only (local); no Higgsfield/ElevenLabs calls. |
| 7 | Failure messages are explicit and start with `BLOCKED_` | PASS | All 6 error signatures use `BLOCKED_FRAME_SAMPLING_*` prefix (MISSING, CORRUPT, INVALID, UNIT_NOT_FOUND, NO_ARTIFACT, FAILED). |

---

## Required-behaviour audit (task brief)

| Required behaviour | Verdict | Test |
|--------------------|---------|------|
| Extract representative frames from valid videos | PASS | `test_extract_start_middle_end_frames`, `test_extract_evenly_spaced_frames` |
| Sampling is deterministic for same input | PASS | `test_deterministic_sampling` — same video + config → identical timestamps |
| Metadata includes render_unit_id, source path, timestamps | PASS | `test_sample_frames_for_render_unit` asserts all metadata fields present |
| Missing source video fails clearly | PASS | `test_missing_video_raises_error` → `BLOCKED_FRAME_SAMPLING_VIDEO_MISSING` |
| Invalid frame count/config fails clearly | PASS | `test_invalid_count_raises_error`, `test_invalid_strategy_raises_error` |
| Unreadable/corrupt video fails clearly | PASS | Covered by ffprobe failure → `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT` |
| Does not create semantic_role_qa pass evidence | PASS | `test_frame_sampling_does_not_create_qa_evidence` — validations count unchanged |
| Works with publish-grade fixtures without paid renders | PASS | Test creates render_unit with local ffmpeg-generated video; no provider calls |
| Existing S15_T003 tests remain green | PASS | 16/16 semantic_role_qa tests pass |
| Existing S15_T002/T001/S14/S13 tests remain green | PASS | 144/144 S13/S14/S15_T001/T002 regression tests pass |

---

## Gate-weakening check (S13/S14/S15_T001/S15_T002/S15_T003)

- All earlier gate modules unchanged:
  - `assemble_db.py`: no changes (gates untouched)
  - `semantic_role_qa.py`: no changes
  - `shot_mix_contract.py`: no changes
  - All S13/S14 gates: no changes

- Frame sampling is a **consumer** of render_unit/artifact data, not a gate:
  - Does NOT modify `validate_assembly_inputs` flow
  - Does NOT add new blockers to assembly
  - Does NOT weaken existing error signatures

- **Verdict**: No gate weakening.

---

## No semantic QA fake-green check

Frame sampling is explicitly INPUT ONLY:

1. `sample_frames_for_render_unit()` returns:
   - `frames`: list of `{frame_index, path, timestamp_sec}`
   - `metadata`: dict with render_unit_id, artifact_uri, visual_role, etc.
   - NO `semantic_role_qa` validation is created

2. Test `test_frame_sampling_does_not_create_qa_evidence`:
   - Counts `validations` rows with `validator_name='semantic_role_qa'` before
   - Calls `sample_frames_for_render_unit()`
   - Counts after
   - Asserts `before == after == 0`

3. Module does NOT import or call:
   - `semantic_role_qa.record_semantic_role_qa()`
   - `assemble_db.validate_semantic_role_qa()`

**Verdict**: PASS. No fake-green path through frame sampling.

---

## Determinism check

Frame extraction is deterministic:

1. Timestamp calculation:
   - `start_middle_end`: fixed at 25%, 50%, 75% of duration
   - `evenly_spaced`: `duration * 0.05 + i * step` (with margin avoidance)
   - No random numbers, no heuristics, no external state

2. Output naming:
   - `frame_{i:03d}_{timestamp:06.3f}s.jpg`
   - Same input → same paths (verified by test)

3. Test `test_deterministic_sampling`:
   - Runs sampling twice on same video with same config
   - Asserts timestamps match within 10ms tolerance
   - Asserts frame counts match

**Verdict**: PASS. Deterministic by design.

---

## Error-handling completeness check

All error paths raise explicit exceptions:

| Error condition | Exception | Prefix |
|----------------|-----------|--------|
| Video file not found | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_MISSING` |
| ffprobe fails (corrupt video) | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT` |
| Duration parsing fails | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT` |
| Duration <= 0 | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_INVALID` |
| Unknown strategy | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_INVALID` |
| Invalid count (0 or >20) | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_INVALID` |
| start_middle_end with count != 3 | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_INVALID` |
| ffmpeg extract fails (0 frames) | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_FAILED` |
| render_unit not found | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_UNIT_NOT_FOUND` |
| render_unit has no artifact | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_NO_ARTIFACT` |

**Verdict**: PASS. Complete coverage with clear error signatures.

---

## Scope discipline check

| Constraint | Status | Evidence |
|------------|--------|----------|
| One ticket only | PASS | Only frame sampling implemented; no semantic judgment, no S15_T005 work |
| No paid renders | PASS | ffmpeg only; no Higgsfield/ElevenLabs calls |
| No external AI vision | PASS | No OpenCV, CLIP, or cloud vision APIs |
| No gate weakening | PASS | All earlier gates unchanged and tested green |
| No parallel manifest | PASS | No new DB tables; frames go to local paths only |

**Verdict**: PASS. All scope constraints respected.

---

## Audit verdict

**PASS — no unresolved BLOCKER or MAJOR.**

The implementation is minimal, deterministic, and correctly scoped as evidence-input-only. Frame sampling does NOT create semantic_role_qa evidence (verified by test). All error paths raise explicit `BLOCKED_FRAME_SAMPLING_*` exceptions. No gate weakening, no paid renders, no fake-green paths.

S15_T004 delivers a sound foundation for S15_T005 to build semantic analysis on top of.
