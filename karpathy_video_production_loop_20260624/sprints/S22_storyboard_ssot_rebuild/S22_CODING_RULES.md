# S22 Coding Rules

## Creative authority

- Python must not author creative storyboard decisions.
- Python must not choose B-roll concepts, graphic concepts, overlay text, or story visual strategy.
- Python may compute timing, costs, hashes, routing constraints, schema validation, and approval state.
- Any Python fallback that creates creative visual content is a BLOCKER.

## Model authority

- Runtime storyboard generation, repair, and final creative review must use Sonnet 5 through Kilo.
- No fallback to DeepSeek, auto, or deterministic Python creative generation.
- If Sonnet 5 is unavailable, fail with `BLOCKED_SONNET5_UNAVAILABLE`.
- DeepSeek v4 Flash/Pro may implement the tickets. That is separate from runtime creative authority.

## Existing infrastructure

Extend, do not duplicate:

- production database
- artifact registry
- provider job registry
- stage runner
- approval requests
- validations
- change requests
- render units
- report folder pattern
- render lock/dry-run pattern

## Safety

- No paid provider calls in tests.
- No real TTS or media generation in default validation.
- Tests must use stubs, fixtures, deterministic media, or `YT_TEST_MODE=1`.
- Do not read or print credentials.
- Do not log tokens or auth file contents.

## Failure style

Blocking errors must use explicit names:

- `BLOCKED_SONNET5_UNAVAILABLE`
- `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN`
- `BLOCKED_SCRIPT_NARRATION_MUTATION`
- `BLOCKED_GENERIC_BROLL`
- `BLOCKED_UNSUPPORTED_CLAIM`
- `BLOCKED_PURPOSELESS_OVERLAY`
- `BLOCKED_DURATION_DRIFT_UNRESOLVED`
- `BLOCKED_STALE_ARTIFACT_REUSE`
- `BLOCKED_FEEDBACK_UNROUTED`
- `BLOCKED_SPEND_GATE_UNAPPROVED`

## Test discipline

Every behavior change requires:

- At least one positive test.
- At least one negative test for the old/bad behavior.
- A focused test command.
- Relevant existing tests when the change touches shared contracts.

## Scope discipline

Each ticket must:

- Modify only files required by that ticket.
- Avoid broad refactors.
- Avoid implementing later tickets early.
- Leave unrelated dirty worktree changes untouched.
- Write engineering, audit, validation, and loop decision reports.

