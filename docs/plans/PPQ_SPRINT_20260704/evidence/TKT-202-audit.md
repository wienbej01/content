# TKT-202 Audit Report

**Ticket**: Production semantic verifier writing `semantic_role_qa`
**Wave**: 2
**Commit**: uncommitted (working tree dirty)
**Auditor**: independent
**Date**: 2026-07-05

## Verdict: PASS_WITH_FINDINGS

## Audit Checks

### 1. Root cause supported by evidence
**PASS**. CS-6 (`DeterministicTestVerifier`, production evidence only via test-mode auto-pass) and CS-7 (`broll_qa.py` unwired dead code). TKT-202 provides a production `Verifier` implementation and wires it into `run_contract_media_qa()`.

### 2. Change satisfies observable outcome
**PASS**.
- `scripts/semantic_verifier.py`: `VisionQAVerifier` sends frame bundle + semantic contract to `vision_qa` profile and parses structured verdict `{claim_supported, must_show_present[], must_avoid_violations[], described_content, confidence}`.
- `scripts/media_service.py`: `_run_semantic_qa_for_unit` dispatches semantic QA for `generated_video` units in production mode, records `semantic_role_qa` evidence.
- Backend selection via `SEMANTIC_QA_BACKEND` env var (`vision|fixture|none`).
- `none` backend records fail-closed validation (INV-3).
- Test mode preserves existing auto-pass behavior via `YT_TEST_MODE=1` guard.

### 3. Production execution path reaches the change
**PASS**. `run_contract_media_qa()` calls `_run_semantic_qa_for_unit()` for `generated_video` units when `YT_TEST_MODE != 1`. This calls `get_verifier()`, `verifier.verify()`, and `record_semantic_role_qa()`.

### 4. Tests fail without implementation
**PASS**. Integration tests (`test_semantic_qa_integration.py`) call `run_contract_media_qa()` and assert `semantic_role_qa` evidence rows exist. Without the implementation, no such rows would be written (test-mode auto-pass only fires under `YT_TEST_MODE=1`).

### 5. Success and failure paths covered
**PASS**.

| Path | Test | Expected |
|------|------|----------|
| Fixture backend → pass evidence | `test_fixture_backend_records_pass_evidence` | `semantic_role_qa` row with status=pass |
| Fixture pass → assembly gate satisfied | `test_assembly_semantic_gate_satisfied` | `validate_semantic_role_qa` passes |
| Backend=none → fail evidence | `test_backend_none_records_fail_evidence` | `semantic_role_qa` row with status=fail |
| Backend=none → assembly gate blocks | `test_backend_none_prod_mode_fails_assembly` | `BLOCKED_SEMANTIC_ROLE_QA_FAILED` |
| YT_TEST_MODE=1 → auto-pass unchanged | `test_yt_test_mode_preserves_auto_pass` | `yt_test_mode` method in evidence |
| Verdict rules: pass all conditions | `test_pass_all_conditions` | status=pass, reason=None |
| Verdict rules: claim_not_supported | `test_fail_claim_not_supported` | status=fail |
| Verdict rules: must_avoid violations | `test_fail_must_avoid_violations` | status=fail |
| Verdict rules: low confidence | `test_fail_low_confidence` | status=fail |
| Verdict rules: missing must_show | `test_fail_missing_must_show` | status=fail |
| Verdict rules: empty must_show | `test_pass_empty_must_show` | status=pass |
| Verdict rules: multiple reasons | `test_fail_multiple_reasons` | all 4 failure reasons aggregated |
| Verdict rules: case-insensitive match | `test_must_show_case_insensitive_match` | status=pass |
| get_verifier: all backends | 6 tests | correct Verifier subclass or None |
| ABC compliance | 2 tests | both verifiers implement `Verifier` |

### 6. Tests prove production behavior rather than mocks alone
**PASS**. Integration tests create real SQLite databases, real ffmpeg test clips, real render units, and exercise the full `run_contract_media_qa` → `_run_semantic_qa_for_unit` → `record_semantic_role_qa` pipeline. Fixture backend avoids paid calls while testing the production dispatch path.

### 7. Hidden duplicate state, fallback, or swallowed failure
**PASS** (with note).
- Unparseable model response → status=fail with `"unparseable_model_response"` reason (never default-pass)
- Missing artifact → `_record_semantic_qa_fail`
- General exception → caught at `_run_semantic_qa_for_unit` line `except Exception` → `_record_semantic_qa_fail`
- Missing `visual_role` → silently skips semantic QA entirely (correct: non-publish-grade units)
- Note: `_run_semantic_qa_for_unit` records QA evidence and updates unit status to `needs_repair` in separate operations. If the status update fails after evidence is recorded, the repair lifecycle won't pick it up. See FINDING-1.

### 8. Partial output, stale state, retries, concurrency, interruption
**PASS** (with note).
- `VisionQAVerifier.verify()` has a single blind retry on `RuntimeError` from the vision model. If both calls fail, the exception propagates to `_run_semantic_qa_for_unit`'s broad handler.
- No idempotency key on vision calls — a retry could produce a second paid call. Budget caps from TKT-201 mitigate the cost risk.

