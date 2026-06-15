# Opus 4.8 Prompt: End-to-End AI Video Pipeline System Validation

You are Opus 4.8 acting as an independent Principal Software Forensics Engineer, Systems Auditor, and Validation Lead for:

`/home/jacobw/YTchannel`

Your task is to perform a comprehensive end-to-end analytic validation of the complete automated AI video-generation system after both remediation efforts have finished:

1. the original forensic remediation sprint; and
2. the post-TTS production-storyboard reconciliation sprint.

This is primarily a **read-only validation and forensic audit**. Do not implement production fixes unless the user separately authorizes remediation after reviewing your findings.

## Primary Question

Does the implemented system now work as intended from research seed to Telegram review, with complete data lineage, enforced controls, functioning feedback loops, correct artifact invalidation, full audio/visual alignment, and no silent degradation path?

Do not accept documentation, passing unit tests, successful process exit, state marked complete, or a passing QA report as proof by itself. Trace and test the real runtime behavior.

## Absolute Constraints

- Do not call paid APIs.
- Do not regenerate ElevenLabs audio.
- Do not call Higgsfield, Seedance, Kling, or any paid generation service.
- Do not spend credits.
- Do not send Telegram messages or videos.
- Do not use production credentials.
- Do not modify production code.
- You may create reports, local fixtures, temporary files, and audit-only inspection scripts under `reports/validation/` or `/tmp`.
- Use local FFmpeg-generated media, mocks, recorded artifacts, schema validation, static analysis, and test commands.
- Record every missing expected artifact, module, field, gate, or log as evidence. Never silently skip it.
- Preserve unrelated worktree changes.

## Required Inputs

Read completely before drawing conclusions:

- `AGENTS.md`
- `README.md`
- `docs/PIPELINE.md`
- `video_forensic_audit_report.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/final_video_forensics.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/root_cause_matrix.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/artifact_inventory.csv`
- `reports/forensics/video_pipeline_audit_20260614_102622/duration_reconciliation.csv`
- `reports/forensics/video_pipeline_audit_20260614_102622/SPRINT_VIDEO_PIPELINE_FORENSIC_REMEDIATION.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/KIRO_CLAUDE_4_6_SPRINT_IMPLEMENTATION_PROMPT.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/KIRO_POST_TTS_STORYBOARD_RECONCILIATION_PROMPT.md`
- `reports/remediation/SPRINT_STATUS.md`
- `reports/remediation/FINAL_IMPLEMENTATION_REPORT.md`
- all per-ticket implementation, audit, and validation reports
- `reports/remediation/post_tts_storyboard/SPRINT_STATUS.md`
- `reports/remediation/post_tts_storyboard/FINAL_REPORT.md`
- all post-TTS per-ticket reports and audited-project preview artifacts

If any expected report is missing, record it explicitly and continue with direct code/runtime validation.

Inspect all relevant files under:

- `scripts/`
- `tests/`
- `schemas/`
- `configs/`
- `docs/`
- `docs/channel_universe/`
- `docs/reviewer_prompts/`
- `strategy/`
- `.kiro/`
- project artifact directories under `Videos/Projects/`

Inspect `git status` first. Distinguish pre-existing changes from audit outputs.

## Validation Standard

Classify every material conclusion as:

- **CONFIRMED PASS** - demonstrated by code tracing and repeatable runtime evidence.
- **CONFIRMED FAIL** - directly contradicted by code, artifacts, or a repeatable test.
- **PROBABLE PASS** - strongly supported but one external or unavailable dependency prevents complete proof.
- **PROBABLE FAIL** - strong defect evidence without a fully reproducible runtime path.
- **NOT TESTED** - evidence cannot be obtained under the audit constraints.
- **NOT APPLICABLE** - requirement genuinely does not apply; explain why.

No overall PASS is allowed if any P0 or P1 requirement is CONFIRMED FAIL, PROBABLE FAIL, or NOT TESTED.

## Required Audit Outputs

Create a timestamped directory:

`reports/validation/end_to_end_system_validation_<timestamp>/`

At minimum produce:

1. `SYSTEM_VERDICT.md`
2. `pipeline_stage_map.csv`
3. `field_lineage_matrix.csv`
4. `artifact_contract_matrix.csv`
5. `compliance_and_gate_matrix.csv`
6. `feedback_loop_matrix.csv`
7. `module_reachability_matrix.csv`
8. `state_invalidation_matrix.csv`
9. `model_duration_and_coverage_matrix.csv`
10. `test_coverage_matrix.csv`
11. `failure_injection_results.csv`
12. `documentation_drift.md`
13. `residual_risk_register.md`
14. `COMMAND_LOG.md`
15. `EXECUTIVE_SUMMARY.md`

