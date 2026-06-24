# Sprint 06 Master — Unlock exactly one controlled canary render only after all readiness gates pass.

## Goal

Unlock exactly one controlled canary render only after all readiness gates pass.

## Render policy

Actual video render/provider generation is forbidden in this sprint unless this is Sprint 06 and the ticket explicitly checks the unlock file. LLM calls are allowed.

## Tickets

- `S06_T001` — Readiness scorecard
- `S06_T002` — Dry-run provider request audit
- `S06_T003` — Actual render unlock and one canary
- `S06_T004` — Post-render forensic comparison

## Sprint exit requirement

Actual render is permitted only for one canary and only after explicit unlock file and all readiness checks pass.

## Required sprint summary

At sprint close, create:

```text
reports/karpathy_loop/sprint_06/sprint_summary.md
reports/karpathy_loop/sprint_06/open_defects.json
```
