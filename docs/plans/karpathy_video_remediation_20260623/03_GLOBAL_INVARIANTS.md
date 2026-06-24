# 03 Global Invariants

These invariants apply to every sprint and ticket.

## DB/source-of-truth invariants

1. Production DB remains source of truth.
2. JSON/manifests may be exported for audit/debug, but must not become live authority.
3. Render units, artifacts, provider jobs, validations, deliverables, stage runs, and timeline spans must be auditable through DB rows.
4. A stage may not be marked succeeded without committed output evidence if its stage definition requires committed output.
5. Missing DB evidence is a failure, not an invitation to infer from filenames.

## Media policy invariants

1. `HERO_SYNC_LOCKED` units must not be speed-changed, looped, frozen, reversed, interpolated, or trimmed through speech.
2. `HERO_SYNC_LOCKED` units may use master narration in final assembly only if the source slice and final master window are proven to match.
3. Provider-returned audio for hero units is diagnostic unless a later ticket explicitly changes policy.
4. Local graphics and deterministic text must not be sent to providers.
5. Provider prompts must not ask for exact text when text policy forbids it.

## Eval invariants

1. Every eval must have a deterministic command.
2. Every eval must write machine-readable JSON evidence.
3. Missing eval output is failure.
4. An eval that always passes is a fake-green eval and must be rejected.
5. A bad fixture must remain in regression tests until explicitly superseded.

## Render/spend invariants

1. LLM calls are allowed from the start.
2. Actual video render calls are forbidden until Sprint 06 unlock.
3. Dry-run provider request construction is allowed only when it cannot submit a real provider job.
4. Any command capable of `higgsfield generate create` must be blocked by default before unlock.
5. Provider render unlock must be explicit, auditable, and limited to one canary render first.

## Reporting invariants

1. Every ticket writes reports under `reports/karpathy_loop/<sprint>/<ticket>/`.
2. Reports must include exact commands run.
3. Reports must include pass/fail status for every required gate.
4. Reports must list changed files.
5. Reports must include unresolved issues.
