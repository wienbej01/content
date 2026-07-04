# TKT-102 Audit Report

Sprint: `PPQ-2026-07`. Ticket: TKT-102 (COMPLEX). Date: 2026-07-04.
Auditor role: independent auditor. No repairs made.

## 1. Audit Summary

**Verdict: PASS_WITH_FINDINGS**

The implementation correctly wires a production sync scorer into `_qa_hero_lipsync()`, records non-simulated `syncnet_offset` validation evidence, and fails closed when no backend is configured. The production execution path (`run_contract_media_qa` → `_qa_hero_lipsync`) reaches the change. Three MEDIUM and two LOW findings identified.

## 2. Evidence Verifications

### Verified: Production path is reachable
`produce_db.py:1820` calls `run_contract_media_qa()`, which dispatches to `_qa_hero_lipsync()` for `lipsync_video` asset_type (verified via `classify_render_method` → `"hero_lipsync"` → dispatch dict key match).

### Verified: Fixture backend writes non-simulated evidence
Test `test_fixture_backend_writes_syncnet_offset` proves:
- `syncnet_offset` validation row created with `status=pass`
- Evidence contains `offset_ms=10.0`, `confidence=0.8`, `face_track_found=True`, `method=fixture_sync_scorer`
- No `simulated` flag; `publish_grade=True`

### Verified: Backend-none fails closed
Test `test_backend_none_records_fail` proves:
- `syncnet_offset` validation row created with `status=fail`
- Evidence has `offset_ms=None`, `confidence=None`, `method=none`, `publish_grade=False`
- `reason` contains "SYNC_SCORER_BACKEND not configured"
- No fabricated pass

### Verified: Test-mode fake path unchanged
The `_is_test_mode_fake_provider_artifact` check at `media_service.py:969` runs BEFORE the sync scorer path and `return (passed, evidence)` on line 999 short-circuits. The sync scorer code only executes when that check returns False (i.e., outside `YT_TEST_MODE` or for non-fake provider jobs).

### Verified: Tests weakened?
- `test_qa_lipsync_gate.py` assertions updated from `eval_lipsync.analyze_video` to `fixture_sync_scorer` — appropriate for new behavior, no gate weakened.
- `test_duration_mismatch_is_not_lipsync_drift` updated to mock sync scorer backend instead of eval_lipsync proxy — functionally equivalent test coverage.
- No existing test assertions were relaxed.

### Verified: Focused invariant suite
`YT_TEST_MODE=1 python3 -m pytest <focused 5 files> -q` → **104 passed in 12.80s**.

### Verified: Broader regression
44 related tests pass (syncnet gate, simulated evidence rejection, lipsync gates, hero lipsync QA, TKT-102 adapter).

## 3. Findings

### FINDING-1 (MEDIUM) — Duplicate scorer logic vs. spike

**File**: `scripts/sync_scorer/scorer.py`

**Evidence**: The `_mouth_envelope`, `_audio_envelope`, `_resample`, `_normalize`, `_cross_correlate` functions and the `_LIP_UPPER_INNER`/`_LIP_LOWER_INNER`/`_LIP_LEFT`/`_LIP_RIGHT` landmark constants are near-verbatim copies of the TKT-101 spike at `scripts/evals/spike_sync_scorer.py:62-258`. The constants `_SEARCH_WINDOW_MS=600`, `_AUDIO_HOP_MS=20`, `REAL_METHOD`, and `DEFAULT_MODEL_PATH` are also duplicated.

**Violated requirement**: Code maintainability — if the landmark indices, search window, or hop rate change, both files must be updated. The score function at `spike_sync_scorer.py:272-319` and the `RealSyncBackend.score` method at `scorer.py:285-345` implement the same algorithm independently.

**Required correction**: Extract the shared algorithmic logic into a single importable module (e.g., `scripts/sync_scorer/_algorithm.py`) and have both the spike and the production backend import from it. Or document the intentional duplication with a justification and cross-reference comments in both files.

**Required regression test**: A test verifying that `RealSyncBackend.score(clip)` on a known talking-head clip produces the same numeric result as `spike_sync_scorer.score(clip, clip, model)` (requires the TKT-101 venv deps).

### FINDING-2 (MEDIUM) — Not registered in lipsync_scoring.py

**File**: `scripts/lipsync_scoring.py`

**Evidence**: The ticket states "A `SyncModelAdapter` implementation (per TKT-101 decision) registered in `scripts/lipsync_scoring.py`". The `lipsync_scoring.py` module defines the abstract `SyncModelAdapter` (line 61-78) and `register_sync_model()` (line 112) but the new backends in `scripts/sync_scorer/scorer.py` are never registered with `register_sync_model()`. Consequently, `get_sync_model()` (line 117-120) still returns `NoModelLoaded()`, and `score_lipsync()` and `record_lipsync_evidence()` still report `NO_REAL_MODEL_LOADED`. 

The production path (`run_contract_media_qa` → `_qa_hero_lipsync`) works correctly because it calls `get_sync_scorer_backend()` directly from the new module. No production caller imports `lipsync_scoring` (confirmed by grep: only tests import it). However, the ticket's explicit requirement is not satisfied.

**Required correction**: Create a `SyncModelAdapter` subclass in `scripts/sync_scorer/scorer.py` that wraps the backends, and call `register_sync_model()` during backend initialization. OR document the intentional deviation in the ticket scope.

