# UCI-02 + UCI-03 Engineer Report

**Date:** 2026-06-15
**Status:** ✅ Complete — all tests pass, full suite green (615 tests)

---

## UCI-02: Kill the stale timing-map cardinality gate

### Problem
`build_manifest.py` had a cardinality check (lines 136-139) that iterated `timing_by_id` keys and errored if any beat_id was present in the timing map but not in the media plan. After production splits (B011→B011a/B011b), the parent beat_id remains in the timing map (frozen at creative storyboard) but the plan only has the children — causing a hard failure.

### Fix
Removed the `for bid in timing_by_id: if bid not in plan_beat_ids: errors.append(...)` block entirely. Replaced with a comment explaining the architectural decision: per-clip timing comes from `required_start_sec`/`required_end_sec` in each plan row (UCI-01), not from a parent-keyed timing map.

The timeline total check remains (sum of segment durations vs `timing_map.total_duration`) as a legitimate validation that the plan accounts for the full narration.

**File:** `scripts/build_manifest.py`

---

## UCI-03: reconcile keys by clip_id, no silent drops

### Problem
`_reconcile_via_db` iterated `timing["beats"]` (the stale, parent-keyed timing map) and built `plan_beats = {b["beat_id"]: b ...}` which overwrites when multiple clips share a beat_id (slots). This caused silent slot drops — only the last slot survived.

### Fix
Rewrote `_reconcile_via_db` to:
1. **Iterate all DB clips** for the project (`clip_db.list_clips(project_id)`) instead of timing-map beats.
2. **Key rows by clip_id** — each row in the reconciliation output uses `clip_id`, not `beat_id`.
3. **Use per-clip `required_dur_sec`** from the DB (set at order time from `required_start_sec`/`required_end_sec`), not the parent timing map.
4. **Count guard:** After iteration, verifies `all_db_clip_ids == evaluated_clip_ids`. If any clip is silently dropped, raises `RuntimeError` naming the dropped clips.

Also rewrote `_reconcile_via_ffprobe` (legacy fallback) to iterate plan beats by `clip_id` instead of building a `{beat_id: beat}` dict that overwrites.

**File:** `scripts/reconcile_duration.py`

---

## Test updates

### New: `tests/test_uci02_uci03_timing_reconcile.py` (6 tests)
| Test | Verifies |
|------|----------|
| `test_split_children_no_timing_map_error` | B011→B011a/B011b in plan, B011 in timing_map — no error |
| `test_per_clip_timing_used` | Manifest segments use per-clip intervals, not timing-map lookup |
| `test_reconcile_no_silent_slot_drop` | B003×3 slots — all 3 evaluated |
| `test_reconcile_counts_all_clips` | Count guard structure — all clips accounted for |
| `test_no_beat_id_dict_overwrite` | Same beat_id slots appear as separate rows |
| `test_per_clip_timing_used_reconcile` | Per-clip `required_dur_sec` used, not parent 20s |

### Updated existing tests
- `tests/test_cdb04_reconcile.py`: Updated `test_deficit_when_children_short` (now 2 per-clip failures, not 1 grouped) and `test_missing_slot_detected` (failure key is clip_id, not beat_id)
- `tests/test_manifest_builder.py`: Updated `test_missing_beat_fails` — now verifies "Timeline mismatch" error since cardinality check was intentionally removed

---

## Verification

```
$ python3 -m pytest tests/test_uci02_uci03_timing_reconcile.py tests/test_duration_reconciliation.py tests/test_cdb04_reconcile.py tests/test_manifest_builder.py -v
29 passed in 3.15s

$ python3 -m pytest -q
615 passed in 145.58s
```

---

## Acceptance criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | No timing-map-vs-plan cardinality check breaks on split children | ✅ |
| 2 | Per-clip timing from the clip's own interval | ✅ |
| 3 | reconcile keys by clip_id / coverage_for_beat — no silent slot drops | ✅ |
| 4 | Count guard fails loudly if any clip is dropped | ✅ |
| 5 | All tests pass; full suite green | ✅ (615 passed) |
