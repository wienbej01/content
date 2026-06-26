# Sprint 19 — Final publish-grade QA

## Objective

Separate test-local technical pass from true publish-grade QA.

## Sprint success criteria

- Publish-grade 16:9 requires 1920x1080 unless explicit profile override.
- Dry-run/test artifacts cannot be publish-grade.
- Audio/video duration tolerance <=100ms.
- Black/blank/static gates enforced.
- Per-hero SyncNet, visual-role QA, graphic QA required.
- Gate B package truthful.

## Ticket list

- `S19_T001` — Publish vs test profile
- `S19_T002` — Final visual QA package
- `S19_T003` — Black/blank/static visual gate
- `S19_T004` — Final audio loudness and continuity gate
- `S19_T005` — Gate B policy update

## Required agents

- Context Librarian
- Software Engineer
- Software Auditor
- Software Validator
- Steering Committee for sprint gate

## Model routing

Use `MODEL_ROUTING_GUIDE.md`. Critical tickets in this sprint should use `ZAI_BEST_REASONING` for audit/validation.
