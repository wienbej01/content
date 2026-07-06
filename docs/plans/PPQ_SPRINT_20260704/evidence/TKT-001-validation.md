# TKT-001 Validation Report

**Ticket**: Reject simulated QA evidence outside test mode
**Commit**: `e45d355`
**Validator**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Acceptance Gates

| Gate | Expected | Result | Evidence |
|------|----------|--------|----------|
| G1 | New negative test passes | PASS | `test_prod_mode_rejects_simulated_syncnet` raises `AssemblyError` with `BLOCKED_SIMULATED_EVIDENCE_REJECTED`; `test_prod_mode_rejects_simulated_semantic` same |
| G2 | Focused 104-suite passes | PASS | `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` → 109 passed |
| G3 | No gate accepts simulated evidence without `YT_TEST_MODE` guard | PASS | Grep: `is_simulated_evidence` called at `assemble_db.py:290` (syncnet_offset gate) and `assemble_db.py:545` (semantic_role_qa gate), both gated on `not os.environ.get("YT_TEST_MODE")`. `is_simulated_evidence()` checks `simulated` flag, `method` prefix `yt_test_mode` at top level and within `details`. |

## Verification Results

| Check | Result |
|-------|--------|
| 6 dedicated tests (syncnet + semantic) | ALL PASS |
| 109 focused invariant tests | ALL PASS |
| assert test-mode allows simulated evidence | PASS |
| assert prod-mode rejects simulated evidence | PASS |
| assert prod-mode allows real evidence | PASS |
| is_simulated_evidence covers top-level simulated flag | PASS |
| is_simulated_evidence covers top-level method prefix | PASS |
| is_simulated_evidence covers details.method prefix | PASS |
| commit e45d355: only assemble_db.py + test file changed | PASS |

## Audit findings disposition

No audit was performed. This validation serves as independent verification.

## Residual risks

- The `is_simulated_evidence` function checks `payload.get("simulated")` with `is True` (identity check). A future writer setting `simulated: 1` (truthy but not `True`) would bypass the check. Mitigation: the only writer is `_qa_hero_lipsync` in `media_service.py` which sets `simulated: True` consistently.
- There is no programmatic enforcement that new evidence writers must set the `simulated` flag. This is a process/training concern, not a code defect.

## State transition

TKT-001 accepted. Independent validation complete. All 3 acceptance gates pass.
