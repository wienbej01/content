# 00 Master Karpathy Loop

## Mission

Diagnose and remediate the AI video production system using a Karpathy-style loop: inspect artifacts first, define measurable failure modes, build evals that reproduce the defect, implement one narrow fix, audit the fix, validate black-box, then tighten gates. Do not rely on subjective impressions or broad refactors.

The current primary defect is severe lipsync failure in the uploaded final video:

```text
production_id=prod_2f9bb58c0508465fb51ac6b4578bba92
fixture=prod_2f9bb58c0508465fb51ac6b4578bba92_16x9.mp4
branch=forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z
```

Secondary defects include long static graphics, weak graphic editorial value, phone/screen text-risk surfaces, and QA that can pass while missing mouth/audio defects.

## Operating principle

For every ticket:

```text
Forensic Analyst -> Eval Engineer -> Software Engineer -> Software Auditor -> Black-Box Validator -> Loop Controller decision
```

The engineer is not allowed to implement until the Forensic Analyst and Eval Engineer have produced a failing or diagnostic eval relevant to the ticket. The Validator is not allowed to accept “looks good” as evidence.

## Non-negotiable repo constraints

1. The production DB is the source of truth. Do not replace it with manifest files, ad hoc JSON, or filename inference.
2. Do not rebuild the platform.
3. Make minimal, localized changes.
4. No dummy fallbacks, fake passes, empty placeholder artifacts, or broad exception swallowing.
5. If required evidence is missing, fail loud with `BLOCKED: <reason>`.
6. Do not silently skip failing evals.
7. Do not make video render/provider generation calls until the actual-render unlock gate passes.
8. LLM calls may be used from the start for analysis, authoring, code review, and implementation assistance.
9. Tests and evals must run without paid video render calls.
10. All new gates must produce machine-readable JSON evidence.

## Render/provider spend lock

The loop starts at `RENDER_LEVEL=0`.

```text
RENDER_LEVEL=0: docs/static analysis only
RENDER_LEVEL=1: local tests/evals on fixtures
RENDER_LEVEL=2: provider request dry-run only; no external video generation
RENDER_LEVEL=3: LLM calls allowed; no video render
RENDER_LEVEL=4: single controlled actual render allowed only after Sprint 06 unlock
```

Allowed from Sprint 00 onward:

```text
- local Python tests
- SQLite queries
- ffmpeg/ffprobe on existing media
- deterministic local graphics rendering
- LLM calls for analysis/planning/code assistance
- dry-run provider request construction if no external video job is submitted
```

Forbidden until Sprint 06 gate:

```text
- higgsfield generate create
- any paid video generation provider call
- regeneration of production media through external video provider
- bulk provider polling/download loops for new paid jobs
```

## Required environment defaults for early sprints

Agents must assume these unless a ticket says otherwise:

```bash
export YT_TEST_MODE=1
export HIGGSFIELD_DRY_RUN=1
export KARPATHY_LOOP_RENDER_LOCK=1
export OCR_STRICT_MODE=0
```

If code introduces a path that can call `higgsfield generate create` while the lock is enabled, that is a BLOCKER.

## Agent loop order per ticket

### Step 1 — Forensic Analyst

Inputs:

```text
- ticket file
- current branch
- existing bad fixture
- relevant DB rows or clear note that DB export is missing
```

Outputs:

```text
reports/<ticket_id>/forensic_report.md
reports/<ticket_id>/failure_ledger.json
```

Must answer:

```text
- What exact failure class is being addressed?
- What artifact proves it exists?
- What DB row or missing DB row matters?
- What would count as success?
```

### Step 2 — Eval Engineer

Outputs:

```text
reports/<ticket_id>/eval_design.md
reports/<ticket_id>/eval_result_before.json
```

Must provide a deterministic command that reproduces the relevant failure, or a diagnostic command that proves the absence of required evidence.

### Step 3 — Software Engineer

Outputs:

```text
reports/<ticket_id>/engineering_report.md
```

Must implement only the ticket. No unrelated cleanup. No migration unless the ticket explicitly requires it.

### Step 4 — Software Auditor

Outputs:

```text
reports/<ticket_id>/audit_report.md
```

Must classify findings:

```text
BLOCKER: cannot proceed
MAJOR: must fix before validation
MINOR: can proceed if documented
NIT: style only
```

Any BLOCKER or MAJOR returns to Software Engineer.

### Step 5 — Black-Box Validator

Outputs:

```text
reports/<ticket_id>/validation_report.md
reports/<ticket_id>/eval_result_after.json
```

Must run commands independently. Must not trust the engineer's reported command output.

### Step 6 — Loop Controller

Outputs:

```text
reports/<ticket_id>/loop_decision.md
```

Decision values:

```text
PASS_TO_NEXT_TICKET
RETURN_TO_ENGINEER
RETURN_TO_EVAL_ENGINEER
BLOCKED_NEEDS_HUMAN_INPUT
BLOCKED_RENDER_LOCK
```

## Bounce-back rules

Return to Eval Engineer if:

```text
- no failing/diagnostic eval exists
- eval result is subjective only
- eval cannot be rerun deterministically
- eval passes before the fix even though it should fail
```

Return to Software Engineer if:

```text
- implementation violates scope
- required tests missing
- DB source-of-truth bypassed
- code can call paid render before unlock
- fake green path exists
```

Return to Auditor if:

```text
- engineer claims fix after audit issues but no new audit was run
```

Return to Validator if:

```text
- commands were not run from a clean state
- evidence files are missing
- validation report has assertions without logs
```

## Definition of done per ticket

A ticket is done only when all of this is true:

```text
- forensic report exists
- eval-before exists
- implementation report exists
- audit report has no BLOCKER/MAJOR
- validation report exists
- eval-after exists
- required tests pass
- all required files are present and non-empty
- loop decision says PASS_TO_NEXT_TICKET
```

## Definition of done per sprint

A sprint is done only when:

```text
- every ticket has PASS_TO_NEXT_TICKET
- S##_GATE_exit_criteria.md checklist is fully satisfied
- sprint summary exists
- unresolved failures are recorded in 02_FAILURE_TAXONOMY.md or reports/sprint_##/open_defects.json
- next sprint scope is narrowed to highest-evidence remaining failures
```

## Absolute stop conditions

Stop immediately and report `BLOCKED:` if:

```text
- a command would create a paid video render before Sprint 06 unlock
- DB schema changes are required but ticket did not authorize migration
- production DB is unavailable and the ticket requires DB evidence
- a provider job was accidentally submitted
- generated evidence contradicts the ticket assumptions
- test fixture cannot be located
- media eval reports no face track for a hero lipsync unit and there is no fallback diagnostic
```

## Required report location

All generated reports must be under:

```text
reports/karpathy_loop/<sprint_id>/<ticket_id>/
```

Do not scatter reports in repo root.
