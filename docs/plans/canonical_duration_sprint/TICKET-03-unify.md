# TICKET-03: Consistency — Unify ms→samples Conversion

**Priority:** MEDIUM
**Type:** Refactor (defense in depth)
**Estimated effort:** Small (1-2 files)
**Sprint:** CANONICAL-DURATION
**Dependency:** TICKET-02 must be Evaluator-APPROVED first

---

## Problem

The codebase has **two different ms→samples conversion patterns**:
- `timeline_utils.ms_to_samples(ms)` — uses `round(ms * 48000 / 1000)` ✅ correct
- `int(duration_ms * 48000 / 1000)` — uses truncation ❌ inconsistent (in `slice_continuous_lipsync.py:80`)

And **two different seconds→ms patterns**:
- `int(float_sec * 1000)` — truncation (in `produce_db.py:335-336`, `tts_service.py:115`, `production_repo.py:103`)
- `round(float_sec, 3)` then `int(* 1000)` — round-then-truncate (in `audio_timing.py:153-154`)

These inconsistencies are why the 1ms divergence exists. TICKET-02 eliminates the re-probing, but if any future code path re-introduces a probe, the rounding asymmetry returns. This ticket makes the conversion functions the **only** way to convert.

## Objective

Audit all ms↔samples and seconds→ms conversions in the timing/slicing path. Replace ad-hoc arithmetic with `timeline_utils.ms_to_samples()` / `samples_to_ms()`. Add a lint-style unit test that fails if any file in `scripts/` contains a raw `* 48000` or `* MASTER_SAMPLE_RATE` outside of `timeline_utils.py`.

## Specification

### File to modify

- `scripts/slice_continuous_lipsync.py` — replace `int(master_probe.duration_ms * MASTER_SAMPLE_RATE / 1000)` with `ms_to_samples(master_probe.duration_ms)` (line 80, and line 306 if duplicated)
- `scripts/canonical_master.py` — replace `int(probe.duration_ms * CANONICAL_SAMPLE_RATE / 1000)` with `ms_to_samples(probe.duration_ms)` (lines 84, 99). Note: `CANONICAL_SAMPLE_RATE` may differ from `MASTER_SAMPLE_RATE` — verify before replacing. If different, add a parameterized helper.

### Change

In `slice_continuous_lipsync.py`:

```python
# Before:
master_duration_samples = int(master_probe.duration_ms * MASTER_SAMPLE_RATE / 1000)

# After:
from timeline_utils import ms_to_samples
master_duration_samples = ms_to_samples(master_probe.duration_ms)
```

Also update line 187 (`actual_samples = int(slice_probe.duration_ms * MASTER_SAMPLE_RATE / 1000)`) to use `ms_to_samples()`.

### Guard test

```
# tests/unit/test_no_raw_sample_arithmetic.py
- Scan all .py files in scripts/ for the pattern `* MASTER_SAMPLE_RATE` or `* 48000`
- Exclude timeline_utils.py (the canonical definition site)
- Assert zero matches — all conversions must go through ms_to_samples / samples_to_ms
```

This prevents regression: if someone adds `int(x * 48000 / 1000)` in a new file, the test fails.

### What NOT to change

- Do NOT change `tts_service.py:115` (`int(float(duration) * 1000)`) — this is the canonical duration registration. It truncates by design (the artifact stores the catalog duration). TICKET-02 makes this the single source of truth.
- Do NOT change `audio_timing.py`'s `round(total_dur, 3)` — after TICKET-02, this path only runs when `canonical_duration_sec` is None (legacy fallback). Changing it now risks breaking the fallback.
- Do NOT touch `production_repo.py:103` (`probe_media`'s `int(float(duration) * 1000)`) — this is the probe-layer truncation that feeds the artifact registration. It's consistent with `tts_service.py`.

## Acceptance Criteria

- [ ] `slice_continuous_lipsync.py` uses `ms_to_samples()` for all ms→samples conversions (no raw `* MASTER_SAMPLE_RATE` arithmetic)
- [ ] `canonical_master.py` uses `ms_to_samples()` (or a parameterized variant if sample rate differs)
- [ ] Guard test `test_no_raw_sample_arithmetic.py` passes (zero raw `* 48000` outside `timeline_utils.py`)
- [ ] Guard test **fails** if someone adds a raw `* 48000` to any other file (verify by temporarily adding one, then removing)
- [ ] Full regression suite passes: `pytest tests/unit tests/integration tests/regression -v`
- [ ] Only `slice_continuous_lipsync.py`, `canonical_master.py` + new test file are modified

## Loop Process

### Phase 1: Engineer

1. Read `_CONTEXT.md`, TICKET-01 and TICKET-02 (both must be APPROVED), and this ticket.
2. Write `test_no_raw_sample_arithmetic.py`. Run it. Confirm it fails (finds existing raw arithmetic).
3. Replace raw arithmetic in `slice_continuous_lipsync.py` and `canonical_master.py`.
4. Run the guard test. Confirm it passes.
5. Temporarily add a raw `* 48000` to any file. Confirm the guard test fails. Remove it.
6. Run `pytest tests/unit tests/integration tests/regression -v`. Confirm 0 failures.
7. Append `## Engineer Report`.

### Phase 2: Auditor

1. Read the Engineer Report.
2. `git diff` the changes.
3. Verify:
   - Only the 2 source files + test file changed
   - No conversion logic was silently changed (only the call site changed, not the math — `ms_to_samples` uses `round`, which may differ from `int()` truncation; verify this doesn't change behavior for any existing test)
   - The guard test actually catches violations (not a no-op)
   - `canonical_master.py`'s sample rate is handled correctly (CANONICAL_SAMPLE_RATE vs MASTER_SAMPLE_RATE)
4. Append `## Auditor Report` with verdict.

### Phase 3: Evaluator

1. Read both reports.
2. Run `pytest tests/unit tests/integration tests/regression -v` independently.
3. Run the guard test independently.
4. Append `## Evaluator Report` with verdict: APPROVED / REJECTED.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*

## Auditor Report

*(To be filled by the Auditor after review)*

## Evaluator Report

*(To be filled by the Evaluator after validation)*
