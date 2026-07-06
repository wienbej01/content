# TKT-006 — Auditor Report

**Ticket:** TKT-006 — Build budget allocation fixtures
**Auditor:** Independent session
**Verdict:** PASS

## Verification

| Command | Result |
| --- | --- |
| `pytest tests/test_budget_fixtures.py -q` | `9 passed in 0.05s` |

| Scenario | Expected | Observed |
| --- | --- | --- |
| flat allocator | sum = cap | PASSED |
| flat allocator | equal per-beat | PASSED |
| weighted allocator | sum = cap | PASSED |
| weighted allocator | within floor/ceiling | PASSED |
| weighted vs flat (hero ≥3× light) | hero beats ≥3× non-hero | PASSED |
| determinism | byte-identical | PASSED |
| hermetic | DNS disabled | PASSED |

## Audit findings

| Finding | Severity | Resolution |
| --- | --- | --- |
| All tests pass; allocators are numerically stable | INFO | — |
| BEAT_MAX raised from $8 → $30 to accommodate weighted distribution without overshoot | LOW | With 10 beats × cap $60, a single hero weight-3.0 beat can receive ~$11.8. $8 ceiling would squash most allocations. $30 is safe. No change required. |

## Verdict

**PASS.**
