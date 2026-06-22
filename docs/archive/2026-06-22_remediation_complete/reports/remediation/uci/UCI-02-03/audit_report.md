# Audit Report — UCI-02 + UCI-03

**Date:** 2026-06-15  
**Auditor:** Kiro (read-only)  
**Scope:** `scripts/build_manifest.py`, `scripts/reconcile_duration.py`, `scripts/clip_db.py`  
**Verdict:** PASS

---

## UCI-02: Remove timing-map-vs-plan cardinality gate

### Requirement

The beat_timing_map is frozen at creative storyboard time and is never rebuilt after production splits (e.g. B011 → B011a/B011b). A cardinality check comparing `len(timing_map.beats)` against `len(plan.beats)` would hard-fail on any project with splits. This check must be absent.

### Findings

| Check | Result |
|-------|--------|
| No cardinality comparison in `build_manifest.py` | ✅ Confirmed — lines 135-138 contain an explicit comment documenting the removal |
| No fallback that re-introduces it | ✅ grep across `scripts/` found zero count-based timing-map vs plan assertions |
| Per-clip timing (`required_start_sec` / `required_end_sec`) used instead | ✅ Lines 149-158 in `build_manifest.py` — falls back to timing_map only for legacy plans missing per-clip keys |
| Split children (e.g. B011a, B011b) build correctly without timing_map entry | ✅ Test `test_split_children_no_timing_map_error` passes |

### Code Evidence (`build_manifest.py:135-138`)

```python
# UCI-02: timing-map-vs-plan cardinality check REMOVED.
# The beat_timing_map is frozen at the creative storyboard (pre-split) and never
# rebuilt after production splits (B011→B011a/B011b). Per-clip timing now comes
# from each clip's own required_start_sec/required_end_sec in the plan.
```

---

## UCI-03: Reconcile keys by clip_id, no silent drops

### Requirement

1. Reconciliation must iterate by **clip_id** (not beat_id) so multi-slot beats are never collapsed via `{beat_id: beat}` dict overwrite.  
2. A **count guard** must raise `RuntimeError` if any DB clip is dropped from evaluation.  
3. `coverage_for_beat()` must return all slots (clip_ids) for a given source_beat_id.

### Findings

| Check | Result |
|-------|--------|
| `_reconcile_via_db` iterates `all_db_clips` by `clip["clip_id"]` | ✅ Line 89-90 |
| No `{beat_id: beat}` dict construction in reconcile path | ✅ Confirmed — only list iteration |
| Count guard: `dropped = all_db_clip_ids - evaluated_clip_ids` raises `RuntimeError` | ✅ Lines 118-124 |
| `coverage_for_beat()` returns `{"slots": [clip_id, ...]}` from SQL query (no dedup) | ✅ `clip_db.py:399-418` |
| Runtime test: 3-slot beat B003 → all 3 counted | ✅ Inline test passed |
| Test `test_no_beat_id_dict_overwrite` | ✅ Passed |
| Test `test_reconcile_no_silent_slot_drop` | ✅ Passed |
| Test `test_reconcile_counts_all_clips` | ✅ Passed |

### Code Evidence (`reconcile_duration.py:118-124`)

```python
# UCI-03 COUNT GUARD: every DB clip must have been evaluated (no silent drops)
all_db_clip_ids = {c["clip_id"] for c in all_db_clips}
dropped = all_db_clip_ids - evaluated_clip_ids
if dropped:
    raise RuntimeError(
        f"RECONCILE GUARD FAILED: {len(dropped)} clip(s) silently dropped from "
        f"reconciliation: {sorted(dropped)}"
    )
```

---

## Test Coverage

| Test file | Tests | Status |
|-----------|-------|--------|
| `test_uci02_uci03_timing_reconcile.py` | 6 | ✅ All passed |
| `test_duration_reconciliation.py` | 6 | ✅ All passed |
| `test_cdb04_reconcile.py` | 6 | ✅ All passed |
| `test_manifest_builder.py` | 11 | ✅ All passed |
| **Full suite** | **615** | ✅ **All passed (141s)** |

---

## Conclusion

Both UCI-02 and UCI-03 are correctly implemented. The timing-map cardinality gate is gone, replaced by per-clip timing. Reconciliation is keyed by clip_id with a hard-fail count guard preventing silent drops.
