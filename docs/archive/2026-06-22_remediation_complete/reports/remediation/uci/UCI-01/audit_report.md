# UCI-01 Audit Report — Manifest Keyed by clip_id

**Date:** 2026-06-15  
**Auditor:** kiro-cli (read-only)  
**Verdict:** PASS

## Findings

### 1. Duplicate-beat_id check removed ✅

No reference to `"Duplicate beat_id"` exists in `scripts/build_manifest.py` or any script.
The old invariant (which falsely rejected slot-expanded plans sharing a beat_id) is fully excised.

### 2. Duplicate-clip_id check present ✅

Lines 123-130 of `build_manifest.py`:
- Iterates plan beats, extracts `clip_id` (falls back to `beat_id` for legacy).
- Accumulates into `seen_clip_ids`; errors on collision.
- This is the correct uniqueness invariant since slot-expanded and split beats share a `beat_id` but carry distinct `clip_id` values.

### 3. Per-clip timing from plan (required_start_sec / required_end_sec) ✅

Line 153-162: each segment derives `timing_in` / `timing_out` from the plan row's `required_start_sec` / `required_end_sec`. Falls back to `beat_timing_map` only for legacy plans without per-clip timing. Comment explicitly states "UCI-01: NOT from beat_timing_map".

### 4. Segments carry clip_id + source_beat_id, ordered by start ✅

Lines 192-194: segment dict has `clip_id`, `id` (== clip_id), and `source_beat_id`.  
Line 228: `segments.sort(key=lambda s: s["timing_in"])` ensures timeline order.

### 5. Golden-truth gate preserved ✅

Lines 90-114: `clip_db.assert_all_valid()` gate runs before any manifest construction. Failure raises `RuntimeError`, blocking the build.

### 6. No "Duplicate beat_id" in tests or scripts ✅

grep across `scripts/` confirms zero hits. Test file `test_uci01_manifest_clipid.py` explicitly tests that shared `beat_id` with distinct `clip_id` succeeds.
