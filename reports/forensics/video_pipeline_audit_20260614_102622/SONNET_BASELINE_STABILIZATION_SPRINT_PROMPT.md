# Sonnet Prompt: Video Pipeline Baseline Stabilization Sprint

You are Claude Sonnet operating as Principal Implementation Orchestrator for:

`/home/jacobw/YTchannel`

Implement the prerequisite stabilization sprint below before the separate post-TTS storyboard reconciliation sprint. Use Engineer, Auditor, and Validator subagents sequentially for every ticket. Do not redesign post-TTS timing or production-storyboard architecture in this sprint.

## Objective

Make the current pipeline baseline internally consistent and fail closed before adding post-TTS storyboard reconciliation. The previous remediation added valuable media and final-output gates, but its claim of full completion is not yet production-safe because active runtime paths still bypass or weaken review, compilation, approval, music, graphics, and manifest guarantees.

The sprint is complete only when the full local test suite passes, production orchestration contains no unsafe paid-generation bypass, and invalid artifacts cannot be marked complete or passed downstream.

## Read First

Read completely:

- `AGENTS.md`
- `docs/PIPELINE.md`
- `video_forensic_audit_report.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/root_cause_matrix.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/SPRINT_VIDEO_PIPELINE_FORENSIC_REMEDIATION.md`
- `reports/remediation/FINAL_IMPLEMENTATION_REPORT.md`
- `reports/remediation/SPRINT_STATUS.md`
- all `reports/remediation/TKT-{01..15}/{engineer,audit,validation}_report.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/KIRO_POST_TTS_STORYBOARD_RECONCILIATION_PROMPT.md`

Then inspect the current code, callers, tests, schemas, and gate ledger for:

- `scripts/produce.py`
- `scripts/review.py`
- `scripts/review_script.py`
- `scripts/review_storyboard.py`
- `scripts/review_media_plan.py`
- `scripts/compile_media_prompts.py`
- `scripts/generate_media.py`
- `scripts/gates.py`
- `scripts/budget.py`
- `scripts/approve.py`
- `scripts/build_manifest.py`
- `scripts/render_graphics.py`
- `scripts/assemble.py`
- `scripts/qa_media.py`
- `scripts/qa_final.py`
- `scripts/build_quality_report.py`
- `tests/test_review.py` and all relevant pipeline tests

Documentation and prior PASS reports are evidence, not proof. Trace the actual `produce.py` execution path and inspect current git changes before editing.

## Confirmed Starting Evidence

Reconfirm these facts locally before implementation:

1. `python3 -m pytest -q tests/test_review.py` currently reports 4 failures and 1 pass.
2. `scripts/review.py::review()` returns a mandatory-issue boolean where callers/tests expect a pass boolean.
3. `WEIGHTED_THRESHOLD` and the intended audience veto are not mechanically enforced by the current aggregator.
4. `review_loop()` has incompatible return and parameter contracts across production callers and tests.
5. `step_storyboard_create()` writes `storyboard.json` and returns success despite nonempty validation errors.
6. `step_compile_media_plan()` writes `media_plan.json` and returns success despite compile errors.
7. `step_generate_media()` invokes `run_from_media_plan(..., force_unsafe=True)` and therefore bypasses required spend gates.
8. `step_gate_a_budget()` records only an interactive answer, while generation requires fresh ledger gates for `storyboard_review`, `media_plan_review`, `budget`, and `render_approval`.
9. `step_build_manifest()` uses `--allow-missing` after media QA and duration reconciliation.
10. `build_manifest.py` selects the first discovered MP3, can silently disable music, does not reliably propagate format, and builds before required graphics are rendered.

If any fact has changed, document the current evidence and adapt narrowly without weakening the stated guarantees.

## Hard Constraints

- Do not call paid APIs.
- Do not generate or regenerate ElevenLabs audio.
- Do not generate Higgsfield, Seedance, Kling, or other paid media.
- Use mocks, dry runs, local FFmpeg fixtures, and temporary project directories.
- Never invoke production generation with `force_unsafe=True`.
- Do not record a gate as passed unless its actual check or explicit human approval succeeded and the gate is bound to current artifact hashes.
- Do not weaken existing final-video, duration, provenance, media-QA, or quality-report gates.
- Do not implement the post-TTS production storyboard in this sprint.
- Do not hide failures by changing tests to accept permissive behavior.
- Do not add dummy media, silent fallbacks, arbitrary `-shortest`, frame holds, or placeholder assets.
- Do not revert unrelated worktree changes.

## Required Subagent Workflow

Implement one ticket at a time in order.

### Engineer Agent

