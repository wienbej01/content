# REPAIR-601B-W1 — Validation Report

**Date**: 2026-07-06T19:10:00+08:00
**Validator**: independent
**Verdict**: PASS

## Acceptance gates

### G1: Real 480ms hero clip, after directional compensation, re-scores ≤ 120ms

| Metric | Before | After | Threshold |
|---|---|---|---|
| Offset | +480ms | -40ms | ≤120ms |
| Verdict | FAIL | **PASS** | close_hero |

Evidence: compensated artifact `pjob_cd63c3115fdb48fcbaf482c6e6d9c349_compensated.mp4` (1,505,654 bytes) exists and re-scores independently.

### G2: Negative-offset compensation path unchanged

| Test | Expected | Result |
|---|---|---|
| `test_negative_offset_delays_audio` | `offset_ms_applied = 300` | PASS |
| `test_correctable_offset_compensates_and_passes` | CORRECTABLE → compensated=True | PASS |
| `test_failing_compensation_routes_to_regeneration` | routed to regen | PASS |

Negative offset path uses `adelay` filter (unchanged behavior). Existing regression fixtures intact.

### G3: Cap justified, no thresholds weakened

- `COMPENSATION_MAX_OFFSET_MS = 600` (was 400)
- Justification: scorer search window `_SEARCH_WINDOW_MS = 600` in `_algorithm.py:27`
- `configs/lipsync_thresholds.yaml` documents `compensation_cap_ms: 600` with provenance
- `close_hero` thresholds: pass=120ms, fail=160ms (pre-existing TKT-104 calibration, not weakened by W1)
- No gate in `lipsync_thresholds.yaml` was loosened by this change

### G4: Full invariant suite

- Invariant: 145/147 passed
- 2 failures: `test_llm_call.py` pre-existing (DeepSeek model override from TKT-601 run)
- Focused compensation tests: 9/9 passed

## Validation steps

1. Focused tests: 9 passed ✓
2. Invariant suite: 145 passed ✓
3. E2E re-score: -40ms ≤ 120ms ✓
4. Negative offset regression: adelay preserved ✓
5. Cap justification: 600ms documented ✓
6. No dummy outputs or silent fallbacks ✓
7. Production path exercised: compensate() → run_repair_lifecycle → run_contract_media_qa ✓
8. No unintended files changed: 4 files in scope ✓
9. Idempotent: compensate() deterministic from same inputs ✓
10. Audit findings: none (PASS) ✓

## Residual risks

- `atrim` trims leading audio for positive offsets (speech onset loss in first `offset_ms`)
- 2 pre-existing LLM config test failures (DeepSeek override)
- `COMPENSATION_MIN_OFFSET_MS = 160` pre-existing change not in W1 scope
- `lipsync_thresholds.yaml` thresholds pre-existing TKT-104 calibration

## Verdict: PASS

REPAIR-601B-W1 accepted. All 4 acceptance gates pass independently. No findings. Ready for W2.