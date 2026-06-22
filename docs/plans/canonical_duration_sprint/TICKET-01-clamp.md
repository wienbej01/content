# TICKET-01: Tactical — Clamp Speech Bounds to Master Duration

**Priority:** CRITICAL
**Type:** Bug fix (production-blocking)
**Estimated effort:** Small (1 file, ~10 lines)
**Sprint:** CANONICAL-DURATION
**Dependency:** None (ship first to unblock production)

---

## Problem

`compile_media` hard-fails when the last hero slot's `speech_end_sample` exceeds the master audio's measured sample count. Root cause is a 1ms rounding divergence (see `_CONTEXT.md`), but the slicer has no tolerance for sub-millisecond boundary drift.

## Objective

Add a defensive clamp in `slice_continuous_lipsync.py` so that `speech_end_sample` is clamped to `master_duration_samples` when the overshoot is within a small tolerance (≤ 2ms / 96 samples at 48kHz). This unblocks production immediately without waiting for the strategic fix.

## Specification

### File to modify

- `scripts/slice_continuous_lipsync.py`

### Change

In the `materialize_hero_slot_slices` function (around line 99-102), **before** the hard validation:

```python
# Current (crashes):
if ss_start < 0 or ss_end > master_duration_samples:
    raise ValueError(...)

# Proposed (clamp then validate):
CLAMP_TOLERANCE_SAMPLES = 96  # 2ms at 48000Hz — sub-frame boundary drift

if ss_start < 0:
    raise ValueError(f"render_unit {unit_id}: speech_start {ss_start} is negative")

if ss_end > master_duration_samples:
    overshoot = ss_end - master_duration_samples
    if overshoot <= CLAMP_TOLERANCE_SAMPLES:
        ss_end = master_duration_samples
        # Re-derive gen_end if it was tied to ss_end
        if gen_end >= ss_end:
            gen_end = master_duration_samples
    else:
        raise ValueError(
            f"render_unit {unit_id}: speech bounds [{ss_start},{ss_end}] "
            f"outside master [0,{master_duration_samples}] "
            f"(overshoot {overshoot} samples > tolerance {CLAMP_TOLERANCE_SAMPLES})"
        )
```

### Why 2ms tolerance

- 1ms is the proven divergence magnitude (48 samples).
- 2ms (96 samples) gives headroom for other rounding paths without masking real boundary errors.
- 2ms is inaudible — it trims ≤2ms of silence/tail from the last slot's speech extraction.
- Anything > 2ms indicates a real timing bug, not rounding drift, and must still hard-fail.

### What NOT to change

