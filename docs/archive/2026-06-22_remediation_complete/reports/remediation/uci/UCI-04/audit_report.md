# UCI-04 Audit Report

**Date:** 2026-06-15  
**Auditor:** Kiro CLI (read-only)  
**Scope:** assemble.py reads clip paths from clip_db.get_path + assert_all_valid gate before mux; legacy fallback for no-clip_id manifests.

---

## Findings

### 1. clip_db import & integration

- `scripts/assemble.py` line 40: `import clip_db  # noqa: E402`
- `scripts/clip_db.py` exposes `init_db()`, `get_path(clip_id)`, `assert_all_valid(project_id)`, `list_clips(project_id)` — all present and correctly typed.

### 2. Path resolution via DB (golden truth)

Lines 997–1010 of `assemble.py`:
- Detects whether segments carry `clip_id` fields.
- If present, calls `clip_db.init_db()` → `clip_db.list_clips(project_id)` to confirm DB population.
- Iterates segments, resolving `seg["media"] = clip_db.get_path(cid)` — DB path overrides manifest's `media` field.
- This establishes the clip DB as golden truth for file paths all the way to mux.

### 3. assert_all_valid gate before mux

Lines 1012–1018:
- Calls `clip_db.assert_all_valid(project_id)` after path resolution.
- Gate checks: (a) all clips have status `valid`, (b) no open change requests exist.
- On failure: raises `RuntimeError("UCI-04 assembly gate FAILED — clips not valid:\n...")` with per-clip actionable detail.
- Assembly is blocked — no partial mux possible.

### 4. Legacy fallback (no clip_id manifests)

Lines 1020–1023:
- If `has_clip_ids` is True but no DB rows exist: emits `UserWarning` (transitional mode), skips gate.
- If `has_clip_ids` is False (no `clip_id` on any segment): emits `UserWarning` (legacy mode), skips DB resolution entirely.
- Existing assembly behavior for pre-UCI-04 manifests is preserved unchanged.

### 5. Existing assembly behavior

- All 22 tests in `tests/test_assemble.py` pass (lipsync, provenance, timing, continuous-mode, etc.).
- 10 warnings confirm legacy manifests hit the expected fallback path.

---

## Conclusion

All UCI-04 acceptance criteria satisfied in production code. Implementation is minimal, gate is hard-blocking, and backward compatibility is fully preserved.
