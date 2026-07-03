# S22 Process Rules

## Loop order per ticket

1. Context Librarian loads the exact ticket and context files.
2. Engineer implements only the current ticket.
3. Engineer runs required tests and writes `engineering_report.md`.
4. Auditor reviews diff, tests, invariants, and evidence.
5. Engineer fixes all BLOCKER and MAJOR findings.
6. Validator runs black-box validation and writes `validation_report.md`.
7. Loop Manager writes `loop_decision.md`.
8. Stop.

Do not proceed to the next ticket automatically.

## Required report folder

For ticket `S22_TNNN`, write:

`reports/karpathy_loop/s22/S22_TNNN/`

Required files:

- `engineering_report.md`
- `audit_report.md`
- `validation_report.md`
- `loop_decision.md`

Evidence files as applicable:

- `dry_run.json`
- `validation_errors.json`
- `before_after_diff_summary.md`
- `db_assertions.json`
- `stage_invalidation_evidence.json`
- `fixture_results.json`

## Loop decision format

Each `loop_decision.md` must include:

```md
# Loop Decision - S22_TNNN

## Verdict
PASS | RETRY | BLOCKED

## Why

## Files changed

## Commands run

## Evidence

## Open issues

## Next action
```

## Stop conditions

Stop the loop if:

- Sonnet 5 is unavailable for a ticket that requires runtime storyboard authorship.
- A ticket would require paid media/TTS calls.
- A required dependency from a prior ticket is not complete.
- Tests are non-deterministic after retry.
- The implementation would duplicate existing DB/stage/artifact infrastructure.
- The engineer cannot prove no Python creative fallback was introduced.
- A compliance finding cannot be routed to a concrete repair/invalidation action.

## Audit minimum

Auditor must inspect:

- Diff.
- Tests.
- Generated reports.
- Any new schemas or prompts.
- Failure messages.
- Model routing.
- Evidence that default tests do not call paid APIs.

## Validation minimum

Validator must:

- Run the ticket's focused tests.
- Run relevant existing tests.
- Validate behavior from public CLI/module surfaces where possible.
- Inspect generated evidence files.
- Confirm `loop_decision.md` matches the actual state.

