# CDB-03 Engineer Report

**Ticket:** CDB-03 — Wire generate_media to clip_db (reuse + record)  
**Date:** 2026-06-15  
**Status:** ✅ Complete  

---

## Summary

`scripts/generate_media.py` now uses the clip authority DB (`clip_db.py`) for all reuse decisions and records actual rendered attributes after generation. This directly eliminates the stale-reuse failure class (10s clip reused when 14s needed).

## Changes Made

### `scripts/generate_media.py`

1. **New import** (line 27): `from clip_db import can_reuse, record_generated, mark_failed, get_path, log_access, init_db`

2. **Reuse decision replaced** (beat loop in `run_from_media_plan`):
   - If beat has `clip_id`: calls `can_reuse(clip_id)` which checks status, file existence, SHA integrity, duration coverage, and audio policy
   - If reusable: logs `log_access(clip_id, 'generate_media', 'reuse', reason)` and skips generation
   - If not reusable: prints reason and proceeds to generate
   - If no `clip_id` (legacy path): falls back to fingerprint-based check with a warning

3. **Canonical path enforcement**: When `clip_id` is set, `out_path` is resolved from `get_path(clip_id)` — fixing the missing-slot bug where B004_B004-s0.mp4 was never generated because paths were re-derived inconsistently.

4. **Record after generation**: After successful download + probe + fingerprint write, calls `record_generated(clip_id, actual_dur_sec, actual_width, actual_height, actual_has_audio, actual_sha256)` + `log_access(...)`.

5. **Mark failed on error**: In the `except RuntimeError` handler, calls `mark_failed(clip_id, error)` before re-raising. The DB never falsely says "generated".

### Preserved safety guarantees

- `require_gates(SPEND_GATES)` — unchanged, still blocks all Higgsfield spend
- No-still-fallback for lipsync — unchanged, `lipsync_required` beats raise on retry failure
- Atomic download (`_atomic_download`) — unchanged
- Gate bypass only via `--force-unsafe` — unchanged

## Tests Added

`tests/test_cdb03_generate_reuse.py` — 7 tests, all mock the Higgsfield provider:

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_reuse_skips_generation_when_valid` | Valid+covering clip → no generation call |
| 2 | `test_regenerate_when_duration_short` | 10s actual < 14s required → regenerate |
| 3 | `test_regenerate_when_change_requested` | Open change request → regenerate |
| 4 | `test_record_generated_writes_actual_attrs` | DB has actual_dur/sha/dimensions after gen |
| 5 | `test_failed_generation_marks_failed` | Failed lipsync → status='failed' in DB |
| 6 | `test_generates_to_canonical_db_path` | Output lands at get_path(clip_id) |
| 7 | `test_slot_clip_generates_to_slot_path` | Slot file at {beat}_{slot}.mp4 |

## Verification

```
$ python3 -m pytest tests/test_cdb03_generate_reuse.py tests/test_generate_media.py -v
21 passed

$ python3 -m pytest -q
571 passed in 131.98s
```

## Acceptance Criteria Checklist

- [x] generate_media calls `can_reuse()` before generating; only reuses clips that actually cover the requirement
- [x] A short/stale clip triggers regeneration (the core fix)
- [x] `record_generated` writes actual attrs after successful gen
- [x] Failed gen calls `mark_failed` (DB never falsely says generated)
- [x] Clips generate to the canonical DB path (slots land at slot paths)
- [x] Existing safety (gates, no-still-fallback, atomic download) preserved
- [x] All new tests pass; full suite green; no paid APIs called
