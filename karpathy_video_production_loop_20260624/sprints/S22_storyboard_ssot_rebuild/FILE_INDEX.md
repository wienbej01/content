# S22 File Index

## Shared plan files

- `S22_MASTER.md` - sprint objective, success criteria, ticket order.
- `S22_CONTEXT.md` - repo context and current storyboard/DB surfaces.
- `S22_STRUCTURAL_FRAMEWORK.md` - architecture layers and stage relationship.
- `S22_CODING_RULES.md` - code and safety rules for implementation tickets.
- `S22_PROCESS_RULES.md` - per-ticket loop process and reports.
- `S22_PROMPT_GUARDRAILS.md` - Sonnet 5 storyboard prompt rules.
- `S22_FEEDBACK_LOOP_RULES.md` - duration drift, compliance feedback, invalidation rules.
- `S22_AGENT_DEFINITIONS.md` - S22 agent roles and model parameters.
- `S22_MODEL_ROUTING.md` - DeepSeek Flash/Pro ticket routing and Sonnet runtime authority.
- `S22_TEST_AND_GATE_MATRIX.md` - required tests, fixtures, and pass gates.
- `S22_GATE_exit_criteria.md` - sprint-level PASS/RETRY/BLOCKED criteria.

## Tickets

- `tickets/S22_T001.md` - Create sprint scaffold and contract audit.
- `tickets/S22_T002.md` - Add Sonnet 5 Kilo profile verification and no-fallback guard.
- `tickets/S22_T003.md` - Define LLM-authored storyboard schema.
- `tickets/S22_T004.md` - Define Sonnet storyboard prompt packet and guardrails.
- `tickets/S22_T005.md` - Add claim inventory schema and validator plan.
- `tickets/S22_T006.md` - Build Sonnet 5 storyboard wrapper plan.
- `tickets/S22_T007.md` - Add segment work-order validator.
- `tickets/S22_T008.md` - Add semantic alignment validator.
- `tickets/S22_T009.md` - Add timing/drift contract validator.
- `tickets/S22_T010.md` - Add bounded Sonnet repair loop.
- `tickets/S22_T011.md` - Add Sonnet creative review gate.
- `tickets/S22_T012.md` - Add human `gate_storyboard` stage.
- `tickets/S22_T013.md` - Build canonical-to-legacy projection.
- `tickets/S22_T014.md` - Update compiler to consume canonical shots.
- `tickets/S22_T015.md` - Compile overlay plan from canonical overlays.
- `tickets/S22_T016.md` - Integrate overlays into render/assembly timeline.
- `tickets/S22_T017.md` - Record observed artifact durations.
- `tickets/S22_T018.md` - Add duration drift resolver.
- `tickets/S22_T019.md` - Add compliance feedback ingestion.
- `tickets/S22_T020.md` - Add downstream invalidation/rerun planner.
- `tickets/S22_T021.md` - Add regression fixtures for known failures.
- `tickets/S22_T022.md` - Run final end-to-end dry-run gate in `YT_TEST_MODE=1`.

## Execution rule

Run one ticket at a time. Each ticket must load `S22_MASTER.md`, the relevant shared S22 files, and its own ticket file before implementation.

