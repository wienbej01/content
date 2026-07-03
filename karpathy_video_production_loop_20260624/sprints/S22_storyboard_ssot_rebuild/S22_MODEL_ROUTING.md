# S22 Model Routing

## Runtime creative authority

Runtime storyboard authorship requires Sonnet 5 through Kilo.

Applies to:

- `storyboard_generation`
- `storyboard_repair`
- `storyboard_creative_review`

If Sonnet 5 is unavailable, the implementation must fail with `BLOCKED_SONNET5_UNAVAILABLE`.

## Ticket implementation models

Use DeepSeek v4 Flash for mechanical, narrow, or fixture-heavy work:

- `S22_T001`
- `S22_T005`
- `S22_T007`
- `S22_T009`
- `S22_T011`
- `S22_T013`
- `S22_T014`
- `S22_T015`
- `S22_T016`
- `S22_T021`

Use DeepSeek v4 Pro for architecture, prompt authority, DB, invalidation, and final gates:

- `S22_T002`
- `S22_T003`
- `S22_T004`
- `S22_T006`
- `S22_T008`
- `S22_T010`
- `S22_T012`
- `S22_T017`
- `S22_T018`
- `S22_T019`
- `S22_T020`
- `S22_T022`

## Model rationale

Flash is acceptable when the task is scoped, testable, and does not decide architecture.

Pro is required when the task touches:

- model routing
- prompt guardrails
- canonical schema
- semantic validation
- repair loop
- approvals/stage graph
- observed-duration DB writeback
- feedback/invalidation
- final integration validation

## Forbidden routing

- No `auto_utility` final approval for creative gates.
- No DeepSeek runtime storyboard authorship unless the user explicitly changes the Sonnet 5 requirement.
- No silent downgrade from Sonnet 5 to another model.
- No model-profile override without explicit report evidence.