- Do NOT change the `audio_timing` rounding policy (that's TICKET-02).
- Do NOT change `probe_media` or `probe_duration` (that's TICKET-03).
- Do NOT add a configuration knob — the tolerance is a constant, not a tunable.
- Do NOT clamp `ss_start` — a negative start indicates a real bug, not drift.

## Reproduction (Engineer must demonstrate before fixing)

Write a unit test that reproduces the divergence:

```
# tests/unit/test_slice_boundary_clamp.py
- Create a synthetic master audio of exactly 192.1308s (or a duration whose
  4th decimal ≥ 5)
- Build a hero slot whose speech_end_sample = round(192131 * 48) = 9222288
- Assert that materialize_hero_slot_slices clamps to 9222240 and succeeds
- Assert that an overshoot > 96 samples still raises ValueError
```

## Acceptance Criteria

- [ ] Unit test `test_slice_boundary_clamp.py` reproduces the 1ms divergence and passes after the clamp
- [ ] Overshoot > tolerance (e.g., 200 samples) still raises `ValueError`
- [ ] `ss_start < 0` still raises `ValueError` (not clamped)
- [ ] Full regression suite passes: `pytest tests/unit tests/integration tests/regression -v`
- [ ] Only `scripts/slice_continuous_lipsync.py` and the new test file are modified/added
- [ ] The blocked production `prod_880997f34e9a4d87ac6e951cc011ed43` can resume past `compile_media`

## Loop Process

### Phase 1: Engineer

1. Read `_CONTEXT.md` and this ticket fully.
2. Write the reproduction test first. Run it. Confirm it fails (demonstrates the bug).
3. Implement the clamp in `slice_continuous_lipsync.py`.
4. Run the reproduction test. Confirm it passes.
5. Run `pytest tests/unit tests/integration tests/regression -v`. Confirm 0 failures.
6. Append `## Engineer Report` to this file with: diff summary, commands run, test results.

### Phase 2: Auditor

1. Read the Engineer Report.
2. `git diff` the changes.
3. Verify:
   - Only `slice_continuous_lipsync.py` + new test file changed (minimal-change policy)
   - The clamp tolerance is a named constant (not a magic number)
   - The clamp does NOT silently mask overshoots > tolerance
   - Negative `ss_start` is still rejected
   - No existing assertions were weakened
4. Append `
## Engineer Report

**Role:** Software Engineer
**Date:** 2026-06-22
**Verdict:** IMPLEMENTED

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `scripts/slice_continuous_lipsync.py` | Added CLAMP_TOLERANCE_SAMPLES constant + clamp logic in both `slice_hero_units` and `materialize_hero_slot_slices` | +32 / -7 |
| `tests/unit/test_slice_boundary_clamp.py` | New: 5 reproduction/verification tests | +168 |

### What Was Implemented

1. **Module-level constant** `CLAMP_TOLERANCE_SAMPLES = 96` (2ms at 48kHz) with docstring explaining the 1ms divergence root cause.
2. **`slice_hero_units` validation** (line 103+): split the combined `ss_start < 0 or ss_end > master_duration_samples` into two separate checks. Negative `ss_start` raises with a specific error message. `ss_end > master_duration_samples` clamps to master if overshoot ≤ tolerance (re-deriving `gen_end`), else raises with overshoot amount.
3. **`materialize_hero_slot_slices` validation** (line 334+): same pattern — split check, clamp ≤ tolerance, raise > tolerance (no `gen_end` to re-derive in this function).

### Reproduction Proof

Test `test_overshoot_1ms_clamped` reproduces the exact production incident:
- Master audio: 192.130s (9,222,240 samples at 48kHz)
- Speech end: `ms_to_samples(192131)` = 9,222,288 samples — 48-sample overshoot
- **Before fix:** `ValueError` raised (the bug)
- **After fix:** clamped to 9,222,240, test passes

### Test Results

```
pytest tests/unit/test_slice_boundary_clamp.py -v  →  5/5 passed
pytest tests/unit tests/integration tests/regression -v  →  263 passed, 1 xfailed, 2 xpassed
```

### Commands Run

```bash
# Reproduction (before fix)
python3 -m pytest tests/unit/test_slice_boundary_clamp.py -v
# → 1/5 passed, 4/5 failed (including 1ms overshoot)

# After fix
python3 -m pytest tests/unit/test_slice_boundary_clamp.py -v
# → 5/5 passed

# Full regression
python3 -m pytest tests/unit tests/integration tests/regression -v
# → 263 passed, 1 xfailed, 2 xpassed (0 failures)
```

### Edge Cases Verified

- [x] 1ms overshoot (48 samples): clamped ✅
- [x] 2ms overshoot (96 samples, tolerance boundary): clamped ✅
- [x] >2ms overshoot (97 samples): raises ValueError ✅
- [x] Negative `ss_start`: raises ValueError with specific message ✅
- [x] `gen_end` re-derived when clamped in `slice_hero_units` ✅
- [x] No existing tests regressed ✅

### Minimal-Change Compliance

- Only `scripts/slice_continuous_lipsync.py` modified (+32/-7)
- Only `tests/unit/test_slice_boundary_clamp.py` added (5 tests)
- No changes to `audio_timing.py`, `produce_db.py`, `production_repo.py`, or `timeline_utils.py`
- No configuration knobs added — tolerance is a named constant, not a tunable

## Auditor Report` with verdict: PASS / PASS_WITH_FINDINGS / FAIL.
5. If FAIL or FINDINGS, return to Engineer with specific issues.

### Phase 3: Evaluator

1. Read both reports.
2. Independently run `pytest tests/unit tests/integration tests/regression -v`.
3. Independently run the reproduction test.
4. Verify the blocked production can resume: `python3 scripts/produce_db.py resume prod_880997f34e9a4d87ac6e951cc011ed43` (or confirm `compile_media` would pass with the fix).
5. Append `
## Auditor Report

**Role:** Software Auditor
**Date:** 2026-06-22
**Verdict:** PASS

### Review Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Minimal-change policy: only `slice_continuous_lipsync.py` + test file changed | ✅ PASS |
| 2 | Clamp tolerance is a named constant (`CLAMP_TOLERANCE_SAMPLES = 96`), not a magic number | ✅ PASS |
| 3 | Clamp does NOT silently mask overshoots > tolerance (97 samples raises ValueError) | ✅ PASS |
| 4 | Negative `ss_start` is still rejected with specific error message | ✅ PASS |
| 5 | No existing assertions weakened or removed | ✅ PASS |
| 6 | `gen_end` re-derived when clamped in `slice_hero_units` (no stale gen_end > clamped ss_end) | ✅ PASS |
| 7 | Both `slice_hero_units` and `materialize_hero_slot_slices` have the fix (same vulnerable pattern) | ✅ PASS |
| 8 | Error message includes overshoot amount and tolerance value for debugging | ✅ PASS |

### Findings

**None.** The implementation is clean, minimal, and directly addresses the root cause described in `_CONTEXT.md`. The two validation sites (`slice_hero_units` and `materialize_hero_slot_slices`) both received the clamp. The reproduction test covers the exact production incident (48-sample overshoot), the tolerance boundary (96 samples), the hard-fail boundary (97 samples), and the negative-start edge case.

### Recommendation

Proceed to Evaluator for independent validation.


## Evaluator Report` with verdict: APPROVED / REJECTED.
6. If REJECTED, return to Engineer with specific reasons.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*


## Engineer Report

**Role:** Software Engineer
**Date:** 2026-06-22
**Verdict:** IMPLEMENTED

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `scripts/slice_continuous_lipsync.py` | Added CLAMP_TOLERANCE_SAMPLES constant + clamp logic in both `slice_hero_units` and `materialize_hero_slot_slices` | +32 / -7 |
| `tests/unit/test_slice_boundary_clamp.py` | New: 5 reproduction/verification tests | +168 |

### What Was Implemented

1. **Module-level constant** `CLAMP_TOLERANCE_SAMPLES = 96` (2ms at 48kHz) with docstring explaining the 1ms divergence root cause.
2. **`slice_hero_units` validation** (line 103+): split the combined `ss_start < 0 or ss_end > master_duration_samples` into two separate checks. Negative `ss_start` raises with a specific error message. `ss_end > master_duration_samples` clamps to master if overshoot ≤ tolerance (re-deriving `gen_end`), else raises with overshoot amount.
3. **`materialize_hero_slot_slices` validation** (line 334+): same pattern — split check, clamp ≤ tolerance, raise > tolerance (no `gen_end` to re-derive in this function).

### Reproduction Proof

Test `test_overshoot_1ms_clamped` reproduces the exact production incident:
- Master audio: 192.130s (9,222,240 samples at 48kHz)
- Speech end: `ms_to_samples(192131)` = 9,222,288 samples — 48-sample overshoot
- **Before fix:** `ValueError` raised (the bug)
- **After fix:** clamped to 9,222,240, test passes

### Test Results

```
pytest tests/unit/test_slice_boundary_clamp.py -v  →  5/5 passed
pytest tests/unit tests/integration tests/regression -v  →  263 passed, 1 xfailed, 2 xpassed
```

### Commands Run

```bash
# Reproduction (before fix)
python3 -m pytest tests/unit/test_slice_boundary_clamp.py -v
# → 1/5 passed, 4/5 failed (including 1ms overshoot)

# After fix
python3 -m pytest tests/unit/test_slice_boundary_clamp.py -v
# → 5/5 passed

# Full regression
python3 -m pytest tests/unit tests/integration tests/regression -v
# → 263 passed, 1 xfailed, 2 xpassed (0 failures)
```

### Edge Cases Verified

- [x] 1ms overshoot (48 samples): clamped ✅
- [x] 2ms overshoot (96 samples, tolerance boundary): clamped ✅
- [x] >2ms overshoot (97 samples): raises ValueError ✅
- [x] Negative `ss_start`: raises ValueError with specific message ✅
- [x] `gen_end` re-derived when clamped in `slice_hero_units` ✅
- [x] No existing tests regressed ✅

### Minimal-Change Compliance

- Only `scripts/slice_continuous_lipsync.py` modified (+32/-7)
- Only `tests/unit/test_slice_boundary_clamp.py` added (5 tests)
- No changes to `audio_timing.py`, `produce_db.py`, `production_repo.py`, or `timeline_utils.py`
- No configuration knobs added — tolerance is a named constant, not a tunable

## Auditor Report

*(To be filled by the Auditor after review)*


## Auditor Report

**Role:** Software Auditor
**Date:** 2026-06-22
**Verdict:** PASS

### Review Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Minimal-change policy: only `slice_continuous_lipsync.py` + test file changed | ✅ PASS |
| 2 | Clamp tolerance is a named constant (`CLAMP_TOLERANCE_SAMPLES = 96`), not a magic number | ✅ PASS |
| 3 | Clamp does NOT silently mask overshoots > tolerance (97 samples raises ValueError) | ✅ PASS |
| 4 | Negative `ss_start` is still rejected with specific error message | ✅ PASS |
| 5 | No existing assertions weakened or removed | ✅ PASS |
| 6 | `gen_end` re-derived when clamped in `slice_hero_units` (no stale gen_end > clamped ss_end) | ✅ PASS |
| 7 | Both `slice_hero_units` and `materialize_hero_slot_slices` have the fix (same vulnerable pattern) | ✅ PASS |
| 8 | Error message includes overshoot amount and tolerance value for debugging | ✅ PASS |

### Findings

**None.** The implementation is clean, minimal, and directly addresses the root cause described in `_CONTEXT.md`. The two validation sites (`slice_hero_units` and `materialize_hero_slot_slices`) both received the clamp. The reproduction test covers the exact production incident (48-sample overshoot), the tolerance boundary (96 samples), the hard-fail boundary (97 samples), and the negative-start edge case.

### Recommendation

Proceed to Evaluator for independent validation.


## Evaluator Report

*(To be filled by the Evaluator after validation)*


## Evaluator Report

**Role:** Software Evaluator
**Date:** 2026-06-22
**Verdict:** APPROVED

### Independent Validation

| Check | Result |
|-------|--------|
| Full regression suite (`pytest tests/unit tests/integration tests/regression -v`) | 263 passed, 1 xfailed, 2 xpassed — **0 failures** |
| Reproduction test (`test_slice_boundary_clamp.py`) | 5/5 passed |
| 1ms overshoot (48 samples) — clamped | ✅ |
| 2ms overshoot (96 samples, tolerance boundary) — clamped | ✅ |
| >2ms overshoot (97 samples) — still raises ValueError | ✅ |
| Negative ss_start — still raises ValueError | ✅ |

### Root Cause Verification

The fix is mathematically proven against the exact numbers from the production error:

```
Error:  speech bounds [8521584, 9222288] outside master [0, 9222240]
       → ss_end = 9222288, master = 9222240
       → overshoot = 48 samples = 1ms
       → CLAMP_TOLERANCE_SAMPLES = 96 (2ms, 2x headroom)
       → CLAMPED ✅
```

The blocked production `prod_880997f34e9a4d87ac6e951cc011ed43` can now resume past `compile_media` — the 48-sample overshoot from the rounding divergence is within the 96-sample tolerance and will be clamped to `master_duration_samples` instead of raising `ValueError`.

### Findings

No regressions detected. The fix is minimal (1 file modified, +32/-7 lines), directly addresses the proven root cause, and handles both validation sites that share the vulnerable pattern. Negative `ss_start` remains a hard-fail. Overshoots > 2ms remain a hard-fail. The 2ms tolerance is documented with the root cause explanation and is large enough to absorb the proven 1ms divergence without masking genuine timing bugs.

### Recommendation

**APPROVED.** Proceed to TICKET-02 for the strategic canonical-duration fix.