- May edit production code and tests for exactly one ticket.
- Must add positive and negative tests.
- Must not perform network or paid operations.
- Writes `reports/remediation/baseline_stabilization/<TICKET>/engineer_report.md`.

### Auditor Agent

- Read-only for production code.
- Reviews the full ticket diff and all active callers.
- Searches for bypasses, warning-only failures, stale hashes, false gate records, and API-contract drift.
- Writes `reports/remediation/baseline_stabilization/<TICKET>/audit_report.md` with PASS or REVISE and file/line evidence.

### Validator Agent

- Does not edit production code.
- Runs focused tests and independent local fixture commands.
- Confirms negative cases fail before downstream work.
- Writes `reports/remediation/baseline_stabilization/<TICKET>/validation_report.md` with PASS or FAIL and exact commands/output.

For each ticket: Engineer -> focused tests -> Auditor -> revision if required -> Validator. Permit at most two revision cycles. Stop and report a blocker if acceptance criteria cannot be met without paid operations or unresolved product-policy decisions.

## Sprint Tickets

### BSS-01 - Repair Reviewer Contract and Enforcement

**Goal:** Define and enforce one review contract across `review()`, `aggregate()`, `review_loop()`, `produce.py`, CLI entry points, and tests.

Implementation requirements:

- `review()` must return an unambiguous `passed` boolean plus a structured report.
- Pass requires no mandatory issues, no applicable veto failure, and the configured weighted threshold.
- Normalize malformed or inconsistent persona results fail closed.
- Define audience-veto semantics explicitly and test them.
- Use one documented `max_rounds` meaning and one return object/tuple contract across every caller.
- Preserve escalation information in the report without incompatible tuple arity.
- A failed final review must raise or block its production step; it cannot be marked complete.

Acceptance criteria:

- `tests/test_review.py` passes without weakening assertions.
- Added tests cover below-threshold/no-blocker, persona `status=fail`, malformed verdict, persistent failure, early pass, and production caller behavior.
- Search confirms no caller interprets `passed` as `has_mandatory` or vice versa.

### BSS-02 - Make Storyboard and Media-Plan Compilation Fail Closed

**Goal:** Prevent invalid creative artifacts from being persisted as successful production inputs.

Implementation requirements:

- Nonempty storyboard validation errors cause `storyboard_create` to fail.
- A failed revision cannot silently retain and approve the previous invalid storyboard.
- Nonempty media-plan compiler errors cause `compile_media_plan` to fail before writing a production plan or marking the step complete.
- Failed attempts may write clearly named diagnostic artifacts, but never overwrite the last known valid production artifact.
- State records failure and invalidates downstream outputs through the existing dependency DAG.

Acceptance criteria:

- Negative tests prove invalid storyboard and media-plan results cannot advance.
- Existing valid fixtures still pass.
- Error messages identify beat IDs/fields and corrective action.

### BSS-03 - Remove Unsafe Generation Bypass and Wire Real Gates

**Goal:** Make paid generation unreachable unless every required fresh gate is present.

Implementation requirements:

- Remove the production `force_unsafe=True` call.
- Trace and use existing gate-ledger APIs rather than inventing a second approval system.
- Add or wire explicit orchestration for `storyboard_review`, `media_plan_review`, `budget`, and `render_approval`.
- Bind each gate to the exact current artifact hash/fingerprint it approves.
- Budget approval must record the evaluated media plan and cap.
- Render approval must be a separate explicit human approval after the dry-run/media-plan report is available.
- Changed upstream artifacts must make approvals stale.
- Dry-run/test paths may avoid spend gates only when they cannot call paid providers.

Acceptance criteria:

- Local tests patch provider entry points and prove they are never reached with a missing, failed, or stale gate.
- A fully mocked, freshly approved gate chain reaches the mocked generation boundary without `force_unsafe`.
- `rg "force_unsafe=True" scripts/produce.py` returns no production bypass.
- Gate records contain project identity, artifact path/hash, timestamp, and approval/check provenance.

### BSS-04 - Harden Manifest, Music, and Graphics Ordering

**Goal:** Build a strict manifest only after every required media and graphics asset exists and is verifiable.

Implementation requirements:

- Render deterministic required graphics before final manifest construction.
- Remove `--allow-missing` from the production manifest path.
- Manifest build must reject missing media, missing required overlays, zero-byte/unreadable assets, and unresolved paths.
- Include project format/episode type explicitly in the manifest.
- Resolve music from explicit project/channel configuration; never select an arbitrary first directory entry.
- For formats requiring music, missing/disabled/unreadable music is fatal before assembly.
- For formats where music is optional, disabled state must be explicit and justified.
- Record hashes for media, overlays, timing map, narration, and music where applicable.
- Preserve compatibility with the later post-TTS sprint, which will also require graphics before manifest construction.

