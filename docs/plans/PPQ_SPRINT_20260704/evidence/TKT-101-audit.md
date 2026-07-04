# TKT-101 Audit Report

**Auditor role**: independent auditor (not the engineer who implemented TKT-101)
**Date**: 2026-07-04T21:50:12+08:00
**Verdict**: PASS_WITH_FINDINGS

## Scope

Audit of TKT-101 commit `a4316e4` — "discovery: select and prove a face-tracked AV-sync scorer". The ticket is a REASONING_CRITICAL discovery ticket; no production modules were modified. Scope is limited to the decision record and the spike script.

## Audit Questions

| # | Question | Result |
|---|---|---|
| 1 | Root cause supported by evidence? | PASS. CS-3 (`eval_syncnet.py` returns `not_run`) confirmed. SyncNet_v2 weight licensing and Python-2-era toolchain risks correctly documented. |
| 2 | Change satisfies observable outcome? | PASS. Decision record + runnable spike exist and execute correctly. |
| 3 | Production execution path reaches the change? | N/A (spike only, no production wiring per ticket scope). |
| 4 | Tests fail without implementation? | N/A (discovery ticket; TKT-101 does not require unit tests). |
| 5 | Success and failure paths covered? | PASS. unshifted, shifted (+200ms differential), mismatch, no_face_track, deps_missing, audio_decode_failed all handled with distinct status codes. |
| 6 | Tests prove production behavior? | N/A (spike only). |
| 7 | Hidden duplicate state, fallback, swallowed failure? | PASS (no fallback; stateless; exit code 2 on precondition failure). |
| 8 | Partial output, stale state, retries, concurrency? | PASS (stateless deterministic scorer; two consecutive unshifted runs produce identical results). |
| 9 | Existing tests/gates weakened? | PASS (no production changes; 104/104 invariant suite passes). |
| 10 | Unrelated scope changed? | PASS (`git diff HEAD~1 --name-only` shows only `scripts/evals/spike_sync_scorer.py` and evidence/docs — zero production files). |
| 11 | Performance/maintainability regression? | PASS (2.39s wall time / 333MB RSS for a 6.04s clip on CPU). |
| 12 | Repository buildable/testable? | PASS (104/104 invariant suite passes; full suite has 1 pre-existing migration failure unrelated to TKT-101). |

## Acceptance Gates

| Gate | Requirement | Audit Result | Evidence |
|---|---|---|---|
| G1 | Decision record exists with measured numbers | **PASS** | `evidence/TKT-101-sync-scorer-decision.md` (208 lines, §7 measurement table, §4 pinned deps, §6 precondition verification) |
| G2 | Spike detects injected 200ms shift within ±40ms tolerance on ≥1 real face video | **PASS** | S002: detected_shift_ms=160.0, error=40.0ms (≤40ms); S000: detected_shift_ms=200.0, error=0.0ms. Independently reproduced by auditor. |
| G3 | Mismatch case does NOT report high confidence | **PASS** | S002+S000 mismatch: confidence=0.138 vs matched 0.4798 (3.4x drop). Independently reproduced by auditor. |
| G4 | No production files modified | **PASS** | `git diff HEAD~1 --name-only` excludes `scripts/evals/` and `docs/plans/` yields zero files. |

## Findings

### FINDING-1 — `--json` output does not create parent directories (severity: LOW)

- **File**: `scripts/evals/spike_sync_scorer.py:391`
- **Issue**: `args.json.write_text(json.dumps(...))` fails with `FileNotFoundError` when the target directory does not exist. The JSON is still printed to stdout, so measurement integrity is unaffected. Both `--shift-ms` and `--mismatch-audio` modes are similarly affected because `write_text` is called before the compound-result exit-code logic.
- **Violated requirement**: None (spike is additive, G2-G4 are satisfied regardless). This is a non-critical UX defect in a discovery artifact.
- **Evidence**: Auditor reproduced: `--json /tmp/kilo/tkt101_audit/S002_unshifted.json` raised `FileNotFoundError` (exit 1) despite writing correct JSON to stdout.
- **Required correction**: Option A: `args.json.parent.mkdir(parents=True, exist_ok=True)` before write. Option B: document that `--json` directory must exist. Neither affects the ticket's acceptance gates.
- **Required regression test**: Not required for a spike; TKT-102 produces production code with proper error handling.

## Residual Risks

1. The chosen scorer is a lip-motion-envelope method, not a deep lipsync expert discriminator. Absolute confidence is moderate (~0.48); TKT-102 must not hardcode permissive thresholds.
2. Mouth landmark indices (13/14/78/308) are MediaPipe-478-point specific; a model swap requires re-validation.
3. Real hero clips carry intrinsic A/V desync (S000: ~120ms, S002: ~440ms); the differential proof is the correct methodology. TKT-103 (compensation loop) should compensate using the *measured* offset, not a "correct" reference offset.

## Audit Event

```json
{"ts": "2026-07-04T21:50:12+08:00", "ticket": "TKT-101", "phase": "audit", "role": "auditor", "verdict": "PASS_WITH_FINDINGS", "findings": [{"id": "FINDING-1", "severity": "low", "file": "scripts/evals/spike_sync_scorer.py:391", "issue": "--json output does not create parent directories; exits 1 on FileNotFoundError despite correct stdout JSON", "required_correction": "Option A: mkdir parents before write; Option B: document directory requirement", "required_regression_test": "none (spike only)"}], "commands": ["/tmp/kilo/tkt101_venv/bin/python scripts/evals/spike_sync_scorer.py outputs/seedance_truth_test_001/review_only/work/S002_norm.mp4 --model /tmp/kilo/tkt101_venv/models/face_landmarker.task (exit 0)", "/tmp/kilo/tkt101_venv/bin/python scripts/evals/spike_sync_scorer.py outputs/seedance_truth_test_001/review_only/work/S002_norm.mp4 --shift-ms 200 --model /tmp/kilo/tkt101_venv/models/face_landmarker.task (exit 0)", "/tmp/kilo/tkt101_venv/bin/python scripts/evals/spike_sync_scorer.py outputs/seedance_truth_test_001/review_only/work/S002_norm.mp4 --mismatch-audio outputs/seedance_truth_test_001/review_only/work/S000_norm.mp4 --model /tmp/kilo/tkt101_venv/models/face_landmarker.task (exit 0)", "YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q (104 passed in 12.87s)"], "exit_codes": [0, 0, 0, 0], "files_changed": [], "commit": "a4316e4", "result": "Audit PASS_WITH_FINDINGS. Acceptance gates G1-G4 all pass. One LOW finding: --json path parent dir not created. Reservoir risks: spike is not production code; TKT-102 must enforce fail-closed backend selection and never hardcode permissive thresholds."}
```
