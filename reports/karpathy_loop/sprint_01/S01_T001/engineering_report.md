# Engineering Report: S01_T001 Source Audio Slice Ledger

## Changes made

### 1. DB migration: `db/migrations/007_source_slice_sha256.sql` (NEW)
Adds `source_slice_sha256 TEXT` column to `render_units` table.
- Additive, non-destructive migration
- Column stores the SHA256 of the per-hero-unit audio slice file
- Distinct from existing `master_audio_sha256` (which is hash of full TTS master)

### 2. `scripts/slice_continuous_lipsync.py` (MODIFIED)
Both slicing functions now populate `source_slice_sha256` on the render_unit row:

**`slice_hero_units()`** (line ~256-270):
- Added `source_slice_sha256=?` to UPDATE statement
- Passes `slice_sha` (computed from the actual slice file on disk)

**`materialize_hero_slot_slices()`** (line ~399-407):
- Added `source_slice_sha256=?` to UPDATE statement  
- Passes `slice_sha` (computed from the actual slice file on disk)

### 3. `scripts/media_service.py` (MODIFIED)
**`submit_provider_job()`** — added provenance gate (after contract checks, before idempotency key):
```python
if ru.get("audio_policy") == "HERO_SYNC_LOCKED":
    ru_slice_sha = ru.get("source_slice_sha256")
    if not ru_slice_sha:
        raise ProviderJobError(
            f"Cannot submit provider job for HERO_SYNC_LOCKED render_unit "
            f"{render_unit_id}: source_slice_sha256 is missing. "
            f"Run audio slicing first (slice_continuous_lipsync.py)."
        )
```
This ensures no HERO_SYNC_LOCKED unit can be submitted to a provider without
provenance of its source audio slice.

### 4. `tests/test_source_slice_ledger.py` (NEW)
7 tests across 3 test classes:
| Test | What it verifies |
|------|-----------------|
| test_reject_hero_unit_without_slice_hash | HERO unit sans hash → ProviderJobError |
| test_accept_hero_unit_with_slice_hash | HERO unit with hash passes the gate |
| test_non_hero_unit_bypasses_gate | BROLL_FLEX units skip the gate |
| test_slice_hash_matches_file | source_slice_sha256 == actual file SHA256 |
| test_slice_hash_changes_when_file_changes | Collision resistance check |
| test_missing_slice_file_raises_runtime_error | Nonexistent file → error |
| test_null_slice_sha256_blocks_submission | Null hash treated as missing |

### Files changed
```
A db/migrations/007_source_slice_sha256.sql
M scripts/slice_continuous_lipsync.py
M scripts/media_service.py
A tests/test_source_slice_ledger.py
```

### Test results
```
7 passed in 0.14s
```

### Render lock verification
YT_TEST_MODE=1 ✓, HIGGSFIELD_DRY_RUN=1 ✓, KARPATHY_LOOP_RENDER_LOCK=1 ✓
No provider render calls made.

### Ticket requirements mapping
| Requirement | Status |
|-------------|--------|
| DB-backed ledger for hero source slices | ✓ source_slice_sha256 column added |
| render_unit_id | ✓ existing field |
| timeline_span_id | ✓ existing field |
| master_audio_artifact_id | ✓ existing field |
| master_audio_sha256 | ✓ existing field |
| source_slice_path | ✓ derivable from artifact URI (not duplicated) |
| source_slice_sha256 | ✓ NEW column |
| source_slice_start/end_sample | ✓ existing speech_start_sample/end_sample |
| leading/trailing_silence_samples | ✓ existing fields |
| test: no submission without source_slice_sha256 | ✓ test_reject_hero_unit_without_slice_hash |
| test: source_slice_sha256 equals file hash | ✓ test_slice_hash_matches_file |
| test: missing source slice fails loud | ✓ test_missing_slice_file_raises_runtime_error |

Gate status:
- Gate 0 Render lock: PASS
- Gate 1 Forensic: PASS
- Gate 2 Eval-first: PASS (pre: 0/6, post: 6/6)
- Gate 3 Engineering: PASS
- Gate 4 Audit: PENDING
