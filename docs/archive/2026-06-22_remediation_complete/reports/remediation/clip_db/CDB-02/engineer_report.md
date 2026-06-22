# CDB-02 Engineer Report — clip_db as Path/ID Authority

**Date:** 2026-06-15
**Status:** ✅ Complete — all acceptance criteria met

---

## Summary

`compile_media_prompts.py` now orders every plan beat/slot through `clip_db.order_clip()` at the end of `compile_plan()`. The DB assigns canonical paths and clip IDs, which are written back into the plan beat dicts. The two conflicting path derivations (line 253: `assets/media/{segment_id}/{beat}.mp4`, line 699: `assets/media/{project_id}/{beat}_{slot}.mp4`) are retained as fallback initial values only — they are unconditionally overwritten by the DB-authoritative path whenever `project_id` is present.

---

## Changes Made

### `scripts/compile_media_prompts.py`

1. Added `hashlib` to top-level imports.
2. Added `db_path=None` parameter to `compile_plan()`.
3. Added CDB-02 ordering block after all plan beats are finalized (post-slot expansion, post-lipsync slicing, post-reference rotation, post-chain merge) — before totals computation.
4. Each plan beat gets `clip_id` and DB-authoritative `output_path` written back.
5. `plan_sha256` computed per beat from order-relevant fields for staleness detection.
6. Added clarifying comments to the two old f-string path derivations.

### `scripts/clip_db.py`

1. Fixed `ON CONFLICT` clause in `order_clip()`: changed from `ON CONFLICT(project_id, production_beat_id, slot_id)` to `ON CONFLICT(clip_id)` — the UNIQUE constraint on the composite columns was secondary to the PRIMARY KEY constraint, causing upsert failure on re-compile.

### `tests/conftest.py` (new)

Global autouse fixture that redirects `clip_db._db_path_override` to a temp path for every test, ensuring no test pollutes `db/clips.db`.

### `tests/test_cdb02_ordering.py` (new)

5 tests covering all acceptance criteria:
- `test_compile_orders_clips_in_db` — clip_db has one row per beat after compile
- `test_compile_output_path_comes_from_db` — plan output_path == clip_db.get_path()
- `test_single_canonical_path_format` — all paths follow `assets/media/{project}/{segment}/{file}.mp4`
- `test_slot_clips_ordered_with_lineage` — source_beat_id → production_beat_id → slot_id preserved
- `test_compile_idempotent` — re-compile upserts, no duplicate rows

---

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | compile_plan orders every plan beat/slot into clip_db | ✅ Verified by test_compile_orders_clips_in_db |
| 2 | plan output_path comes FROM the DB (single canonical format) | ✅ Verified by test_compile_output_path_comes_from_db + test_single_canonical_path_format |
| 3 | No two conflicting path formats in compile output | ✅ All output_paths use `assets/media/{project}/{segment}/{file}.mp4` |
| 4 | Lineage (source→production→slot) recorded in DB | ✅ Verified by test_slot_clips_ordered_with_lineage |
| 5 | Idempotent (re-compile upserts, no dupes) | ✅ Verified by test_compile_idempotent |
| 6 | All tests pass; full suite green | ✅ 564 passed |
| 7 | Tests use temp DB | ✅ conftest.py autouse fixture + per-test tmp_path |

---

## Test Results

```
tests/test_cdb02_ordering.py: 5 passed
tests/test_compile_media_prompts.py: 14 passed
tests/test_slot_expansion.py: 9 passed
Full suite: 564 passed in 135s
```

---

## Backward Compatibility

- Storyboards **with** `project_id` (all production usage): paths come from clip_db, single canonical format.
- Storyboards **without** `project_id` (no real-world case but unit tests may omit): the old f-string initial value survives as fallback.
- No existing test expectations needed updating — the conftest.py fixture handles DB isolation transparently.
- The `db_path` parameter is optional; existing callers work unchanged.
