# CDB-01 Audit Report — Clip Authority DB Manager

**Date:** 2026-06-15  
**Auditor:** Kiro (subagent)  
**Scope:** scripts/clip_db.py + tests/test_clip_db.py vs docs/CLIP_DB_DESIGN.md  
**Verdict:** PASS

---

## 1. ONE Canonical Path Rule

**Requirement:** Single function computes all clip paths; no scattered derivation.

**Finding:** PASS  
- `_canonical_path()` at line 127 is the sole path derivation function.
- Format: `assets/media/{project_id}/{segment_id}/{filename}` where filename includes slot_id if present.
- `order_clip()` calls `_canonical_path()` and stores result in `output_path` column.
- No other function constructs paths from components.
- `grep` for `assets/media` in clip_db.py returns only line 130 (inside `_canonical_path`).

---

## 2. can_reuse Checks Actual Attributes (Not Just File Existence)

**Requirement:** Reuse checks duration + SHA + status + audio policy, not just file-exists.

**Finding:** PASS  
`can_reuse()` (line 218) performs five sequential checks:

| # | Check | Rejects when |
|---|-------|-------------|
| 1 | Status | status in (stale, change_requested, failed) |
| 2 | File existence | file missing at output_path |
| 3 | SHA-256 integrity | actual file hash ≠ recorded actual_sha256 |
| 4 | Duration adequacy | actual_dur < required_dur - tolerance (0.25s) |
| 5 | Audio policy | lipsync_required but clip has no audio |

This matches the design: "Returns True only if: file exists at canonical output_path AND actual_sha256 matches recorded AND plan_sha256 unchanged AND actual_dur_sec covers required_dur_sec (within tolerance) AND audio policy satisfied."

---

## 3. Change-Request Loop

**Requirement:** request_change drops clip out of valid; resolve returns to ordered; assert_all_valid fails on any open request.

**Finding:** PASS

- `request_change()` (line 314): INSERTs into clip_change_requests with status='open', UPDATEs clips.status to 'change_requested'.
- `resolve_change()` (line 348): UPDATEs requests status='resolved', returns clip to 'ordered' (re-enters flow).
- `assert_all_valid()` (line 373): queries for ANY clip not in 'valid' AND any open change request; returns False if either set is non-empty.

State machine enforced: valid → change_requested → (resolve) → ordered → generated → valid.

---

## 4. assert_all_valid as Assembly Gate

**Requirement:** Fails on any non-valid clip OR open change request.

**Finding:** PASS  
Two queries:
1. `SELECT ... WHERE project_id=? AND status != 'valid'` — catches ordered/generated/stale/failed/change_requested clips.
2. `SELECT ... FROM clip_change_requests ... WHERE status='open'` — catches lingering open requests even if clip somehow returned to valid (belt-and-suspenders).

Both result sets combined → if non-empty, returns `(False, problems)`.

---

## 5. coverage_for_beat Resolves Parent→Children

**Requirement:** Sums all clips sharing source_beat_id to report coverage.

**Finding:** PASS  
`coverage_for_beat()` (line 394): queries `WHERE source_beat_id=?`, then sums `required_dur_sec` and `actual_dur_sec` across all matching rows. Reports `deficit = max(0, required - available)` and `all_present` flag. This correctly resolves B005→{B005a, B005b} lineage via the source_beat_id column.

---

## 6. Tests Use Temp DB

**Requirement:** Tests never touch the real db/clips.db.

**Finding:** PASS  
- `tmp_db` fixture (autouse) at line 18: creates `tmp_path / "test_clips.db"`, sets `_db_path_override`, yields path, resets override on teardown.
- All test functions receive and pass `tmp_db` (or use the override mechanism).
- No reference to `db/clips.db` in test code.

---

## 7. No Pipeline Wiring (CDB-01 scope)

**Requirement:** No other pipeline scripts import clip_db yet.

**Finding:** PASS  
```
grep -rn 'clip_db\|import clip_db' scripts/produce.py scripts/compile_media_prompts.py \
    scripts/generate_media.py scripts/reconcile_duration.py → (empty)
```
clip_db.py is self-contained. Pipeline integration is deferred to CDB-02+.

---

## 8. Schema Conformance to Design Doc

| Design element | Implementation | Status |
|----------------|---------------|--------|
| clips table with all specified columns | Lines 28–73 | ✅ |
| clip_access_log table | Lines 75–84 | ✅ |
| clip_change_requests table | Lines 86–99 | ✅ |
| order_clips() bulk API | Line 185 | ✅ |
| can_reuse() with reason | Line 218 | ✅ |
| record_generated() | Line 265 | ✅ |
| mark_valid / mark_failed / mark_stale | Lines 279/289/295 | ✅ |
| request_change() | Line 314 | ✅ |
| open_change_requests(target_step) | Line 330 | ✅ |
| resolve_change() | Line 348 | ✅ |
| apply_human_override() | Line 363 | ✅ |
| assert_all_valid() gate | Line 373 | ✅ |
| coverage_for_beat() | Line 394 | ✅ |
| get_clip / get_path / list_clips | Lines 414–433 | ✅ |
| log_access() | Line 436 | ✅ |
| CLI interface | Lines 445–497 | ✅ |

---

## 9. Code Quality

- Clean Python 3, snake_case, argparse CLI pattern.
- Module + function docstrings present.
- WAL journal mode for SQLite concurrency.
- db_path parameter threading for testability.
- No external dependencies beyond stdlib + sqlite3.

---

## Summary

All 7 audit criteria pass. The implementation faithfully follows CLIP_DB_DESIGN.md, enforces the golden-truth invariant, and is properly scoped to CDB-01 (manager only, no pipeline wiring).
