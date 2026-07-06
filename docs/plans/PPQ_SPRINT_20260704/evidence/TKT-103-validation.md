# TKT-103 Validation Report

**Validator:** independent (validate-scope skill)
**Date:** 2026-07-04T23:30:05+08:00
**Verdict:** PASS

## Gate Verification

### G1: Measure → compensate → re-measure loop with distinct validation rows — PASS

**Evidence:** `test_correctable_offset_compensates_and_passes` (200ms offset)
- Fixture backend returns 200ms (first call) → QA detects CORRECTABLE ✓
- Repair lifecycle runs `compensate_hero_audio` → ffmpeg adelay remux ✓
- Re-measure returns 5ms → QA passes → `compensated_artifact_path` set ✓
- `compensation_attempt` validation row written with `offset_ms=200.0` ✓
- Re-measure `syncnet_offset` validation row written with `offset_ms=5.0` ✓
- Two distinct validation rows: pre-compensation (200ms) and post-compensation (5ms) ✓

### G2: Failing re-measure never sets compensated_artifact_path — PASS

**Evidence:** `test_failing_compensation_routes_to_regeneration` (constant 200ms backend)
- Compensation runs → re-measure returns same 200ms → `compensated=False` ✓
- Change request for regeneration created ✓
- `compensated_artifact_path` remains NULL ✓

### G3: Full suite passes — PASS

| Test suite | Result |
|-----------|--------|
| `test_offset_compensation_loop.py` | 3/3 passed |
| `test_remux_compensated_hero.py` | 5/5 passed |
| `test_sync_scorer_adapter.py` | 13/13 passed |
| Focused invariant (104 tests) | 104/104 passed |

Pre-existing failure: `test_eval_lipsync_low_confidence_requires_human_review` (TKT-101 era, old eval_lipsync proxy path). Unrelated to TKT-103.

## Audit Finding Resolution

| Finding | Severity | Status |
|---------|----------|--------|
| F1: Compensation band misaligned | MEDIUM | RESOLVED — MIN changed 40→160, aligned with fail_ms |
| F2: offset_ms_applied sign ambiguity | LOW | UNRESOLVED, non-blocking |
| F3: idempotency on resume | LOW | UNRESOLVED, non-blocking |

## Production Path Verification

- `compensate()` function extracted from `remux_compensated_hero.py` into `scripts/compensate.py` ✓
- CLI wrapper in `remux_compensated_hero.py` still functional (imports from compensate.py) ✓
- `hero_lipsync_offset_correctable` classification wired in `classify_validation_failure()` ✓
- `compensate_hero_audio` action wired in `run_repair_lifecycle()` ✓
- `compensated_artifact_path` set on provider_jobs table on success ✓
- Video stream copied (no re-encode) — HERO_SYNC_LOCKED compliant ✓
- Audio delayed via ffmpeg `adelay` filter — correct for time alignment ✓

## Residual Risks

- Pre-existing TKT-101 eval_lipsync test failure (separate subsystem)
- LOW findings F2 (sign ambiguity) and F3 (idempotency) remain
- Compensation band (160-400ms) defined statically; no dynamic policy binding

**TKT-103 ACCEPTED**
