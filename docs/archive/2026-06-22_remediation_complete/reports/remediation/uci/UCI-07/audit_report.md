# UCI-07 Audit Report

**Date:** 2026-06-15  
**Auditor:** Kiro (read-only validation agent)  
**Scope:** Unified clip_id end-to-end on slot+split beats, per-clip manifest, clip_id-keyed feedback loop with sibling independence, assert_all_valid gating

---

## 1. clip_id Generation (clip_db._clip_id)

**Formula:** `{project_id}::{production_beat_id}::{slot_id|"whole"}`

- Slot-expanded beats: slot_id suffix distinguishes siblings → `proj::B003::B003-s0`, `proj::B003::B003-s1`
- Split beats: production_beat_id already unique per split child (e.g. B002a, B002b) → `proj::B002a::whole`, `proj::B002b::whole`
- Whole beats: suffix = "whole" → `proj::C003::whole`
- ON CONFLICT(clip_id) → upsert guarantees idempotent re-compile

**Verdict:** ✅ Uniqueness guaranteed by design across all beat types.

---

## 2. Slot+Split Full Chain (E2E)

Test: `TestSlotAndSplitFullChain::test_slot_and_split_full_chain`

Covers:
- 3-slot coverage expansion (source_beat_id=A001 → 3 clip_ids with slot_id suffix)
- 2-split beat (source_beat_id=B002 → B002a, B002b production_beat_ids)
- 2 whole beats (C003, D004)
- 7 clips total, all unique clip_ids verified
- record_generated + mark_valid → coverage_for_beat confirms all_present=True
- build_manifest produces 7 segments, each keyed by clip_id, contiguous timing
- assemble path resolution verified via clip_db.get_path()

**Verdict:** ✅ Full chain slot+split → manifest → assemble resolves cleanly.

---

## 3. Per-Clip Manifest (build_manifest.py)

Key findings at lines 123-216:
- Uniqueness check: iterates plan beats, detects duplicate clip_id (not beat_id) — hard error if found
- Segment construction: one segment per plan row, keyed by `b.get("clip_id") or bid`
- Per-clip timing: uses `required_start_sec` / `required_end_sec` from each plan row (not beat_timing_map)
- CDB-06 golden-truth gate: calls `clip_db.assert_all_valid(project_id)` — hard RuntimeError on failure

**Verdict:** ✅ Manifest is 1:1 with clips, keyed on clip_id.

---

## 4. Feedback Loop Keyed on clip_id

Test: `TestFeedbackLoopKeyedOnClipId::test_feedback_loop_keyed_on_clip_id`

Mechanism (clip_db.py):
- `request_change(clip_id, ...)` — inserts into `clip_change_requests` table, sets clip status to `change_requested` (keyed by clip_id PK)
- `resolve_change(clip_id, ...)` — resolves open requests for that clip_id only, returns clip to `ordered`
- `assert_all_valid` — queries clips with status != 'valid' OR open change requests; returns problem list keyed by clip_id

Test confirms:
- Change request on slot s0 does NOT affect sibling slot s1
- assert_all_valid fails citing only s0's clip_id
- After resolve + re-generate + mark_valid → assert_all_valid passes

**Verdict:** ✅ Feedback loop is clip_id-scoped; siblings independent.

---

## 5. Sibling-Slot Independence

Test: `TestSiblingSlotsIndependent::test_sibling_slots_independent`

- Two slots share source_beat_id but have distinct clip_ids
- Change request on one leaves sibling in `valid` status
- assert_all_valid correctly isolates the problematic clip_id

**Verdict:** ✅ No cross-contamination between sibling slots.

---

## 6. assert_all_valid Gating

Enforcement points:
1. **build_manifest.py (line 97):** Calls `assert_all_valid(project_id)` → RuntimeError blocks manifest build
2. **assemble.py (line 1012):** Calls `assert_all_valid(project_id)` → RuntimeError blocks assembly

Both gates are clip_id-level: the error messages include clip_id for each problem.

**Verdict:** ✅ Double-gated; no manifest or assembly can proceed with invalid clips.

---

## 7. Audited Project (how_to_use_ai_to_better_organize_your_de_short)

```
compile errors: 0 | orphans: 0 | dup-key: 0
clips: 16 | unique: 16 | all unique: True
```

The production project compiles with:
- Zero orphan beats
- Zero duplicate clip_id keys
- 16 clips with 16 unique clip_ids

**Verdict:** ✅ Production project clean.

---

## 8. Full Test Suite

```
628 passed, 12 warnings in 145.72s
```

All 628 tests pass. The 12 warnings are expected UCI-04 legacy-mode notices from tests that use pre-clip_id fixtures.

**Verdict:** ✅ No regressions.

---

## Summary

| Criterion | Status |
|-----------|--------|
| Slot+split beats → unique clip_ids, zero drops | ✅ PASS |
| Manifest: one segment per clip, keyed by clip_id | ✅ PASS |
| Feedback loop keyed on clip_id, sibling independence | ✅ PASS |
| assert_all_valid gates manifest + assemble | ✅ PASS |
| Audited project compiles cleanly (0 errors, 16 unique clip_ids) | ✅ PASS |
| Full suite green (628/628) | ✅ PASS |

**Overall: PASS**
