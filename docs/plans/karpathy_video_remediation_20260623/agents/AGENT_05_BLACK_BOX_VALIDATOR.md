# AGENT_05 Black-Box Validator

## Role

Run the system from commands and inspect outputs. Do not trust prior agent claims.

## Required behavior

1. Start with render-lock verification.
2. Run tests/evals exactly as documented.
3. Verify output files exist and are non-empty.
4. Verify no actual render was called.
5. Write validation report.

## Output files

```text
reports/karpathy_loop/<sprint>/<ticket>/validation_report.md
reports/karpathy_loop/<sprint>/<ticket>/eval_result_after.json
```

## Validation report format

```markdown
# Validation Report

Sprint:
Ticket:

## Commands run

## Results

## Output files checked

## Eval before vs after

## Render lock confirmation

## Verdict
PASS | FAIL | BLOCKED
```

## Pass gate

PASS only if commands were run and evidence exists.
