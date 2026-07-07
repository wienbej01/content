# TKT-104 — Auditor Report

**Ticket:** TKT-104 — SyncNet scorer drift check + calibration pin
**Auditor:** Independent session
**Verdict:** PASS

## Verification

| Command | Result |
| --- | --- |
| `pytest tests/test_sync_scorer_drift.py -q` | `7 passed in 0.58s` |

| Scenario | Expected | Observed |
| --- | --- | --- |
| Script help works | exit 0 | PASSED |
| No drift case | exit 0 | PASSED |
| Drift case | exit 2 | PASSED |
| JSON output | valid report | PASSED |
| Fixture generation | deterministic | PASSED |

## Audit findings

| Finding | Severity | Resolution |
| --- | --- | --- |
| All 7 tests pass; drift check is deterministic | INFO | — |
| Fixture clips generated from scratch (no external data needed) | INFO | — |
| Calibration pin hash included in report for provenance | INFO | — |

## Verdict

**PASS.**
