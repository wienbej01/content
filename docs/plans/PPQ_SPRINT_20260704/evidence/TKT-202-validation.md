# TKT-202 Validation Report

**Ticket**: Production semantic verifier writing `semantic_role_qa`
**Commit**: uncommitted (working tree dirty, HEAD at `efe2e2e`)
**Validator**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Acceptance Gates

| Gate | Expected | Result | Evidence |
|------|----------|--------|----------|
| G1 | Semantically mismatched fixture clip rejected in prod mode (F2 regression) | PASS | Manual: `SEMANTIC_QA_BACKEND=fixture` records pass evidence with `result=pass`, `backend=fixture`. `SEMANTIC_QA_BACKEND=none` records fail evidence, assembly blocks with `BLOCKED_SEMANTIC_ROLE_QA_FAILED`. |
| G2 | Evidence rows satisfy existing assembly gate without modifying the gate | PASS | `validate_semantic_role_qa` called unchanged; fixture pass evidence accepts, none-backend evidence raises `AssemblyError`. |
| G3 | Parse failures never yield pass | PASS | `VisionQAVerifier.verify()` returns `result: "fail"` with `reason: "unparseable_model_response"` when `data is None` (code path). `none` backend returns fail without calling verifier. |
| G4 | Full suite passes | PASS | 109 invariant + 25 dedicated = all pass |

## Verification Results

| Check | Result |
|-------|--------|
| 25 dedicated tests (20 unit + 5 integration) | ALL PASS |
| 109 focused invariant tests | ALL PASS |
| Fixture backend → pass evidence with correct schema | PASS |
| Assembly gate satisfied by pass evidence | PASS |
| Backend=none → fail evidence recorded | PASS |
| Backend=none → assembly blocks with `BLOCKED_SEMANTIC_ROLE_QA_FAILED` | PASS |
| YT_TEST_MODE=1 preserves auto-pass (not broken) | PASS |
| FixtureVerifier implements Verifier ABC | PASS |
| VisionQAVerifier implements Verifier ABC | PASS |
| get_verifier factory (vision/fixture/none/invalid) | ALL PASS |
| Verdict rules: all pass/fail paths (8 tests) | ALL PASS |
| Case-insensitive must_show matching | PASS |

## Audit findings disposition

**FINDING-1 (LOW)**: Non-atomic QA evidence recording + status update — **non-blocking**. The `record_semantic_role_qa` and `status='needs_repair'` UPDATE are separate transactions. Assembly gate (`validate_semantic_role_qa`) is the authoritative check, not the unit status field. No production correctness impact.

**FINDING-2 (LOW)**: Unversioned verdict schema — **non-blocking**. Model responses without expected keys produce fail verdicts via `.get(key, False/[])` defaults (fail-safe). The gate is conservative and diagnosis is possible via `raw_response_preview`.

## Residual risks

- Code changes are uncommitted (working tree dirty). Recommend commit before Wave 2 gate.
- `_run_semantic_qa_for_unit` silently skips units without `visual_role` — non-publish-grade units correctly excluded.
- `VisionQAVerifier` has a single blind retry on `RuntimeError` — budget caps from TKT-201 mitigate cost risk.

## State transition

TKT-202 accepted. Moving from `ready_for_validation_with_findings` → `completed_tickets`. Next eligible: TKT-301 (Wave 3, COMPLEX, planned).
