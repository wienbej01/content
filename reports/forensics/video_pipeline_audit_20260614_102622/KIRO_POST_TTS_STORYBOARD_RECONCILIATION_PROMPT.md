# Kiro Follow-On Prompt: Post-TTS Production Storyboard Reconciliation

You are Claude 4.6 operating through `kiro-cli` as Principal Implementation Orchestrator for:

`/home/jacobw/YTchannel`

The existing forensic remediation sprint must be completed first. This is a separate follow-on enhancement. Do not reopen or weaken completed sprint guarantees.

## Objective

Add a post-TTS production-storyboard stage so the approved creative storyboard is reconciled against the exact final narration before media generation.

The system must guarantee:

1. Approved narration is never shortened, truncated, omitted, overlapped, or silently rewritten.
2. Every narration interval has complete planned visual coverage.
3. No generated-video or lipsync assignment exceeds the selected model's duration limit.
4. Video cannot be extended with unintended frozen frames, long `tpad`, implicit loops, or placeholders.
5. The media plan, budget, generation, QA, manifest, and assembly use only the post-TTS production storyboard.

## Read First

Read completely:

- `AGENTS.md`
- `docs/PIPELINE.md`
- `video_forensic_audit_report.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/final_video_forensics.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/root_cause_matrix.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/duration_reconciliation.csv`
- `reports/forensics/video_pipeline_audit_20260614_102622/SPRINT_VIDEO_PIPELINE_FORENSIC_REMEDIATION.md`
- `reports/remediation/SPRINT_STATUS.md`
- `reports/remediation/FINAL_IMPLEMENTATION_REPORT.md`, if present

Then inspect the current implementation and tests for:

- `scripts/produce.py`
- `scripts/direct_storyboard.py`
- `scripts/storyboard.py`
- `scripts/audio_timing.py`
- `scripts/tts.py`
- `scripts/compile_media_prompts.py`
- `scripts/slice_continuous_lipsync.py`
- `scripts/generate_media.py`
- `scripts/qa_media.py`
- manifest-building code
- `scripts/assemble.py`
- graphics rendering code
- state, fingerprint, reconciliation, and quality-report modules added by the completed sprint
- relevant schemas, model routing, constraints, reviewer prompts, and tests

Documentation is not proof. Confirm the current runtime path before editing.

## Constraints

- Do not call paid APIs.
- Do not regenerate ElevenLabs audio.
- Do not generate Higgsfield, Seedance, Kling, or other paid media.
- Use deterministic local fixtures, FFmpeg, mocks, and recorded JSON.
- Do not modify the narration text during production reconciliation.
- Do not add silent fallbacks.
- Do not use arbitrary audio truncation, `-shortest`, long frame holds, looping, or placeholder clips to satisfy coverage.
- Do not revert unrelated worktree changes.

## Required Architecture

Implement two distinct storyboard artifacts:

### Creative Storyboard

Created before TTS and reviewed for:

- narrative treatment,
- visual concepts,
- shot types,
- graphics and overlays,
- continuity,
- provisional pacing,
- estimated cost.

This remains the creative source of intent.

### Production Storyboard

Created after final TTS and exact timing-map generation. Suggested filename:

`production_storyboard.json`

It must contain exact, measured timing for every beat:

```json
{
  "beat_id": "B008a",
  "source_beat_id": "B008",
  "audio_start_sec": 86.627,
  "audio_end_sec": 96.200,
  "audio_duration_sec": 9.573,
  "narration_text": "Exact unchanged narration text",
  "treatment": "hero_lipsync",
  "model": "seedance_2_0",
  "model_max_duration_sec": 10.0,
  "coverage_plan": [
    {
      "asset_role": "primary",
      "asset_type": "generated_video",
      "required_start_sec": 86.627,
      "required_end_sec": 96.200,
      "required_duration_sec": 9.573
    }
  ]
}
```

The production storyboard must preserve traceability to the original creative beat and approved narration.

## Reconciliation Strategy

Use deterministic Python rules before involving an LLM.

### Deterministic Pass

For each creative beat:

1. Map its exact narration text to the authoritative timing map.
2. Attach measured audio start, end, and duration.
3. Compare duration with model and treatment limits.
4. Preserve the beat unchanged if it fits and coverage is valid.
5. Split over-limit narration only at validated sentence or silence boundaries.
6. Never split inside a spoken word.
7. Never discard words or shorten the source audio.
8. Reject ambiguous text-to-audio mapping instead of guessing.

The deterministic pass should resolve mechanical cases such as splitting a 19-second B-roll interval into four or more bounded visual slots.

### Targeted LLM Repair Pass

Invoke the storyboard LLM only for unresolved creative decisions, such as:

