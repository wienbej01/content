# Engineering Report — S22_T017

## Ticket

Record observed artifact durations after media/overlay artifacts are created or registered.

## Primary agent

DB Feedback Engineer

## Summary

Added `record_observed_artifact_duration()` to `production_repo.py` and updated `link_artifact_to_render_unit()` to copy artifact `duration_ms` into `render_units.actual_render_duration_ms`. This makes observed media duration a reliable DB truth for later drift resolution.

## Implementation

### 1. `record_observed_artifact_duration()` (production_repo.py:849-922)

New function that:
- Looks up the artifact in the DB
- Probes the actual file duration via `MediaProbe.from_path()` (ffprobe)
- Updates `render_units.actual_render_duration_ms` when `render_unit_id` is provided
- Preserves `render_units.required_duration_ms`
- Records a validation row with evidence: artifact_id, render_unit_id, required_duration_ms, actual_duration_ms, delta_ms, artifact_uri, probe_method
- Returns the evidence dict
- Fails with `BLOCKED_DURATION_PROBE_FAILED` for missing artifacts, missing files, or ffprobe failures

### 2. `link_artifact_to_render_unit()` update (production_repo.py:800-834)

Modified to also SELECT `duration_ms` from the artifact and write it to `render_units.actual_render_duration_ms` during the link operation. This ensures observed duration is captured at the moment an artifact is linked to a render unit.

### 3. Tests (tests/test_observed_artifact_duration.py)

10 tests covering:
1. `test_register_artifact_records_duration_ms` — 5.1s fixture → `artifacts.duration_ms` set
2. `test_linked_render_unit_records_actual_render_duration_ms` — link copies duration to `actual_render_duration_ms`
3. `test_required_duration_remains_unchanged` — `required_duration_ms` preserved
4. `test_missing_artifact_fails_with_explicit_error` — nonexistent artifact raises `BLOCKED_DURATION_PROBE_FAILED`
5. `test_corrupt_artifact_file_fails_with_explicit_probe_error` — non-media file raises `BLOCKED_DURATION_PROBE_FAILED`
6. `test_non_video_local_graphic_handled_or_fails` — unparseable non-media fails explicitly
7. `test_re_registering_same_artifact_is_idempotent` — same path+sha returns existing row
8. `test_duration_evidence_in_validation_output` — evidence dict and validation row have all required fields
9. `test_record_observed_artifact_duration_without_render_unit` — works with only artifact_id
10. `test_link_artifact_updates_actual_render_and_preserves_required` — required and actual are distinct columns

## Files changed

| File | Change |
|---|---|
| `scripts/production_repo.py` | +125/-4 lines. Added `record_observed_artifact_duration()`, `ObservedDurationError`. Updated `link_artifact_to_render_unit()`. |
| `tests/test_observed_artifact_duration.py` | New file, 10 tests. |

## Commands run

```bash
python3 -m pytest tests/test_observed_artifact_duration.py -q   # 10 passed
python3 -m pytest tests/e2e/test_crash_matrix.py -q              # 5 passed, 1 skipped
```

## DB columns used

- `artifacts.duration_ms` (existing, 001 migration)
- `render_units.actual_render_duration_ms` (existing, 012 migration)
- `render_units.required_duration_ms` (existing, 001 migration)
- `validations` table (existing, 001 migration)

No new DB columns, no new migrations, no new tables. All columns confirmed present before implementation.

## Non-goals preserved

- No drift resolution
- No media regeneration
- No new DB tables
- No paid APIs called