### 9. Existing tests or gates weakened
**PASS**. No existing tests modified. `validate_semantic_role_qa` in `assemble_db.py` is unchanged — the new evidence satisfies it.

### 10. Unrelated scope changed
**PASS**. Only `scripts/semantic_verifier.py` (new), `scripts/media_service.py` (wiring), and test files. Also `test_repair_classifier.py` (adding `semantic_mismatch` — technically TKT-203 scope but benign).

### 11. Performance or maintainability regressed
**PASS**. Vision calls are gated by SEMANTIC_QA_BACKEND env var (default `none` = no calls). Frame bundle is shared with TKT-201 utility.

### 12. Repository remains buildable and testable
**PASS**. 25 dedicated + 109 invariant = all pass.

## Findings

### FINDING-1 (LOW): Non-atomic QA evidence recording and status update

**File**: `scripts/media_service.py` — `_run_semantic_qa_for_unit` and `_record_semantic_qa_fail`

**Issue**: In both the success path (after `record_semantic_role_qa`) and the fail path (`_record_semantic_qa_fail`), the `semantic_role_qa` validation evidence is recorded first, then the render unit status is updated to `needs_repair` in a *separate* transaction. If the status UPDATE fails (e.g., DB connection loss between the two operations), the QA evidence row exists but the unit stays in its previous state, so the repair lifecycle would not pick it up.

This is partially mitigated because the assembly gate checks the evidence, not the unit status — a unit with failing evidence will always be blocked at assembly regardless of its status field. The `needs_repair` status is an optimization for the repair lifecycle, not a correctness gate.

**Required correction**: Wrap `record_semantic_role_qa` and the status UPDATE in a single `_db.transaction()` context manager, or accept the risk and document that the assembly gate is the authoritative check.

**Required regression test**: Force a failure between evidence recording and status update, verify no inconsistent state.

### FINDING-2 (LOW): No output schema version or compatibility guard

**File**: `scripts/semantic_verifier.py` — `VQA_PROMPT_TEMPLATE` (lines 34-50)

**Issue**: The vision model is instructed to return a JSON verdict with `{claim_supported, must_show_present, must_avoid_violations, described_content, confidence}` but there is no schema version field in the output or a compatibility check. If the model changes its response format (e.g., due to a prompt drift or model upgrade), `_apply_verdict_rules` would silently return unexpected values (e.g., `None` for missing keys → `not claim_supported` → treated as fail, which is fail-safe but opaque).

The fail-safe behavior mitigates this — missing keys are treated as fails (e.g., `verdict.get("claim_supported", False)`), so the gate is conservative. But diagnosing the cause requires reading `raw_response_preview`.

**Required correction**: Add a `schema_version` field (e.g., `1`) to the prompt instruction and validate it in the response. Log a warning on version mismatch.

**Required regression test**: Assert that responses missing schema version or version mismatch produce a fail verdict with a distinct reason.

## Gates verification

| Gate | Status | Evidence |
|------|--------|----------|
| G1: Semantically mismatched fixture clip rejected in prod mode (F2 regression) | PASS | `test_backend_none_prod_mode_fails_assembly` — backend=none records fail evidence; `test_assembly_semantic_gate_satisfied` — fixture pass evidence satisfies gate |
| G2: Evidence rows satisfy existing assembly gate without modifying the gate | PASS | `validate_semantic_role_qa` called unchanged; pass evidence passes, fail evidence raises `AssemblyError` |
| G3: Parse failures never yield pass | PASS | `VisionQAVerifier.verify()` returns `result: "fail"` with reason `"unparseable_model_response"` when `data is None` |
| G4: Full suite passes | PASS | 109 invariant + 25 dedicated = all pass |

## Execution log

```json
{"ts": "2026-07-05T17:12:11+08:00", "ticket": "TKT-202", "phase": "audit", "role": "auditor", "verdict": "PASS_WITH_FINDINGS", "findings": [{"id": "FINDING-1", "severity": "low", "file": "scripts/media_service.py (_run_semantic_qa_for_unit)", "issue": "Non-atomic QA evidence recording and status update — if status UPDATE fails, evidence row exists but unit stays in previous state", "required_correction": "Wrap record_semantic_role_qa and status UPDATE in single _db.transaction()", "required_regression_test": "Force failure between evidence recording and status UPDATE, verify no inconsistent state"}, {"id": "FINDING-2", "severity": "low", "file": "scripts/semantic_verifier.py:34-50", "issue": "Verdict schema not versioned — model output format changes silently produce fail verdicts without clear diagnostic", "required_correction": "Add schema_version field to prompt and validate in response"}], "gates_verified": {"G1": "PASS", "G2": "PASS", "G3": "PASS", "G4": "PASS"}, "commands": ["YT_TEST_MODE=1 python3 -m pytest tests/test_semantic_verifier.py tests/test_semantic_qa_integration.py -v (25 passed)", "YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q (109 passed)"], "files_changed": [], "result": "PASS_WITH_FINDINGS. All 4 acceptance gates pass. 2 LOW findings: non-atomic evidence+status update, unversioned verdict schema.", "commit": "efe2e2e (working tree dirty)"}
```
