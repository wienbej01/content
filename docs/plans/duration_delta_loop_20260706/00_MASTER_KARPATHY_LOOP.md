# 00 Master Karpathy Loop — Duration Delta Feedback Closure

## Mission

Close the broken **Storyboard -> Render -> Edit duration feedback loop** so that
sub-second rounding deltas flow back to the storyboard and are *addressed in edit*
(trim / extend), and any **major** delta is proven impossible except as a
process, code, or instruction error.

The current primary defect class is *unwired duration drift*: the system has a
fully implemented `resolve_drift()` resolver that can create change requests and
emit trim/extend assembly instructions, but it is never called by any production
stage. As a result minor rounding errors (e.g. +303ms video over a 7738ms audio
slice) survive to assembly and compound into major defects (the +303ms became a
480ms lipsync desync on `prod_4e0ce12e24314d7798188aff60dca45f`).

This loop is **measurement-first, root-cause-first**, and never loosens a gate
to obtain a pass.

## Operating principle (the thesis under test)

> The storyboard must **instruct** render, and any (probably rounding
> sub-second) deltas must be **fed back** to story/board and **addressed in
> edit**. Any current *major* delta MUST be a process/code/instruction error.

This loop proves or refutes that thesis by closing every link so a delta can
only exist as one of:
- (a) sub-second rounding -> deterministic trim/extend in edit, or
- (b) process/code/instruction error -> fails a tight gate, routes to re-plan.

There is no third state.

## Loop structure (per ticket)

```text
Forensic Analyst -> Eval Engineer -> Software Engineer -> Software Auditor
                                                              |
                                                              v
                                          Black-Box Validator -> Loop Controller
                                                                      |
                                          +---------------------------+
                                          v                           v
                                  PASS_TO_NEXT_TICKET         RETURN_TO_* (bounce)
```

The engineer is **not allowed** to implement until the Forensic Analyst and
Eval Engineer have produced a failing or diagnostic eval relevant to the
ticket. The Validator is **not allowed** to accept "looks good" as evidence.

## Non-negotiable repo constraints

1. The production DB is the source of truth. Do not replace it with manifest
   files, ad-hoc JSON, or filename inference.
2. The storyboard is the single source of truth for *planned* durations. No
   DB-side patch of `required_duration_ms` / `timeline_spans.*_ms` to satisfy a
   gate. Feedback re-runs the plan via change requests, never mutates the
   numbers directly (this is the anti-pattern that produced the 125.3->177.4
   band-aid and must become impossible).
3. Make minimal, localized changes per ticket. No unrelated cleanup. No
   migration unless the ticket explicitly authorizes one.
4. No dummy fallbacks, fake passes, permissive `try/except pass`, empty
   placeholder artifacts, or test-specific production behavior.
5. If required evidence is missing, fail loud with `BLOCKED: <reason>`.
6. Never silently skip a failing eval or weaken a threshold/tolerance to obtain
   a pass. The clip is corrected, then re-measured against the unchanged gate.
7. Tests and evals run without paid provider/LLM/TTS calls under
   `YT_TEST_MODE=1`. No paid video render in any ticket of this loop.
8. All new gates must produce machine-readable JSON evidence written to the
   `validations` table with validator name, method, and input SHA provenance
   (existing repository invariant INV-4).
9. An engineer must not approve its own implementation. Every ticket passes
   through an independent auditor and an independent validator.

## Conventions carried over from the parent sprint

This loop inherits the architectural invariants of `PPQ-2026-07`
(`docs/plans/PPQ_SPRINT_20260704/PLAN.md` section 1):

- INV-1: `YT_TEST_MODE=1 python3 -m pytest -q` passes; the focused
  5-file invariant suite passes.
- INV-2: No paid provider/LLM/TTS call under `YT_TEST_MODE=1` or in pytest.
- INV-3: Publish-grade evidence writers fail loud when their backend is
  unavailable; they never fabricate a pass.
- INV-4: All new evidence recorded in `validations` with validator name,
  method, and input SHA provenance.
- INV-5: Repository stays runnable after every ticket; new stages/paths sit
  behind explicit config until the relevant wave gate.

These are immutable for this loop. Tickets that appear to require violating one
must instead report `BLOCKED` with the specific invariant and the reason.

## Spend / render lock

The loop runs entirely at the documentation/fixture/test level. No paid video
render, no paid regeneration. The existing `prod_4e0ce12e` hero artifact on disk
is reused for any measurement; no new Higgsfield job is submitted. If a ticket
appears to require a paid regeneration to prove itself, it reports
`BLOCKED_RENDER_LOCK` instead of submitting the job.

