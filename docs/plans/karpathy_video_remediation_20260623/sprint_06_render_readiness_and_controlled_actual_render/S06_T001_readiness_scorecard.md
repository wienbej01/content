# S06_T001 Readiness Scorecard

## Purpose

Prove the code/evals have reached high readiness before any actual render.

## Required checks

```text
- S00 passed
- S01 passed
- S02 passed
- S03 passed
- S04 passed
- S05 passed
- lipsync eval exists
- source slice ledger exists
- provider diagnostic compare exists
- assembly transform ledger exists
- final defect ledger exists
- regression suite exists
```

## Required output

```json
{
  "ready_for_actual_render": false,
  "passed_sprints": [],
  "missing_requirements": [],
  "recommendation": "remain_locked|allow_one_canary"
}
```

## Pass gates

PASS if readiness scorecard is complete. It may recommend remain_locked.
