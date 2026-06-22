# TKT-14 Validation Report — E2E Smoke Test

**Validator:** Kiro (subagent)  
**Date:** 2026-06-14  
**Environment:** Python 3.13.7, pytest 9.0.3, Linux

## Execution

```
$ python3 -m pytest tests/test_pipeline_local_e2e.py -v
============================= test session starts ==============================
collected 7 items

tests/test_pipeline_local_e2e.py::test_valid_pipeline_passes PASSED      [ 14%]
tests/test_pipeline_local_e2e.py::test_stream_mismatch_fails_final_qa PASSED [ 28%]
tests/test_pipeline_local_e2e.py::test_missing_segment_fails_reconciliation PASSED [ 42%]
tests/test_pipeline_local_e2e.py::test_frozen_clip_detected PASSED       [ 57%]
tests/test_pipeline_local_e2e.py::test_stale_hash_fails_qa PASSED        [ 71%]
tests/test_pipeline_local_e2e.py::test_missing_required_music_fails_assembly PASSED [ 85%]
tests/test_pipeline_local_e2e.py::test_missing_required_overlay_fails_assembly PASSED [100%]

============================== 7 passed in 6.19s ===============================
```

## Full Suite Regression Check

```
$ python3 -m pytest -q
5 failed, 349 passed in 98.24s
```

Only pre-existing failures in `tests/test_review.py` (5 tests — known, unrelated to TKT-14).

## Confirmed Behaviors

1. **Stream parity ≤0.25s**: `qa_final.py` threshold `length_tol_sec: 0.25` applied; valid test uses exactly matched 3s streams → PASS.
2. **No paid APIs**: grep for elevenlabs/higgsfield/requests/httpx returns zero matches in the test file.
3. **7 tests, 7 correct gate failures**: Each test asserts the specific error string from the appropriate pipeline script.

## Verdict

**PASS** — TKT-14 validated. All acceptance criteria met.
