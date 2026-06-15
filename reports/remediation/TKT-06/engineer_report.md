# TKT-06 Engineer Report — Media Generation Status and Stale-Output Handling

**Date:** 2026-06-14
**Status:** ✅ Complete

## Changes Implemented

### Change 1: Atomic Download with Validation

Added `_atomic_download(url, out_path, expected_duration)` helper:
- Downloads to `<path>.downloading` temp file
- Validates: file size > 0, ffprobe confirms video stream, duration within [0.5×, 2.0×] expected
- Atomically renames to final path via `os.replace()` on success
- Deletes temp file on any validation failure, raising RuntimeError with specifics

Added `_cleanup_stale_downloads(directory)` to remove leftover `.downloading` files from interrupted runs — called before generation and when checking existing outputs.

Both `generate_segment` (legacy path) and `_generate_beat_clip` (media_plan path) now use atomic download.

### Change 2: Generation Metadata Log

`_record_beat_provenance()` now writes richer metadata per beat:
- `project_id`, `job_id`, `provider`, `model`, `status`
- `sha256` of the output file
- `probe_summary`: `{duration, width, height, has_audio}`
- `generated_at` timestamp
- `request_params`: `{prompt, duration, model}`
- `audio_source_sha256` / `audio_source_path` for lipsync beats

### Change 3: No Retry-to-Still for Required Lipsync

In `run_from_media_plan`, the retry-then-fallback path now checks `beat.get("lipsync_required")`. When True, after the retry fails, raises `RuntimeError` with message "no still fallback allowed" instead of calling `_still_kenburns()`. B-roll beats retain the still_kenburns fallback.

### Change 4: Existing Output Re-check

Added `_validate_existing_output(out_path, expected_duration)`:
- Checks size > 0, ffprobe video stream, duration sanity
- Returns False for corrupt/zero-byte/invalid files

In `run_from_media_plan`, before the fingerprint check, the existing file is validated. If invalid, it's deleted and regeneration proceeds. Stale `.downloading` temps are also cleaned at this point.

## Tests Added

| Test | Validates |
|------|-----------|
| `test_interrupted_download_cleaned_up` | `.downloading` temp file removal |
| `test_zero_byte_output_triggers_regeneration` | Zero-byte file → delete + action=generate |
| `test_lipsync_beat_no_still_fallback` | Provider failure → RuntimeError, no still produced |

## Verification

```
tests/test_generate_media.py: 14 passed
Full suite: 326 passed, 4 failed (pre-existing test_review.py failures, unrelated)
```

## Acceptance Criteria

1. ✅ Zero-byte, partial, stale, and invalid outputs all fail with clear errors
2. ✅ Download temp files are never left permanently (cleaned on next run)
3. ✅ Required lipsync failures raise RuntimeError (no silent degradation to stills)
4. ✅ All new tests pass, no regressions introduced
