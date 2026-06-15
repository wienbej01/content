# Kiro CLI Claude 4.6 Sprint Implementation Prompt

You are Claude 4.6 operating through kiro-cli as the Principal Implementation Orchestrator for this repository:

`/home/jacobw/YTchannel`

Your task is to implement the complete forensic remediation sprint using subagents with strict Engineer, Auditor, and Validator roles.

## Authoritative Inputs

Read these files completely before modifying code:

1. `/home/jacobw/YTchannel/AGENTS.md`
2. `/home/jacobw/YTchannel/docs/PIPELINE.md`
3. `/home/jacobw/YTchannel/video_forensic_audit_report.md`
4. `/home/jacobw/YTchannel/reports/forensics/video_pipeline_audit_20260614_102622/final_video_forensics.md`
5. `/home/jacobw/YTchannel/reports/forensics/video_pipeline_audit_20260614_102622/root_cause_matrix.md`
6. `/home/jacobw/YTchannel/reports/forensics/video_pipeline_audit_20260614_102622/duration_reconciliation.csv`
7. `/home/jacobw/YTchannel/reports/forensics/video_pipeline_audit_20260614_102622/artifact_inventory.csv`
8. `/home/jacobw/YTchannel/reports/forensics/video_pipeline_audit_20260614_102622/COMMAND_LOG.md`
9. `/home/jacobw/YTchannel/reports/forensics/video_pipeline_audit_20260614_102622/SPRINT_VIDEO_PIPELINE_FORENSIC_REMEDIATION.md`

Also inspect relevant architecture, constraints, tests, and implementation files under:

- `docs/`
- `docs/channel_universe/`
- `docs/plans/`
- `schemas/`
- `configs/`
- `scripts/`
- `tests/`

Documentation is not proof. Verify behavior directly in code and local artifacts.

## Primary Objective

Make it impossible for a structurally broken video to pass production gates or reach Telegram review.

Implement every ticket in the sprint plan, one ticket at a time, using this required order:

1. TKT-02
2. TKT-07
3. TKT-03
4. TKT-09
5. TKT-01
6. TKT-13
7. TKT-04
8. TKT-05
9. TKT-06
10. TKT-08
11. TKT-10
12. TKT-11
13. TKT-12
14. TKT-14
15. TKT-15

Do not reorder tickets without documenting a concrete dependency conflict.

## Absolute Constraints

- Do not call paid external APIs.
- Do not regenerate ElevenLabs audio.
- Do not call Higgsfield, Seedance, Kling, or other paid generation services.
- Do not spend credits.
- Do not use production API credentials.
- Use local FFmpeg-generated fixtures and mocks.
- Do not add dummy or silent fallbacks.
- Fail loudly with actionable errors.
- Do not hide failures with `-shortest`, arbitrary truncation, long frame holds, loops, or placeholder media.
- Do not revert unrelated existing worktree changes.
- Preserve backward compatibility only where it does not weaken fail-loud guarantees.

## Subagent Workflow

Use the native Kiro subagent/task mechanism. Create a fresh role-specific subagent for each ticket phase.

### Engineer Subagent

The Engineer may edit production code and tests.

Instructions:

- Implement exactly one ticket.
- Read the ticket and its dependencies completely.
- Inspect current code before editing.
- Keep changes limited to the ticket.
- Add focused positive and negative tests.
- Use production entry points in integration tests.
- Run no paid or network operations.
- Produce an implementation report containing:
  - files changed,
  - behavior added,
  - tests added,
  - commands executed,
  - known risks.

### Auditor Subagent

The Auditor is read-only for production code.

Instructions:

- Review the Engineer's complete diff.
- Trace all affected runtime paths.
- Verify every ticket acceptance criterion.
- Look specifically for:
  - silent degradation,
  - warning-only failures,
  - stale artifact reuse,
  - casing or enum inconsistencies,
  - missing dependency invalidation,
  - duration inferred from container instead of streams,
  - unchecked bypasses,
  - overbroad refactors,
  - missing negative tests.
- Do not repair production code.
- Write `reports/remediation/TKT-XX/audit_report.md`.
- Return PASS or REVISE with exact file and line references.

### Validator Subagent

The Validator may run commands but must not edit production code.

Instructions:

- Run the ticket's required tests and local fixture commands.
- Independently verify acceptance criteria.
- Inspect actual generated fixture media with ffprobe/FFmpeg where relevant.
- Confirm failures return non-zero status and actionable messages.
- Write `reports/remediation/TKT-XX/validation_report.md`.
- Return PASS or FAIL with command evidence.

## Ticket Loop

For every ticket:

1. Create `reports/remediation/TKT-XX/`.
2. Engineer implements the ticket.
3. Run focused tests.
4. Auditor reviews the implementation.
5. If Auditor returns REVISE, return to the Engineer with findings.
6. Validator independently validates the corrected implementation.
7. Do not begin the next ticket until both Auditor and Validator return PASS.
8. Allow at most two revision cycles before stopping and reporting a blocker.
9. Update `reports/remediation/SPRINT_STATUS.md`.

The status file must include ticket state, tests, audit verdict, validation verdict, and dependencies.

## Required Early Proof

After TKT-02, prove that this existing defective file fails:

`Videos/Projects/using_ai_to_help_memory_retention_short/using_ai_to_help_memory_retention_short_16x9.mp4`

Expected evidence:

- container: approximately 146.600s,
- video stream: approximately 83.333s,
- audio stream: approximately 146.600s,
- mismatch: approximately 63.267s,
- gate exits non-zero,
- Telegram review cannot run.

After TKT-07, prove that lowercase per-beat `fail` results cannot become an aggregate pass.

After TKT-03, prove the audited project reports approximately 63.266s insufficient visual coverage before assembly.

After TKT-09, prove assembly refuses these inputs before muxing the defective final.

## Verification Requirements

Run focused tests after each ticket. At major checkpoints run:

```bash
python3 -m pytest -q
```

Use local FFmpeg fixtures for:

- valid lipsync video with baked audio,
- silent b-roll,
- local graphic,
- music bed,
- missing media,
- short visual/long audio mismatch,
- frozen video,
- black video,
- stale hashes,
- missing overlays,
- missing required music.

Run final static checks or linters already supported by the repository. Do not introduce a new formatter or broad formatting churn.

## Final Acceptance

The sprint is complete only when:

1. The audited defective MP4 fails before Telegram review.
2. A valid local fixture passes every gate.
3. Audio/video/container durations differ by no more than 0.25s.
4. Every beat has sufficient visual coverage.
5. Failed, missing, stale, partial, skipped, or unprovenanced artifacts cannot pass.
6. Required music is present and measurably mixed.
7. Required graphics are deterministically rendered and composited.
8. Lipsync provenance is closed from master audio through final assembly.
9. Resume and `--from-step` invalidate all downstream dependencies.
10. `run_quality_report.md` is mandatory and fail-closed.
11. The complete test suite passes without paid API access.

## Final Deliverables

Produce:

- `reports/remediation/SPRINT_STATUS.md`
- `reports/remediation/FINAL_IMPLEMENTATION_REPORT.md`
- one implementation report per ticket,
- one audit report per ticket,
- one validation report per ticket,
- final test output summary,
- final ffprobe and freeze-detection evidence,
- remaining risks, if any.

Begin by reading all authoritative inputs, inspecting `git status`, and creating the sprint status file. Then execute TKT-02 only. Do not implement multiple tickets in one Engineer pass.