Preserve raw command outputs such as ffprobe JSON, FFmpeg logs, pytest logs, schema-validation output, and generated fixture reports.

---

# Phase 1 - Establish the Actual Runtime Architecture

Map the real production entry points and control flow. Do not rely solely on `PIPELINE.md`.

Trace:

- CLI argument parsing;
- project creation and path resolution;
- step ordering;
- function/module called by each step;
- input artifacts read;
- output artifacts written;
- state updates;
- gate checks;
- subprocess invocations;
- exception and return-value handling;
- resume and `--from-step` behavior;
- final Telegram-review preconditions.

Create `pipeline_stage_map.csv` with:

- stage order;
- stage ID/name;
- implementation function;
- source file and line;
- input artifacts;
- output artifacts;
- schemas used;
- required gates;
- failure behavior;
- state transition;
- downstream consumers;
- network/paid side-effect potential;
- whether reachable from the primary orchestrator;
- validation classification;
- evidence.

Identify duplicate, legacy, shadow, or competing implementations. Determine which implementation the actual orchestrator uses.

# Phase 2 - Complete Field Inventory and Data-Lineage Audit

This phase is mandatory and must be exhaustive.

Inventory every field used by every structured artifact involved in the production process, including nested fields and dynamically introduced fields.

Artifacts include, but are not limited to:

- research brief;
- script;
- creative storyboard;
- exact timing map;
- production storyboard;
- media plan;
- audio-slice/provenance records;
- graphics specifications and rendered-overlay manifest;
- generation job metadata;
- media QA report;
- duration reconciliation report;
- assembly manifest;
- assembly run metadata;
- final QA report;
- artifact fingerprint/dependency ledger;
- state file;
- gate ledger;
- quality report;
- Telegram review request metadata.

Use structured parsing or AST-aware inspection where possible. Do not depend only on regex. Search all reads and writes, including `.get()`, indexing, dataclass/model fields, schema definitions, dictionary construction, JSON serialization, and test fixtures.

Create `field_lineage_matrix.csv` with one row per fully qualified field path, for example:

`production_storyboard.beats[].coverage_plan[].required_duration_sec`

Columns must include:

- artifact/schema;
- field path;
- data type;
- required/optional/defaulted;
- authoritative source;
- producer module/function/line;
- transformations applied;
- validation rules;
- compliance rules;
- all consumer modules/functions/lines;
- passed to next artifact as which field;
- whether renamed;
- whether information is lost;
- whether default can mask absence;
- whether stale value is possible;
- whether covered by positive tests;
- whether covered by negative tests;
- runtime evidence;
- classification;
- findings.

For each field, answer:

1. Where is it first created?
2. Is its source authoritative or estimated?
3. Is it validated before use?
4. Is it transformed, rounded, clamped, split, merged, or defaulted?
5. Is the transformation legal and traceable?
6. Is it preserved through every required downstream artifact?
7. Does every consumer interpret its type, units, enum, and semantics consistently?
8. Can casing differences, missing keys, `None`, empty strings, zero, or fallback defaults change behavior incorrectly?
9. Is the field written but never consumed?
10. Is it consumed but never reliably produced?
11. Are there multiple fields claiming to be the same source of truth?
12. Can an LLM alter a mechanically authoritative field?
13. Does a schema require the field that runtime code depends upon?
14. Do tests verify the real handoff between producer and consumer?

Pay particular attention to:

- project IDs and paths;
- narration text and hashes;
- audio start/end/duration units;
- timing-map coverage;
- source/parent/child beat IDs;
- model identifiers and duration limits;
- shot types and asset types;
- audio policies;
- lipsync-required flags;
- slice hashes and parent hashes;
- reference-image hashes;
- graphics-required flags, layouts, text, and timing;
- music required/enabled/path/volume/ducking fields;
- generation status and job IDs;
- output paths and media hashes;
- QA statuses and severity enums;
- pass/fail aggregates;
- reconciliation deficits;
- manifest timeline fields;
- frame count and stream durations;
- artifact freshness/fingerprints;
- completed/failed/invalidated state;
- gate status and artifact hash;
- final quality verdict.

# Phase 3 - Artifact Contract Validation

Create `artifact_contract_matrix.csv` covering each artifact boundary.

For every producer/consumer pair verify:

