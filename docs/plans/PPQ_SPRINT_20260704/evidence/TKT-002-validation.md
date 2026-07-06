# TKT-002 Validation Report

**Ticket**: Real concept keys and enforced dedup quota
**Commit**: `6b9ee5a`
**Validator**: independent
**Date**: 2026-07-05

## Verdict: PASS

## Acceptance Gates

| Gate | Expected | Result | Evidence |
|------|----------|--------|----------|
| G1 | concept_key != shot_id for projected units | PASS | Manual verification: `project_canonical` produces `concept_key='across_blinking_leds_rack_racks_server_shot_slow_tracking'` not `'SH_UNIQUE_12345'`; `concept_hash` is 64-char SHA-256 |
| G2 | Forbidden-concept plan fails compile | PASS | `is_forbidden_concept('laptop_desk_typing')` → True; `is_forbidden_concept('neural_network_layers')` → False; integration test `test_forbidden_concept_rejected` asserts `RuntimeError` |
| G3 | Focused suite passes | PASS | `YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q` → 109 passed |

## Verification Results

| Check | Result |
|-------|--------|
| 16 dedicated tests | ALL PASS |
| 109 focused invariant tests | ALL PASS |
| concept_key != shot_id | PASS |
| concept_hash = SHA-256 hex digest | PASS |
| Stopword removal works | PASS |
| Forbidden concept detection works | PASS |
| Quota enforcement works | PASS |
| concept_memory rows written | PASS |
| Distinct concepts produce distinct keys | PASS |
| Empty/all-stopword fallback returns "concept" | PASS |
| Audit findings disposition | 0 findings — N/A |

## Audit findings disposition

Audit returned **PASS** with 0 findings. No unresolved items.

## Residual risks

- `derived_concept_key` uses `sorted(set(tokens))` — while distinct from `shot_id`, key collisions are possible on semantically similar shots (by design: this is dedup, not unique identification).
- `_concept_key` at `scripts/produce_db.py:499` is dead code (no callers remain) — harmless but untidy.

## State transition

TKT-002 accepted. Moving from `ready_for_validation` → `completed_tickets`. Next eligible ticket per dependency order: TKT-003 (Wave 0, ROUTINE, ready_for_audit).
