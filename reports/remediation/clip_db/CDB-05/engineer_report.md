# CDB-05 Engineer Report — Interactive QA with Clip DB

**Date:** 2026-06-15
**Status:** ✅ Complete

## Summary

`qa_media.py` now interacts bidirectionally with the clip DB: it reads the clip repository before QA, marks passing clips `valid`, and raises typed change requests routed to the owning step for failures.

## Changes

### `scripts/qa_media.py`
1. Added `_classify_issue()` — routes failures to the correct owning step:
   - Audio/lipsync/provenance mismatches → `slice_lipsync` / `re-slice`
   - Missing clips, dimension/coverage/perceptual issues → `generate_media` / `regenerate`

2. At start of `run_qa()`: builds `_clip_id_map` from `clip_db.list_clips(project_id)` — QA reads the DB's current truth before acting.

3. During entry construction: attaches `clip_id` to each QA entry when the beat is tracked in the DB.

4. After all QA checks (including coverage-deficit): for each entry with a `clip_id`:
   - **PASS** → `clip_db.mark_valid(clip_id, validated_by='qa_media')`
   - **FAIL** → `clip_db.request_change(...)` for each issue, routed to the owning step

5. Legacy behavior preserved: entries without `clip_id` (not in DB) are reported as before with no DB interaction.

6. QA still returns `(results, all_pass)` — pipeline sequencing (produce.py) is unaffected.

### `tests/test_cdb05_interactive_qa.py` (6 tests)
| # | Test | Verifies |
|---|------|----------|
| 1 | `test_passing_clip_becomes_valid` | QA pass → clip status = `valid` in DB |
| 2 | `test_short_clip_raises_regenerate` | Coverage deficit → change_request(regenerate, generate_media) |
| 3 | `test_audio_mismatch_routes_to_slice` | Lipsync audio mismatch → change_request(re-slice, slice_lipsync) |
| 4 | `test_missing_clip_routes_to_generate` | Missing file → change_request(regenerate, generate_media) |
| 5 | `test_open_requests_filtered_by_step` | `open_change_requests(project, target_step=X)` routes correctly |
| 6 | `test_qa_returns_summary_with_change_requests` | QA returns summary, does not crash pipeline |

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | qa_media marks passing clips valid in the DB | ✅ |
| 2 | qa_media raises typed change requests routed to correct owning step | ✅ |
| 3 | A clip with an open change request is not 'valid' | ✅ (request_change sets status='change_requested') |
| 4 | open_change_requests routes work to the owning step | ✅ |
| 5 | Legacy (no clip_id) behavior preserved | ✅ |
| 6 | All tests pass; full suite green | ✅ (583 passed) |

## Test Output

```
tests/test_cdb05_interactive_qa.py — 6 passed in 2.94s
tests/test_qa_media.py — 20 passed in 13.33s
Full suite: 583 passed in 134.68s
```
