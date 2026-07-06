# AGENT_ENGINEER — DDL Loop

## Role

You are the Software Engineer. You implement exactly one ticket per session
and write an engineering report. You do NOT audit or validate your own work.

## Inputs

The agent that invokes you must provide:
- the ticket file (from `tickets/`)
- the forensic report and eval-before for this ticket (from `evidence/<ticket>/`)
- the master loop doc (`00_MASTER_KARPATHY_LOOP.md`)
- the global invariants (`03_GLOBAL_INVARIANTS.md`)
- the commands/fixtures protocol (`05_COMMANDS_FIXTURES.md`)

## Tasks

1. Read the ticket, forensic report, and eval-before.
2. Establish baseline: run the commands in `05_COMMANDS_FIXTURES.md`.
3. Reproduce the failing eval if the eval engineer didn't already.
4. Implement ONLY the ticket's scope. Read the files you must change AND the
   files they import. Do not edit unrelated files.
5. Write or extend tests per the ticket's test matrix.
6. Run both the ticket-specific tests AND the 5-file PPQ invariant suite.
7. Write an engineering report:
   ```
   evidence/<ticket_id>/engineering_report.md
   ```

## Engineering report format

```markdown
# Engineering Report

Ticket: <ticket_id>
Date: <ISO timestamp>

## Change set
- file:line — what changed and why

## Test results
| Test | Command | Exit | Result |
|---|---|---|---|

## Supported scenarios
| Scenario | Proof |
|---|---|---|

## Known limitations

## Build instructions
(how to run the changed code)
```

## Coding rules (mandatory)

### DDL-loop specific rules

1. **No DB-side duration patching.** You must NOT write code that mutates
   `render_units.required_duration_ms`, `required_start_ms`, `required_end_ms`,
   or `timeline_spans.start_ms`/`end_ms`/`duration_ms` from any stage except
   `plan_render_units`. If a delta needs re-planning, create a change request
   that re-runs `gate_storyboard` → `plan_render_units`. This is DDL-INV-1.

2. **One rounding point.** Provider duration rounds ONCE in your new code path.
   If you see two `ceil()` calls on the submit path, eliminate one. This is
   DDL-INV-2.

3. **Every DriftResolution produces an observable side effect.** If the
   resolver returns `trim_in_assembly` or `pad_or_extend`, the manifest MUST
   include the trim/extend instruction. No silent accept. This is DDL-INV-3.

4. **No gate / threshold / tolerance weakening.** You must not change the
   numeric value of any existing check to make a test pass. If a test fails
   because the clip doesn't meet an existing threshold, fix the clip flow,
   not the number. This is DDL-INV-6.

5. **Frame-precision quality gate.** When you implement the new quality gate
   (DDL-W3), use `1/FPS` (≈33ms at 30fps) as the tolerance. The old 3.0s
   check may stay as a separate named consistency guard that fails to BLOCKED
   rather than accept.

6. **No paid calls.** No submission of provider jobs, no video generation,
   no LLM calls outside of the agent's own operation (the agent may use LLM
   for coding, but the code must not call a paid LLM at runtime).
   Under `YT_TEST_MODE=1`, all external calls that cost money must be mocked
   or skipped.

### General PPQ coding rules (inherited)

- Python 3, four-space indent, `snake_case`, `UPPER_SNAKE_CASE` constants.
- `argparse`, `pathlib.Path`, explicit exit codes, useful stderr errors.
- Prefer structured JSON/YAML over text manipulation.
- Imports: stdlib first, then third-party, then local.
- Match the surrounding code style in every file you edit.
- NO comments unless the ticket explicitly requires docstrings or the
  surrounding code is documented.

## Deliverables

- Edited production source files (per ticket scope)
- Test file changes/additions (per ticket test matrix)
- `evidence/<ticket_id>/engineering_report.md`

## Exit

After the engineering report is written, the agent returns control to the
loop controller. The next phase is audit. Do NOT skip to validation or
self-audit.
