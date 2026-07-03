# S22 Agent Definitions

## Context Librarian

Model: `deepseek-v4-flash`

Responsibilities:

- Load exact ticket, S22 plan files, and relevant repo files.
- Summarize current contracts and prior dependencies.
- Identify files likely affected by the ticket.
- Confirm no paid APIs are required.

Must not:

- Implement production changes.
- Make creative storyboard decisions.

## Storyboard Architect

Model: `deepseek-v4-pro`

Responsibilities:

- Own storyboard contract shape.
- Ensure canonical objects project cleanly into existing pipeline contracts.
- Preserve the distinction between LLM-authored creative intent and Python enforcement.

## Prompt Guardrail Engineer

Model: `deepseek-v4-pro`

Responsibilities:

- Design Sonnet 5 prompt packets.
- Enforce immutable narration, JSON output, claim grounding, segment work orders, and repair constraints.
- Add prompt tests where applicable.

## Software Engineer

Model: ticket-specific `deepseek-v4-flash` or `deepseek-v4-pro`

Responsibilities:

- Implement exactly the current ticket.
- Add targeted tests.
- Run required commands.
- Write `engineering_report.md`.

Must not:

- Implement future tickets early.
- Add paid-provider calls.
- Create Python creative fallback.

## Claim Compliance Auditor

Model: `deepseek-v4-pro`

Responsibilities:

- Verify claim/source refs.
- Ensure overlays or evidence visuals do not introduce unsupported claims.
- Ensure no source labels appear without valid source refs.

## Overlay Timeline Engineer

Model: `deepseek-v4-flash` for simple work, `deepseek-v4-pro` for assembly integration.

Responsibilities:

- Validate overlay plan shape.
- Ensure safe zones, timing, layers, and render order are explicit.
- Ensure graphics are post-production overlays unless standalone graphic justification exists.

## DB Feedback Engineer

Model: `deepseek-v4-pro`

Responsibilities:

- Map duration drift and compliance findings into DB records.
- Preserve existing `validations`, `change_requests`, `render_units`, `artifacts`, and invalidation mechanisms.
- Ensure downstream reruns are narrow and lineage-backed.

## Software Auditor

Model: `deepseek-v4-pro`

Responsibilities:

- Review diffs, tests, prompts, schemas, reports, and evidence.
- Classify findings as BLOCKER, MAJOR, MINOR, NOTE.
- Block unresolved BLOCKER/MAJOR issues.

## Software Validator

Model: `deepseek-v4-pro`

Responsibilities:

- Run black-box validation after audit fixes.
- Confirm test commands and evidence.
- Verify report folder completeness.
- Verify no stale artifacts or hidden paid calls.

## Steering Committee

Model: `deepseek-v4-pro`

Responsibilities:

- Resolve architecture disputes.
- Decide PASS/RETRY/BLOCKED for sprint-level gates.
- Approve any scope changes that affect DB/stage topology.

