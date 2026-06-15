# CDB-04 Engineer Report

**Ticket:** CDB-04 — reconcile_duration uses clip_db.coverage_for_beat()  
**Date:** 2026-06-15  
**Status:** ✅ Complete

## Problem

`reconcile_duration.py` looked up parent beat IDs (B005, B011) from `beat_timing_map.json` against `media_plan.json` which only contained child IDs (B005a, B005b). Result: full duration reported as deficit even when children clips existed and covered the interval.

## Solution

Rewrote `reconcile()` to:

1. **Prefer clip_db** — calls `clip_db.coverage_for_beat(project_id, beat_id)` which sums all clips sharing a `source_beat_id`, resolving parent→children lineage automatically.
2. **Use actual_dur_sec from DB** — no re-probing files; the DB already has truth from CDB-03's `record_generated`.
3. **Legacy fallback** — if `clip_db.list_clips(project_id)` returns no rows, falls back to the original ffprobe-based logic so old projects still work.

## Changes

| File | Change |
|------|--------|
| `scripts/reconcile_duration.py` | Split into `_reconcile_via_db()` and `_reconcile_via_ffprobe()`; `reconcile()` dispatches based on DB row presence |
| `tests/test_cdb04_reconcile.py` | 6 new tests covering parent→child, deficit, missing slot, single beat, CSV output, legacy fallback |

## Test Results

```
tests/test_cdb04_reconcile.py          6 passed
tests/test_duration_reconciliation.py  6 passed
Full suite:                            577 passed in 128.97s
```

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Resolves parent→children via coverage_for_beat | ✅ |
| 2 | PASSES when children cover parent interval | ✅ |
| 3 | FAILS (named beat + deficit) when short/missing | ✅ |
| 4 | CSV still written | ✅ |
| 5 | Legacy fallback works | ✅ |
| 6 | All tests pass; full suite green | ✅ |
