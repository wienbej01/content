# TKT-104 Re-Audit Report (Repair Cycle 1)

**Auditor:** independent (audit-ticket skill)
**Date:** 2026-07-04T23:20:05+08:00
**Audit Cycle:** 2
**Commit:** efe2e2e (working tree dirty)
**Original Audit Findings:** F1 (MEDIUM), F2 (MEDIUM), F3-F5 (LOW)
**Verdict:** PASS_WITH_FINDINGS

## Resolution of Prior Findings

### FINDING-1 (MEDIUM — confidence=0.0 bypass) → RESOLVED

- **Change:** `min_confidence` changed from `0.0` to `0.001` in YAML config, calibration JSON, and policy test assertions.
- **New test:** `test_confidence_zero_fails` verifies `evaluate_lipsync(offset_ms=50, confidence=0.0)` returns FAIL with "below minimum" reason.
- **Verification:** `confidence=0.001` passes, `confidence=0.0` fails. Scorer returns confidence=0.0 only when no face detected, creating defense-in-depth.
- **Status:** ✓ RESOLVED

### FINDING-2 (MEDIUM — warn_ms calibration imprecision) → RESOLVED

- **Change:** `close_warn` derivation changed from `close_pass * 1.33` → `round(close_pass * 4 / 3, 1)`, producing exact `160.0` matching YAML.
- **Test tolerance:** Calibration pinning tolerances tightened from `abs=0.5` → `abs=0.1` for warn_ms/fail_ms, and from `abs=0.01` → `abs=0.0001` for min_confidence.
- **Verification:** YAML `warn_ms=160` matches JSON `warn_ms=160.0` within `abs=0.1` tolerance.
- **Status:** ✓ RESOLVED

### Unresolved LOW Findings

| ID | Status | File | Issue |
|----|--------|------|-------|
| F3 | UNRESOLVED | `tests/test_lipsync_policy_calibrated.py:16` | Calibration pinning to `/tmp/kilo/tkt104/calibration.json` — fragile path outside project |
| F4 | UNRESOLVED | `tests/test_lipsync_policy.py:175` | `TestRequiredPassCriteria` class docstring says "S14_T001" but tests rewritten for TKT-104 |
| F5 | UNRESOLVED | `evidence/TKT-104-calibration.md:42` | Markdown report missing failed-clip identification |

## New Issues from Repair

No new issues introduced. The repair was scoped to F1 (min_confidence epsilon) and F2 (derivation formula + tolerances). No production code outside the calibration script, config, and tests was changed. No test coverage was removed.

## Gate Re-verification

| Gate | Status | Evidence |
|------|--------|----------|
| G1 (report with real numbers) | PASS | Updated report with 12 measurements, min_confidence=0.001, warn_ms=160.0 |
| G2 (zero false-pass) | PASS | Unchanged — calibration thresholds same as before repair |
| G3 (known-goods pass or justified) | PASS | S000 passes (120≤120), S002 justified |
| G4 (full suite passes) | PASS | 50 policy/calibration + 104 invariant + 13 adapter = 167 passed |

## Test Evidence

- `python3 -m pytest tests/test_lipsync_policy_calibrated.py -v` — 14 passed
- `python3 -m pytest tests/test_lipsync_policy.py -v` — 36 passed (includes new `test_confidence_zero_fails`)
- `YT_TEST_MODE=1 python3 -m pytest <focused suite> -q` — 104 passed
- `python3 -m pytest tests/test_sync_scorer_adapter.py -v` — 13 passed

## Audit Summary

**Overall:** PASS_WITH_FINDINGS — F1 and F2 resolved correctly. F3-F5 (LOW) remain unaddressed but non-blocking. No new issues. Ready for validation.

**Reservoir risks:** small sample size (2 face-tracked clips), 600ms xcorr saturation boundary, /tmp calibration JSON fragility, misleading S14_T001 class reference.
