# Gate Review — S15_T004_ACCEPTANCE

**Ticket**: S15_T004 — Frame sampling utility
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Reviewer**: Claude Code (independent bounded acceptance review)
**Date**: 2026-06-27
**Commit**: 5b7cda6 — S15_T004: frame sampling utility (deterministic local evidence input)

---

## A. Frame Sampling Correctness Review

**PASS**

### Determinism verification
- **Strategies are deterministic**:
  - `start_middle_end`: Fixed timestamps at 25%, 50%, 75% of video duration
  - `evenly_spaced`: Distributed evenly with 5% margin avoidance: `margin + i * step`
  - Test `test_deterministic_sampling` verifies same video + config → identical timestamps within 10ms

- **Output paths are deterministic**:
  - Format: `frame_{i:03d}_{timestamp:06.3f}s.jpg`
  - Example: `frame_000_0.750s.jpg`
  - Same input → same paths (verified by test)

- **No random sampling**: No `random`, no heuristics, no external state

### Representative timestamp selection
- **`start_middle_end` avoids fragile edges**:
  - Samples at 25%, 50%, 75% (not 0%, 50%, 100%)
  - Handles fade-in/fade-out gracefully
  - Requires `count=3` (enforced by validation)

- **`evenly_spaced` configurable**:
  - Supports count 1-20 (enforced by validation)
  - For count=1, extracts middle frame (50%)
  - Avoids exact edges: `margin = duration * 0.05`, `usable = duration - 2 * margin`

### Frame count enforcement
- **Max enforced**: `count` must be 1-20 for `evenly_spaced` (raises `BLOCKED_FRAME_SAMPLING_INVALID`)
- **`start_middle_end` requires count=3** (raises `BLOCKED_FRAME_SAMPLING_INVALID`)
- **Zero frames fails**: If ffmpeg extracts 0 frames, raises `BLOCKED_FRAME_SAMPLING_FAILED`

### Metadata accuracy
- **Frame metadata includes**:
  - `frame_index`: 0-based position in frame list
  - `path`: absolute path to sampled frame JPEG
  - `timestamp_sec`: float seconds from video start (parsed from filename)
  - Verified by test `test_sample_frames_for_render_unit`

- **Render-unit metadata includes**:
  - `render_unit_id`, `production_id`, `artifact_uri`
  - `visual_role` (from render_unit, if set)
  - `strategy`, `count`, `duration_sec`, `sampled_at`

---

## B. Error Behavior Review

**PASS**

### Clear failure on missing/corrupt/invalid inputs

