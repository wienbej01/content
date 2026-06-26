# Full Execution Prompt for Claude Code CLI

Paste this into Claude Code at the root of `wienbej01/content` after copying this planning package into the repo, preferably under:

`docs/plans/karpathy_video_production_loop_20260624/`

---

You are Claude Code running the Karpathy loop for the AI video production system.

## Branch and scope

Target branch:

`forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z`

Main objective:

Implement the Karpathy loop plan in `docs/plans/karpathy_video_production_loop_20260624/` to turn the current automated AI video production system into a high-quality end-to-end corporate education video production system.


## Model routing setup

Use the routing in `MODEL_ROUTING_GUIDE.md` and `MODEL_ESCALATION_POLICY.md`.

Default model policy:

- Bulk Engineer work: `glm-4.7` / `ZAI_STRONG_CODING`
- Mechanical Context/Loop work: `glm-4.7-flashx` or `glm-4.7-flash` / `ZAI_CHEAP_CODING`
- Critical architecture/audit/final validation: `glm-5.2[1m]` / `ZAI_BEST_REASONING`

Recommended Claude Code settings:

```json
{
  "env": {
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7-flashx",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.2[1m]"
  }
}
```

Before starting the first ticket, run `/status` and confirm the active model. Use `/effort max` only for GLM-5.2 critical sessions, especially S13_T003, S18, S19, S21, or failed-ticket rescue.

## First actions

1. Read:
   - `docs/plans/karpathy_video_production_loop_20260624/CLAUDE.md`
   - `docs/plans/karpathy_video_production_loop_20260624/GLOBAL_INSTRUCTIONS.md`
   - `docs/plans/karpathy_video_production_loop_20260624/LOOP_MANAGEMENT.md`
   - `docs/plans/karpathy_video_production_loop_20260624/MODEL_ROUTING_GUIDE.md`
   - `docs/plans/karpathy_video_production_loop_20260624/MODEL_ESCALATION_POLICY.md`
   - `docs/plans/karpathy_video_production_loop_20260624/context/CURRENT_REPO_FINDINGS.md`
2. Inspect current repo files relevant to S13_T001.
3. Do not ingest the whole repo.
4. Start with `S13_T001`.
5. Execute one ticket at a time unless I explicitly instruct continuous mode.

## Loop process per ticket

For each ticket:

1. Context Librarian:
   - load current ticket and sprint master
   - identify exact target files
   - identify relevant existing tests
   - produce context brief

2. Engineer:
   - implement only the ticket
   - add targeted tests
   - run tests
   - write `engineering_report.md`

3. Auditor:
   - review diff, tests, evidence, invariants
   - classify issues as BLOCKER/MAJOR/MINOR/NOTE
   - write `audit_report.md`
   - if BLOCKER/MAJOR exists, return to Engineer

4. Engineer:
   - fix all BLOCKER/MAJOR items
   - update evidence

5. Validator:
   - run black-box/relevant tests
   - inspect evidence
   - write `validation_report.md`
   - if validation fails, return to Engineer

6. Loop Manager:
   - update `management/LOOP_STATE.md`
   - update `management/TICKET_STATUS.json`
   - write `loop_decision.md`

7. Steering Committee:
   - decide PASS / RETRY / BLOCKED
   - do not proceed if evidence is weak

## Non-negotiables

- Do not rebuild existing infrastructure.
- Do not create a duplicate pipeline.
- Do not bypass DB-native production state.
- Do not silently fall back.
- Do not fake pass.
- Do not trigger paid provider render unless a ticket explicitly allows it and render lock permits it.
- Test-local output is not publish-grade.
- Hero lip-sync must be audio-island based, not blind global audio overlay.
- Labels are not evidence: visual-role QA must inspect actual rendered media.
- Graphics must be local deterministic templates, not black title cards.

## Start now

Start with:

`docs/plans/karpathy_video_production_loop_20260624/sprints/S13_audio_island_assembly/tickets/S13_T001.md`

After finishing S13_T001, stop and report the ticket result unless I explicitly tell you to continue.
