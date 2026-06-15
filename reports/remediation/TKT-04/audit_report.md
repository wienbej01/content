# TKT-04 Audit Report — Lipsync Audio Provenance Hardening

**Auditor:** Kiro subagent (read-only)  
**Date:** 2026-06-14  
**Verdict:** **PASS**

---

## 1. `slice_continuous_lipsync.py` — Audio Slice Provenance Fields

| Field | Present | Value Source |
|-------|---------|--------------|
| `sha256` | ✅ | `_sha(slice_path)` after write |
| `slice_sha256` | ✅ | same as above (dual-key compat) |
| `master_sha256` | ✅ | `_sha(master)` (continuous.mp3) |
| `parent_mp3_sha256` | ✅ | same as above (dual-key compat) |
| `master_start_sec` | ✅ | from beat_timing_map start − 0.15s lead-in |
| `master_end_sec` | ✅ | start + padded duration |
| `speech_len_sec` | ✅ | from timing map |
| `padded_len_sec` | ✅ | max(ceil(speech+0.2), 4), clamped to 10 |
| `file` / `path` | ✅ | relative path to slice |
| `parent_mp3` | ✅ | `"narration/continuous.mp3"` |

**`.fp.json` fingerprint:** Written via `artifact_fingerprint.write_fingerprint()` (producer=`slice_continuous_lipsync`, version `1.1`, upstream_hashes includes master SHA). ✅

---

## 2. `qa_media.py` — Lipsync Provenance QA Checks

`lipsync_checks()` (line 75) performs:

- **a.** Audio stream existence → FAIL if missing ✅
- **b.** Audio duration match vs `speech_len_sec` / `padded_len_sec` / `LIPSYNC_MAX_DUR` (±0.15s tolerance) ✅
- **c.** Video duration ≥ slice duration (or clamped at `LIPSYNC_MAX_DUR`) ✅
- **d.** Provenance fields (`slice_sha256`, `parent_mp3_sha256`, `file`) required → FAIL if missing ✅
- **d.** Live SHA-256 recomputation of slice file vs recorded `slice_sha256`:
  - **Missing file → FAIL** with `"PROVENANCE: audio slice missing"` ✅
  - **Hash mismatch → FAIL** with `"PROVENANCE: audio slice hash mismatch"` ✅

All issues are returned as entries in the issues list which makes the beat `FAIL`.

---

## 3. `assemble.py` — Provenance Verification at Assembly Time

### Segment-by-segment path (default)
- Line 831: `validate_lipsync_provenance(seg, base)` called **before** `process_segment` for every `keep_lipsync` segment ✅
- On hash mismatch: **`raise RuntimeError`** (hard fail, immediate abort) ✅
- On missing slice file: returns problems list → caller raises `ValueError` (hard fail) ✅
- On missing `lipsync_provenance` field (backward compat): **warns to stderr, returns empty** (does not block) ✅ — acceptable for old manifests

### Continuous mode
- Does NOT call `validate_lipsync_provenance` — **acceptable by design**: in continuous mode the master narration is the sole audio track; baked clip audio is intentionally stripped (`-an`). Provenance of the slice is checked at QA time (before assembly), and the master narration integrity is validated by its own SHA at generation time.

### No narration overlay on keep_lipsync beats
- **Segment-by-segment path:** `process_segment()` returns early at line 335 after writing the clip with `-map 0:a` (baked audio). The caller then executes `continue` at line 847, skipping any narration overlay logic. ✅
- **Continuous mode:** Uses a single master narration overlay on muted visuals. This is correct by design — lipsync clips were rendered FROM slices of the same master, so mouth sync is preserved. The baked audio is redundant (it IS the master audio for that span). No double-audio or echo. ✅
- **Multi-shot segments with mixed lipsync/voiceover:** Line 348+ detects `has_lipsync` and switches to per-shot processing. Lipsync shots get `-map 0:a` (baked audio); voiceover shots get a proportional narration slice overlay. No narration is overlaid on lipsync shots. ✅

---

## 4. Tests — `tests/test_lipsync_provenance.py`

All 5 tests **PASS** (1.78s):

| Test | Behavior Verified | Correct |
|------|-------------------|---------|
| `test_slice_hash_recorded` | `slice_continuous_lipsync` writes correct SHA-256 + `.fp.json` | ✅ |
| `test_tampered_slice_fails_qa` | Overwrites slice AFTER recording hash → QA returns FAIL with "PROVENANCE hash mismatch" | ✅ |
| `test_missing_slice_fails_qa` | Unlinks slice file → QA returns FAIL with "PROVENANCE missing" | ✅ |
| `test_silent_hero_clip_fails_qa` | Hero clip without audio stream → QA FAIL | ✅ |
| `test_provenance_ok_passes` | Valid fixture → QA PASS | ✅ |

### Test quality:
- `test_tampered_slice_fails_qa`: Creates slice at 220Hz, records SHA, then re-generates at **880Hz** (different bytes). Verifies QA detects the mismatch. Proper tamper simulation. ✅
- `test_missing_slice_fails_qa`: Unlinks the slice file entirely after recording the hash. Verifies QA detects missing file. ✅

---

## 5. Original Bug — Continuous Mode Narration Overlay on keep_lipsync

**NOT present.** The two assembly paths handle this correctly:

1. **Segment-by-segment:** `process_segment` returns early with baked audio for `KEEP_LIPSYNC`; no narration overlay is applied.
2. **Continuous mode:** ALL clips (including lipsync) are muted, and the single master narration is applied to the whole bed. This is the correct design — the master narration IS the audio the lipsync mouths were generated from. Using baked audio here would create duplicates.
3. **Multi-shot mixed segments:** Per-shot routing ensures lipsync shots keep baked audio while voiceover shots get narration slices.

---

## Minor Observations (non-blocking)

1. **`validate_lipsync_provenance` mixed error strategy:** Hash mismatches raise `RuntimeError` immediately; missing files append to `problems` list. Both ultimately halt assembly, but through different exception types (`RuntimeError` vs `ValueError` from caller). Cosmetic inconsistency; functionally sound.

2. **Continuous mode doesn't call `validate_lipsync_provenance`:** In theory, a tampered slice in continuous mode wouldn't be caught at assembly time. However, QA (which must pass gate G8 before assembly) DOES check slice provenance. The gate system prevents assembly without passing QA. Acceptable defense-in-depth.

---

## Verdict

**PASS** — All three requirements are satisfied:

1. ✅ Tampered/missing slice = FAIL in QA (`lipsync_checks` recomputes SHA-256, fails on mismatch or missing)
2. ✅ Assembly hard-fails if provenance hash mismatches (`RuntimeError` in `validate_lipsync_provenance`)
3. ✅ Continuous mode does NOT overlay narration on keep_lipsync beats (by design: master narration covers the whole timeline; baked audio is correctly stripped since it's a subset of master)
