# S22 Test and Gate Matrix

## Required default test posture

All tests must be hermetic by default:

- No real paid TTS.
- No real paid video generation.
- No provider API calls.
- No real Sonnet call in default unit tests.
- Stub Kilo/Sonnet output where needed.
- Use `YT_TEST_MODE=1` for integration-style production flow checks.

## Mandatory negative fixtures

Each must appear in at least one ticket test by the end of S22:

- Sonnet 5 unavailable.
- Non-Sonnet profile requested for storyboard generation.
- Python fallback tries to create creative storyboard content.
- Approved narration mutated.
- Generic B-roll.
- B-roll without narrative alignment.
- Graphic/overlay without semantic purpose.
- Unsupported factual claim.
- Generated shot asks for readable in-scene text.
- Segment lacks work order.
- Missing duration drift policy.
- Actual render duration too short for policy.
- Actual render duration too long for policy.
- Compliance finding has no repair route.
- Downstream stage reuses stale artifact.
- Raw script `visual_brief` leaks into compiled media prompt.
- `graphic`/`graphics` mismatch creates false review failures.

## Gate checks

### Schema gate

Passes only if:

- valid fixture passes
- invalid fixture fails
- errors identify exact path/entity
- schema is documented

### Prompt gate

Passes only if:

- prompt includes all required context
- prompt forbids narration rewrite
- prompt requires segment work orders
- prompt requires timing drift policy
- prompt requires strict JSON

### Storyboard validation gate

Passes only if:

- every segment is covered
- every claim ref resolves
- every shot has semantic alignment
- every overlay has purpose
- every duration policy is complete
- creative author is Sonnet 5

### Spend gate

Passes only if:

- storyboard hash is approved
- review hash matches storyboard hash
- media plan derives from canonical shots
- overlays derive from canonical overlays
- cost estimate exists
- no stale feedback is open

### Feedback gate

Passes only if:

- observed artifact duration is recorded
- drift policy is applied
- compliance findings become change requests
- downstream invalidation is narrow and complete
- stale artifact reuse is blocked

### Final sprint gate

Passes only if `S22_T022` produces an evidence bundle proving:

- approved script is immutable
- Sonnet-authored storyboard fixture is accepted
- invalid storyboard fixtures are blocked
- media compiler ignores raw `visual_brief`
- duration drift resolver handles trim/pad/block cases
- feedback/invalidation reruns only affected downstream stages
- no paid APIs are called

