# Sprint 22 - Storyboard SSOT Rebuild

## Objective

Rebuild the storyboard process so the approved script is transformed into a complete, production-authoritative storyboard by an LLM creative director, while Python only enforces contracts, state, approvals, validation, feedback routing, and downstream reruns.

The storyboard author is Sonnet 5 through the Kilo CLI interface. Python must not design creative B-roll, graphics, overlays, shot strategy, or narrative visual choices.

## Sprint success criteria

- Sonnet 5 is the only final storyboard author for `storyboard_generation`, `storyboard_repair`, and `storyboard_creative_review`.
- If Sonnet 5 is unavailable through Kilo, storyboard generation blocks with `BLOCKED_SONNET5_UNAVAILABLE`; no silent fallback is allowed.
- The storyboard contract contains claims, narrative beats, shots, overlays, segment work orders, timing drift policy, and repair policy.
- Every shot explains how it supports the script argument, reference, conclusion, or viewer comprehension.
- Every B-roll shot has concrete narrative alignment and cannot be generic filler unless explicitly marked `emotional_reset`.
- Every graphic or overlay has semantic purpose, safe-zone data, timing, style token, and source/claim linkage where applicable.
- Approved script and narration are immutable after approval.
- Rendered media duration is measured after generation and stored as observed truth.
- Duration drift and compliance findings become targeted feedback records/change requests.
- Downstream stage invalidation is narrow, lineage-backed, and blocks stale artifact reuse.
- No paid APIs are required for the default test suite or final sprint validation.

## Non-negotiables

- Do not rebuild the production database, artifact registry, stage runner, approval system, render lock, or report pattern.
- Do not use raw script `visual_brief` as a production media prompt source.
- Do not let Python create storyboard creative strategy.
- Do not let a low-authority model approve creative gates.
- Do not continue downstream after unresolved BLOCKER or MAJOR findings.
- Do not call ElevenLabs, Higgsfield, or any paid provider in ticket tests.
- Do not call DeepSeek or auto models for runtime storyboard authorship when Sonnet 5 is required.

## Ticket order

1. `S22_T001` - Create sprint scaffold and contract audit.
2. `S22_T002` - Add Sonnet 5 Kilo profile verification and no-fallback guard.
3. `S22_T003` - Define LLM-authored storyboard schema.
4. `S22_T004` - Define Sonnet storyboard prompt packet and guardrails.
5. `S22_T005` - Add claim inventory schema and validator plan.
6. `S22_T006` - Build Sonnet 5 storyboard wrapper plan.
7. `S22_T007` - Add segment work-order validator.
8. `S22_T008` - Add semantic alignment validator.
9. `S22_T009` - Add timing/drift contract validator.
10. `S22_T010` - Add bounded Sonnet repair loop.
11. `S22_T011` - Add Sonnet creative review gate.
12. `S22_T012` - Add human `gate_storyboard` stage.
13. `S22_T013` - Build canonical-to-legacy projection.
14. `S22_T014` - Update compiler to consume canonical shots.
15. `S22_T015` - Compile overlay plan from canonical overlays.
16. `S22_T016` - Integrate overlays into render/assembly timeline.
17. `S22_T017` - Record observed artifact durations.
18. `S22_T018` - Add duration drift resolver.
19. `S22_T019` - Add compliance feedback ingestion.
20. `S22_T020` - Add downstream invalidation/rerun planner.
21. `S22_T021` - Add regression fixtures for known failures.
22. `S22_T022` - Run final end-to-end dry-run gate in `YT_TEST_MODE=1`.

## Required agents

- Context Librarian
- Storyboard Architect
- Prompt Guardrail Engineer
- Software Engineer
- Claim Compliance Auditor
- Overlay Timeline Engineer
- DB Feedback Engineer
- Software Auditor
- Software Validator
- Steering Committee

## Model routing

Ticket implementation should use DeepSeek v4 Flash or DeepSeek v4 Pro as listed in `S22_MODEL_ROUTING.md`.

Runtime storyboard authorship is separate from ticket implementation. Runtime storyboard authorship must use Sonnet 5 through Kilo.

## Required reports

Each ticket must write reports under:

`reports/karpathy_loop/s22/<ticket_id>/`

Required files:

- `engineering_report.md`
- `audit_report.md`
- `validation_report.md`
- `loop_decision.md`
- JSON evidence files where the ticket creates validation or dry-run artifacts.

## Sprint final gate

The sprint passes only when `S22_T022` proves the full dry-run path in `YT_TEST_MODE=1`:

approved script -> Sonnet-authored storyboard contract -> validation -> creative review -> human storyboard approval path -> compile media from canonical shots -> overlay plan -> observed-duration feedback simulation -> targeted invalidation -> downstream readiness report.

