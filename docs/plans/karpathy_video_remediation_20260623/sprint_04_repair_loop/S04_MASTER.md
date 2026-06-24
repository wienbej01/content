# Sprint 04 Master — Make failed validations drive targeted repair and minimal reruns.

## Goal

Make failed validations drive targeted repair and minimal reruns.

## Render policy

Actual video render/provider generation is forbidden in this sprint unless this is Sprint 06 and the ticket explicitly checks the unlock file. LLM calls are allowed.

## Tickets

- `S04_T001` — Failure class to repair action map
- `S04_T002` — Repair from failed validations only
- `S04_T003` — Rerun minimal affected stages
- `S04_T004` — Repair audit report

## Sprint exit requirement

Repair must consume failed evidence and choose minimal safe action without actual render before unlock.

## Required sprint summary

At sprint close, create:

```text
reports/karpathy_loop/sprint_04/sprint_summary.md
reports/karpathy_loop/sprint_04/open_defects.json
```
