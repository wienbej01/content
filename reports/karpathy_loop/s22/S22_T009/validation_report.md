# Validation Report — S22_T009

## Validator

Software Validator (automated)

## Validation commands

### 1. Focused tests
```bash
$ python3 -m pytest tests/test_storyboard_timing_policy.py -q
...............                                                          [100%]
15 passed in 0.05s
```

Result: **15 passed, 0 failed.**

### 2. CLI dry-run on valid fixture
```bash
$ python3 scripts/validate_timing_drift_policy.py \
    tests/fixtures/storyboard_v2/valid_semantic_storyboard.json
TIMING DRIFT POLICY: PASS
```

### 3. CLI dry-run on invalid fixtures

```bash
$ python3 scripts/validate_timing_drift_policy.py \
    tests/fixtures/storyboard_v2/timing_missing_planned_duration.json
TIMING ERROR: [BLOCKER] SH001: BLOCKED_MISSING_PLANNED_DURATION: shot 'SH001' ...

$ python3 scripts/validate_timing_drift_policy.py \
    tests/fixtures/storyboard_v2/timing_hero_lipsync_pad_only.json
TIMING ERROR: [BLOCKER] SH001: BLOCKED_HERO_LIPSYNC_PAD_ONLY: ...
```

All negative fixtures produce correct BLOCKER errors with shot ID and field path.

### 4. JSON output mode
```bash
$ python3 scripts/validate_timing_drift_policy.py \
    tests/fixtures/storyboard_v2/timing_unknown_drift_policy.json \
    --output-json /tmp/timing_result.json
```
Output JSON contains `task`, `status`, `errors` array, and `error_count`. Verified correct.

### 5. Existing test regression
```bash
$ python3 -m pytest tests/test_storyboard_v2_schema.py -q  # 22 passed
$ python3 -m pytest tests/test_storyboard_semantic_alignment.py -q  # 13 passed
$ python3 -m pytest tests/test_storyboard*.py tests/test_production_storyboard*.py -q  # 117 passed
```

No regression in existing tests.

## Evidence files

- `tests/test_storyboard_timing_policy.py` — All 15 timing policy tests.
- `tests/fixtures/storyboard_v2/timing_*.json` — 8 fixture files covering all negative scenarios.
- `scripts/validate_timing_drift_policy.py` — Validator module.

## Fixture realism

Fixtures use realistic timing values:
- `planned_duration_sec: 5.0`, `min: 3.0`, `max: 6.5` (realistic B-roll range).
- `planned_duration_sec: 8.5`, `min: 4.0`, `max: 12.0` (realistic hero lipsync range).
- Drift policy values match realistic real-world policies (trim_ok, pad_ok, extend_still_ok).

## Verdict

**PASS.** All validation gates satisfied:
- Focused tests pass.
- CLI works correctly with valid and invalid inputs.
- JSON output mode produces machine-readable results.
- Existing tests show no regression.
- No drift resolution is implemented (confirmed).
- No paid APIs are called (confirmed).
- No Python creative fallback exists (confirmed).
