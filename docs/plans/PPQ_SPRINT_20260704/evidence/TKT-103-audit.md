# TKT-103 Audit Report

**Auditor:** independent (audit-ticket skill)
**Date:** 2026-07-04T23:20:05+08:00
**Commit:** efe2e2e
**Verdict:** PASS_WITH_FINDINGS

## G1: Measure → compensate → re-measure loop with distinct validation rows — PASS

- `test_correctable_offset_compensates_and_passes`: Fixture backend returns 120ms then 5ms. QA detects CORRECTABLE → repair runs compensate → re-measures → passes → `compensated_artifact_path` set ✓
- `compensation_attempt` validation row written with `offset_ms=120.0` ✓
- Re-measure `syncnet_offset` validation row written with `offset_ms=5.0` ✓
- Two distinct validation rows: one pre-compensation, one post-compensation ✓

## G2: Failing re-measure never sets compensated_artifact_path — PASS

- `test_failing_compensation_routes_to_regeneration`: constant 120ms backend — compensation runs, re-measure produces same 120ms → repair routes to regeneration ✓
- `compensated_artifact_path` remains NULL after failed compensation ✓
- Change request for regeneration created ✓

## G3: Full suite passes — PASS

- 3 compensation loop tests pass
- 5 remux CLI regression tests pass
- 104 focused invariant tests pass
- 50 broader regression tests pass

---

## Findings

### FINDING-1 (MEDIUM): Compensation band not aligned with TKT-104 calibrated policy thresholds

- **File:** `scripts/compensate.py:13-14` vs `configs/lipsync_thresholds.yaml`
- **Issue:** `COMPENSATION_MIN_OFFSET_MS=40` is lower than the calibrated `close_hero pass_ms=120`. Offsets 40-120ms are PASS by policy (no gating impact) but QA flags them as CORRECTABLE, routing them into the compensation loop unnecessarily. This wastes CPU/IO cycles and writes spurious `compensation_attempt` validation rows at offsets that would pass assembly.
- **Evidence:** Policy says offsets ≤120ms pass. QA code (`_qa_hero_lipsync`) uses `offset >= COMPENSATION_MIN_OFFSET_MS` (40) to set `lipsync_review_status=CORRECTABLE`. Gap: offsets 40-120ms are both PASS and CORRECTABLE.
- **Required correction:** Set `COMPENSATION_MIN_OFFSET_MS` to `close_hero pass_ms` (120) or the policy fail boundary (160). Document that compensation only triggers when a clip would fail assembly.
- **Required regression test:** Test that an offset of 80ms (within 40-120 range) gets `lipsync_review_status=PASS` not CORRECTABLE. Test that compensation is NOT triggered for offsets below 120ms.

### FINDING-2 (LOW): offset_ms_applied sign ambiguity in compensate()

- **File:** `scripts/compensate.py:70`
- **Issue:** `"offset_ms_applied": delay_ms if offset_ms < 0 else -delay_ms` — the docstring says "a negative offset means source audio needs to be delayed", but the compensation applies `abs(offset_ms)` with `adelay={delay_ms}`. The sign in the result dict flips neg→pos and pos→neg, creating ambiguity about what was actually applied.
- **Evidence:** The caller in `media_service.py` passes `int(offset_ms)` directly (could be positive or negative from the scorer). The compensate function applies `abs(offset_ms)` in delay. The result dict then flips sign back.
- **Required correction:** Either always store positive `offset_ms_applied` matching the actual `adelay` value, or store sign with explicit explanation. Current sign-flip is confusing.
- **Required regression test:** Test that `compensate()` returns `offset_ms_applied` matching intended direction.

### FINDING-3 (LOW): _reset_render_unit_for_repair may clobber concurrent state

- **File:** `scripts/media_service.py:1867` (call site in compensate_hero_audio handler)
- **Issue:** `_reset_render_unit_for_repair` sets `status='generated'` unconditionally. If another repair action or the parent orchestration has updated the status since the last read, this could clobber it. The repair lifecycle is single-threaded inside `run_repair_lifecycle`, but the ticket audit focus is "idempotency across resume" — a partially completed compensation on resume could re-trigger.
- **Evidence:** Handler does `_reset_render_unit_for_repair(render_unit_id, db_path)` then `UPDATE render_units SET status='generated'...`. On resume, if compensation already ran, the re-run would re-compensate again — but the idempotency key in `record_validation_evidence` may mitigate this (depends on validation dedup).
- **Required correction:** Add explicit check for prior `compensation_attempt` validation before re-running compensation, or use a meaningful non-replayable state transition.
- **Required regression test:** Test that running compensation handler twice on the same unit does not produce duplicate compensated artifacts.

---

## Audit Summary

| Gate | Verdict | Evidence |
|------|---------|----------|
| G1 (measure→compensate→re-measure) | PASS | 3 tests covering correctable, uncorrectable, failing-compensation |
| G2 (no compensated path on fail) | PASS | `test_failing_compensation_routes_to_regeneration` verifies NULL path |
| G3 (full suite passes) | PASS | 104 invariant + 3 comp + 5 remux + 50 regression |

**Overall:** PASS_WITH_FINDINGS — 1 MEDIUM (F1: compensation band misaligned with TKT-104 thresholds), 2 LOW (F2: sign ambiguity, F3: potential idempotency issue). All three are actionable without architectural redesign.

**Reservoir risks:**
- Compensation band constants documented as "placeholders" in the original commit message, unchanged post-TKT-104
- Video is stream-copied (no re-encode) — correct for HERO_SYNC_LOCKED protection ✓
- `broad except Exception` in sync scorer call site (inherited from TKT-102 F4, unaddressed)
- Compensation reuses `run_contract_media_qa` for re-measurement — correct contract path
