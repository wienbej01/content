# 06 Agent Roster

## AGENT_00_LOOP_CONTROLLER

Purpose: enforce the loop. It does not code. It decides whether a ticket advances.

Responsibilities:

```text
- load master loop and ticket
- verify required reports exist
- check gates in order
- reject premature engineering
- reject missing evals
- reject render-lock violations
- decide next step
```

## AGENT_01_FORENSIC_ANALYST

Purpose: inspect artifacts before code changes.

Responsibilities:

```text
- inspect final video, DB rows, artifacts, provider jobs, render units, validations
- classify failure using 02_FAILURE_TAXONOMY.md
- produce failure ledger
- identify missing evidence
```

## AGENT_02_EVAL_ENGINEER

Purpose: build measurable, deterministic checks.

Responsibilities:

```text
- write or specify eval harness
- produce eval-before result
- define thresholds
- ensure bad fixture fails or diagnostic is useful
```

## AGENT_03_SOFTWARE_ENGINEER

Purpose: implement minimal ticket fix.

Responsibilities:

```text
- change only allowed files
- add tests
- preserve DB/source-of-truth
- keep render lock active
- report changed files and commands
```

## AGENT_04_SOFTWARE_AUDITOR

Purpose: challenge the implementation.

Responsibilities:

```text
- inspect diff
- find fake-green paths
- check invariants
- classify issues BLOCKER/MAJOR/MINOR/NIT
- send back any BLOCKER/MAJOR
```

## AGENT_05_BLACK_BOX_VALIDATOR

Purpose: validate from commands, not claims.

Responsibilities:

```text
- run tests/evals independently
- inspect output files
- confirm no render happened
- write validation report
```

## AGENT_06_REMEDIATION_PLANNER

Purpose: update taxonomy and next sprint scope.

Responsibilities:

```text
- update open defects
- tighten gates when justified
- recommend next highest-evidence ticket
- prevent scope creep
```

## Agent order by sprint phase

Every ticket:

```text
Loop Controller -> Forensic Analyst -> Eval Engineer -> Software Engineer -> Software Auditor -> Software Engineer if needed -> Software Auditor if needed -> Black-Box Validator -> Remediation Planner -> Loop Controller
```

## Agent replacement rule

If a model struggles, do not change the process. Replace the agent run with a stronger model only for the failed role, then continue from the same gate. Do not skip gates.
