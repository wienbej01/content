# Karpathy Loop Management

## Loop roles

The loop is not a single agent doing everything. It runs the following cycle per ticket:

1. Context Librarian loads exact repo context and ticket.
2. Engineer implements the ticket.
3. Auditor reviews code, tests, invariants, and evidence.
4. Engineer fixes all BLOCKER/MAJOR issues.
5. Validator runs black-box/integration validation.
6. Loop Manager updates loop state.
7. Steering Committee decides whether to proceed, retry, or block.

## Required status values

Use these values only:

- `NOT_STARTED`
- `IN_PROGRESS`
- `ENGINEERING_DONE`
- `AUDIT_BLOCKED`
- `AUDIT_PASS`
- `VALIDATION_BLOCKED`
- `VALIDATION_PASS`
- `DONE`
- `BLOCKED`

## Ticket execution rule

Do not proceed to the next ticket if the current ticket has unresolved:

- BLOCKER
- MAJOR
- missing evidence
- missing tests
- unverified command output
- uncommitted/uncaptured changes

## Output folder convention

For each ticket:

`reports/karpathy_loop/<sprint_id>/<ticket_id>/`

Required files:

- `engineering_report.md`
- `audit_report.md`
- `validation_report.md`
- `eval_result_before.json` where applicable
- `eval_result_after.json` where applicable
- `loop_decision.md`

## Loop decision template

Each `loop_decision.md` must include:

```md
# Loop Decision — <ticket_id>

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

Stop the full loop if:

- repo state is dirty in a way that cannot be explained
- tests are non-deterministic after retry
- paid provider rendering would be required but render lock forbids it
- SyncNet or required dependencies are unavailable for a ticket that requires real validation
- the implementation would require rebuilding the architecture instead of extending existing infrastructure
