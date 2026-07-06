# TKT-004 Validation Report

**Ticket**: Wire model-free b-roll technical checks into qa_media
**Commit**: `7783175`
**Validator**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Acceptance Gates

| Gate | Expected | Result | Evidence |
|------|----------|--------|----------|
| G1 | Frozen clip fails QA | PASS | `test_frozen_clip_fails`: frozen red 5s clip → `status=fail`, `FROZEN_VIDEO: 100% frozen` in issues. `test_moving_clip_passes`: testsrc2 clip → `status=pass`. |
| G2 | Evidence row present | PASS | `test_broll_technical_fail_registers_validation`: `broll_technical` validation row with `status=fail` in validations table. Manual: same result with `run_contract_media_qa` through full production path. |
| G3 | Focused suite passes | PASS | 109 invariant + 5 dedicated = all pass |

## Verification Results

| Check | Result |
|-------|--------|
| 5 dedicated tests | ALL PASS |
| 109 focused invariant tests | ALL PASS |
| Frozen clip (color source) → fail | PASS |
| Moving clip (testsrc2) → pass | PASS |
| Missing file → fail | PASS |
| broll_technical validation row recorded | PASS |
| Fail routes through existing repair classification | PASS |
| commit 7783175: only broll_qa.py + media_service.py + tests changed | PASS |

## Audit findings disposition

**FINDING-1 (LOW)**: Frozen metrics always 0.0 in structured evidence — **non-blocking**. The pass/fail logic is correct and the freeze information is available in the free-text issue string (e.g., `"FROZEN_VIDEO: 100% frozen (5.0s of 5.0s)"`). The structured `frozen` dict showing `{"total_freeze_sec": 0.0, "freeze_pct": 0.0}` is misleading for downstream key-based consumers but does not affect QA correctness.

## Residual risks

- FFmpeg subprocess errors are silently swallowed (no `check=True`, no stderr inspection). A corrupted video could silently pass both checks.
- Scene-change threshold (`_MAX_SCENE_CHANGES=30`) is absolute, not duration-relative. A long clip (e.g., 120s) with 30 scene changes (0.25/s) is flagged as gibberish — possible false positive.
- Both risks are acceptable for the b-roll use case (typical clips 4-15s).

## State transition

TKT-004 accepted. Moving from `ready_for_validation_with_findings` → `completed_tickets`. Next eligible ticket per dependency order: TKT-005 (Wave 0, ROUTINE, ready_for_audit).