```text
RENDER_LEVEL=0: docs/static analysis only
RENDER_LEVEL=1: local tests/evals on fixtures (this loop's default)
RENDER_LEVEL=2: provider request dry-run only; no external video generation
```

ICLE-2026-07 fixes W1-W2 may be verified against the existing compensated hero
artifact at
`assets/media/prod_4e0ce12e24314d7798188aff60dca45f/pjob_cd63c3115fdb48fcbaf482c6e6d9c349_compensated.mp4`
(no paid call) once the drift feedback wire-up allows re-scoring after re-trim.

## Required environment defaults

Agents must assume these unless a ticket overrides:

```bash
export YT_TEST_MODE=1
export HIGGSFIELD_DRY_RUN=1
export OCR_STRICT_MODE=0
export SKIP_PREFLIGHT=1   # tesseract not installed in this env; preflight would fail otherwise
```

## Agent loop order per ticket

### Step 1 - Forensic Analyst
Inputs: ticket file, current branch, relevant code evidence.
Outputs: `evidence/<ticket_id>/forensic_report.md`,
         `evidence/<ticket_id>/failure_ledger.json`.
Must answer: exact failure class, the artifact/code that proves it exists, the
DB row or missing DB row that matters, what counts as success.

### Step 2 - Eval Engineer
Outputs: `evidence/<ticket_id>/eval_design.md`,
         `evidence/<ticket_id>/eval_result_before.json`.
Provides a **deterministic** command that reproduces the relevant failure or
proves the absence of required evidence.

### Step 3 - Software Engineer
Outputs: `evidence/<ticket_id>/engineering_report.md`.
Implements only the ticket. No unrelated cleanup. No migration unless the
ticket explicitly requires one.

### Step 4 - Software Auditor
Outputs: `evidence/<ticket_id>/audit_report.md`.
Classifies findings as `BLOCKER | MAJOR | MINOR | NIT`.
Any BLOCKER or MAJOR returns to Software Engineer.

### Step 5 - Black-Box Validator
Outputs: `evidence/<ticket_id>/validation_report.md`,
         `evidence/<ticket_id>/eval_result_after.json`.
Runs commands **independently**. Does not trust the engineer's reported output.

### Step 6 - Loop Controller
Outputs: `evidence/<ticket_id>/loop_decision.md`.
Decision values: `PASS_TO_NEXT_TICKET`, `RETURN_TO_ENGINEER`,
`RETURN_TO_EVAL_ENGINEER`, `BLOCKED_NEEDS_HUMAN_INPUT`, `BLOCKED_RENDER_LOCK`.

## Bounce-back rules

Return to Eval Engineer if no failing/diagnostic eval exists, if the eval is
subjective-only, if it cannot be rerun deterministically, or if it passes
before the fix when it should fail.

Return to Software Engineer if the implementation violates scope, required
tests are missing, the DB source-of-truth is bypassed (DB-side duration
patching counts), code can call a paid render before unlock, or a fake
green path exists.

Return to Auditor if the engineer claims a fix after audit issues but no new
audit was run.

Return to Validator if commands were not run from a clean state, evidence
files are missing, or the validation report has assertions without logs.

## Definition of done per ticket

```text
- forensic report exists and is non-empty
- eval-before exists and reproduces the defect (or proves absence)
- implementation report exists
- audit report has no BLOCKER/MAJOR
- validation report exists
- eval-after exists and proves the fix
- required tests pass
- git commit after validation (imperative subject, Conventional Commit prefix)
- loop decision says PASS_TO_NEXT_TICKET
```

## Definition of done for the loop

```text
- every DDL ticket has PASS_TO_NEXT_TICKET
- the parent production (prod_4e0ce12e) assembly succeeds with the feedback loop
  closed and NO DB-side duration patching (re-plan or trim-in-edit only)
- the aggregate assembly tolerance is tightened to frame precision; no residual
  > 1/FPS passes silently
- unresolved defects recorded in 02_FAILURE_TAXONOMY.md open_defects
- no gate, threshold, or tolerance was weakened to obtain a pass
```

## Absolute stop conditions

Stop immediately and report `BLOCKED: <reason>` if:

```text
- a command would submit a paid video render
- a DB migration is required but the ticket did not authorize it
- the production DB is unavailable and the ticket requires DB evidence
- a provider job was accidentally submitted
- generated evidence contradicts the ticket assumptions
- a fix requires weakening an existing gate/threshold/tolerance
```

## Required report location

All generated reports under `evidence/<ticket_id>/` within this sprint folder.
Do not scatter reports in the repository root.