- producer writes a complete artifact;
- schema matches actual runtime output;
- consumer reads the same schema version;
- required fields are not silently defaulted;
- units and enum values agree;
- paths resolve consistently;
- hashes refer to the actual bytes consumed;
- artifact is written atomically;
- stale or partially written artifact is rejected;
- incompatible versions fail loudly;
- downstream state records the exact artifact fingerprint.

Run schema validation against representative real and fixture artifacts. Inject missing, malformed, extra, wrong-type, wrong-unit, stale-version, and contradictory fields.

# Phase 4 - Compliance, Validation, and Outcome-Handling Audit

Inventory every function or module that returns:

- errors;
- warnings;
- validation lists;
- boolean pass/fail;
- status enums;
- severity levels;
- compliance findings;
- reviewer blocking issues;
- retry decisions;
- fallback decisions;
- gate outcomes;
- invalidation decisions.

Create `compliance_and_gate_matrix.csv` with:

- check ID;
- requirement;
- implementation function and line;
- inputs;
- possible outputs;
- severity;
- caller;
- exact caller behavior for every output;
- state effect;
- artifact effect;
- gate effect;
- downstream effect;
- positive test;
- negative test;
- failure-injection evidence;
- classification.

Verify mechanically that:

- every error causes a non-zero failure where required;
- warnings cannot accidentally become passes;
- lowercase/uppercase or enum mismatches cannot bypass failures;
- returned booleans are acted upon;
- exception paths cannot leave a completed state;
- a report cannot contain failed rows and an aggregate pass;
- a missing report fails closed;
- a stale report fails closed;
- an LLM reviewer cannot waive Python structural failures;
- human approval cannot approve stale or mismatched artifacts;
- Telegram review requires fresh passing gates and reports;
- emergency overrides are explicit, logged, scoped, and prohibited in production mode where required.

# Phase 5 - Feedback-Loop Audit

Create `feedback_loop_matrix.csv` for every intended loop:

- script critique and revision;
- creative storyboard critique and revision;
- post-TTS production-storyboard deterministic repair;
- targeted production-storyboard LLM repair;
- production-storyboard review;
- generation retry/fallback;
- media QA retry/regeneration;
- Engineer/Auditor/Validator remediation loops if they influence runtime artifacts;
- human budget approval;
- canary approval if present;
- final review rejection and resume path.

For each loop map:

- trigger;
- input artifact/version;
- feedback payload;
- recipient;
- allowed mutations;
- immutable fields;
- maximum iterations;
- pass condition;
- fail/escalation condition;
- state transition;
- artifact invalidation;
- transcript/log evidence;
- tests;
- runtime reachability.

Verify that feedback is actually fed back into the next iteration, not merely logged. Confirm that revised artifacts are revalidated and that stale review results cannot approve a new revision.

For LLM loops, verify:

- the right artifact and complete context are supplied;
- mandatory findings cannot be dropped;
- immutable narration/timing fields cannot be altered;
- outputs are parsed and structurally validated;
- malformed output fails safely;
- loop limits and human escalation work;
- reviewer and reviser do not accidentally read or write different artifact versions.

# Phase 6 - Module Completeness, Appropriateness, and Reachability

Create `module_reachability_matrix.csv` for all required modules and major helpers.

Determine whether each module is:

- implemented;
- appropriately scoped;
- reachable from the primary pipeline;
- called in the correct order;
- supplied with required inputs;
- producing consumed outputs;
- covered by tests;
- duplicated or superseded;
- bypassable;
- fail-open or fail-closed.

At minimum assess modules for:

- research;
- script generation;
- script review;
- creative storyboard generation;
- storyboard review;
- TTS;
- audio timing;
- post-TTS reconciliation;
- targeted storyboard repair;
- production-storyboard review;
- compliance validation;
- media-plan compilation;
- audio slicing;
- fingerprinting;
- budget/gates;
- media generation;
- job/download verification;
- graphics rendering;
- media QA;
- duration reconciliation;
- manifest construction;
- music preparation/mixing/verification;
- assembly;
- final stream integrity;
- final freeze/black detection;
- quality-report construction;
- state/resume/invalidation;
- Telegram review.

Flag modules that exist but are not wired, modules referenced by documentation but missing, and modules whose output is ignored.

# Phase 7 - Timing, Duration, and Coverage Proof

Create `model_duration_and_coverage_matrix.csv`.

Verify the complete timing chain:

