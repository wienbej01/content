# TKT-104 Validation Report

**Validator:** independent (validate-scope skill)
**Date:** 2026-07-04T23:30:05+08:00
**Verdict:** PASS

## Gate Verification

### G1: Calibration report exists with real measured numbers — PASS

- `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.md` present ✓
- 12 measurements from RealSyncBackend (3 clips × 4 conditions) ✓
- All clips referenced: S000 (face_track=True), S001 (face_track=False), S002 (face_track=True) ✓
- Differential verification: scorer tracks injected shifts on S000 with 0ms error ✓
- Policy YAML references report: "See: docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.md" ✓

### G2: All injected-shift negatives fail policy — PASS

- `zero_false_pass_close: True` (0/6 negatives pass close_hero) ✓
- `zero_false_pass_medium: True` (0/6 negatives pass medium_hero) ✓
- S000+80ms=200ms > close_pass=120 → FAIL ✓
- S000+160ms=280ms > close_pass=120 → FAIL ✓
- S000+320ms=440ms > close_pass=120 → FAIL ✓
- S002+80ms=520ms, +160ms=600ms, +320ms=600ms → all FAIL ✓

### G3: All known-good clips pass or are individually justified — PASS

- S000: unshifted offset=120ms → passes close_hero at exact pass_ms=120 ✓
- S001: face_track_found=False → excluded from policy evaluation (scorer gate) ✓
- S002: unshifted offset=440ms → fails close_hero (440 > 120) ✓
  - Justified: "Native Seedance v1 output with known lipsync drift. Route to compensation loop (TKT-103)." ✓
- All justifications recorded in calibration JSON `false_fail_justifications` ✓

### G4: Full suite passes — PASS

| Test suite | Result |
|-----------|--------|
| `test_lipsync_policy_calibrated.py` | 14/14 passed |
| `test_lipsync_policy.py` | 36/36 passed (includes new `test_confidence_zero_fails`) |
| `test_sync_scorer_adapter.py` | 13/13 passed |
| Focused invariant (104 tests) | 104/104 passed |

## Audit Finding Resolution

| Finding | Severity | Status |
|---------|----------|--------|
| F1: confidence=0.0 bypass | MEDIUM | RESOLVED — min_confidence 0.0→0.001 + regression test |
| F2: warn_ms calibration imprecision | MEDIUM | RESOLVED — formula 1.33→4/3, tolerances tightened |
| F3: /tmp calibration JSON fragility | LOW | UNRESOLVED, non-blocking |
| F4: misleading S14_T001 class docstring | LOW | UNRESOLVED, non-blocking |
| F5: markdown missing false-fail clip ID | LOW | UNRESOLVED, non-blocking |

## Calibrated Policy Constants

| Tier | pass_ms | warn_ms | min_confidence |
|------|---------|---------|----------------|
| close_hero | 120 | 160 | 0.001 |
| medium_hero | 168 | 210 | 0.001 |
| diagnostic_legacy | 160 | 160 | 0.0 |

Thresholds verified to match calibration JSON within tight tolerances (abs≤0.1 for ms, abs≤0.0001 for confidence).

## Residual Risks

- Small sample size: 3 clips, only 2 face-tracked (S001 had no face detection)
- 600ms xcorr search window saturation boundary on S002+320ms
- LOW findings F3-F5 remain (cosmetic/documentation)
- Confidence min_confidence=0.001 relies on defense-in-depth (face_track_found check in scorer)

**TKT-104 ACCEPTED**
