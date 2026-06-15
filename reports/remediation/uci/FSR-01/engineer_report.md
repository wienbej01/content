# FSR-01 Engineer Report: Clip DB ↔ Filesystem Reconciliation Fix

**Date:** 2026-06-15  
**Ticket:** FSR-01  
**Status:** ✅ COMPLETE — all 646 tests green

---

## Fixes Implemented

### FIX A — Asset-type-aware canonical path (P0)

**File:** `scripts/clip_db.py`

Added `_ext_for_asset_type(asset_type)` helper:
- `local_graphic` / `still_image` → `.png`
- All other types → `.mp4`

Updated `_canonical_path()` to accept `asset_type` parameter and use the helper for extension. Updated `order_clip()` to pass `asset_type` through to `_canonical_path()`.

**Result:** DB `output_path` is now `.png` for local_graphic clips from the moment they are ordered. No post-hoc patching needed.

### FIX B — Filesystem truth in validation gates (P1)

**File:** `scripts/clip_db.py`

1. **`verify_clip_file(clip, root=None)`** — shared helper (DRY):
   - Checks file exists at `output_path`
   - If `actual_sha256` is recorded, verifies it matches the live file
   - Handles both absolute and relative paths
   - Reused by `can_reuse`, `mark_valid`, and `assert_all_valid`

2. **`mark_valid(clip_id)`** — now verifies filesystem before marking valid:
   - Calls `verify_clip_file()`
   - If file missing or SHA mismatch → marks clip `failed` + raises `FileNotFoundError`
   - Prevents the contradiction: status=valid but no file on disk

3. **`assert_all_valid(project_id)`** — now checks filesystem for ALL clips:
   - After DB status checks, iterates all clips and calls `verify_clip_file()`
   - Any file missing or SHA mismatch → reported as a problem regardless of DB status
   - This is the golden-truth gate: it now verifies reality, not just DB flags

4. **`can_reuse(clip_id)`** — refactored to use `verify_clip_file()` (DRY):
   - Removed inline file existence + SHA checks
   - Now calls the shared helper

### FIX C — Assemble UCI-04 path resolution gated by filesystem truth (P0)

**File:** `scripts/assemble.py`

The `assert_all_valid` call already runs AFTER the DB path override loop (line ordering preserved). Since `assert_all_valid` now checks the filesystem, a stale/wrong-extension path that doesn't exist on disk will be caught with an actionable error message before any ffprobe/mux operation.

No TOCTOU gap remains: paths are resolved from DB → filesystem check → mux.

---

## Test Results

### New tests (`tests/test_fsr01_filesystem_truth.py`) — 7/7 PASS

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_canonical_path_local_graphic_is_png` | FIX A: extension awareness |
| 2 | `test_mark_valid_rejects_missing_file` | FIX B: file must exist |
| 3 | `test_mark_valid_rejects_sha_mismatch` | FIX B: SHA must match |
| 4 | `test_mark_valid_accepts_present_matching_file` | FIX B: happy path |
| 5 | `test_assert_all_valid_flags_absent_file` | FIX B: filesystem overrides DB |
| 6 | `test_assert_all_valid_passes_when_all_present` | FIX B: happy path |
| 7 | `test_local_graphic_roundtrip` | End-to-end .png lifecycle |

### Targeted suite — 34/34 PASS

```
tests/test_fsr01_filesystem_truth.py    7 passed
tests/test_assemble.py                 15 passed
tests/test_uci04_assemble_db.py         5 passed
tests/test_orphan_beat_guard.py         5 passed (includes local_graphic golden gate)
```

### Full suite — 646/646 PASS

```
646 passed, 12 warnings in 146.05s
```

---

## Existing Tests Updated

Tests that called `mark_valid` without creating files (the exact bug we fixed) were updated to create real files + use real SHA-256 values:

- `tests/test_clip_db.py` — 5 tests (change requests, assert_all_valid, access log)
- `tests/test_uci07_e2e.py` — 2 tests (slot deficit, sibling independence)
- `tests/test_cdb05_interactive_qa.py` — 2 tests (QA pass marks valid, QA summary)
- `tests/test_cdb06_golden_gate.py` — 2 tests (change request blocks, all valid proceeds)
- `tests/test_cdb06_e2e.py` — 1 test (regen + resolve flow)
- `tests/conftest.py` — added `make_clip_file()` helper for future tests

---

## Audited Project Recovery Path

For `how_to_use_ai_to_better_organize_your_de_short`:

1. **Recompile** (`compile_media_prompts.py`) → `order_clip` now assigns `.png` output_path for all `local_graphic` beats
2. **render_graphics** → writes `.png` at the correct path (already does this)
3. **mark_valid** → verifies `.png` file exists at the new correct path before validating
4. **assert_all_valid** → confirms all 16 clips have real files on disk
5. **assemble** → DB path override returns `.png` paths → filesystem gate passes → mux succeeds

The `build_manifest.py` `.mp4→.png` workaround (line 228) is now redundant (DB already stores `.png`) but remains harmless as defense-in-depth.

---

## Acceptance Criteria Checklist

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `_canonical_path` / `output_path` asset_type-aware (local_graphic=.png, video=.mp4) | ✅ |
| 2 | `mark_valid` verifies file exists + SHA before validating; refuses otherwise | ✅ |
| 3 | `assert_all_valid` checks filesystem, not just status flag | ✅ |
| 4 | Assemble post-override path gated by filesystem-aware `assert_all_valid` | ✅ |
| 5 | Shared `verify_clip_file` helper (DRY) reused by can_reuse/mark_valid/assert_all_valid | ✅ |
| 6 | All tests pass; full suite green (646 passed) | ✅ |
| 7 | Recovery path documented for audited project | ✅ |
