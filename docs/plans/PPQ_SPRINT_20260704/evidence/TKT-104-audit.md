# TKT-104 Audit Report

**Auditor:** independent (audit-ticket skill)
**Date:** 2026-07-04T23:09:00+08:00
**Commit:** efe2e2e (working tree dirty, uncommitted changes)
**Verdict:** PASS_WITH_FINDINGS

## G1: Calibration report exists with real measured numbers — PASS

- `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.md` exists
- Contains 12 measurements (3 clips × 4 conditions)
- All measurements from real `RealSyncBackend` (mediapipe face landmarker) run, not simulated
- Differential verification confirms scorer detects injected shifts on S000 with 0ms error
- S002 differential: +80ms and +160ms detected correctly; +320ms saturates at 600ms search window (documented)

## G2: All injected-shift negatives fail policy — PASS

- S000: unshifted=120, +80=200 (fails both tiers), +160=280 (fails), +320=440 (fails)
- S002: unshifted=440 (fails both tiers, justified), +80=520 (fails), +160=600 (fails), +320=600 (fails)
- Zero false-pass on both close_hero (pass_ms=120) and medium_hero (pass_ms=168)
- face_track_found=False clips (S001) excluded from threshold analysis — they fail at the scorer level

## G3: All known-good clips pass or are individually justified — PASS

- S000: unshifted offset=120ms → passes close_hero at exactly pass_ms=120 ✓
- S001: no face track → excluded from analysis; will be caught by scorer's face_track_found gate ✓
- S002: unshifted offset=440ms → fails close_hero and medium_hero
  - Justified in report: "Native Seedance v1 output with known lipsync drift. Route to compensation loop (TKT-103)." ✓

## G4: Full suite passes — PASS

- 14 calibration-pinning tests pass
- 35 updated policy tests pass
- 104 focused invariant tests pass (YT_TEST_MODE=1)
- 13 TKT-102 adapter tests pass (no regression)

---

## Findings

### FINDING-1 (MEDIUM): confidence=0.0 bypass when face_track_found not checked

- **File:** `scripts/lipsync_policy.py:184`
- **Issue:** `evaluate_lipsync` gates confidence with `confidence < policy.min_confidence`. With `min_confidence=0.0`, the condition `0.0 < 0.0` evaluates False, allowing confidence=0.0 to pass the policy. The scorer returns `confidence=0.0` exclusively when `face_hits==0` (no face detected). In the current production path (`_qa_hero_lipsync` in `media_service.py`), `face_track_found` is checked before calling the policy, providing defense-in-depth. However, the assembly path (`assemble_db.py:576`) calls `evaluate_lipsync` directly from validation records and does not check `face_track_found` before evaluating confidence. If a future scorer or a malformed validation record provides `confidence=0.0` without `face_track_found=False`, the assembly gate would not block.
- **Required correction:** Either (a) change min_confidence to a small epsilon (e.g. 0.001) so that confidence=0.0 fails, or (b) add `face_track_found` check in the assembly gate path, or (c) document the defense-in-depth assumption explicitly.
- **Required regression test:** Test that `evaluate_lipsync(offset_ms=50, confidence=0.0, policy_name="close_hero")` returns a FAIL verdict or that the assembly gate rejects a validation row with `confidence=0.0` when `face_track_found` is not explicitly True.

### FINDING-2 (MEDIUM): warn_ms differs between calibration report and YAML config

- **File:** `configs/lipsync_thresholds.yaml:19` vs `evidence/TKT-104-calibration.md:29`
- **Issue:** Calibration report derives `close_hero warn_ms=159.6` from `close_pass * 1.33 = 120 * 1.33 = 159.6`. The YAML config sets `warn_ms: 160` (integer rounded up). The calibration-pinning test passes because it uses `pytest.approx(expected, abs=0.5)` tolerance. The YAML value is not a direct reflection of the calibration derivation.
- **Evidence:** `calibrate_sync_thresholds.py:210`: `close_warn = close_pass * 1.33` → 159.6. YAML: `warn_ms: 160`.
- **Required correction:** Round to one decimal in the YAML (`warn_ms: 159.6`) or change the calibration derivation to produce integer values. Current tolerance-masked discrepancy is fragile.
- **Required regression test:** Tighten `pytest.approx(abs=0.1)` tolerance in `test_close_hero_warn_ms_matches_calibration`, or assert exact equality after correcting the derivation.

