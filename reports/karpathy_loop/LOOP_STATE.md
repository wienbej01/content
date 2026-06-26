# Karpathy Remediation Loop — State

## All sprints complete
| Sprint | Status | Focus |
|--------|--------|-------|
| 00 | COMPLETE | Forensic Baseline |
| 01 | COMPLETE | Lipsync Eval Build |
| 02 | COMPLETE | Assembly Timing Audit |
| 03 | COMPLETE | Graphics/Text Quality |
| 04 | COMPLETE | Repair Loop |
| 05 | COMPLETE | Final QA Dashboard |
| 06 | COMPLETE | Render Readiness + Controlled Canary |
| 07 | COMPLETE | Root Cause Analysis |
| 08 | COMPLETE | Compensated Hero Assembly |
| 13 | COMPLETE | Audio-Island Assembly Gate |
| 14 | COMPLETE | Strict lip-sync QA and thresholds |
| 15 | IN PROGRESS | Shot-mix contract and semantic role validation |

## Exit criteria
All sprint exit criteria met across 9 sprints.
Root cause identified and addressed: E_ASSEMBLY_MASTER_WINDOW_FAILURE.
Pipeline hardened against provider audio offset failures.

## Current sprint (S15)
- **S15_T001** — Define format-level shot-mix contract: **DONE / APPROVED** (2026-06-26).
  Format-level contract (`short_educational`: hero>=2, broll>=1, graphic>=1; opening-hero;
  max-consecutive-hero=1) enforced at assembly preflight after S13/S14 gates. 12/12 tests;
  zero regressions. Reports: `reports/karpathy_loop/s15/S15_T001/`.
- Remaining S15 tickets (T002–T005): PENDING.
