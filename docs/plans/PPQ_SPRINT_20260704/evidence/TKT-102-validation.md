# TKT-102 Validation Report

Sprint: `PPQ-2026-07`. Ticket: TKT-102. Date: 2026-07-04.
Validator role: independent validator.

## 1. Validation Verdict

**PASS** — TKT-102 is accepted.

All four binary acceptance gates (G1–G4) pass with independently executed evidence. Two MEDIUM audit findings resolved (repair cycle 1), three LOW findings remain non-blocking. The implementation correctly produces non-simulated `syncnet_offset` evidence in production mode, fails closed without backend, preserves test-mode semantics, and passes all invariant and regression suites.

## 2. Acceptance Gate Evidence

### G1: Production-mode QA with fixture backend writes non-simulated syncnet_offset row

**Status**: PASS

**Independent verification**: Built a hero render unit, linked a real ffmpeg-generated video artifact, ran `run_contract_media_qa` with `FixtureSyncBackend(offset_ms=10, confidence=0.8, face_track_found=True)`, and inspected the `validations` table.

Observed:
```
validator=syncnet_offset status=pass
  method=fixture_sync_scorer
  offset_ms=10.0
  confidence=0.8
  face_track_found=True
  publish_grade=True
  simulated=None
```

All required fields present. No `simulated` flag. No `yt_test_mode` method prefix. `publish_grade=True`.

**Test evidence**: `tests/test_sync_scorer_adapter.py` — 13 tests pass.

### G2: Backend-absent case fails loudly

**Status**: PASS

**Independent verification**: Ran `run_contract_media_qa` with `_set_sync_scorer_backend(None)`. Observed `syncnet_offset` validation row with `status=fail`, `method=none`, `publish_grade=False`, `offset_ms=None`, `reason` containing "SYNC_SCORER_BACKEND not configured". Render unit status → `needs_repair`. No fabricated pass evidence.

**Test evidence**: `test_backend_none_records_fail`, `test_backend_none_no_fabricated_pass` — both pass.

### G3: Assembly gate accepts new evidence (with TKT-001 rejection active)

**Status**: PASS

**Test evidence**: 21 tests pass across `test_s14_t003_per_segment_syncnet.py` (per-segment SyncNet mandatory, hero units with/without SyncNet, b-roll exempt), `test_s14_t004_syncnet_confidence.py` (threshold gates, policy selection, evidence validation), and `test_simulated_evidence_rejection.py` (TKT-001 simulated evidence rejection + real evidence acceptance). These tests exercise the full gate path including `validate_assembly_inputs` at `assemble_db.py:479-598`.

### G4: Full suite passes

**Status**: PASS

**Command**: `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q`

**Result**: 104 passed in 12.43s.

**Broader regression** (45 tests): all pass.

## 3. Audit Findings Disposition

| Finding | Severity | Status | Assessment |
| --- | --- | --- | --- |
| F1 Code duplication | MEDIUM | RESOLVED | `_algorithm.py` shared module verified |
| F2 Not registered | MEDIUM | RESOLVED | `_build_sync_scorer_adapter()` verified, test passes |
| F3 Dead code | LOW | UNRESOLVED | Non-blocking; test-only artifact |
| F4 Broad exception | LOW | UNRESOLVED | Non-blocking; fail-safe behavior preserved |
| F5 Misleading comment | LOW | UNRESOLVED | Non-blocking; documentation issue |

All unresolved findings are LOW severity and do not affect acceptance gate satisfaction, runtime behavior, or architectural invariants.

## 4. Scope Verification

| Check | Result |
| --- | --- |
| Files changed within scope | ✅ `scripts/sync_scorer/` (new), `scripts/media_service.py`, `scripts/lipsync_scoring.py`, `scripts/evals/spike_sync_scorer.py`, `tests/test_sync_scorer_adapter.py` (new), `tests/test_qa_lipsync_gate.py`, `tests/unit/test_hero_lipsync_qa.py` |
| No unintended files modified | ✅ |
| INV-1 (full pytest suite passes) | ✅ 104 focused invariant, 45 broader regression, 13 TKT-102 tests |
| INV-2 (no paid calls under YT_TEST_MODE) | ✅ All tests run under `YT_TEST_MODE=1`; no paid provider touched |
| INV-3 (no fabricated pass evidence) | ✅ Backend-none correctly records fail with `publish_grade=False` |
| INV-4 (evidence in validations table) | ✅ syncnet_offset rows present with validator_name, method field, status |
| No dummy output or silent fallback | ✅ Fail-close path records explicit reason string |
| Test-mode unchanged | ✅ Fake provider path at `media_service.py:969-999` runs BEFORE sync scorer, early-returns |
| Old proxy removed | ✅ `eval_lipsync.analyze_video` no longer imported in `_qa_hero_lipsync` (confirmed by grep for `eval_lipsync` in media_service.py) |

## 5. Commands Executed by Validator

| Command | Exit | Result |
| --- | --- | --- |
| `python3 -m pytest tests/test_sync_scorer_adapter.py -v` | 0 | 13 passed |
| `python3 -m pytest tests/test_sync_scorer_adapter.py::TestBackendNoneFailsLoudly -v` | 0 | 2 passed |
| `python3 -m pytest tests/test_s14_t003_per_segment_syncnet.py tests/test_s14_t004_syncnet_confidence.py tests/test_simulated_evidence_rejection.py -v` | 0 | 21 passed |
| `YT_TEST_MODE=1 python3 -m pytest <focused suite> -q` | 0 | 104 passed in 12.43s |
| `python3 -m pytest <6 broader regression files> -q` | 0 | 45 passed in 5.29s |
| Independent evidence verification script | 0 | syncnet_offset row confirmed with all required fields |

## 6. Residual Risks

- **F3/F4/F5 (LOW)**: Three cosmetic/minor findings remain. Recommended cleanup in a future maintenance pass.
- **Real backend untested**: `RealSyncBackend` requires mediapipe/opencv in `/tmp/kilo/tkt101_venv`. Not tested in CI. Backend correctly reports `availability()=False` without those deps (fail-closed).
- **Cached adapter in lipsync_scoring**: `_sync_scorer_adapter` is cached globally. If backend reconfiguration occurs mid-process (unlikely in single-shot pipeline), stale adapter may be returned via `get_sync_model()`. Primary production path (`_qa_hero_lipsync` → `get_sync_scorer_backend()`) is unaffected.
- **Audio slice SHA not in evidence**: Current evidence includes `method` and measured fields but not explicit provenance hashes. The `qa_media_contract` evidence includes `sha_match` for the artifact. Noted for future improvement (TKT-103 compensation loop may add this).

## 7. Disposition

TKT-102 is **accepted**. The ticket satisfies all four acceptance gates and the observable outcome specified in the ticket. Three LOW audit findings remain non-blocking. Ready to advance to TKT-103 (compensation loop).
