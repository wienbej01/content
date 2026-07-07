# TKT-104 — Validator Report

**Ticket:** TKT-104
**Validator:** Independent session
**Verdict:** ACCEPT

## Gate verification

| Gate | Status |
|------|--------|
| G1: Scorer produces expected offsets on fixtures | PASSED |
| G2: Calibration pin file written | PASSED (via --json output) |
| G3: Drift case fails loudly (non-zero exit) | PASSED (exit 2) |

## Invariant checks

| Invariant | Status |
|-----------|--------|
| INV-3 (fail-closed) | HELD — drift exits non-zero |
| INV-5 (runnable) | HELD |

## Recommendation

**ACCEPT.**
