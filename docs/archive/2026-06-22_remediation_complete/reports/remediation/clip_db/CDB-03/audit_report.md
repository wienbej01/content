# CDB-03 Audit Report — generate_media uses clip DB for reuse

**Auditor:** kiro-cli (read-only)  
**Date:** 2026-06-15  
**Verdict:** PASS

---

## 1. can_reuse called before generation

**Status: ✅ PASS**

`generate_media.py` L1084–1093: before any generation attempt, the beat's `clip_id` is read. If present (and not `--force` / `--dry-run`), `can_reuse(clip_id)` is called. Only when it returns `True` does the loop `continue` (skip generation). Otherwise, it prints the rejection reason and proceeds to regenerate.

```python
clip_id = beat.get("clip_id")
if clip_id and not force and not dry_run:
    reusable, reason = can_reuse(clip_id)
    if reusable:
        log_access(clip_id, 'generate_media', 'reuse', reason)
        ...
        continue
    else:
        print(f"  [{bid}] regenerating: {reason}")
```

## 2. Stale/short clip triggers regeneration (core fix)

**Status: ✅ PASS**

`clip_db.can_reuse()` (L223–266) checks `actual_dur_sec < required_dur_sec - tolerance` (tolerance=0.25s). A 10s clip needing 14s returns `False, "actual_dur 10.10s < required 14.00s - tolerance"`.

Manual validation confirmed:
```
can_reuse for 10s clip needing 14s: False | actual_dur 10.10s < required 14.00s - tolerance
PASS: stale-short-clip correctly triggers regeneration
```

Additional `can_reuse` checks: status (stale/failed/change_requested → False), file existence, SHA256 integrity, lipsync audio policy.

## 3. record_generated writes actual attrs after success

**Status: ✅ PASS**

`generate_media.py` L1180–1188: after successful generation and file existence check, `probe_video(out_path)` extracts actual dimensions/duration/audio, then:

```python
record_generated(clip_id, actual_dur_sec=info['duration'],
                 actual_width=info['width'], actual_height=info['height'],
                 actual_has_audio=info['has_audio'],
                 actual_sha256=file_sha256(out_path))
```

`record_generated` (clip_db.py L275) writes these to the `clips` table and sets `status='generated'`.

## 4. Failed generation marks_failed, not generated

**Status: ✅ PASS**

`generate_media.py` L1193–1194: the `except RuntimeError` handler calls `mark_failed(clip_id, str(e)[:500])` which sets `status='failed'` and stores the error in `status_reason`.

`mark_failed` (clip_db.py L297) explicitly sets `status='failed'`, never `'generated'`.

Test `test_failed_generation_marks_failed` confirms: after a provider error, `row["status"] == "failed"`.

## 5. Generates to canonical DB path (slot paths)

**Status: ✅ PASS**

`generate_media.py` L1112–1115: when `clip_id` is set, `get_path(clip_id)` is called and the generation output path is overridden to the canonical DB path. This fixes the missing-slot bug where derived paths didn't match slot-suffixed paths.

Tests verify:
- `test_generates_to_canonical_db_path`: asserts `op == expected_full` inside the mock
- `test_slot_clip_generates_to_slot_path`: asserts `"B007_B007-s0.mp4"` in the generation path

## 6. Safety preserved

**Status: ✅ PASS**

| Safety mechanism | Evidence |
|---|---|
| `require_gates` | L1039: called before any generation if not dry_run/force_unsafe |
| No still fallback for lipsync | L1152 comment + L1166 raises RuntimeError if lipsync retries exhaust |
| Atomic download | `_atomic_download` (L568) used at L396 and L996; temp file + ffprobe validate + atomic rename |

## 7. Tests pass, no paid APIs

**Status: ✅ PASS**

- `tests/test_cdb03_generate_reuse.py`: 7/7 passed
- `tests/test_generate_media.py`: 14/14 passed
- Full suite: **571 passed** in 136s
- All generation calls are mocked (`patch("generate_media._generate_beat_clip")`); no real Higgsfield/ElevenLabs calls.

---

## Summary

All 7 audit criteria pass. CDB-03 correctly wires clip_db into the generation loop: stale clips are caught by duration/SHA/status checks, generation results are persisted, failures are recorded distinctly, canonical paths are used, and all existing safety mechanisms (gates, no-still-fallback, atomic download) remain intact.
