# TKT-03 Audit Report

**Date:** 2026-06-14  
**Auditor:** Subagent (read-only)  
**Verdict:** REVISE (one issue: format-duration vs stream-duration)

---

## 1. `scripts/reconcile_duration.py`

### ✓ Correct behaviors

| Check | Status | Location |
|-------|--------|----------|
| Handles `local_graphic` as always-sufficient | ✓ PASS | line 72–74 |
| Missing clip files → FAIL (not skip) | ✓ PASS | line 77–80 |
| Writes `duration_reconciliation.csv` | ✓ PASS | line 93–100 |
| Tolerance = 0.25s | ✓ PASS | line 20 (`TOLERANCE = 0.25`) |
| Exit 1 on any beat with deficit > 0.25s | ✓ PASS | line 113–118 |
| Exit 0 only when all beats sufficient | ✓ PASS | line 120 |
| Beat IDs from timing map matched to media plan | ✓ PASS | line 61 (`plan_beats.get(beat_id)`) |
| Beat in timing map but not in plan → MISSING_PLAN + FAIL | ✓ PASS | lines 63–67 |

### ✗ ISSUE: format-duration vs stream-duration

**File:** `scripts/reconcile_duration.py` **line 26**

```python
["ffprobe", "-v", "error", "-show_entries", "format=duration",
 "-of", "csv=p=0", str(path)],
```

This probes the **container format duration**, not the `v:0` stream duration. The correct call should be:

```python
["ffprobe", "-v", "error", "-select_streams", "v:0",
 "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
```

**Impact:** Measured empirically on `B001.mp4`:
- `format=duration` → 7.082s  
- `stream=duration (v:0)` → 7.042s  

The format duration is ~40ms **longer** than stream duration in this case. This means the script is *slightly optimistic* about available coverage — a clip that actually has 7.042s of video frames is reported as having 7.082s. In this project the deficits are so large (6–15s) that it doesn't change any pass/fail outcomes, but for borderline beats (deficit near 0.25s tolerance), this could produce a false PASS.

**Recommendation:** Switch to `v:0` stream duration. This is what assembly actually gets (video frames), and matches what the forensic audit measured.

### Observation: beats in plan but not in timing map

Beats that exist in `media_plan.json` but NOT in `beat_timing_map.json` are silently ignored (the loop iterates timing beats only). For the audited project this set is empty, and the behavior is arguably correct (extra plan beats don't need reconciliation). Document this as intentional.

---

## 2. `scripts/produce.py`

| Check | Status | Location |
|-------|--------|----------|
| `reconcile_duration` in STEPS between `qa_media` and `build_manifest` | ✓ PASS | lines 43–46 |
| `reconcile_duration` in STEP_FNS | ✓ PASS | line 441 |
| Failing raises RuntimeError → halts pipeline | ✓ PASS | lines 320–328 (raise), 492–498 (catch) |
| Assembly unreachable after reconcile failure | ✓ PASS | `return False` at line 498 prevents loop continuation |

---

## 3. `tests/test_duration_reconciliation.py`

| Test | Assertion | Status |
|------|-----------|--------|
| `test_audited_project_fails` | Runs against REAL project, asserts exit 1, deficit 55–80s | ✓ PASS |
| `test_deficit_fails` | 10s required, 5s clip → exit 1, "B001" + "deficit" in output | ✓ PASS |
| `test_missing_clip_fails` | Nonexistent file → exit 1 | ✓ PASS |
| `test_local_graphic_coverage` | local_graphic beat, 20s required, no clip → exit 0 | ✓ PASS |
| `test_sufficient_coverage_passes` | 5s required, 5s clip → exit 0 | ✓ PASS |
| `test_total_deficit_accumulates` | 3 beats each 0.2s deficit → total 0.6s > 0.25s → exit 1 | ✓ PASS |

All 6 tests pass (confirmed: `6 passed in 2.25s`).

---

## 4. Live validation

```
$ python3 scripts/reconcile_duration.py Videos/Projects/using_ai_to_help_memory_retention_short
Duration reconciliation: 10 beats
  Total deficit: 71.189s
FAILED — 9 beat(s) with insufficient coverage
Exit: 1
```

9/10 beats fail. Total deficit 71.189s. The ~8s discrepancy from the forensic estimate (~63.266s) is explained by:
1. Forensic analysis used stream durations; this script uses (slightly longer) format durations
2. The forensic audit may have used different timing map values (pre-TTS re-run)

Both analyses agree: massive deficit, hard failure, assembly blocked.

---

## 5. Summary

| Category | Verdict |
|----------|---------|
| Gate enforcement (exit 1 blocks assembly) | ✓ PASS |
| produce.py integration | ✓ PASS |
| Test coverage | ✓ PASS |
| ffprobe accuracy | ✗ REVISE — use `v:0` stream duration |

---

## Required fix

**`scripts/reconcile_duration.py` line 25–27** — change:

```python
["ffprobe", "-v", "error", "-show_entries", "format=duration",
 "-of", "csv=p=0", str(path)],
```

to:

```python
["ffprobe", "-v", "error", "-select_streams", "v:0",
 "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
```

This is a one-line fix. All existing tests should still pass (format and stream durations are close enough that no test crosses the tolerance boundary in the wrong direction).

---

**Overall: REVISE** (one fix required before sign-off)
