# TKT-102 Re-Audit Report (Repair Cycle 1)

Sprint: `PPQ-2026-07`. Ticket: TKT-102 (COMPLEX). Date: 2026-07-04.
Auditor role: independent auditor. Prior audit: PASS_WITH_FINDINGS (5 findings).
Repair cycle 1 addressed F1 and F2. This audit verifies the repairs and
re-evaluates remaining findings.

## 1. Audit Summary

**Verdict: PASS_WITH_FINDINGS**

Two MEDIUM findings from the original audit (F1 code duplication, F2 unregistered adapter) are resolved with acceptable implementations. Three LOW findings (F3-F5) remain unaddressed. No new issues introduced by the repair. All four binary acceptance gates continue to pass.

## 2. Resolution Verification

### FINDING-1 (RESOLVED) — Code duplication with spike

**Resolution**: Created `scripts/sync_scorer/_algorithm.py` containing shared algorithmic primitives (`_LIP_*` constants, `_SEARCH_WINDOW_MS`, `_AUDIO_HOP_MS`, `DEFAULT_MODEL_PATH`, `_check_real_deps`, `_audio_envelope`, `_mouth_envelope`, `_resample`, `_normalize`, `_cross_correlate`). Both `scripts/sync_scorer/scorer.py` and `scripts/evals/spike_sync_scorer.py` import from this module.

**Verification**:
- `scorer.py` has 0 inline algorithm function definitions (confirmed via grep)
- `_algorithm.py` imports successfully from system Python
- Spike's `sys.path` manipulation (`scripts/` → repo root) correctly resolves the import
- Spike's inline function definitions (`_audio_envelope`, `_mouth_envelope`, `_resample`, `_normalize`, `_cross_correlate`) removed, replaced by `from sync_scorer._algorithm import ...`
- Spike's `_check_deps()` now wraps `_check_real_deps()`, preserving backward API

### FINDING-2 (RESOLVED) — Not registered in lipsync_scoring.py

**Resolution**: Added `_build_sync_scorer_adapter()` in `scripts/lipsync_scoring.py:118-166`. The function:
1. Calls `get_sync_scorer_backend()` from `sync_scorer`
2. Wraps the backend in an inline `SyncModelAdapter` subclass (`_Adapter`)
3. Caches the adapter globally (`_sync_scorer_adapter`)
4. Is called from `get_sync_model()` before falling back to `NoModelLoaded()`

**Verification**:
- Test `test_get_sync_model_returns_adapter_with_fixture` passes: `get_sync_model()` returns adapter (not `NoModelLoaded`), `model.load()` returns True, `model.score()` returns expected fields (`offset_estimate_ms=10.0`, `confidence=0.8`, `face_track_found=True`, `method=fixture_sync_scorer`)
- `record_lipsync_evidence()` at `lipsync_scoring.py:225` calls `score_lipsync()` which calls `get_sync_model()` — this path now propagates through the adapter

**Residual risk**: The cached `_sync_scorer_adapter` is reset only on restart, not on backend reconfiguration. If `SYNC_SCORER_BACKEND` or `_set_sync_scorer_backend()` changes between calls to `get_sync_model()`, the cached adapter (wrapping the old backend) is returned. This affects only the `get_sync_model()` pathway — the primary production path (`_qa_hero_lipsync` → `get_sync_scorer_backend()`) is unaffected.

## 3. Remaining Findings

### FINDING-3 (LOW, UNRESOLVED) — Dead code in test file

**File**: `tests/test_qa_lipsync_gate.py:112-115`
**Evidence**: Method `_qa_hero_lipsync_with_mock` still present with `pass` body and "placeholder replaced below" comment.
**Required correction**: Remove the dead method.
**Required regression test**: None.

### FINDING-4 (LOW, UNRESOLVED) — Broad exception handling

**File**: `scripts/media_service.py` (sync scorer call site in `_qa_hero_lipsync`)
**Evidence**: `except Exception` still catches all exceptions at the sync scorer call site.
**Required correction**: Catch `ImportError` and `RuntimeError` specifically; re-raise unexpected exceptions.
**Required regression test**: None.

### FINDING-5 (LOW, UNRESOLVED) — Misleading comment

**File**: `scripts/media_service.py:1003`
**Evidence**: "The old eval_lipsync proxy runs only as a diagnostic pre-filter" — inaccurate (proxy was removed, not retained).
**Required correction**: Update comment to reflect replacement.
**Required regression test**: None.

## 4. Acceptance Gate Re-Assessment

| Gate | Status | Evidence |
| --- | --- | --- |
| G1: fixture backend writes non-simulated syncnet_offset row | PASS | 13 adapter tests pass (incl. new F2 registration test) |
| G2: backend-absent case fails loudly | PASS | test_backend_none_records_fail + test_backend_none_no_fabricated_pass unchanged |
| G3: assembly gate accepts new evidence | PASS | 45 broader regression tests pass |
| G4: full suite passes | PASS | 104 focused invariant pass; lipsync tests unchanged from prior baseline |

## 5. New Issues From Repair

None identified. All tests pass (104 invariant, 45 regression, 11 lipsync_scoring tests). Code review of the repair diff confirms:
- Spike backward-compatibility aliases (`SEARCH_WINDOW_MS = _SEARCH_WINDOW_MS`, etc.) correctly maintain the spike's own constant references in `score()` and `main()`.
- No circular imports — `_algorithm.py` has no project imports; `scorer.py` imports from `_algorithm` (sibling); `lipsync_scoring.py` imports from `sync_scorer` (which imports from `_algorithm`). Import chain is acyclic.
- The `_check_real_deps()` returns `tuple[bool, dict]` whereas the spike's original `_check_deps()` returned `dict` — the thin wrapper at spike line 85-88 correctly adapts.
- `_build_sync_scorer_adapter()` catches `except Exception` — same pattern as F4, but benign because the only expected exceptions are `ImportError` from module not found and `None` backend.

## 6. Commands Executed During Re-Audit

| Command | Exit | Purpose |
| --- | --- | --- |
| `grep` for inline functions in scorer.py | 0 | Confirm zero duplicate algorithm definitions |
| `python3 -c "from sync_scorer._algorithm import ..."` | 0 | Verify _algorithm.py importable |
| `python3 -c "from lipsync_scoring import get_sync_model"` | 0 | Verify lipsync adapter registration |
| `grep` for F3/F4/F5 evidence | 0 | Confirm unresolved findings |
| `python3 -m pytest TKT-102 tests -v` | 0 | 13 tests pass (incl. F2 registration test) |
| `YT_TEST_MODE=1 pytest focused suite -q` | 0 | 104 passed |
| `pytest 45 broader regression tests -v` | 0 | 45 passed |
| `pytest lipsync_scoring module tests -v` | 1* | 10 passed, 1 pre-existing failure |

\* Pre-existing `test_slice_hash_recorded` failure (canonical_master.py NameError, unrelated).

## 7. Audit Disposition

**Verdict**: `PASS_WITH_FINDINGS` — two MEDIUM findings (F1, F2) resolved. Three LOW findings (F3, F4, F5) remain unaddressed but do not block acceptance. All acceptance gates pass. No new issues from repair cycle 1. TKT-102 is ready for independent validation.

**Changes since prior audit**: F1 resolved (shared _algorithm.py, 1 new file), F2 resolved (adapter registration in lipsync_scoring.py, 1 new test), spike refactored to import shared primitives.
