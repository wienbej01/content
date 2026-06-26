# Sprint 15 — Shot-mix contract and semantic role validation

## Objective

Ensure the system produces the instructed editorial structure and validates actual visual role, not labels.

## Sprint success criteria

- Shorts require minimum shot mix.
- Labels verified against rendered content.
- B-roll visually distinct from hero.
- Graphics are explanatory, not title cards.
- Assembly blocks if shot plan violates contract.

## Ticket list

- `S15_T001` — Define format-level shot-mix contract
- `S15_T002` — Add visual_role metadata
- `S15_T003` — Post-render semantic role QA
- `S15_T004` — Frame sampling utility
- `S15_T005` — Enforce shot-mix preflight

## Required agents

- Context Librarian
- Software Engineer
- Software Auditor
- Software Validator
- Steering Committee for sprint gate

## Model routing

Use `MODEL_ROUTING_GUIDE.md`. Critical tickets in this sprint should use `ZAI_BEST_REASONING` for audit/validation.