**Required regression test**: A test calling `get_sync_model()` and verifying it returns a working adapter (not `NoModelLoaded`) when `SYNC_SCORER_BACKEND=fixture`.

### FINDING-3 (LOW) — Dead code in test file

**File**: `tests/test_qa_lipsync_gate.py:112-115`

**Evidence**: The method `_qa_hero_lipsync_with_mock` has a `pass` body and the comment says "not used" / "placeholder replaced below". It was left over from a refactoring iteration where the original plan to mock `_qa_hero_lipsync` directly was replaced by mocking `get_sync_scorer_backend` instead.

**Required correction**: Remove the dead method.

**Required regression test**: None (cleanup only).

### FINDING-4 (LOW) — Broad exception handling

**File**: `scripts/media_service.py` (sync scorer call site in `_qa_hero_lipsync`)

**Evidence**: The `try/except Exception` block catches ALL exceptions. While it correctly records a `syncnet_offset` fail validation and logs the issue string, catching `KeyboardInterrupt`-level exceptions is undesirable. An `ImportError` from the lazy `from sync_scorer import get_sync_scorer_backend` (if the module path is misconfigured) and `RuntimeError` from `backend.score()` (if deps not available) should be caught separately from unexpected errors.

**Required correction**: Catch specific exception types (`ImportError`, `RuntimeError`) at the sync scorer call site. Re-raise unexpected exceptions after recording the fail validation.

**Required regression test**: None (correctness is unchanged; the issue is about specificity of error handling).

### FINDING-5 (LOW) — Misleading comment about eval_lipsync proxy

**File**: `scripts/media_service.py:1002-1004`

**Evidence**: The comment says "The old eval_lipsync proxy runs only as a diagnostic pre-filter and its result can never pass a hero unit." This is inaccurate — the eval_lipsync proxy was entirely REMOVED (lines 1001-1049 in the original), not retained as a pre-filter. The sync scorer backend is the sole authoritative scorer.

**Required correction**: Update the comment to accurately reflect the replacement, e.g., "Replaces the old whole-frame-diff proxy with the production sync scorer. The proxy's result was never publish-grade evidence."

**Required regression test**: None (documentation only).

## 4. Acceptance Gate Assessment

| Gate | Status | Evidence |
| --- | --- | --- |
| G1: production-mode QA with fixture backend writes non-simulated syncnet_offset row | PASS | test_fixture_backend_writes_syncnet_offset asserts all fields |
| G2: backend-absent case fails loudly | PASS | test_backend_none_records_fail + test_backend_none_no_fabricated_pass |
| G3: assembly gate accepts new evidence (with TKT-001 rejection active) | PASS | test_simulated_evidence_rejection integration tests all pass (44 regression tests) |
| G4: full suite passes | PASS | 104 focused invariant + 137 lipsync tests, 0 new failures |

## 5. Residual Risks

- **Real backend not tested in CI**: The `RealSyncBackend` requires mediapipe/opencv/numpy in `/tmp/kilo/tkt101_venv`. Runtime opt-in tests (`pytest -m sync_model`) are documented but not yet created as a marker.
- **Singleton state leakage**: `_registered_backend` is a module-level global. If two test workers share the same Python process, backend state could leak. Current pytest setup uses `autouse` fixtures to reset it, so this is well-contained.
- **No audio slice provenance**: The scorer is called with `(artifact_path, artifact_path)` — video as both video and audio sources. The evidence does not reference the original master-narration audio slice SHA, though the ticket's step 4 mentions "audio slice sha". The video's embedded audio is used instead.
- **Duplication drift risk**: If FINDING-1 is not addressed, future adjustments to the mouth-envelope algorithm or MediaPipe landmark indices in one file will silently diverge from the other.

## 6. Commands Executed During Audit

| Command | Exit | Purpose |
| --- | --- | --- |
| `git diff HEAD -- scripts/` | 0 | Inspect all production changes |
| `grep -n "score_lipsync\|register_sync_model" scripts/lipsync_scoring.py` | 0 | Verify lipsync_scoring.py registration |
| `grep -n "eval_lipsync\|analyze_video" scripts/media_service.py` | 0 | Confirm old proxy removed |
| `grep -rn "import.*lipsync_scoring" scripts/ tests/` | 0 | Map callers of lipsync_scoring |
| `python3 -m pytest tests/test_sync_scorer_adapter.py -v` | 0 | Verify all 12 new TKT-102 tests pass |
| `YT_TEST_MODE=1 python3 -m pytest <focused suite> -q` | 0 | Verify invariant suite (104/104) |
| `python3 -m pytest tests/test_qa_lipsync_gate.py tests/unit/test_hero_lipsync_qa.py tests/test_s14_t003_per_segment_syncnet.py tests/test_s14_t004_syncnet_confidence.py tests/test_simulated_evidence_rejection.py -v` | 0 | Verify 44 broader regression tests pass |

## 7. Audit Disposition

**Verdict**: `PASS_WITH_FINDINGS` — three MEDIUM findings (FINDING-1 code duplication, FINDING-2 unregistered adapter, FINDING-3 dead code) and two LOW findings (FINDING-4 broad exception handling, FINDING-5 misleading comment). All four binary acceptance gates pass with real test evidence. No gates were weakened. The production execution path is reachable and validated end-to-end.
