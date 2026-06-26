# Sprint 14 — Strict lip-sync QA and thresholds

## Objective

Move from prototype sync to professional close-up sync with stricter per-segment SyncNet and confidence gates.

## Sprint success criteria

- Close hero fail threshold <=45ms.
- Medium hero fail threshold <=60ms.
- 2-frame offset is not publish-pass for close hero.
- SyncNet confidence affects pass/fail.
- Per-hero evidence required; merged face track insufficient.

## Ticket list

- `S14_T001` — Define tiered lip-sync policy
- `S14_T002` — Add hero framing metadata
- `S14_T003` — Make per-segment SyncNet mandatory
- `S14_T004` — SyncNet confidence and face-track gate
- `S14_T005` — Recalibrate current S000/S002 baseline

## Required agents

- Context Librarian
- Software Engineer
- Software Auditor
- Software Validator
- Steering Committee for sprint gate

## Model routing

Use `MODEL_ROUTING_GUIDE.md`. Critical tickets in this sprint should use `ZAI_BEST_REASONING` for audit/validation.
