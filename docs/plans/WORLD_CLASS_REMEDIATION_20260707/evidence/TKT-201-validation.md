# TKT-201 — Validator Report

**Ticket:** TKT-201
**Validator:** Independent session
**Verdict:** ACCEPT

## Gate verification

| Gate | Status |
|------|--------|
| G1: Chapter mode produces different frame sets per act | PASSED |
| G2: No two consecutive hero beats in the same act share a frame | PASSED (round-robin within allowed_angles avoids consecutive repeat when len>1) |
| G3: Flat mode produces output identical to current code | PASSED (act ignored; same path) |
| G4: Edge case (acts outside 1-6) handled without crash | PASSED (falls back to flat) |
| G5: Full suite passes | PASSED (9/9) |

## Invariant checks

| Invariant | Status |
|-----------|--------|
| INV-5 (runnable after every ticket) | HELD |
| INV-7 (6-Act MITmonk master structure preserved) | HELD |

## Recommendation

**ACCEPT.**
