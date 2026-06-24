# Sprint 01 Master — Make lipsync and audio provenance measurable before any render reruns.

## Goal

Make lipsync and audio provenance measurable before any render reruns.

## Render policy

Actual video render/provider generation is forbidden in this sprint unless this is Sprint 06 and the ticket explicitly checks the unlock file. LLM calls are allowed.

## Tickets

- `S01_T001` — Source audio slice ledger
- `S01_T002` — Provider diagnostic audio comparison
- `S01_T003` — SyncNet or fallback lipsync eval harness
- `S01_T004` — Lipsync validation DB records

## Sprint exit requirement

A bad fixture has objective/diagnostic lipsync evidence and hero units have source-slice provenance requirements.

## Required sprint summary

At sprint close, create:

```text
reports/karpathy_loop/sprint_01/sprint_summary.md
reports/karpathy_loop/sprint_01/open_defects.json
```