Acceptance criteria:

- Tests cover required music missing, explicit music path, nondeterministic directory contents, required overlay missing, stale overlay hash, missing media, and successful strict build.
- Manifest format reliably activates assembly music policy.
- No production warning says `TKT-10 pending` or `TKT-11 pending`.

### BSS-05 - Verify Orchestrator State, Gate, and Completion Semantics

**Goal:** Ensure a step is complete only when its outputs and required gates are valid.

Implementation requirements:

- Review every `produce.py` step for warning-only errors, swallowed exceptions, unconditional success messages, and incomplete outputs.
- Ensure failed steps are persisted as failed and downstream steps are invalidated.
- Ensure resume cannot skip a failed review, failed compile, stale gate, missing graphic, missing music, or strict manifest failure.
- Ensure assembly requires current media-QA/duration/manifest prerequisites and final review requires current final-QA and quality-report PASS.
- Do not duplicate the post-TTS invalidation work reserved for the follow-on sprint; stabilize only current artifact dependencies.

Acceptance criteria:

- State/resume tests cover every new failure boundary from BSS-01 through BSS-04.
- A deliberately stale approval cannot be reused after changing the approved artifact.
- No failed or partially written artifact is marked complete.

### BSS-06 - Full Local Regression and Handoff Gate

**Goal:** Prove the repository is a clean baseline for the post-TTS sprint.

Implementation requirements:

- Run the full local test suite with no paid/network operations.
- Run the existing local end-to-end fixture suite.
- Run the defective memory-retention project only through read-only QA/reconciliation commands; do not regenerate assets.
- Confirm it remains blocked for known duration/media/overlay defects.
- Produce a concise compatibility assessment for the post-TTS prompt.

Acceptance criteria:

- Full suite has zero failures. Skips must be explained and must not hide relevant pipeline coverage.
- Defective final MP4 still fails final stream-integrity checks.
- Existing broken project remains blocked before paid generation/Telegram review.
- No provider API was called and no credits were spent.
- The follow-on post-TTS prompt can begin without changing its architectural objective.

## Required Commands

Use commands appropriate to the current repository, including at minimum:

```bash
python3 -m pytest -q tests/test_review.py
python3 -m pytest -q tests/test_produce_resume.py
python3 -m pytest -q tests/test_manifest_builder.py tests/test_music.py tests/test_graphics.py
python3 -m pytest -q tests/test_pipeline_local_e2e.py
python3 -m pytest -q
python3 scripts/qa_final.py Videos/Projects/using_ai_to_help_memory_retention_short/using_ai_to_help_memory_retention_short_16x9.mp4
python3 scripts/reconcile_duration.py Videos/Projects/using_ai_to_help_memory_retention_short
```

Record exact exit codes and key output. The last two commands are expected to fail on the defective audited project; that failure is proof of correct gating.

## Deliverables

Create:

- `reports/remediation/baseline_stabilization/SPRINT_STATUS.md`
- one Engineer, Auditor, and Validator report per ticket
- `reports/remediation/baseline_stabilization/FINAL_REPORT.md`
- `reports/remediation/baseline_stabilization/FOLLOW_ON_READINESS.md`
- updated documentation only after behavior is implemented and validated

`FINAL_REPORT.md` must list exact code changes, test counts, unresolved risks, gate behavior, and confirmation that no paid API was called.

`FOLLOW_ON_READINESS.md` must state whether the post-TTS sprint is GO or NO-GO and explicitly check:

- reviewer contract is stable;
- compile stages fail closed;
- no unsafe generation bypass remains;
- all spend gates are fresh and hash-bound;
- manifest is strict;
- graphics precede manifest;
- music policy is explicit;
- full suite is green.

## Definition of Done

This sprint is done only when:

1. The active reviewer contract is coherent, enforced, and fully tested.
2. Storyboard and media-plan errors stop the pipeline.
3. Production generation cannot bypass required approvals.
4. Gate approvals are real, current, and hash-bound.
5. Required media, graphics, and music are verified before manifest completion.
6. Resume cannot treat failed or stale work as complete.
7. The complete local test suite passes with zero unexplained failures.
8. The known defective project remains impossible to ship.
9. Auditor and Validator both mark every ticket PASS.
10. `FOLLOW_ON_READINESS.md` says GO.

Begin by creating the sprint status file and reproducing the baseline evidence. Then execute BSS-01 through BSS-06 sequentially. Do not start the post-TTS storyboard reconciliation sprint in this run.
