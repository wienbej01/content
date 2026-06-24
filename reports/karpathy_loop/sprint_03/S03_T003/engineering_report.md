# Engineering Report: S03_T003 Static Graphic Hold Gate

## Changes made

### `scripts/assemble_db.py` (MODIFIED)
Graduated hold thresholds with `hold`-label bypass:
- `LOCAL_GRAPHIC_MAX_DURATION_MS`: 15000 → **4000** (warn threshold)
- `LOCAL_GRAPHIC_FAIL_DURATION_MS`: **6000** (new fail threshold)
- `_validate_timeline_heuristics()` now:
  - Warns at 4s+ without `hold` in label
  - Raises AssemblyError at 6s+ without `hold` in label
  - Allows any duration with explicit `hold` in label

### `scripts/evals/eval_static_hold.py` (NEW)
Eval that checks local graphic units against hold thresholds.

### `tests/test_static_hold_gate.py` (NEW)
9 tests:
| Test | Verifies |
|------|----------|
| test_warn_threshold_correct | 4000ms |
| test_fail_threshold_correct | 6000ms |
| test_fail_greater_than_warn | 6000 > 4000 |
| test_short_hold_passes | 3s passes |
| test_hold_between_warn_and_fail_warns | 5s warns |
| test_hold_over_fail_raises | 7s fails |
| test_hold_over_fail_with_hold_marker_passes | 7s + "hold" label passes |
| test_non_graphic_bypasses | Non-graphic not checked |
| test_eval_real_production | Bad fixture → fail |

## Bad fixture result
```
[S003] 7167ms → status=fail
```
The known bad 7.125s static hold is correctly flagged as `fail`.

## Files changed
```
M scripts/assemble_db.py    (thresholds + gate)
A scripts/evals/eval_static_hold.py
A tests/test_static_hold_gate.py
```

## Test results: 9/9 pass
