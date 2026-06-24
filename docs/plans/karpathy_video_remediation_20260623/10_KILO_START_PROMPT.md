# 10 Kilo Start Prompt

Paste this into Kilo Code to start the process.

```text
You are running the Karpathy Video Remediation Loop for this repo.

Target branch:
forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z

Primary bad fixture production:
prod_2f9bb58c0508465fb51ac6b4578bba92

Load these files first:
- docs/plans/karpathy_video_remediation_20260623/00_MASTER_KARPATHY_LOOP.md
- docs/plans/karpathy_video_remediation_20260623/01_CONTEXT_CURRENT_STATE.md
- docs/plans/karpathy_video_remediation_20260623/02_FAILURE_TAXONOMY.md
- docs/plans/karpathy_video_remediation_20260623/03_GLOBAL_INVARIANTS.md
- docs/plans/karpathy_video_remediation_20260623/04_PASS_GATES.md
- docs/plans/karpathy_video_remediation_20260623/05_COMMANDS_AND_FIXTURE_PROTOCOL.md
- docs/plans/karpathy_video_remediation_20260623/06_AGENT_ROSTER.md
- docs/plans/karpathy_video_remediation_20260623/09_LLM_AND_RENDER_SPEND_POLICY.md

Start with Sprint 00:
- docs/plans/karpathy_video_remediation_20260623/sprint_00_forensic_baseline/S00_MASTER.md
- docs/plans/karpathy_video_remediation_20260623/sprint_00_forensic_baseline/S00_T001_fixture_capture_and_artifact_ledger.md

Role for this first run:
AGENT_00_LOOP_CONTROLLER, then AGENT_01_FORENSIC_ANALYST, then AGENT_02_EVAL_ENGINEER only.
Do not implement code until the Forensic and Eval gates pass.

Hard constraints:
- LLM calls are allowed from the start.
- Actual video render/provider generation is forbidden.
- Set/assume: YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1.
- Do not run `higgsfield generate create` or any real external video generation.
- If a required command would call actual render, stop with BLOCKED_RENDER_LOCK.
- DB is the source of truth.
- No rebuild, no broad refactor, no dummy fallback, no fake-green eval.

Your first output must be a short execution plan and then the reports required by the current ticket. Follow the report paths specified in the ticket.
```

## Follow-up prompt for next agent phase

```text
Continue the Karpathy Video Remediation Loop from the current LOOP_STATE.
Load the same master files plus the current ticket.
Execute only the next required agent phase.
Do not skip gates.
Do not call actual video render.
If any BLOCKER or MAJOR issue exists, return to the appropriate prior agent.
```

## Prompt to advance to next ticket

```text
Review reports/karpathy_loop/LOOP_STATE.md and the current ticket's loop_decision.md.
If and only if the decision is PASS_TO_NEXT_TICKET, load the next ticket in the sprint.
Otherwise continue the bounce-back path specified by the Loop Controller.
```