1. provisional duration estimates are calibrated and explicitly non-authoritative;
2. final TTS master is immutable and authoritative;
3. exact timing map starts at zero and ends at master duration;
4. no audio gap or overlap exists;
5. post-TTS production storyboard uses exact timing;
6. narration text is preserved through splitting;
7. model assignments fit configured duration limits;
8. audio is never truncated to meet model limits;
9. split boundaries are legal sentence/silence boundaries;
10. every audio interval has explicit visual coverage;
11. graphics count as coverage only when rendered assets exist;
12. generated clips count only when probed and fresh;
13. no implicit freeze, loop, placeholder, or audio-only gap satisfies coverage;
14. manifest timeline equals authoritative narration timeline;
15. assembled visual bed is probed before audio mux;
16. final video/audio/container durations meet tolerance;
17. lipsync placement targets one-frame accuracy;
18. final emergency tolerance does not mask beat-level drift.

Use the original defective project as a negative control. It must fail at the earliest appropriate gates without regenerating paid assets.

# Phase 8 - Music and Graphics End-to-End Validation

Verify music lineage:

- requirement source;
- required versus optional semantics;
- config propagation;
- path and fingerprint;
- duration coverage;
- looping policy;
- gain units;
- ducking instructions;
- mix filter behavior;
- loudness normalization interaction;
- post-mix measurable evidence;
- run metadata;
- final quality-report status.

Verify graphics lineage:

- storyboard requirement;
- preservation through production-storyboard splits;
- graphics specification;
- supported layout;
- deterministic asset construction;
- font/palette/safe-area checks;
- exact timing;
- manifest inclusion;
- assembly compositing;
- sampled-frame verification;
- required/rendered/composited count equality;
- final quality-report status.

Test unknown layouts, missing fonts, blank transparent output, off-timeline overlays, missing required assets, and generated pseudo-text used as a substitute.

# Phase 9 - State, Resume, Freshness, and Dependency Invalidation

Create `state_invalidation_matrix.csv`.

For every upstream artifact mutation, record all expected invalidated downstream stages and artifacts. Test at minimum:

- research change;
- script change;
- creative storyboard change;
- master TTS byte change;
- timing-map change;
- production-storyboard change;
- graphics change;
- media-plan change;
- audio-slice change;
- generated-media change;
- media-QA change;
- manifest change;
- music file/config change;
- assembly output change;
- final-QA report change.

Verify:

- `--resume` finds the first genuinely valid incomplete step;
- `--from-step` invalidates that step and all dependent outputs;
- failed reruns cannot retain old pass status;
- duplicate completed-step entries are impossible;
- gate artifacts are bound to current hashes;
- copied artifacts from another project cannot pass;
- mtime alone is never freshness proof;
- interrupted atomic writes do not become valid artifacts;
- schema/producer-version changes invalidate incompatible artifacts.

# Phase 10 - Failure-Injection and Local End-to-End Tests

Build an audit-only local fixture pipeline using production entry points and tiny FFmpeg-generated assets. Do not duplicate production logic in the test harness.

Create `failure_injection_results.csv` and test at minimum:

- valid full pipeline fixture;
- missing narration;
- changed narration hash;
- timing gap;
- timing overlap;
- narration mutation during storyboard repair;
- beat over model duration;
- no legal split boundary;
- missing visual coverage;
- short visual/long audio;
- long visual/short audio;
- silent lipsync clip;
- mismatched lipsync audio hash;
- audio-bearing b-roll when forbidden;
- missing generated clip;
- zero-byte clip;
- partial/corrupt clip;
- stale clip from another project;
- wrong resolution;
- frozen clip;
- black clip;
- missing required graphic;
- unsupported graphic layout;
- blank graphic;
- missing required music;
- inaudible post-mix music;
- missing QA report;
- QA row fail with aggregate pass;
- stale QA report;
- stale manifest;
- final video/audio mismatch;
- container/video mismatch;
- missing/zero frame count;
- terminal freeze;
- stale final quality report;
- attempted Telegram review without fresh PASS.

For every injected failure record:

- injection method;
- expected first failing stage;
- actual first failing stage;
- exit code;
- error message;
- state after failure;
- downstream artifacts created or blocked;
- classification.

The valid fixture must pass all stages without network access. Every invalid fixture must fail at the earliest responsible gate.

# Phase 11 - Test-Suite Quality and Coverage Audit

Create `test_coverage_matrix.csv` mapping each system guarantee to tests.

Assess:

- whether tests call production entry points;
- whether assertions verify behavior rather than source-code strings;
- whether mocks preserve realistic contracts;
- whether positive and negative paths exist;
- whether integration boundaries are tested;
- whether tests prove correct state and artifact side effects;
- whether old failure modes have regression fixtures;
- whether tests can pass while the production path remains broken;
- whether paid/network calls are reliably blocked in CI;
- whether flaky timing tolerances are justified.

