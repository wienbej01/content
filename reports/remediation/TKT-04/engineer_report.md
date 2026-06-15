# TKT-04 Engineer Report: Lipsync Audio Provenance Hardening

**Status:** ✅ Complete  
**Date:** 2026-06-14  

## Changes Made

### 1. `scripts/slice_continuous_lipsync.py`

- Added `from artifact_fingerprint import write_fingerprint` import
- Extended `audio_slice` dict with new provenance fields: `path`, `sha256`, `master_sha256`, `master_start_sec`, `master_end_sec` (alongside existing `file`, `slice_sha256`, `parent_mp3_sha256` for backward compatibility)
- Added `.fp.json` fingerprint write beside each slice using `write_fingerprint()` with the master hash as upstream

### 2. `scripts/qa_media.py`

- Updated `lipsync_checks()` section (d) to:
  - Look up slice file via `"file"` OR `"path"` key (supports both legacy and new schema)
  - Look up expected hash via `"slice_sha256"` OR `"sha256"` key
  - Emit `PROVENANCE: audio slice missing for {beat_id}` on missing file
  - Emit `PROVENANCE: audio slice hash mismatch for {beat_id}` on tampered slice

### 3. `scripts/assemble.py`

- `validate_lipsync_provenance()` updated:
  - Missing `lipsync_provenance` now prints a WARNING to stderr and returns `[]` (soft guard for old manifests) instead of hard-blocking
  - Reads slice file from `prov.get("slice_file") or prov.get("file") or prov.get("path")`
  - Reads expected hash from `prov.get("slice_sha256") or prov.get("sha256")`
  - Reads parent hash from `prov.get("parent_mp3_sha256") or prov.get("master_sha256")`
  - On mismatch: raises `RuntimeError` with beat ID (hard kill, no assembly)

### 4. `tests/test_lipsync_provenance.py` (new)

| Test | Validates |
|------|-----------|
| `test_slice_hash_recorded` | slice_continuous_lipsync records correct sha256, master_sha256, writes .fp.json |
| `test_tampered_slice_fails_qa` | Modified slice → QA FAIL with PROVENANCE message |
| `test_missing_slice_fails_qa` | Missing slice file → QA FAIL with PROVENANCE message |
| `test_silent_hero_clip_fails_qa` | No-audio hero clip → QA FAIL (LIPSYNC/audio stream) |
| `test_provenance_ok_passes` | Valid slice with matching hash → QA PASS |

### 5. `tests/test_assemble.py` (minor fix)

- `test_provenance_mismatch_fails_assembly` now expects `(ValueError, RuntimeError)` since the provenance check now raises RuntimeError directly.

## Test Results

```
tests/test_lipsync_provenance.py: 5 passed
tests/test_assemble.py: all pass (including provenance mismatch test)
tests/test_qa_media.py: 20 passed
Full suite: 318 passed, 4 failed (pre-existing test_review.py failures, unrelated)
```

## Acceptance Criteria Verification

1. ✅ Tampered audio slice fails QA with `PROVENANCE: audio slice hash mismatch for B001`
2. ✅ Missing slice fails QA with `PROVENANCE: audio slice missing for B001`  
3. ✅ Stale clips from wrong project fail before assembly (RuntimeError on hash mismatch)
4. ✅ All 5 new tests pass
5. ✅ No regressions (318 passed; 4 pre-existing failures in unrelated test_review.py)