- choosing visual treatments for newly split intervals,
- converting part of an overlong hero passage into B-roll or local graphics,
- maintaining visual continuity across new cuts,
- selecting appropriate transitions,
- preserving required citations, overlays, and narrative emphasis.

Do not regenerate the whole storyboard from scratch. Provide the LLM with:

- the approved creative storyboard,
- exact narration text and timing,
- only the beats requiring repair,
- model duration limits,
- shot-mix constraints,
- graphics requirements,
- previous and next beat context,
- explicit immutable fields.

The LLM must not alter:

- narration text,
- source citations,
- audio start/end boundaries except selecting from supplied legal split points,
- approved factual meaning,
- project identity,
- required graphics or overlays.

All LLM output must be structurally and semantically validated by Python.

## Hard Invariants

Enforce these mechanically:

```text
production timeline starts at 0
production timeline ends at master audio duration
every audio sample is covered exactly once
no audio gaps
no audio overlaps
narration text is byte-for-byte or canonically equivalent to the approved script
all split children concatenate to the exact parent narration text
all split children concatenate to the exact parent audio interval
hero lipsync duration <= configured model maximum
generated clip target duration <= configured model maximum
every beat has one or more explicit visual coverage assignments
combined visual coverage spans the complete beat interval
no implicit freeze, loop, placeholder, or audio-only gap
required graphics and overlays survive every split
all source_beat_id relationships are present
```

Use frame-aware timing. At 24 fps, target timeline-boundary accuracy should be one frame, approximately `0.0417s`. A `0.25s` tolerance is only an outer emergency gate, not the normal alignment target.

## Pipeline Integration

Update the orchestrator to use this order:

```text
research
script_create
script_review_loop
creative_storyboard_create
creative_storyboard_review_loop
tts
build_exact_timing_map
production_storyboard_reconcile
production_storyboard_review
compliance_check
compile_media_plan
render_graphics
budget_gate
generate_media
media_qa
duration_reconciliation
manifest_build
assembly
final_stream_integrity
quality_report
Telegram review
```

The precise names may follow existing conventions, but responsibilities must remain distinct.

Changing the master TTS or timing map must invalidate:

- production storyboard,
- production-storyboard review,
- media plan,
- audio slices,
- graphics,
- budget approval,
- generated media unless fingerprints still prove exact compatibility,
- media QA,
- duration reconciliation,
- manifest,
- assembly,
- final QA,
- quality report,
- Telegram review.

## Production Storyboard Review

Add a focused review step after reconciliation. It should not re-review the entire creative concept unless reconciliation materially changed it.

Review and validate:

- complete audio coverage,
- legal model durations,
- sensible visual changes at split boundaries,
- continuity,
- shot variety,
- hero lipsync proportion,
- graphics and citation preservation,
- no text-heavy content delegated to generative video,
- cost implications,
- no narration changes.

Python owns structural acceptance. An LLM or human reviewer may assess creative quality but cannot waive structural failures.

## Subagent Process

Retain the Engineer, Auditor, and Validator workflow. Implement one ticket at a time.

### Engineer Agent

- May edit production code and tests.
- Implements exactly one ticket.
- Uses no paid or network operations.
- Adds positive and negative tests.
- Writes `reports/remediation/post_tts_storyboard/TKT-XX/implementation_report.md`.

### Auditor Agent

- Read-only for production code.
- Reviews the complete ticket diff and runtime path.
- Checks narration immutability, timeline completeness, legal splits, fail-loud behavior, fingerprints, and downstream invalidation.
- Looks for hidden truncation, approximate text matching, LLM overreach, warning-only errors, or bypasses.
- Writes `reports/remediation/post_tts_storyboard/TKT-XX/audit_report.md`.
- Returns PASS or REVISE with exact file and line references.

### Validator Agent

- Runs tests and local fixture commands.
- Does not edit production code.
- Independently verifies exact timing and failure behavior.
- Writes `reports/remediation/post_tts_storyboard/TKT-XX/validation_report.md`.
- Returns PASS or FAIL with command evidence.

For each ticket: Engineer -> focused tests -> Auditor -> revision if needed -> Validator. Do not start the next ticket until Auditor and Validator both pass. Allow at most two revision cycles before reporting a blocker.

## Ticket Plan

### PST-01 - Define Production Storyboard Schema and Invariants

Create a versioned schema containing source-beat traceability, exact audio timing, legal split points, treatment/model limits, and explicit visual coverage assignments.

Acceptance criteria:

- schema rejects gaps, missing provenance, missing coverage, and illegal model durations;
- narration identity and split-parent relationships are represented;
- schema has no optional path that permits audio-only coverage.

### PST-02 - Calibrated Pre-TTS Duration Estimates

Use measured approved-voice pacing data to improve provisional creative-storyboard estimates. Support overall and block-type rates where evidence exists.

