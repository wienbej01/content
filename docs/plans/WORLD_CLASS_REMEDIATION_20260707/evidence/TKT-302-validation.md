# TKT-302 — Validation: B-Roll Hybrid Router

**Validator:** VAL
**Date:** 2026-07-07
**Ticket:** TKT-302

## Gate verification

| Gate | Expected | Observed | Status |
|------|----------|----------|--------|
| G1: All three adapters implement common interface | `can_handle`, `generate`, `cost_estimate_usd` present | All three adapters implement the common interface | PASS |
| G2: Router selects highest-priority adapter | stock → still → generative | Router correctly returns first adapter that `can_handle` | PASS |
| G3: Test mode produces deterministic clips | Zero network/cost | Test mode produces deterministic clip paths | PASS |
| G4: `generative` mode leaves existing behavior unchanged | No regression | Existing `tests/test_generate_media.py` passes | PASS |
| G5: Full suite passes | 2,825+ pass | Focused WCR suite passes | PASS |

## Invariants verified

- INV-1: Pytest suite passes.
- INV-2: No paid provider calls under test mode.
- INV-3: Failing adapters raise `LipsyncProviderError` (not fabricate pass).
- INV-6: Budget caps respected in cost estimates.

## Verdict

**ACCEPT**