### FINDING-3 (LOW): Calibration pinning test depends on external /tmp file

- **File:** `tests/test_lipsync_policy_calibrated.py:16`
- **Issue:** `_CALIBRATION_JSON = Path("/tmp/kilo/tkt104/calibration.json")` — pins to a temp file outside the project. If `/tmp` is cleared (system reboot, CI environment, different machine), the test silently skips without verifying thresholds. The report is the source of truth, not the JSON.
- **Required correction:** Store the calibration JSON inside the project (e.g. `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.json` ) alongside the markdown report, or embed the expected values directly in the test (hardcoded from the calibration report). Moving to project path is preferred.
- **Required regression test:** Verify the test does not skip when run from a fresh clone (path must exist in repo).

### FINDING-4 (LOW): Misleading class docstring in test_lipsync_policy.py

- **File:** `tests/test_lipsync_policy.py:175`
- **Issue:** `TestRequiredPassCriteria` class docstring says "Required tests from S14_T001 ticket" but the tests were completely rewritten for TKT-104 calibrated thresholds. The `test_80ms_fails_close_hero` was changed to `test_80ms_passes_close_hero` (opposite assertion). The class name and docstring imply these are legacy requirements when they are actually TKT-104 calibration-derived behavior.
- **Evidence:** Old test `test_80ms_fails_close_hero` → new `test_80ms_passes_close_hero`. Old test `test_160ms_not_publish_pass_for_close_hero` → new `test_320ms_fails_close_hero`. Old test `test_low_confidence_fails` → new `test_low_confidence_passes`.
- **Required correction:** Rename class to `TestTKT104CalibratedPassCriteria` and update docstring to reference TKT-104 calibration.
- **Required regression test:** None (cosmetic).

### FINDING-5 (LOW): Calibration markdown report missing false-fail clip identification

- **File:** `docs/plans/PPQ_SPRINT_20260704/evidence/TKT-104-calibration.md:42`
- **Issue:** Report line "False-fail (close_hero): 1  (known-good rejected)" does not identify which clip was rejected. The JSON report contains `false_fail_candidates_close: [{"clip": "S002_norm.mp4", "offset_ms": 440.0}]` but the markdown does not.
- **Evidence:** `calibrate_sync_thresholds.py:436-438` — the markdown writer only prints the count, not the candidates.
- **Required correction:** Include the rejected clip name(s) and offset in the markdown report for audit trail.
- **Required regression test:** None (cosmetic — JSON contains the data).

---

## Audit Summary

| Gate | Verdict | Evidence |
|------|---------|----------|
| G1 (report with real numbers) | PASS | Calibration report with 12 measurements from RealSyncBackend |
| G2 (zero false-pass on negatives) | PASS | Verified: no shifted clip passes close_hero or medium_hero |
| G3 (known-goods pass or justified) | PASS | S000 passes, S002 justified (Seedance v1 drift) |
| G4 (full suite passes) | PASS | 166 tests pass (14+35+13+104) |

**Overall:** PASS_WITH_FINDINGS — 2 MEDIUM findings (F1: confidence bypass edge case, F2: warn_ms imprecision), 3 LOW findings (F3: /tmp pinning, F4: misleading docstring, F5: incomplete markdown). All findings are actionable without architectural redesign.

**Reservoir risks:**
- Small sample size (2 face-tracked clips) limits generality
- 600ms xcorr search window saturation on S002+320ms shift
- min_confidence=0.0 relies entirely on face_track_found for quality gating
- S002 native 440ms offset means existing Seedance v1 outputs will be heavily flagged

**No evidence of:** fabricated results, weakened gates, dummy outputs, silent fallbacks, unrelated scope changes.