Acceptance criteria:

- estimates use repository calibration data, not an unexplained constant;
- estimate confidence/error is recorded;
- estimates are explicitly non-authoritative and never replace measured TTS duration.

### PST-03 - Deterministic Post-TTS Reconciliation Engine

Build the exact timing attachment, legal split-point generation, mechanical splitting, and immutable-text validation.

Acceptance criteria:

- overlong beats split without dropping or duplicating narration;
- no split occurs inside a word;
- all output intervals cover the master exactly once;
- ambiguous mappings fail with actionable context.

### PST-04 - Targeted Storyboard LLM Repair

Add a narrowly scoped LLM repair interface for unresolved visual-treatment decisions. Tests must mock the LLM.

Acceptance criteria:

- only named problematic beats are sent;
- immutable fields are rejected if changed;
- illegal model durations or omitted graphics fail validation;
- no whole-storyboard regeneration occurs.

### PST-05 - Production Storyboard Review Gate

Add deterministic validation plus focused creative review. Structural failures cannot be overridden.

Acceptance criteria:

- review report distinguishes structural failures from creative recommendations;
- required graphics, citations, and overlays survive splits;
- narration mutation is always fatal.

### PST-06 - Downstream Production Storyboard Adoption

Make media-plan compilation and all downstream stages consume only the production storyboard. Reject a creative storyboard supplied to production entry points.

Acceptance criteria:

- model requests derive from exact production intervals;
- budget reflects split asset count;
- every media-plan beat traces to production and creative beat IDs.

### PST-07 - State and Fingerprint Invalidation

Wire the new artifacts into the completed sprint's dependency DAG and fingerprint system.

Acceptance criteria:

- changing TTS or timing invalidates all listed downstream artifacts;
- changing only an unrelated creative annotation does not invalidate compatible media unless defined as a dependency;
- stale production storyboards cannot resume.

### PST-08 - Local End-to-End Alignment Tests

Create local fixtures covering:

- a beat fitting one lipsync clip,
- a 23-second hero beat requiring split/reroute,
- a 19-second B-roll passage requiring multiple visuals,
- a sub-minimum lipsync beat requiring silence padding,
- no legal silence split,
- attempted narration mutation,
- missing visual coverage,
- required graphics across split children,
- timing-map change during resume.

Acceptance criteria:

- valid fixtures align within one frame;
- invalid fixtures fail before media generation;
- no fixture uses paid APIs.

## Required Proof on the Audited Project

Run the new reconciliation in analysis/dry-run mode against:

`Videos/Projects/using_ai_to_help_memory_retention_short`

Do not regenerate audio or media.

The report must identify at least:

- B001 as exceeding available visual/lipsync coverage,
- B003 and B005 as needing multiple visual assignments,
- B007 as under-covered,
- B008 and B009 as exceeding Seedance limits substantially,
- B010 as exceeding the configured limit or available clip coverage,
- all six required graphics as preserved requirements.

Write the proposed corrected artifact to a report/preview location, not over the existing production storyboard:

`reports/remediation/post_tts_storyboard/audited_project_preview/production_storyboard.preview.json`

Also write:

- `reconciliation_preview.md`
- `duration_coverage_preview.csv`

## Validation Commands

Run focused tests after every ticket and the full suite at major checkpoints:

```bash
python3 -m pytest -q
```

Run schema validation, reconciliation dry runs, state invalidation tests, and local FFmpeg fixture probes. Record exact commands and outputs in ticket validation reports.

## Final Deliverables

Produce:

- `reports/remediation/post_tts_storyboard/SPRINT_STATUS.md`
- per-ticket implementation, audit, and validation reports,
- `reports/remediation/post_tts_storyboard/FINAL_REPORT.md`
- audited-project preview production storyboard,
- audited-project preview coverage CSV,
- updated pipeline documentation after implementation is verified,
- full test summary and remaining risks.

## Definition of Done

This enhancement is complete only when:

1. Final TTS duration is the authoritative production timeline.
2. Narration cannot be cut, omitted, duplicated, overlapped, or silently rewritten.
3. Every beat is reconciled to exact audio timing.
4. Every model assignment fits configured limits.
5. Every audio interval has explicit complete visual coverage.
6. Required graphics and overlays survive reconciliation and are rendered downstream.
7. No long freeze, implicit loop, placeholder, or audio-only gap can satisfy coverage.
8. Downstream production rejects an unreconciled creative storyboard.
9. Resume/fingerprint logic invalidates stale reconciliations and dependent artifacts.
10. Local end-to-end tests prove valid alignment within one frame and reject all broken cases before paid generation.

Begin by confirming that the original forensic remediation sprint is complete and its tests pass. Then create the follow-on status file and execute `PST-01` only.