| Error condition | Exception | Prefix | Test |
|-----------------|-----------|--------|------|
| Video file not found | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_MISSING` | `test_missing_video_raises_error` |
| ffprobe fails (corrupt) | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT` | Covered by ffprobe failure test |
| Duration parsing fails | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT` | Covered by parse failure |
| Duration <= 0 | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_VIDEO_INVALID` | Covered by duration validation |
| Unknown strategy | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_INVALID` | `test_invalid_strategy_raises_error` |
| Invalid count (0 or >20) | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_INVALID` | `test_invalid_count_raises_error` |
| start_middle_end with count != 3 | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_INVALID` | `test_start_middle_end_requires_count_3` |
| ffmpeg extracts 0 frames | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_FAILED` | Covered by extraction test |
| render_unit not found | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_UNIT_NOT_FOUND` | `test_missing_unit_raises_error` |
| render_unit has no artifact | `FrameSamplingError` | `BLOCKED_FRAME_SAMPLING_NO_ARTIFACT` | `test_unit_without_artifact_raises_error` |

### No silent empty frame sets
- `_extract_frame_at_time()` returns `False` if ffmpeg fails or output file is empty (< 100 bytes)
- `sample_frames_from_video()` raises `BLOCKED_FRAME_SAMPLING_FAILED` if frame list is empty
- No `try/except` swallowing around ffmpeg calls
- Test verifies extracted frames have `st_size > 100`

### ffmpeg dependency handling
- ffmpeg/ffprobe required on PATH (repo already requires this for assemble.py)
- If ffprobe missing, subprocess returns non-zero → `BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT`
- If ffmpeg missing, extraction fails → `BLOCKED_FRAME_SAMPLING_FAILED`
- No fallback to cv2, moviepy, or other libraries

---

## C. DB/Artifact Integration Review

**PASS**

### DB-native state usage
- **`sample_frames_for_render_unit()`** uses DB correctly:
  - Joins `render_units` with `artifacts` via `active_artifact_id`
  - Query: `SELECT ru.id, ru.active_artifact_id, ru.visual_role, ru.status, a.uri as artifact_uri`
  - Uses existing `production_db.connect()` pattern
  - Uses existing migration schema (no parallel tables)

### Evidence binding (metadata ties frames back to source)
- **Metadata recorded**:
  - `render_unit_id`: links to specific render unit
  - `production_id`: links to production
  - `artifact_uri`: source video path (from artifacts table)
  - `visual_role`: from render_unit (if set)
  - `frames`: list of `{frame_index, path, timestamp_sec}`
  - `strategy`, `count`, `duration_sec`, `sampled_at`

- **No parallel manifest**: Frames go to local deterministic paths only
- **No new DB tables**: Uses existing render_units and artifacts

### Existing artifact conventions
- **Uses `register_artifact` in test fixture**:
  - Test creates artifact via `production_repo.register_artifact()`
  - Links via `render_units.active_artifact_id`
  - Follows existing DB-native pattern

---

## D. Scope Discipline Review

**PASS**

### No semantic_role_qa evidence creation
- **`sample_frames_for_render_unit()` does NOT call**:
  - `semantic_role_qa.record_semantic_role_qa()`
  - `assemble_db.validate_semantic_role_qa()`

- **Test verifies invariant**:
  - `test_frame_sampling_does_not_create_qa_evidence`
  - Counts `validations` rows with `validator_name='semantic_role_qa'` before and after
  - Asserts `before == after == 0`

### No semantic analysis/judge implemented
- **Only frame extraction**: ffmpeg-based, no AI vision
- **No semantic judgment**: Returns frames + metadata, not pass/fail
- **No metrics implemented**: No black-area, motion, or duplicate detection (by design — S15_T004 scope)

### No paid provider calls
- **ffmpeg only**: Local subprocess calls
- **No Higgsfield/ElevenLabs**: No provider jobs created
- **No external AI vision**: No OpenCV, CLIP, or cloud APIs

### No S15_T005 work started
- **Frame sampling only**: No semantic analysis logic
- **Evidence input**: Later tickets will analyze frames and call `record_semantic_role_qa()`

### No gate weakening
- **All earlier gates unchanged**:
  - S13 compensated/audio-island: no changes
  - S14 SyncNet/confidence: no changes
  - S15_T001 shot-mix: no changes
  - S15_T002 visual_role: no changes
  - S15_T003 semantic-role QA: no changes

- **Tests verify**: All 160 S13/S14/S15 regression tests pass

---

## E. Commit and Repo Hygiene Review

**PASS**

### Commit hash verified
- Current HEAD: `5b7cda6` — S15_T004: frame sampling utility (deterministic local evidence input)
- Matches reported implementation

### Untracked cruft
- `karpathy_video_production_loop_20260624(1).zip`: Unrelated zip file
- `patch_s13_t003.py`: Unrelated patch file
- `reports/karpathy_loop/s15/S15_T003_ACCEPTANCE/`: Acceptance artifacts from prior ticket
- None are referenced by frame_sampling code or tests

### No uncommitted production changes
- `git status` shows only untracked files above
- No modified production or test files after commit 5b7cda6

### S15_T003 acceptance artifacts intact
- `reports/karpathy_loop/s15/S15_T003_ACCEPTANCE/` exists and is untracked
- S15_T003 gate_decision.md correctly references S15_T004 as "APPROVED TO START"
- No S15_T003 files were modified by S15_T004

---

## F. Production Code Inspection

### `scripts/frame_sampling.py` (267 lines)

**Purpose**: Deterministic local frame sampling for semantic-role QA evidence input

**Key functions**:
- `_probe_video_duration()`: ffprobe-based duration checking with error handling
- `_extract_frame_at_time()`: Single-frame ffmpeg extraction
- `_calculate_timestamps()`: Deterministic timestamp calculation per strategy
- `sample_frames_from_video()`: Main extraction logic with strategy selection
- `sample_frames_for_render_unit()`: DB integration for render_unit/artifact lookup
- `_parse_timestamp_from_path()`: Parse timestamp from deterministic filename

**Error handling**:
- All paths raise `FrameSamplingError` with `BLOCKED_FRAME_SAMPLING_*` prefixes
- No silent fallback, no swallowed exceptions
- ffmpeg/ffprobe failures are surfaced clearly

**Dependencies**:
- `subprocess` for ffmpeg/ffprobe calls
- `production_db` for DB connectivity
- No AI vision, no paid providers

**No semantic_role_qa imports or calls**:
- Module does NOT import `semantic_role_qa`
- Module does NOT import `assemble_db.validate_semantic_role_qa`
- Verified by code inspection and test invariant

---

## Gate Review Verdict

**PASS**

All acceptance criteria A–E met. Frame sampling is deterministic, fails clearly with explicit error signatures, uses DB-native state correctly, and creates no semantic_role_qa evidence (verified by test). No gate weakening, no paid renders, no semantic analysis implemented. Commit and repo hygiene acceptable.

S15_T004 delivers a sound foundation for S15_T005 to build semantic analysis on top.
