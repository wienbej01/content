# Engineering Report: S03_T004 Graphic Editorial Quality Report

## Changes made

### `scripts/evals/eval_graphic_editorial.py` (NEW)
Per-graphic editorial quality analysis:
- Classifies editorial role: setup/contrast/summary/callout/transition/missing
- Analyzes text quality: empty, complete thought, capitalization
- Analyzes duration appropriateness: too-short, too-long, readable
- Flags weak graphics (empty text, too short, too long)
- Produces recommended revision

### `tests/test_graphic_editorial.py` (NEW)
16 tests:
| Test class | Tests | Verifies |
|-----------|-------|----------|
| TestClassifyRole | 6 | All role classifications |
| TestTextQuality | 3 | Empty, complete, incomplete |
| TestDuration | 3 | Short, long, ok |
| TestEvalUnit | 3 | Weak/not-weak detection |
| TestEvalProduction | 1 | Real DB returns structure |

## Bad fixture result
```
1 graphic, Status: pass
[S003] role=callout dur=7167ms text_empty=False weak=False
```
Non-stale graphic "WHICH COSTS MORE: SLACK" is a valid callout.
14 stale graphics with empty text show the historical quality gap (F-GFX-002).

## Files changed
```
A scripts/evals/eval_graphic_editorial.py
A tests/test_graphic_editorial.py
```

## Test results: 16/16 pass
