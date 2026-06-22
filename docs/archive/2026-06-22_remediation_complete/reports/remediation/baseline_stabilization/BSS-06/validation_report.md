# BSS-06 Validation Report — Full Local Regression and Handoff Gate

**Date:** 2026-06-14  
**Validator:** kiro-cli (automated)  
**Verdict:** ✅ PASS

---

## Command Results

### 1. Focused review tests (`tests/test_review.py`)

```
........                                                                 [100%]
8 passed in 0.01s
```

**Exit: 0** ✅

### 2. Resume tests (`tests/test_produce_resume.py`)

```
...............                                                          [100%]
15 passed in 0.03s
```

**Exit: 0** ✅

### 3. Manifest/music/graphics tests

```
.....................                                                    [100%]
21 passed in 6.51s
```

**Exit: 0** ✅

### 4. E2E fixture (`tests/test_pipeline_local_e2e.py`)

```
.......                                                                  [100%]
7 passed in 7.01s
```

**Exit: 0** ✅

### 5. Full test suite

```
376 passed in 101.86s (0:01:41)
```

**Exit: 0** ✅

### 6. Defective MP4 fails final QA (must exit 1)

```
  ✗ CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s (delta 63.3s > 0.25s tolerance)
  ✗ LENGTH_MISMATCH: video 83.3s vs audio 146.6s (delta 63.3s > 0.25s tolerance)
  ✗ TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s (audio outlasts video by 63.3s)
Exit: 1
```

**Exit: 1** ✅ (correctly rejects defective output)

### 7. Duration reconciliation fails (must exit 1)

```
Duration reconciliation: 10 beats
  CSV: Videos/Projects/using_ai_to_help_memory_retention_short/duration_reconciliation.csv
  Total deficit: 71.463s

FAILED — 9 beat(s) with insufficient coverage:
  B001: deficit 6.952s
  B002: deficit 0.622s
  B003: deficit 12.852s
  B005: deficit 15.559s
  B006: deficit 0.584s
  B007: deficit 5.045s
  B008: deficit 13.847s
  B009: deficit 13.380s
  B010: deficit 2.619s

  Total deficit: 71.463s (tolerance: 0.25s)
Exit: 1
```

**Exit: 1** ✅ (correctly reports coverage deficit)

### 8. Quality report FAIL on audited project (must exit 1)

```
Quality Report: FAIL
Failures: stream_integrity, beat_coverage, media_qa
Exit: 1
```

**Exit: 1** ✅ (correctly identifies quality failures)

### 9. No `force_unsafe=True` in `produce.py`

```
force_unsafe check exit: 1
```

**Exit: 1** ✅ (grep found no matches — pattern absent from file)

---

## Summary

All 9 validation checks passed. The pipeline is fail-closed, the test suite is green at 376 tests, defective artifacts are correctly rejected, and no unsafe bypasses remain in the orchestrator.
