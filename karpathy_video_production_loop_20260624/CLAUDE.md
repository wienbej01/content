# Claude Code Instructions — Karpathy Video Production Loop

You are running the Karpathy loop for the AI video production system in `wienbej01/content`.

Read these first:

1. `GLOBAL_INSTRUCTIONS.md`
2. `LOOP_MANAGEMENT.md`
3. `MODEL_ROUTING_GUIDE.md`
4. `context/CURRENT_REPO_FINDINGS.md`
5. the current sprint `S##_MASTER.md`
6. the current ticket file

## Execution mode

For each ticket:

1. Do not start coding until you have loaded the ticket, relevant sprint master, and exact target files.
2. Implement only the current ticket.
3. Add/update tests.
4. Run required tests and commands.
5. Write the ticket evidence reports.
6. Run audit.
7. Fix all BLOCKER/MAJOR audit issues.
8. Run validation.
9. Update loop state.
10. Stop unless explicitly instructed to continue to the next ticket.

## Forbidden

- Do not rebuild the pipeline.
- Do not bypass existing DB-native flow.
- Do not create dummy/fake fallback passes.
- Do not silently ignore missing SyncNet, missing graphics, or missing artifacts.
- Do not trigger provider renders when render lock/dry-run forbids it.
- Do not call test-local output publish-grade.

## Required failure style

If blocked, write:

`BLOCKED: <precise reason>`

and include:

- files inspected
- commands run
- evidence found
- exact missing dependency or invariant
- recommended next action


## Model routing default

Use GLM-4.7 for routine ticket implementation. Escalate to GLM-5.2[1m] for architecture-critical work, hard audit, failed-ticket rescue, and final integration. Use GLM-4.7-FlashX/Flash only for mechanical context/report/loop-state work. Follow `MODEL_ROUTING_GUIDE.md` and `MODEL_ESCALATION_POLICY.md`.
