# Loop Decision — S22_T017

## Verdict

PASS

## Why

All pass gates satisfied:
- Observed artifact duration persisted on `artifacts.duration_ms` and `render_units.actual_render_duration_ms`
- Planned and actual durations stored in distinct columns
- No drift resolution attempted (matches non-goal)
- Artifact registration remains idempotent

No BLOCKER or MAJOR findings from audit or validation. All 10 focused tests and 5 crash matrix tests pass. No regression.

## Files changed

| File | Change |
|---|---|
| `scripts/production_repo.py` | +125/-4: Added `record_observed_artifact_duration()`, `ObservedDurationError`. Updated `link_artifact_to_render_unit()` to set `actual_render_duration_ms`. |
| `tests/test_observed_artifact_duration.py` | New: 10 tests |

## Commands run

```bash
python3 -m pytest tests/test_observed_artifact_duration.py -q   # 10 passed
python3 -m pytest tests/e2e/test_crash_matrix.py -q              # 5 passed, 1 skipped
```

## Evidence

- `tests/test_observed_artifact_duration.py` — 10 passing tests
- DB columns used: `artifacts.duration_ms`, `render_units.actual_render_duration_ms`, `render_units.required_duration_ms` (all existing)
- No new migrations, no new tables, no paid APIs

## Open issues

None.

## Next action

Proceed to S22_T018 (duration drift resolver) which consumes the observed durations recorded here.
