# Engineering Report: S03_T001 Deterministic Graphics Eval

## Changes made

### 1. `scripts/media_service.py` (MODIFIED)
`_qa_local_graphic()` — added text length bounds check:
- Extracts text from `deterministic_text_spec`
- Fail: text too long (> 500 chars)
- Fail: text empty (< 1 char)
- Records `text_length`, `text_length_ok` in QA evidence

### 2. `scripts/evals/eval_deterministic_graphics.py` (NEW)
Eval that verifies per-graphic QA gates:
- Checks deterministic_text_spec exists
- Checks text length within bounds
- Checks QA validation records contain expected fields

### 3. `tests/test_deterministic_graphics.py` (NEW)
5 tests:
| Test | Verifies |
|------|----------|
| test_text_length_ok | Normal text passes |
| test_text_too_long_fails | >500 chars blocked |
| test_empty_text_fails | Empty string blocked |
| test_eval_detects_missing_dts | No DTS → fail |
| test_eval_with_real_production | Real DB returns structure |

## Files changed
```
M scripts/media_service.py          (+17 lines: text length check)
A scripts/evals/eval_deterministic_graphics.py
A tests/test_deterministic_graphics.py
```

## Test results: 5/5 pass
