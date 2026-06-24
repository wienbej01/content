# Engineering Report: S02_T004 Visual Bed Duration Contract

## Changes made

### `scripts/assemble.py` — tightened 3 duration thresholds

| Check | Old (120s) | New | Rationale |
|-------|-----------|-----|-----------|
| Contract total vs narration (line 968) | > 120.0 | > 3.0 | Clip timing must match narration within freeze-pad limits |
| Visual bed vs narration (line 1074) | > 120.0 | > 3.0 | Pre-mux catches excessive shortfall before ffmpeg mux |
| Post-mux output vs narration (line 1110) | > 120.0 | > 1.5 | Final integrity — encoding drift should be minimal |

Existing thresholds: MAX_FREEZE=0.5s, TAIL_PAD=0.25s (unchanged).

### Tests: `tests/test_visual_bed_duration.py` (NEW)
7 tests verifying all thresholds are realistic.

## Files changed
```
M scripts/assemble.py           (3 threshold values)
A tests/test_visual_bed_duration.py
```

## Test results: 7/7 pass