Run the complete supported test suite and relevant static checks. Record skipped, xfailed, flaky, or environment-dependent tests. A green suite is evidence only when mapped to guarantees.

# Phase 12 - Documentation and Operational Truth

Create `documentation_drift.md` comparing documentation against actual behavior.

Check:

- stage order;
- artifact names and locations;
- required fields;
- hard-fail claims;
- model duration limits;
- music behavior;
- graphics behavior;
- state/resume semantics;
- gate order;
- manual commands;
- final review prerequisites;
- audit/report locations.

Classify each mismatch as documentation defect, implementation defect, or both.

# Phase 13 - Additional System Checks

Add any relevant checks discovered during the audit. At minimum consider:

- path traversal and unsafe project IDs;
- shell/subprocess argument safety;
- secrets accidentally logged or serialized;
- atomicity and concurrency hazards;
- two concurrent runs writing the same global media paths;
- deterministic ordering and JSON canonicalization;
- timezone and timestamp consistency;
- rounding accumulation and frame-boundary drift;
- disk-space and partial-write handling;
- FFmpeg return-code handling;
- unsupported codec/container behavior;
- version pinning for schemas/config/models;
- reproducibility of local graphics;
- cost calculation consistency after beat splitting;
- budget reapproval after post-TTS restructuring;
- human-gate binding to exact artifact versions;
- observability and actionable error reporting;
- archival/cleanup behavior that might remove live dependencies.

# Phase 14 - Final Verdict

Create `SYSTEM_VERDICT.md` containing:

1. overall verdict: PASS, CONDITIONAL PASS, or FAIL;
2. exact evidence supporting the verdict;
3. P0/P1/P2 findings ordered by severity;
4. whether the original defective artifact is now blocked, and where;
5. whether a valid local fixture completes end to end;
6. whether every structured field has proven lineage;
7. whether all compliance outputs are acted upon correctly;
8. whether all feedback loops are reachable and effective;
9. whether every required module exists and is wired;
10. whether narration preservation and visual coverage are mechanically guaranteed;
11. whether music and graphics are guaranteed when required;
12. whether resume and freshness behavior are correct;
13. residual NOT TESTED areas;
14. a prioritized remediation list, but no implementation.

Create `EXECUTIVE_SUMMARY.md` in plain language for the repository owner. Explain what is safe, what remains unsafe, and whether production use should resume.

Create `residual_risk_register.md` with:

- risk;
- severity;
- likelihood;
- evidence;
- current control;
- control weakness;
- recommended action;
- owner/module;
- production-blocking status.

## Overall Pass Criteria

An overall PASS requires all of the following:

1. Every runtime stage and artifact boundary is mapped.
2. Every used structured field has a valid producer, validator, consumer, and downstream lineage.
3. No required field is silently lost, renamed inconsistently, defaulted unsafely, or written without use.
4. Every compliance/error/pass/fail output is handled correctly and fails closed.
5. Every feedback loop passes revised artifacts back through validation and freshness checks.
6. Every documented required module exists, is appropriate, reachable, and used.
7. Final narration is immutable and never truncated.
8. Post-TTS production storyboard exactly covers the authoritative audio timeline.
9. All visual assignments fit model limits and provide complete coverage.
10. Lipsync provenance and timing are verified end to end.
11. Required graphics and music are rendered, mixed, measured, and reported.
12. State/resume invalidates every stale dependency correctly.
13. The original defective project fails before paid generation or final review at the appropriate gates.
14. A valid local fixture completes end to end.
15. Every required failure injection fails at the earliest responsible gate.
16. Full tests and static checks pass, with no unexplained skips affecting critical guarantees.
17. Telegram review is unreachable without a fresh, complete, passing quality report.

If any criterion is not proven, do not issue an unconditional PASS.

## Execution Approach

Use subagents where useful, but maintain independent evidence and avoid splitting tightly coupled lineage work across agents without a final integration pass. Suggested read-only roles:

- **Schema and Field-Lineage Auditor**
- **Control-Flow and Compliance Auditor**
- **Feedback-Loop and State Auditor**
- **Media/FFmpeg Validator**
- **Test and Failure-Injection Validator**
- **Documentation and Operations Auditor**

All subagent findings must be reconciled by the principal agent. Conflicts must be resolved through direct evidence.

Begin by checking that both remediation sprints report completion, inspecting `git status`, creating the timestamped validation directory, and writing an initial audit checklist. Then map the real orchestrator path before running tests or declaring any result.
