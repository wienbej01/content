# CDB-01 Engineer Report — Clip/Slot Authority Database

## Summary

Built `scripts/clip_db.py` — the single-source-of-truth manager for clip IDs, canonical paths, status lifecycle, and interactive change requests. No pipeline wiring yet (CDB-02+).

## Deliverables

| File | Purpose |
|------|---------|
| `scripts/clip_db.py` | Manager module + CLI (530 lines) |
| `tests/test_clip_db.py` | 16 focused tests (245 lines) |

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | clip_db.py with all API functions + CLI | ✅ |
| 2 | ONE canonical path rule (`_canonical_path`), deterministic | ✅ |
| 3 | `can_reuse` checks duration/sha/status/policy | ✅ |
| 4 | Change-request loop: request drops out of valid, resolve returns to flow | ✅ |
| 5 | `assert_all_valid` is the golden-truth gate | ✅ |
| 6 | `coverage_for_beat` resolves parent→children | ✅ |
| 7 | All 16 tests pass; full suite green (559 passed) | ✅ |
| 8 | Tests use temp DB, never touch real db/clips.db | ✅ |

## API Surface

### Ordering
- `order_clip(...)` — upsert with canonical ID + path
- `order_clips(project_id, plan_beats)` — bulk from media-plan dicts

### Reuse Authority
- `can_reuse(clip_id, tolerance=0.25)` — checks file exists, sha match, duration, status, audio policy

### Status Transitions
- `record_generated(...)`, `mark_valid(...)`, `mark_failed(...)`, `mark_stale(...)`

### Change-Request Loop (golden-truth mechanism)
- `request_change(clip_id, requested_by, target_step, change_type, reason)`
- `open_change_requests(project_id, target_step=None)`
- `resolve_change(clip_id, resolved_by, outcome)`
- `apply_human_override(clip_id, decision, note)`
- `assert_all_valid(project_id)` — GATE for assembly

### Coverage Authority
- `coverage_for_beat(project_id, source_beat_id)` — resolves parent→children

### Lookups
- `get_clip(clip_id)`, `get_path(clip_id)`, `list_clips(project_id, status)`

### CLI
```
python3 scripts/clip_db.py init
python3 scripts/clip_db.py list <project_id> [--status STATUS]
python3 scripts/clip_db.py show <clip_id>
python3 scripts/clip_db.py coverage <project_id> <source_beat_id>
python3 scripts/clip_db.py requests <project_id> [--step STEP]
python3 scripts/clip_db.py assert-valid <project_id>
```

## Canonical Path Rule

```python
def _canonical_path(project_id, segment_id, production_beat_id, slot_id=None):
    filename = f"{production_beat_id}_{slot_id}.mp4" if slot_id else f"{production_beat_id}.mp4"
    return f"assets/media/{project_id}/{segment_id}/{filename}"
```

Single function. Deterministic. No other step computes paths.

## Test Results

```
tests/test_clip_db.py::test_init_creates_tables PASSED
tests/test_clip_db.py::test_order_clip_assigns_canonical_path_and_id PASSED
tests/test_clip_db.py::test_canonical_path_is_deterministic PASSED
tests/test_clip_db.py::test_slot_clip_path_includes_slot_id PASSED
tests/test_clip_db.py::test_can_reuse_false_when_file_missing PASSED
tests/test_clip_db.py::test_can_reuse_false_when_duration_too_short PASSED
tests/test_clip_db.py::test_can_reuse_false_when_change_requested PASSED
tests/test_clip_db.py::test_can_reuse_true_when_valid_and_matches PASSED
tests/test_clip_db.py::test_request_change_drops_clip_out_of_valid PASSED
tests/test_clip_db.py::test_resolve_change_returns_clip_to_flow PASSED
tests/test_clip_db.py::test_assert_all_valid_fails_with_open_request PASSED
tests/test_clip_db.py::test_assert_all_valid_passes_when_all_valid PASSED
tests/test_clip_db.py::test_coverage_for_beat_sums_children PASSED
tests/test_clip_db.py::test_coverage_for_beat_reports_deficit PASSED
tests/test_clip_db.py::test_access_log_records_actions PASSED
tests/test_clip_db.py::test_open_change_requests_routes_to_target_step PASSED
16 passed in 0.15s

Full suite: 559 passed in 133.78s
```

## Design Decisions

1. **Test isolation via `_db_path_override`** — module global + `db_path` param on all functions. Tests set the override in a fixture; production code uses the default `db/clips.db`.
2. **Mirrors content_db.py style** — stdlib sqlite3, `sqlite3.Row` factory, `get_db()`/`init_db()` pattern, argparse CLI.
3. **SHA-256 reuses artifact_fingerprint.py approach** — same chunked read pattern (no dependency import needed, the hash logic is trivial).
4. **Resolve returns to `ordered`** — after a change request is resolved, the clip re-enters the generation flow at `ordered` status (not auto-promoted to valid).
5. **No pipeline wiring** — this is a standalone foundation. CDB-02+ tickets wire each step.

## Next Steps (CDB-02)

Wire `compile_media_plan.py` to call `order_clips()` so the DB becomes the path authority.
