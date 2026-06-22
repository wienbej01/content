# TKT-06 Audit Report

**Date:** 2026-06-14  
**Auditor:** Kiro (read-only)  
**Scope:** `scripts/generate_media.py` — atomic download + no-still-fallback for lipsync

---

## 1. Atomic Download

**Status: ✅ IMPLEMENTED**

`_atomic_download()` (line 558) implements the full atomic pattern:

1. Downloads to a `.downloading` temp file.
2. Validates non-zero size.
3. Validates ffprobe shows a video stream with non-zero width.
4. Validates duration is within [0.5×, 2.0×] of expected.
5. Atomically renames via `os.replace()` to the final path.
6. On any failure: temp file is unlinked before re-raising.

Stale `.downloading` files from interrupted runs are cleaned by `_cleanup_stale_downloads()` (line 551) before each download.

---

## 2. No Still Fallback for Lipsync

**Status: ✅ IMPLEMENTED**

The retry/fallback dispatch (line ~1154) enforces:

```python
if beat.get("lipsync_required"):
    raise RuntimeError(
        f"{bid}: hero_lipsync generation failed after retries — "
        f"no still fallback allowed (zero silent degradation). ...")
```

Only non-lipsync beats fall through to `_still_kenburns()`. The RuntimeError propagates up and causes a hard failure of the entire run (line 1187: `raise`).

Additional hard-fail points for lipsync:
- Missing `audio_path` → RuntimeError (line 359, line ~950)
- Missing reference image → RuntimeError (line ~940)
- Missing `audio_slice` in media plan → RuntimeError (line ~1149)
- Banned model → RuntimeError (line 898)

---

## 3. Code Path Analysis: Silent Degradation Risk

**Finding: NO path exists** where `lipsync_required=True` silently falls back to a still image.

The `_still_kenburns()` function (line 851) is only reachable via:
1. Explicit `shot_type == "still_kenburns"` routing (correct — these beats never have `lipsync_required`).
2. Fallback after retry failure — gated by `if beat.get("lipsync_required")` check which raises instead.

---

## 4. Test Coverage

14/14 tests pass, including:
- `test_interrupted_download_cleaned_up` — validates `.downloading` cleanup
- `test_zero_byte_output_triggers_regeneration` — validates corrupt file detection
- `test_lipsync_beat_no_still_fallback` — verifies RuntimeError on provider failure for lipsync beats, confirms no still produced at output path

---

## 5. Observations

- The 4 failing tests in the full suite (`tests/test_review.py`) are unrelated to TKT-06.
- Full suite: 326 passed, 4 failed (review module only).
