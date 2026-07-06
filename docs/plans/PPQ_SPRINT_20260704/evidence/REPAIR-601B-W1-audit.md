# REPAIR-601B-W1 — Audit Report

**Date**: 2026-07-06T19:05:00+08:00
**Auditor**: independent
**Verdict**: PASS

## Audit steps

### 1. Root cause evidence

| Claim | Evidence | Verdict |
|---|---|---|
| Defect C: `abs(offset_ms)` always delays audio, wrong for positive offsets | `compensate.py:31` (old): `delay_ms = abs(offset_ms)` | CONFIRMED |
| Defect D: 400ms cap rejects 480ms offset | `compensate.py:14` (old): `COMPENSATION_MAX_OFFSET_MS = 400` | CONFIRMED |
| Inverted docstring: `_algorithm.py:181` said "lag>0 means audio leads" | `_algorithm.py:181` (old): `lag>0 means audio leads` | CONFIRMED |
| Baseline offset: +480ms (audio lags mouth) | Real scorer: `offset_ms=480.0, confidence=0.1898` | CONFIRMED |

### 2. Observable outcome verification

| Requirement | Implementation | Verdict |
|---|---|---|
| Directional correction for positive offset | `atrim=start={offset_ms}ms,asetpts=PTS-STARTPTS` (advances audio) | PASS |
| Negative offset still uses `adelay` | `adelay={delay_ms}\|{delay_ms}` (current behavior preserved) | PASS |
| Cap raised to ≥500ms | `COMPENSATION_MAX_OFFSET_MS = 600` | PASS |
| Cap justification documented | `configs/lipsync_thresholds.yaml`: compensation_cap_ms block with scorer search window reference | PASS |
| Docstring fixed | `_algorithm.py:181`: "lag>0 means audio lags" | PASS |
| Re-score after compensate | `media_service.py:2103`: `qa = run_contract_media_qa(...)` after compensation | PASS (preexisting) |

### 3. Production execution path

- `media_service.py:25`: imports `COMPENSATION_MAX_OFFSET_MS` from `compensate` → classification uses updated 600
- `media_service.py:1160-1170`: `offset >= COMPENSATION_MIN_OFFSET_MS (160) && offset <= COMPENSATION_MAX_OFFSET_MS (600)` → 480ms classified CORRECTABLE ✓
- `media_service.py:2068`: `compensate(video_path, audio_path, int(offset_ms), compensated_path)` → directional logic applied ✓
- `media_service.py:2103`: `run_contract_media_qa(...)` re-scores compensated artifact ✓

### 4. Test coverage

| Scenario | Test | Expected | Result |
|---|---|---|---|
| Positive offset advances audio | `test_positive_offset_advances_audio` | `offset_ms_applied = -480` | PASS |
| Negative offset delays audio | `test_negative_offset_delays_audio` | `offset_ms_applied = 300` | PASS |
| Cap raised to 600 | `test_compensation_cap_raised` | `COMPENSATION_MAX_OFFSET_MS == 600` | PASS |
| 480ms correctable with raised cap | `test_positive_offset_correctable_with_raised_cap` | CORRECTABLE, compensated=True | PASS |
| 700ms uncorrectable (>600) | `test_offset_above_cap_uncorrectable` | FAIL, routed to regen | PASS |
| Positive offset produces valid output | `test_positive_offset_reduces_measured_offset` | output exists, duration > 0 | PASS |
| Existing correctable test | `test_correctable_offset_compensates_and_passes` | 200ms (updated from 120ms) | PASS |
| Existing uncorrectable test | `test_uncorrectable_offset_routes_to_regeneration` | 800ms (unchanged, >600) | PASS |
| Existing failing compensation | `test_failing_compensation_routes_to_regeneration` | 200ms (updated from 120ms) | PASS |

### 5. E2E proof

Real hero clip `pjob_cd63c3115fdb48fcbaf482c6e6d9c349.mp4`:
- Before: **+480ms** (audio lags mouth)
- After directional compensation: **-40ms**
- `close_hero` pass threshold: ≤120ms → **PASS**

### 6. Regression checks

- No thresholds in `lipsync_thresholds.yaml` weakened (pre-existing TKT-104 calibration changes already in working tree; W1 only added `compensation_cap_ms`)
- Negative offset compensation path unchanged (adelay preserved)
- Invariant suite: 145/147 passed (2 pre-existing LLM config failures)
- Compensation tests: 9/9 passed

### 7. Pre-existing modifications noted

- `COMPENSATION_MIN_OFFSET_MS = 40` → `160` (pre-existing, not introduced by W1)
- `lipsync_thresholds.yaml` close_hero/medium_hero threshold changes (pre-existing TKT-104 calibration)
- `configs/llm_models.yaml` DeepSeek model override (pre-existing TKT-601 run)

### 8. Residual risks

- `atrim` approach for positive offsets trims leading audio content — the first `offset_ms` of speech is lost; acceptable per plan scope
- 2 pre-existing LLM config test failures (DeepSeek override) unrelated to this change
- `COMPENSATION_MIN_OFFSET_MS = 160` pre-existing change not in scope of W1 audit

## Verdict: PASS

No findings. All 4 acceptance gates verified. Ready for validation.