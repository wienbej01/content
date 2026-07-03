# Audit Report — S22_T017

## Auditor

Software Auditor (deepseek-v4-pro)

## Audit scope

S22_T017 implementation: record observed artifact durations via ffprobe into existing DB columns.

## Findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | NOTE | Code uses existing `artifacts.duration_ms` and `render_units.actual_render_duration_ms` columns — no migration needed. | Confirmed. Both columns are present from migrations 001 and 012. |
| 2 | NOTE | `record_observed_artifact_duration()` reads artifact metadata, probes file, then opens a second transaction. Connection handling is sequential and correct (first conn closed before transaction opens). | Confirmed. Pattern matches `register_artifact()` style. |
| 3 | NOTE | ffprobe failures raise `ObservedDurationError` with `BLOCKED_DURATION_PROBE_FAILED` prefix. No silent pass. | Confirmed. Three failure paths: missing artifact, missing file, unparseable media. |
| 4 | NOTE | No paid APIs called. All duration probing uses local ffprobe. | Confirmed. |
| 5 | NOTE | `link_artifact_to_render_unit()` already fetches `duration_ms` from artifact when updating render_unit. Good — captures observed duration at link time without extra probe. | Confirmed. |
| 6 | NOTE | Tests cover: positive, negative, missing, corrupt, idempotency, evidence fields, and no-render-unit path. | Confirmed. 10 tests, all passing. |
| 7 | NOTE | `register_artifact()` already stored `duration_ms` on artifact — no duplication. | Confirmed. The new function probes from disk as an additional verification and writes to render_unit. |
| 8 | NOTE | Crash matrix e2e tests still pass — no regression. | Confirmed. 5 passed, 1 skipped (same as baseline). |

## Audit verdict

**PASS** — No BLOCKER or MAJOR findings. Implementation extends existing infrastructure correctly, no regression, tests pass.

## Files audited

- `scripts/production_repo.py` (+125/-4)
- `tests/test_observed_artifact_duration.py` (new, 10 tests)
