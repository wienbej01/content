# AI Influencer YouTube Production System
## Lipsync Integrity, Hero/B-Roll Audio Architecture, and B-Roll Quality Engineering Sprint Plan

**Status:** Implementation-ready  
**Scope:** Coding remediation and validation plan  
**Primary implementation model:** Software Engineer → Software Auditor → Software Validator  
**Purpose:** Correct structural lipsync failures, protect synchronized hero footage from unsafe temporal editing, establish one authoritative narration timeline, improve B-roll usefulness and diversity, and eliminate generated gibberish text through deterministic routing and compositing.

---

# 1. How to Use This Plan

This plan is designed for implementation by lower-capability coding models. Each ticket is intentionally explicit and bounded.

For every ticket:

1. The **Software Engineer** reads the relevant documentation and code, implements only the ticket scope, adds tests, and produces an evidence report.
2. The **Software Auditor** independently reviews the implementation and runs prescribed and adversarial tests. The auditor does not write production code.
3. The **Software Validator** independently validates the completed sprint from a clean checkout and clean test database. The validator does not write production code.
4. Failed audit or validation findings return to the Software Engineer for remediation.
5. A sprint remains blocked until both the auditor and validator pass it.

Audit and validation are governance roles for the **coding process**. They are not stages or agents in the video-production workflow.

Automated lipsync checks, B-roll relevance checks, visual duplicate checks, text-policy checks, and media-quality checks are runtime software features implemented by the Software Engineer.

---

# 2. Required Context for Implementers

Before starting Sprint 0, all agents must read the following files if present:

1. `YT_AI_INFLUENCER_SYSTEM_CONTEXT_AND_TARGET_SPEC.md`
2. `YT_AI_INFLUENCER_SPRINT_PLAN.md`
3. `DB_ALIGNMENT_CUTOVER_SPRINT_PLAN.md`
4. `PRODUCTION_DATA_FLOW_MAP.md`
5. `PIPELINE.md`
6. `CLIP_DB_DESIGN.md`
7. `HARMONIZED_CLIP_FINGERPRINTS.md`
8. `ENHANCED_DATABASE_SYSTEM_SUMMARY.md`
9. `SUBSECOND_DURATION_MISMATCH_SOLUTION_REPORT.md`
10. storyboard, prompt, reviewer, provider-routing, media-QA, and assembly documentation
11. channel technical bible and brand specification

The implementer must verify code rather than assume the documentation is accurate.

Where the current repository differs from this plan, the agent must report:

```text
BLOCKED: repository contract differs from plan
Expected: <expected contract>
Observed: <actual contract>
Affected ticket: <ticket ID>
Required decision: <specific architecture decision>
```

No agent may silently adapt the architecture.

---

# 3. Engineering Position

## 3.1 One master narration is authoritative

The continuous ElevenLabs narration artifact must be the only authoritative narration used in the final video.

Hero render units may receive exact audio slices from the master narration as Seedance conditioning. Seedance-returned audio must be retained only as diagnostic evidence and must not be used as final narration.

B-roll normally contributes picture only. The master narration continues uninterrupted underneath hero footage, B-roll, graphics, screen captures, and archival media.

## 3.2 Hero video is temporally locked

Approved hero footage with visible speech must not be:

- sped up;
- slowed down;
- looped;
- reversed;
- frame-interpolated;
- freeze-extended;
- retimed with non-identity `setpts`;
- trimmed through active speech;
- independently shifted relative to its assigned master-audio interval.

The system may apply non-temporal operations:

- crop;
- scale;
- position;
- pad;
- grade;
- denoise;
- sharpen;
- subtitle;
- graphic overlay;
- hard cut at an approved boundary;
- B-roll cutaway over the hero picture.

The precise rule is:

> No temporal transformation of an approved `HERO_SYNC_LOCKED` render unit.

## 3.3 Hero-to-B-roll narration continuity does not normally require one generated render

The narration timeline is continuous. The picture timeline may cut from hero to B-roll and back.

One continuous Seedance hero render may cover a short B-roll cutaway when:

- the full render group fits the provider duration limit;
- James appears immediately before and after the cutaway;
- pose and gesture continuity are valuable;
- the scene and camera remain consistent.

Otherwise, separate hero render units must use clean, non-overlapping audio intervals.

## 3.4 B-roll must communicate information

Every B-roll beat must declare its purpose:

- `demonstration`;
- `evidence`;
- `mechanism`;
- `contrast`;
- `consequence`;
- `metaphor`;
- `context`.

Generic “professional at laptop” footage is not acceptable unless the beat is explicitly classified as context and the sequence-level context quota permits it.

## 3.5 Generated meaningful text is prohibited

The system must not depend on Seedance or another video generator to produce readable, stable text on:

- notebooks;
- books;
- laptop screens;
- phones;
- whiteboards;
- charts;
- signs;
- presentation slides.

Text-heavy visuals must be routed to:

- deterministic graphics;
- real screen capture;
- post-composited UI/text;
- deliberately unreadable background surfaces;
- visuals with no visible text.

---

# 4. Agent Roles

## 4.1 Software Engineer

The Software Engineer has read/write access to ticket-approved code, tests, migrations, and documentation.

Specialization may vary by ticket:

- core pipeline engineer;
- database engineer;
- audio/lipsync engineer;
- FFmpeg/video engineer;
- storyboard/prompt engineer;
- media-QA engineer.

The specialization does not create a separate governance role. It remains the implementing Software Engineer.

### Responsibilities

- inspect the current implementation;
- implement the exact ticket;
- add and run specified tests;
- produce evidence;
- avoid unrelated refactors;
- fail loudly on missing contracts;
- never approve the engineer’s own ticket.

## 4.2 Software Auditor

The Software Auditor has read and test-execution access only.

### Responsibilities

- inspect the changed code and migration;
- verify the ticket scope;
- search for unsafe fallbacks;
- run prescribed tests;
- design adversarial tests;
- inspect generated commands and artifacts;
- issue findings with severity and exact reproduction;
- pass or fail the ticket.

The auditor must not modify production code.

## 4.3 Software Validator

The Software Validator has read and test-execution access only and operates after the sprint’s tickets have passed audit.

### Responsibilities

- validate from a clean checkout;
- use a clean database and deterministic fixtures;
- run the sprint-level exit suite;
- test integration across tickets;
- inspect evidence and reports;
- verify rollback readiness;
- pass or block the sprint.

The validator must not modify production code.

---

# 5. Required Evidence and Finding Formats

## 5.1 Engineer evidence report

Every ticket must produce:

```text
reports/remediation/lipsync_broll/<TICKET-ID>/engineer_report.md
```

The report must include:

- files read;
- files changed;
- implementation summary;
- schema changes;
- tests added;
- exact commands executed;
- test results;
- sample diagnostic output;
- assumptions;
- known limitations;
- rollback steps;
- git diff summary;
- commit SHA, if committed.

## 5.2 Auditor report

Every ticket must produce:

```text
reports/remediation/lipsync_broll/<TICKET-ID>/auditor_report.md
```

Each finding must use:

```text
Finding ID:
Severity: BLOCKER | HIGH | MEDIUM | LOW
Ticket:
File/line:
Reproduction command:
Expected:
Actual:
Evidence:
Required remediation:
Required retest:
Status: OPEN | RESOLVED
```

## 5.3 Validator report

Every sprint must produce:

```text
reports/remediation/lipsync_broll/SPRINT-<N>/validator_report.md
```

The report must include:

- clean environment used;
- database initialization;
- fixtures used;
- commands executed;
- test results;
- invariant checks;
- artifact inspection;
- unresolved risks;
- verdict: `PASS` or `BLOCKED: <reason>`.

---

# 6. Global Non-Negotiable Invariants

## Audio invariants

1. One immutable master narration artifact is authoritative.
2. The final video contains the master narration exactly once.
3. Hero provider-returned audio is diagnostic-only.
4. B-roll provider audio is discarded unless explicitly classified as ambience or sound effect.
5. Hero speech slices never contain neighbouring speech.
6. Padding uses generated silence or approved room tone containing no speech.
7. One canonical timebase is used across TTS, slicing, rendering, QA, and assembly.
8. No module independently rounds hero speech intervals.

## Hero invariants

1. Hero render units use `HERO_SYNC_LOCKED`.
2. No temporal transform is permitted after hero approval.
3. Any trim during active speech is forbidden.
4. B-roll may replace the hero picture while master narration continues.
5. Returning to hero requires an approved visible interval.
6. Safe edit boundaries are evidence-backed, not assumed.

## B-roll invariants

1. Every B-roll beat has a visual function.
2. Every B-roll beat states what information it communicates.
3. Sequence-level duplicate concepts are rejected.
4. Generic laptop/notebook imagery is quota-limited and never the default.
5. Text policy is mandatory.
6. Meaningful readable text is routed away from generative video.
7. B-roll relevance is validated against the narration claim.
8. B-roll is not accepted merely because the file is technically valid.

## Database invariants

1. All new policies and evidence are stored in the production database.
2. JSON reports are exports, not execution authority.
3. Render units use canonical IDs, not display labels.
4. Artifact SHA and provenance are mandatory.
5. Reuse requires exact semantic input fingerprints.
6. A changed master audio, slice, prompt, model, or plan invalidates dependent assets.
7. Runtime validation evidence is versioned and tied to exact artifacts.

---

# 7. Sprint and Dependency Map

## Critical path

```text
Sprint 0: truth baseline and safety freeze
    |
Sprint 1: policy/schema foundation
    |
Sprint 2: master narration and canonical timebase
    |
Sprint 3: clean hero slicing and render grouping
    |
Sprint 4: Seedance provider contract
    |
Sprint 5: locked hero assembly
    |
Sprint 6: lipsync QA and repair
    |
Sprint 10: integrated cutover and proof
```

## Parallel B-roll path

```text
Sprint 0
    |
Sprint 7: storyboard semantic contract
    |
Sprint 8: prompt compiler and diversity
    |              \
Sprint 9A: text-safe compositing
    |              /
Sprint 9B: B-roll runtime QA
    |
Sprint 10: integrated cutover and proof
```

Sprint 10 cannot begin until both the hero/lipsync path and the B-roll path have passed validation.

---

# 8. Sprint 0 — Current-State Audit and Safety Freeze

## Sprint goal

Reproduce the current failure, map the actual code path, and prevent further unsafe temporal editing while the remediation is built.

## Ticket LB-000 — Trace the live audio and hero-video path

**Primary implementer:** Software Engineer  
**Implementation specialization:** Core/audio pipeline  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** None  
**Priority:** BLOCKER

### Objective

Produce an evidence-backed map from script revision to ElevenLabs output, hero slice, Seedance request, generated clip, assembly command, and final soundtrack.

### Files to inspect

At minimum, if present:

- `scripts/tts.py`;
- `scripts/audio_timing.py`;
- `scripts/slice_continuous_lipsync.py`;
- `scripts/compile_media_prompts.py`;
- `scripts/generate_media.py`;
- provider adapters;
- `scripts/qa_media.py`;
- `scripts/reconcile_duration.py`;
- `scripts/build_manifest.py`;
- `scripts/assemble.py`;
- database/repository services;
- current tests;
- artifacts for B001 and B008a–B008c.

### Allowed changes

- diagnostics;
- reports;
- test-only probes;
- no behavior changes except instrumentation.

### Implementation steps

1. Trace the actual production entry point.
2. Identify the master narration file and database record.
3. Record source sample or millisecond boundaries for B001 and B008a–B008c.
4. Record all padding logic.
5. Identify whether padding includes neighbouring speech.
6. Record provider request duration and audio path.
7. Probe returned video and audio streams.
8. Capture FFmpeg assembly commands.
9. Identify all temporal filters.
10. Identify which audio reaches the final video.
11. Compare planned speech duration, source slice duration, provider output duration, and assembly trim duration.
12. Document every divergence.

### Tests

Create:

```text
tests/integration/test_lipsync_current_failure_reproduction.py
```

Suggested tests:

- `test_b001_slice_contains_next_beat_speech_current_state`
- `test_b008_chain_has_overlapping_speech_current_state`
- `test_assembly_uses_provider_audio_current_state`
- `test_hero_trim_uses_planned_speech_len_current_state`

These tests may initially be marked expected-failure with explicit reason. They must not remain expected-failure after remediation.

### Acceptance criteria

- the root cause is reproduced;
- every relevant audio artifact is identified;
- every trim and retime operation is identified;
- the final audio source is proven;
- the report distinguishes documented behavior from actual behavior.

### Auditor checklist

- reproduce using the engineer’s commands;
- verify no relevant path is omitted;
- inspect FFmpeg commands independently;
- verify B001 and B008 evidence.

### Validator pass gate

The validator can independently reproduce the failure from the supplied fixture or audited project.

### BLOCKED conditions

- production artifacts unavailable;
- provider request logs unavailable;
- runtime path cannot be identified;
- current code differs materially from documentation.

---

## Ticket LB-001 — Add temporary hero temporal-edit fail-closed guard

**Primary implementer:** Software Engineer  
**Implementation specialization:** FFmpeg/assembly  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-000  
**Priority:** BLOCKER

### Objective

Prevent new hero clips from being silently retimed, looped, freeze-extended, or trimmed through active speech.

### Required behavior

For hero clips, fail closed on:

- non-identity `setpts`;
- speed changes;
- frame interpolation;
- loop;
- reverse;
- freeze extension;
- audio `atempo`;
- arbitrary trim through speech;
- provider-audio concatenation.

### Required error format

```text
BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN
render_unit_id=<id>
operation=<operation>
source=<file/function>
```

### Tests

Create:

```text
tests/unit/test_hero_temporal_edit_guard.py
```

Tests:

- `test_rejects_hero_speed_change`
- `test_rejects_hero_freeze_extension`
- `test_rejects_hero_loop`
- `test_rejects_hero_frame_interpolation`
- `test_rejects_trim_inside_active_speech`
- `test_allows_crop_scale_and_overlay`

### Acceptance criteria

No production run can apply forbidden temporal edits to a hero clip without a hard error.

### Rollback

A feature flag may allow legacy behavior only for archived proof projects. The default must remain fail-closed.

---

## Sprint 0 Exit Gate

The sprint passes only when:

- the current failure is reproducible;
- B001 and B008 chain evidence exists;
- unsafe hero temporal edits are blocked;
- auditor passes both tickets;
- validator independently reproduces the defect and verifies the guard.

---

# 9. Sprint 1 — Audio and Text Policy Schema

## Sprint goal

Make hero, B-roll, audio, and generated-text behavior explicit and database-enforced.

## Ticket LB-100 — Add audio-policy enum and constraints

**Primary implementer:** Software Engineer  
**Implementation specialization:** Database/repository  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 0

### Required values

- `HERO_SYNC_LOCKED`
- `BROLL_FLEX`
- `BROLL_SYNCED_ACTION`
- `AMBIENCE_OR_SFX`
- `MUSIC_BED`
- `SILENT_GRAPHIC`

### Required fields

At minimum:

- `render_units.audio_policy`;
- `render_units.final_audio_source`;
- `render_units.provider_audio_usage`;
- temporal-policy metadata;
- versioned policy schema.

### Migration

1. Add constrained columns.
2. Backfill visible speaking units conservatively as `HERO_SYNC_LOCKED`.
3. Backfill B-roll as `BROLL_FLEX` unless evidence requires another policy.
4. Reject null policy on new units.
5. Provide rollback migration.
6. Preserve audit events for backfill.

### Tests

- `test_new_render_unit_requires_audio_policy`
- `test_unknown_audio_policy_rejected`
- `test_hero_policy_defaults_to_master_narration`
- `test_broll_policy_discards_provider_narration`
- `test_migration_backfills_existing_units`

### Acceptance criteria

Every active render unit has a valid audio policy.

---

## Ticket LB-101 — Add text-policy enum and constraints

**Primary implementer:** Software Engineer  
**Implementation specialization:** Database/storyboard  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-100

### Required values

- `NO_VISIBLE_TEXT`
- `UNREADABLE_BACKGROUND`
- `POST_COMPOSITE`
- `REAL_SCREEN_CAPTURE`
- `DETERMINISTIC_GRAPHIC`

### Required behavior

A render unit involving a screen, notebook, page, sign, phone, whiteboard, chart, or slide must have a non-null text policy.

No production schema may allow `GENERATE_READABLE_TEXT`.

### Tests

- `test_text_bearing_surface_requires_text_policy`
- `test_generate_readable_text_policy_rejected`
- `test_post_composite_requires_replacement_asset_spec`
- `test_real_screen_capture_requires_source_artifact`
- `test_deterministic_graphic_requires_graphic_spec`

### Acceptance criteria

Text-heavy beats cannot enter generation without an explicit safe routing policy.

---

## Ticket LB-102 — Add policy-aware repository validation

**Primary implementer:** Software Engineer  
**Implementation specialization:** Repository/service layer  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-100, LB-101

### Objective

Centralize policy validation so scripts cannot bypass database rules.

### Required APIs

- `validate_audio_policy(render_unit)`
- `validate_text_policy(render_unit)`
- `validate_temporal_edit_policy(render_unit, operation)`
- `validate_final_audio_source(render_unit)`
- `validate_provider_audio_usage(render_unit)`

### Tests

- direct repository write cannot bypass validation;
- service write cannot bypass validation;
- import path cannot create invalid policies;
- export path cannot reactivate invalid data.

### Acceptance criteria

All write paths use the same validation contract.

---

## Sprint 1 Exit Gate

- migrations apply and roll back cleanly;
- all active render units are backfilled;
- repository rejects invalid policies;
- auditor confirms no bypass path;
- validator runs migration and full policy suite from a clean database.

---

# 10. Sprint 2 — Immutable Master Narration and Canonical Timebase

## Sprint goal

Create one authoritative narration artifact and eliminate independent rounding.

## Ticket LB-200 — Register immutable master narration artifact

**Primary implementer:** Software Engineer  
**Implementation specialization:** TTS/database  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 1

### Required provenance

- artifact ID;
- production ID;
- script revision ID;
- voice ID;
- ElevenLabs model;
- voice settings;
- request fingerprint;
- provider request ID;
- SHA-256;
- sample rate;
- channels;
- sample count;
- duration milliseconds;
- storage URI;
- actual cost;
- created timestamp.

### Reuse rule

Reuse is allowed only if:

- script revision hash matches;
- voice ID matches;
- model matches;
- voice configuration matches;
- provider settings match;
- stored bytes exist;
- checksum matches.

### Tests

- `test_exact_tts_fingerprint_reuses_master`
- `test_script_change_invalidates_master`
- `test_voice_change_invalidates_master`
- `test_voice_setting_change_invalidates_master`
- `test_checksum_mismatch_invalidates_master`
- `test_retry_does_not_duplicate_tts_job`

### Acceptance criteria

Every timing span and hero slice references one immutable master narration artifact.

---

## Ticket LB-201 — Implement canonical timeline timebase

**Primary implementer:** Software Engineer  
**Implementation specialization:** Audio/timeline  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-200

### Required decision

Use integer audio samples internally at the master sample rate. Expose integer milliseconds for human-readable reports and provider interfaces.

### Required utilities

- `samples_to_ms`
- `ms_to_samples`
- `validate_interval`
- `interval_duration_samples`
- `detect_overlap_samples`
- `detect_gap_samples`
- `clamp_to_master_bounds`
- `provider_duration_from_samples`

### Prohibited behavior

- direct floating-point duration arithmetic in production modules;
- independent `ceil()` or `round()` decisions in slicing, prompt compilation, generation, QA, or assembly.

### Tests

- exact round trip;
- 100-span cumulative drift equals zero;
- negative interval rejected;
- out-of-bounds interval rejected;
- exact final span reaches master end;
- provider rounding occurs in one named utility only.

### Acceptance criteria

Repository search confirms no independent hero-duration rounding outside the canonical module.

---

## Ticket LB-202 — Make final assembly use the master narration once

**Primary implementer:** Software Engineer  
**Implementation specialization:** FFmpeg/assembly  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-200, LB-201

### Required behavior

- add master narration as one final audio input;
- strip narration audio from hero videos;
- strip B-roll audio unless explicitly `AMBIENCE_OR_SFX`;
- mix music and ambience beneath master narration;
- preserve configured loudness and ducking;
- prohibit concatenated hero narration.

### Tests

Create:

```text
tests/integration/test_master_audio_spine.py
```

Tests:

- `test_final_video_contains_single_narration_source`
- `test_hero_provider_audio_is_not_mixed`
- `test_broll_provider_audio_is_discarded`
- `test_explicit_ambience_can_be_mixed`
- `test_master_waveform_alignment_with_output`
- `test_no_duplicate_words_at_hero_boundary`

### Acceptance criteria

Waveform correlation proves the final narration derives from the master artifact, within expected encoding tolerance.

---

## Sprint 2 Exit Gate

- master artifact is immutable and fingerprinted;
- one canonical timebase is used;
- final narration is laid exactly once;
- provider narration cannot reach the final mix;
- auditor and validator pass the audio-spine integration suite.

---

# 11. Sprint 3 — Clean Hero Slicing and Hero Render Groups

## Sprint goal

Generate exact, non-overlapping hero conditioning slices using silence padding only.

## Ticket LB-300 — Store speech intervals separately from visible intervals

**Primary implementer:** Software Engineer  
**Implementation specialization:** Timeline/database  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 2

### Required fields

- `speech_start_sample`
- `speech_end_sample`
- `visible_start_sample`
- `visible_end_sample`
- `generation_start_sample`
- `generation_end_sample`
- `leading_silence_samples`
- `trailing_silence_samples`
- `master_audio_artifact_id`
- `master_audio_sha256`
- boundary reason
- boundary confidence

### Rules

- speech intervals must not overlap;
- generation may exceed speech only through silence;
- visible intervals may be shorter than generation intervals;
- B-roll may cover portions of a generated hero group;
- all intervals remain within master bounds.

### Tests

- overlapping speech rejected;
- generation extension without silence rejected;
- visible interval outside generation rejected;
- wrong master hash rejected.

### Acceptance criteria

The data model can distinguish spoken audio, generated duration, and visible picture timing.

---

## Ticket LB-301 — Replace adjacent-speech padding with generated silence

**Primary implementer:** Software Engineer  
**Implementation specialization:** Audio slicing  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-300

### Implementation steps

1. Extract the exact assigned speech samples.
2. Calculate provider-required duration centrally.
3. Generate leading/trailing silence at the master sample rate.
4. Concatenate speech and silence deterministically.
5. Store slice artifact and provenance.
6. Verify no adjacent speech samples are included.
7. Store exact padding values.
8. Fail closed when the interval is ambiguous.

### Required fixtures

- B001/B002 overlap case;
- B008a/B008b/B008c overlap chain;
- zero-padding case;
- minimum-duration case;
- integer-duration case;
- final beat at end of master.

### Tests

- `test_b001_slice_excludes_b002_speech`
- `test_b008_chain_has_zero_speech_overlap`
- `test_padding_is_silence_not_neighbor_audio`
- `test_padding_length_matches_provider_requirement`
- `test_slice_checksum_is_deterministic`
- `test_final_beat_padding_does_not_exceed_master`

### Acceptance criteria

All hero source slices have zero spoken-audio overlap.

---

## Ticket LB-302 — Implement hero render-group planner

**Primary implementer:** Software Engineer  
**Implementation specialization:** Storyboard/timeline  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-300, LB-301

### Objective

Decide when hero-before and hero-after B-roll should be one continuous Seedance render.

### Required decision inputs

- total generation duration;
- provider duration limits;
- clause and sentence boundaries;
- B-roll cutaway duration;
- same scene/camera;
- pose and gesture continuity value;
- rhetorical reset;
- expected regeneration cost;
- return-to-hero timing;
- safe boundary confidence.

### Required outputs

- `hero_render_group_id`;
- generation interval;
- member visible intervals;
- B-roll-covered intervals;
- source audio slice;
- prompt;
- model;
- requested duration;
- regeneration blast radius;
- temporal edit policy.

### Required rules

One continuous group is permitted only when:

- total duration is provider-valid;
- no unrelated neighbouring speech is included;
- the scene and camera remain consistent;
- the return interval is explicit;
- continuity benefit is documented.

### Tests

- short cutaway forms one group;
- long cutaway creates separate groups;
- provider maximum forces split;
- scene change forces split;
- rhetorical reset may split;
- group cannot include unrelated next beat;
- B-roll-covered interval remains within group.

### Acceptance criteria

Hero grouping is deterministic and fully stored in the database.

---

## Sprint 3 Exit Gate

- speech and visible intervals are separate;
- contaminated padding is removed;
- B001 and B008 fixtures pass;
- hero grouping is deterministic;
- auditor confirms zero adjacent speech;
- validator runs complete slicing suite from clean data.

---

# 12. Sprint 4 — Seedance Provider Contract and Diagnostic Audio

## Sprint goal

Make Seedance requests deterministic and prevent provider-returned audio from becoming final narration.

## Ticket LB-400 — Create hero request semantic fingerprint

**Primary implementer:** Software Engineer  
**Implementation specialization:** Provider integration  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 3

### Fingerprint inputs

- production ID;
- render-unit ID;
- hero render-group ID;
- master artifact hash;
- slice artifact hash;
- exact source samples;
- silence padding;
- prompt hash;
- reference image/video hash;
- Seedance model/version;
- requested duration;
- aspect ratio;
- provider parameters;
- code/config revision.

### Tests

- prompt change invalidates reuse;
- slice change invalidates reuse;
- padding change invalidates reuse;
- reference image change invalidates reuse;
- model change invalidates reuse;
- exact retry reuses provider job.

### Acceptance criteria

No stale hero clip can be reused after a meaningful input change.

---

## Ticket LB-401 — Store provider-returned audio as diagnostic-only

**Primary implementer:** Software Engineer  
**Implementation specialization:** Provider/media service  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-400

### Required behavior

- probe returned container;
- register video artifact;
- extract returned audio as a separate optional artifact;
- tag audio as `diagnostic_only`;
- link diagnostic audio to source slice;
- set `eligible_for_final_narration=false`;
- reject it in assembly narration queries.

### Tests

- provider audio is registered separately;
- assembly cannot select it as narration;
- provider audio may be used by QA;
- missing provider audio does not fail video generation unless contract requires it.

### Acceptance criteria

The repository makes it structurally impossible to use provider audio as final narration.

---

## Ticket LB-402 — Add provider timing-drift evidence

**Primary implementer:** Software Engineer  
**Implementation specialization:** Audio/media QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-401

### Required measurements

- source duration;
- returned audio duration;
- returned video duration;
- speech-start lag;
- speech-end delta;
- correlation lag;
- drift at beginning, middle, and end;
- mouth motion during padded silence;
- duplicate or dropped speech evidence.

### Required outputs

Versioned validation evidence tied to:

- hero artifact ID;
- source slice artifact ID;
- validation algorithm version;
- thresholds;
- measured values;
- pass/fail result.

### Tests

Use deterministic fixtures for:

- perfect alignment;
- constant offset;
- progressive drift;
- early speech end;
- speech in silence pad;
- missing provider audio.

### Acceptance criteria

Every hero candidate has timing-drift evidence before it can proceed to lipsync approval.

---

## Sprint 4 Exit Gate

- provider requests are fingerprinted;
- retries are idempotent;
- returned audio is diagnostic-only;
- timing drift is measured;
- auditor and validator verify no path to final narration.

---

# 13. Sprint 5 — Locked Hero Assembly

## Sprint goal

Assemble hero footage without breaking synchronization.

## Ticket LB-500 — Add policy-complete assembly DTOs

**Primary implementer:** Software Engineer  
**Implementation specialization:** Assembly/repository  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 4

### DTO must include

- render-unit ID;
- hero render-group ID;
- approved video artifact ID;
- exact timeline placement;
- visible intervals;
- B-roll cover intervals;
- master narration reference;
- audio policy;
- text policy;
- permitted spatial transforms;
- forbidden temporal transforms;
- boundary-evidence IDs;
- lipsync-evidence IDs.

### Tests

- missing policy rejected;
- missing QA evidence rejected;
- stale artifact rejected;
- stale validation rejected;
- wrong master audio rejected.

### Acceptance criteria

Assembly cannot construct a hero command from incomplete data.

---

## Ticket LB-501 — Enforce no temporal hero filters

**Primary implementer:** Software Engineer  
**Implementation specialization:** FFmpeg  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-500

### Forbidden operations

- non-identity `setpts`;
- speed change;
- interpolation;
- looping;
- reverse;
- freeze extension;
- arbitrary trim through active speech;
- audio retiming;
- provider narration concatenation.

### Allowed operations

- crop;
- scale;
- pad;
- grade;
- denoise;
- sharpen;
- subtitles;
- graphic overlays;
- hard cuts;
- trim outside speech at approved boundaries;
- B-roll picture replacement.

### Tests

- one test per forbidden operation;
- one test per allowed operation;
- command inspection test;
- test that a future unknown temporal filter fails closed.

### Acceptance criteria

The generated FFmpeg command contains no unauthorized temporal transformation.

---

## Ticket LB-502 — Implement hero/B-roll picture cutaways over continuous narration

**Primary implementer:** Software Engineer  
**Implementation specialization:** FFmpeg/timeline  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-501

### Required behavior

- hero may continue beneath a B-roll picture cutaway;
- master narration continues unchanged;
- B-roll replaces only the video layer;
- return to hero uses a declared visible interval;
- crossfades through visible mouth motion are prohibited by default;
- hard cuts are permitted at approved boundaries;
- B-roll duration is independently adjustable within policy.

### Tests

- hero → B-roll → same hero group;
- hero → B-roll → separate hero group;
- B-roll covers part of a sentence;
- master narration remains continuous;
- return outside visible interval rejected;
- unsafe crossfade rejected;
- B-roll provider audio not introduced.

### Acceptance criteria

The final picture can change while the master narration remains sample-aligned.

---

## Sprint 5 Exit Gate

- assembly DTOs are complete;
- hero temporal filters are forbidden;
- picture cutaways preserve narration;
- all commands pass static inspection;
- validator renders and probes the integration fixture.

---

# 14. Sprint 6 — Lipsync Runtime QA and Repair Routing

## Sprint goal

Detect synchronization defects automatically and route failed hero units back to the correct generation stage.

## Ticket LB-600 — Add speech-boundary and overlap validation

**Primary implementer:** Software Engineer  
**Implementation specialization:** Audio QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 5

### Checks

- no speech overlap across source slices;
- no neighbouring words in silence pad;
- source speech begins and ends within assigned interval;
- no active speech truncated by visible trim;
- provider speech end is measured but not authoritative.

### Tests

- overlapping source slices fail;
- silence-only pad passes;
- speech in pad fails;
- trim through active speech fails;
- provider timing difference creates evidence.

---

## Ticket LB-601 — Add audiovisual lipsync scoring

**Primary implementer:** Software Engineer  
**Implementation specialization:** Media QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-600

### Required behavior

Implement or integrate an audiovisual synchronization score.

The implementation must record:

- score;
- offset estimate;
- confidence;
- algorithm/model version;
- input artifact hashes;
- pass threshold;
- review threshold;
- failure reason.

### Test fixtures

- aligned talking head;
- fixed offset;
- progressive drift;
- frozen mouth;
- mouth movement during silence;
- no visible face;
- multiple faces;
- low-confidence occlusion.

### Result states

- `PASS`;
- `FAIL_REGENERATE`;
- `REVIEW_REQUIRED`;
- `NOT_APPLICABLE`.

### Acceptance criteria

A hero unit cannot become valid without lipsync evidence.

---

## Ticket LB-602 — Add safe-boundary validation

**Primary implementer:** Software Engineer  
**Implementation specialization:** Video QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-601

### Required checks

- mouth closure or low-motion boundary;
- blink or natural transition where available;
- no cut inside a high-confidence phoneme;
- no unstable startup or terminal provider frames;
- approved return-to-hero interval.

### Tests

- safe pause passes;
- cut mid-word fails;
- unstable first frames fail;
- B-roll masks unsafe hidden interval but return remains safe;
- low-confidence result requires review.

---

## Ticket LB-603 — Route failed hero units to selective regeneration

**Primary implementer:** Software Engineer  
**Implementation specialization:** Workflow/change requests  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-600, LB-601, LB-602

### Required behavior

- create structured change request;
- identify owning generation stage;
- preserve unaffected hero and B-roll assets;
- invalidate only failed unit and dependent deliverables;
- retain failure evidence;
- regenerate with updated fingerprint;
- resolve request transactionally only after new evidence passes.

### Tests

- failed unit regenerates selectively;
- unaffected units are reused;
- open request blocks assembly;
- successful replacement resolves request;
- stale old artifact cannot be reactivated;
- failed replacement leaves request open.

### Acceptance criteria

Lipsync repair does not require manual file surgery or full-video regeneration.

---

## Sprint 6 Exit Gate

- overlap and boundary checks pass;
- lipsync score is mandatory;
- repair loop is selective;
- B001 and B008 chain pass;
- auditor and validator approve the complete hero path.

---

# 15. Sprint 7 — B-Roll Semantic Storyboard Contract

## Sprint goal

Make the storyboard specify what each B-roll shot must teach or demonstrate.

## Ticket LB-700 — Extend storyboard schema with B-roll semantic fields

**Primary implementer:** Software Engineer  
**Implementation specialization:** Storyboard/database  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 0

### Required fields

- `visual_function`;
- `narrative_claim`;
- `information_to_show`;
- `viewer_takeaway`;
- `required_actions`;
- `forbidden_cliches`;
- `distinct_from_recent_beats`;
- `text_policy`;
- `render_mode`;
- `semantic_acceptance_criteria`.

### Validation rules

- `information_to_show` cannot be empty;
- `viewer_takeaway` cannot merely repeat the narration;
- `context` requires explicit justification;
- text-bearing surfaces require text policy;
- generic laptop/notebook actions require explicit informational rationale;
- every generated B-roll beat must have observable actions.

### Tests

- generic empty B-roll rejected;
- demonstration with explicit sequence passes;
- unjustified context rejected;
- text-bearing beat without policy rejected;
- repeated cliché list enforced.

### Acceptance criteria

No B-roll beat can enter prompt compilation without a semantic contract.

---

## Ticket LB-701 — Add B-roll render-mode router

**Primary implementer:** Software Engineer  
**Implementation specialization:** Storyboard/media planning  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-700

### Supported modes

- `GENERATED_VIDEO`;
- `DETERMINISTIC_GRAPHIC`;
- `REAL_SCREEN_CAPTURE`;
- `POST_COMPOSITE_VIDEO`;
- `ARCHIVAL_OR_LICENSED`;
- `HERO`;
- `NO_VISUAL_CHANGE`.

### Routing rules

Use deterministic graphics when:

- exact text matters;
- a labelled framework is shown;
- numbers or comparisons matter;
- a chart or sequence must be correct.

Use real screen capture when:

- software interaction matters;
- a real UI is explained.

Use post-composite when:

- a moving screen/page is useful;
- exact content must be inserted.

Use generated video when:

- physical action or metaphor matters;
- exact text is not required.

### Tests

- text-heavy laptop UI routes to screen capture/post-composite;
- labelled framework routes to deterministic graphic;
- physical recall exercise routes to generated video;
- factual event routes to archival/licensed;
- unsupported combination fails closed.

### Acceptance criteria

The planner no longer sends every visual idea to Seedance.

---

## Ticket LB-702 — Add context-shot quota and cliché policy

**Primary implementer:** Software Engineer  
**Implementation specialization:** Storyboard rules  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-700

### Required policy

Within a configurable rolling window:

- maximum one generic desk scene;
- maximum one laptop-centric shot;
- maximum one notebook-writing shot;
- maximum one passive “thinking professional” shot;
- no duplicate location/action combination;
- no repeated metaphor without explicit approval.

### Tests

- repeated laptop shots rejected;
- distinct demonstrations pass;
- context quota configurable by format;
- approved exception recorded and audited.

### Acceptance criteria

The system cannot produce a sequence dominated by near-identical desk activity.

---

## Sprint 7 Exit Gate

- semantic fields are required;
- routing is deterministic;
- cliché quotas are enforced;
- auditor reviews sample storyboards;
- validator confirms invalid plans cannot compile.

---

# 16. Sprint 8 — B-Roll Prompt Compiler and Diversity

## Sprint goal

Compile action-specific, informative prompts and reject semantic duplicates before paid generation.

## Ticket LB-800 — Replace generic B-roll prompt templates

**Primary implementer:** Software Engineer  
**Implementation specialization:** Prompt compiler  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 7

### Prompt requirements

Each generated-video prompt must include:

- observable beginning state;
- ordered physical action;
- visible consequence or result;
- camera framing;
- motion;
- environment;
- text-policy instructions;
- negative constraints;
- distinction from recent shots.

### Example required transformation

Weak input:

```text
Professional man using a laptop and taking notes.
```

Required form:

```text
A senior professional closes a reference book and moves it out of reach.
He writes three recall marks on a blank card without looking at the book.
He reopens the book, compares the source, and circles one missed point.
Medium close-up, clear sequence of actions, natural hands, no laptop,
no readable handwriting, no visible printed text.
```

### Tests

- prompt includes ordered action;
- prompt includes narrative function;
- prompt includes text policy;
- prompt includes prohibited clichés;
- generic occupation-only prompt rejected;
- prompt does not invent unsupported claims.

### Acceptance criteria

All B-roll prompts describe a visible informational sequence.

---

## Ticket LB-801 — Add production-level visual-concept memory

**Primary implementer:** Software Engineer  
**Implementation specialization:** Planning/database  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-800

### Required stored attributes

- location;
- subject type;
- primary action;
- prop set;
- camera setup;
- visual metaphor;
- color/environment;
- semantic embedding;
- keyframe embedding after generation.

### Required behavior

Before generation:

- compare proposed concept with prior concepts;
- reject high-similarity duplicates;
- suggest a different visual function or render mode;
- record exception rationale when override is used.

### Tests

- two laptop/notebook prompts rejected as duplicates;
- same subject with materially different action passes;
- same metaphor repeated fails;
- threshold is configurable and versioned;
- override requires reason and approval event.

### Acceptance criteria

Semantic duplicates are detected before paid generation.

---

## Ticket LB-802 — Add prompt preflight quality gate

**Primary implementer:** Software Engineer  
**Implementation specialization:** Prompt QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-800, LB-801

### Checks

- semantic contract coverage;
- observable action;
- no unsupported readable-text request;
- no forbidden cliché;
- no semantic duplicate;
- provider capability compatibility;
- expected duration feasible;
- human anatomy risk noted;
- fallback render mode available.

### Result

- `PASS`;
- `REVISE_PROMPT`;
- `REROUTE_RENDER_MODE`;
- `BLOCKED`.

### Tests

One test per result state.

### Acceptance criteria

No paid B-roll request is submitted without preflight pass.

---

## Sprint 8 Exit Gate

- prompts are action-specific;
- visual memory is persisted;
- duplicates are rejected;
- prompt preflight is mandatory;
- validator runs a sample 15-beat storyboard with no redundant laptop/notebook cluster.

---

# 17. Sprint 9A — Text-Safe Graphics and Compositing

## Sprint goal

Eliminate gibberish text by routing exact information to deterministic or post-composited assets.

## Ticket LB-900 — Implement deterministic graphic render units

**Primary implementer:** Software Engineer  
**Implementation specialization:** Graphics/media  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 7

### Supported outputs

- text cards;
- labelled frameworks;
- process diagrams;
- charts;
- chapter headings;
- kinetic text;
- simple UI mockups.

### Required behavior

- exact text from structured data;
- deterministic font/layout configuration;
- safe-area validation;
- spelling validation;
- artifact checksum;
- versioned graphic template;
- render-unit registration.

### Tests

- exact text rendered;
- long text wraps or fails safely;
- missing font/config fails loudly;
- checksum deterministic;
- graphic dimensions correct;
- no provider call made.

### Acceptance criteria

Exact text can be shown without generative-video typography.

---

## Ticket LB-901 — Implement blank-surface post-composite workflow

**Primary implementer:** Software Engineer  
**Implementation specialization:** Video compositing  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-900

### Required workflow

1. Generated prompt requests blank, stable, trackable surface.
2. Generated video is validated for surface visibility.
3. Replacement asset is rendered deterministically.
4. Surface is tracked or transformed.
5. Asset is corner-pinned or overlaid.
6. Final composite is validated for legibility and stability.

### Required supported surfaces

- laptop screen;
- phone screen;
- notebook/page;
- whiteboard;
- presentation screen.

### Tests

- static planar surface;
- moving planar surface;
- partial occlusion;
- excessive motion causes reroute/failure;
- correct perspective;
- exact spelling;
- stable placement over frames.

### Acceptance criteria

Meaningful text is inserted after generation, not generated by Seedance.

---

## Ticket LB-902 — Add text-policy assembly and QA enforcement

**Primary implementer:** Software Engineer  
**Implementation specialization:** Assembly/runtime QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-900, LB-901

### Required checks

- `NO_VISIBLE_TEXT`: reject obvious readable text;
- `UNREADABLE_BACKGROUND`: ensure text is not focal or claimed as meaningful;
- `POST_COMPOSITE`: require replacement artifact and composite evidence;
- `REAL_SCREEN_CAPTURE`: require source provenance;
- `DETERMINISTIC_GRAPHIC`: require rendered graphic artifact.

### Tests

- generated gibberish focal text fails;
- intentionally blurred background passes;
- missing replacement asset fails;
- correctly composited screen passes;
- misspelled deterministic text fails.

### Acceptance criteria

No text-bearing visual can pass without satisfying its declared policy.

---

## Sprint 9A Exit Gate

- deterministic graphics work;
- post-compositing works;
- text policy is enforced;
- auditor inspects sample outputs;
- validator confirms readable text is exact and stable.

---

# 18. Sprint 9B — B-Roll Runtime Quality Validation

## Sprint goal

Reject technically valid but useless, repetitive, or semantically wrong B-roll.

## Ticket LB-930 — Add B-roll semantic-relevance evidence

**Primary implementer:** Software Engineer  
**Implementation specialization:** Runtime media QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 8

### Inputs

- narration claim;
- visual function;
- information to show;
- viewer takeaway;
- generated keyframes;
- prompt;
- artifact hash.

### Required result

- relevance score;
- action-completion score;
- contradiction flag;
- missing-required-element list;
- confidence;
- algorithm/model version;
- pass/fail/review result.

### Tests

- correct recall demonstration passes;
- generic laptop typing fails;
- irrelevant office shot fails;
- partially completed action requires review;
- contradiction fails.

### Acceptance criteria

B-roll cannot pass solely because it is visually attractive.

---

## Ticket LB-931 — Add cross-clip visual duplicate detection

**Primary implementer:** Software Engineer  
**Implementation specialization:** Runtime media QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-930

### Required comparisons

- semantic embedding;
- keyframe image embedding;
- action label;
- location;
- prop combination;
- camera setup.

### Required behavior

- compare new output with all active B-roll in the production;
- reject near-duplicates above threshold;
- distinguish purposeful callback from accidental duplication;
- record evidence and threshold version.

### Tests

- slightly different laptop renders fail as duplicates;
- same location with different mechanism passes;
- purposeful before/after pair passes when declared;
- threshold boundary tests;
- override requires documented reason.

### Acceptance criteria

Repeated laptop/notepad outputs are caught even when prompts differ superficially.

---

## Ticket LB-932 — Add generated-text and malformed-object detection

**Primary implementer:** Software Engineer  
**Implementation specialization:** Runtime media QA  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-930, Sprint 9A

### Required checks

- focal gibberish text;
- malformed book/page geometry;
- unstable laptop screen;
- broken hands during key action;
- disappearing props;
- temporal inconsistency;
- unusable anatomy.

### Result states

- `PASS`;
- `FAIL_REGENERATE`;
- `FAIL_REROUTE_TO_GRAPHIC`;
- `REVIEW_REQUIRED`.

### Tests

Use curated fixtures:

- gibberish notebook;
- malformed laptop;
- stable blank screen;
- correct composite;
- hand distortion;
- disappearing object.

### Acceptance criteria

Known defective B-roll classes are automatically routed to regeneration or deterministic alternatives.

---

## Ticket LB-933 — Implement B-roll change-request routing

**Primary implementer:** Software Engineer  
**Implementation specialization:** Workflow  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-930, LB-931, LB-932

### Routing rules

- semantic mismatch → revise storyboard/prompt;
- visual duplicate → revise concept;
- gibberish text → reroute to composite/graphic;
- malformed object → regenerate or reroute;
- technical corruption → regenerate;
- repeated failure → require alternative render mode.

### Tests

- each failure routes to correct owner stage;
- unaffected clips remain valid;
- repeated failure escalates;
- successful replacement resolves request;
- old failed artifact remains superseded.

### Acceptance criteria

The pipeline repairs the cause, not merely regenerates the same bad prompt.

---

## Sprint 9B Exit Gate

- semantic relevance is measured;
- duplicate detection works;
- gibberish/malformed-object checks work;
- repair routing is cause-specific;
- validator evaluates a representative B-roll fixture set.

---

# 19. Sprint 10 — Integrated Pipeline Cutover

## Sprint goal

Prove the hero/lipsync and B-roll remediation together in the DB-native pipeline.

## Ticket LB-1000 — Build deterministic integrated E2E fixture

**Primary implementer:** Software Engineer  
**Implementation specialization:** Integration testing  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprints 6, 8, 9A, 9B

### Fixture must include

- continuous master narration;
- B001-style hero followed by B-roll;
- B008a–B008c-style hero chain;
- hero → B-roll → same hero group;
- hero → B-roll → separate hero group;
- informative demonstration B-roll;
- attempted duplicate laptop B-roll;
- text-heavy laptop concept rerouted to composite;
- deterministic graphic;
- music/ambience;
- final assembly.

### Required assertions

- zero spoken overlap;
- one final narration source;
- hero provider audio absent;
- no hero retiming;
- correct hero/B-roll picture cutaways;
- duplicate B-roll rejected before paid submission;
- gibberish text route blocked;
- exact composited text present;
- all artifacts and validation evidence traceable;
- no unresolved change requests;
- final deliverable valid.

### Acceptance criteria

The complete fixture passes without manual file edits.

---

## Ticket LB-1001 — Add crash and resume matrix

**Primary implementer:** Software Engineer  
**Implementation specialization:** Reliability testing  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-1000

### Crash points

- after master narration commit;
- during slice creation;
- before Seedance submit;
- after Seedance submit before external ID commit;
- after external ID commit;
- after download before artifact registration;
- after lipsync failure;
- during B-roll reroute;
- during composite render;
- before final assembly;
- after final assembly before validation.

### Assertions

- no duplicate paid job;
- no duplicate master narration;
- committed work reused;
- stale work not reused;
- open requests preserved;
- resume begins from correct state.

### Acceptance criteria

Every injected crash resumes safely.

---

## Ticket LB-1002 — Add forbidden-behavior CI gates

**Primary implementer:** Software Engineer  
**Implementation specialization:** CI/static analysis  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-1000

### CI must fail on

- provider audio selected as final narration;
- hero non-identity retiming;
- adjacent-speech padding;
- direct hero-duration rounding outside canonical module;
- `GENERATE_READABLE_TEXT`;
- B-roll without semantic contract;
- text-bearing surface without text policy;
- prompt submission without preflight;
- runtime validation bypass;
- legacy JSON used as execution authority.

### Acceptance criteria

Each forbidden pattern has a positive failure fixture and a negative pass fixture.

---

## Sprint 10 Exit Gate

- integrated E2E fixture passes;
- crash matrix passes;
- forbidden-behavior CI gates pass;
- auditor signs off all code paths;
- validator runs the suite from clean checkout and database;
- no real provider spend is required for this sprint.

---

# 20. Sprint 11 — Controlled Real-Provider Validation and Release

## Sprint goal

Verify the architecture against actual ElevenLabs and Seedance behavior with tightly capped spend.

## Ticket LB-1100 — Prepare paid smoke-test plan

**Primary implementer:** Software Engineer  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** Sprint 10

### Required plan

- exact clips to generate;
- exact expected cost;
- hard budget cap;
- provider models and parameters;
- master audio and slice fingerprints;
- success criteria;
- stop conditions;
- evidence paths;
- no automatic retry beyond approved count.

### Required smoke cases

1. short clean hero slice with trailing silence;
2. hero → B-roll → same hero render group;
3. separate hero return;
4. action-specific B-roll;
5. blank laptop screen for compositing.

### Acceptance criteria

The plan is approved before any paid request.

---

## Ticket LB-1101 — Execute controlled real-provider smoke

**Primary implementer:** Software Engineer  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-1100  
**Human prerequisite:** Explicit spend approval

### Required outputs

- provider job IDs;
- actual cost;
- source fingerprints;
- returned artifact hashes;
- timing drift evidence;
- lipsync evidence;
- B-roll relevance evidence;
- composite result;
- failures and retries.

### Pass criteria

- no neighbouring speech;
- no duplicated narration;
- hero output passes lipsync threshold or follows review policy;
- B-roll demonstrates intended information;
- blank surface supports composite;
- exact text appears only after composite;
- actual cost remains within cap.

---

## Ticket LB-1102 — Release and legacy behavior retirement

**Primary implementer:** Software Engineer  
**Auditor:** Software Auditor  
**Validator:** Software Validator  
**Dependencies:** LB-1101

### Required work

- enable new path by default;
- disable legacy overlapping slice logic;
- disable provider-audio final mix;
- disable unsafe hero temporal edits permanently;
- archive obsolete configuration;
- update documentation;
- update migration notes;
- preserve rollback tag;
- publish operational runbook.

### Acceptance criteria

A new production cannot select the legacy unsafe behavior.

---

## Sprint 11 Exit Gate

- real-provider smoke completed within cap;
- lipsync and B-roll evidence reviewed;
- no architecture regression;
- legacy behavior disabled;
- rollback documented and tested;
- auditor pass;
- validator pass;
- release approved.

---

# 21. Required Test Inventory

## Unit tests

- audio policy validation;
- text policy validation;
- canonical time conversion;
- speech interval overlap;
- silence padding;
- request fingerprints;
- hero grouping;
- prompt semantic fields;
- duplicate concept logic;
- render-mode routing;
- text-policy routing;
- repair routing.

## Contract tests

- repository write validation;
- provider job adapter;
- assembly DTO;
- QA evidence schema;
- change-request lifecycle;
- artifact provenance;
- final narration selection;
- graphic/composite contracts.

## Integration tests

- master narration to slice;
- slice to Seedance request;
- Seedance output to diagnostic evidence;
- approved hero to assembly;
- hero/B-roll cutaway;
- B-roll prompt to generation;
- B-roll output to semantic QA;
- text-heavy concept to composite;
- repair and selective regeneration.

## End-to-end tests

- deterministic full fixture;
- B001 regression;
- B008a–B008c regression;
- duplicate laptop rejection;
- gibberish text reroute;
- crash/resume matrix;
- real-provider controlled smoke.

---

# 22. Sprint-Level Audit Rules

The Software Auditor must perform these checks in every sprint where relevant.

## Code-scope checks

- only authorized files changed;
- no unrelated refactor;
- no hidden fallback;
- no broad exception swallowing;
- no production dummy data;
- no unversioned thresholds;
- no direct database writes bypassing repository contracts.

## Audio checks

- master narration remains authoritative;
- provider audio cannot reach final narration;
- no neighbouring speech in pads;
- no independent rounding;
- sample offsets and hashes are stored.

## Video checks

- no hero retiming;
- no freeze extension;
- no unsafe trim;
- B-roll cutaway affects picture only;
- exact composite text comes from deterministic assets.

## Workflow checks

- failures create structured change requests;
- only affected descendants are invalidated;
- stale evidence cannot qualify new artifacts;
- repair closes requests transactionally.

---

# 23. Sprint-Level Validation Rules

The Software Validator must:

1. use a clean checkout;
2. create a clean database;
3. apply migrations from zero;
4. run unit, contract, and integration suites;
5. run the sprint exit fixture;
6. inspect generated artifact metadata;
7. inspect one FFmpeg command where relevant;
8. verify rollback or down migration;
9. confirm documentation updates;
10. issue `PASS` or `BLOCKED: <reason>`.

No sprint may pass based solely on engineer or auditor reports.

---

# 24. Definition of Done

## Lipsync and audio

1. One immutable ElevenLabs master narration is authoritative.
2. Final narration is laid down exactly once.
3. Hero conditioning slices contain no neighbouring speech.
4. Model-duration padding contains silence only.
5. Provider-returned audio is diagnostic-only.
6. Approved hero footage is never temporally altered.
7. Hero/B-roll picture cutaways preserve continuous narration.
8. Lipsync and safe-boundary evidence are mandatory.
9. Failed hero units regenerate selectively.
10. B001 and B008 regression fixtures pass.

## B-roll

11. Every B-roll beat has an informational function.
12. Every generated B-roll prompt contains observable action and consequence.
13. Repeated laptop/notebook concepts are rejected.
14. Production-level visual memory is active.
15. Exact text is never delegated to unconstrained video generation.
16. Text-heavy concepts route to graphics, screen capture, or post-composite.
17. Runtime B-roll relevance is validated.
18. Semantic duplicates are rejected.
19. Gibberish and malformed-object failures route to the correct repair.
20. Repair changes the cause, not merely the random seed.

## Engineering governance

21. Every ticket has engineer evidence.
22. Every ticket passes independent software audit.
23. Every sprint passes independent software validation.
24. Crash/resume tests prove no duplicate paid work.
25. Forbidden-behavior CI gates are active.
26. Legacy unsafe behavior is disabled.
27. One controlled real-provider smoke passes within budget.
28. Documentation accurately describes the released system.

---

# 25. Immediate Execution Order

Start in this order:

1. `LB-000` — trace actual failure;
2. `LB-001` — freeze unsafe hero temporal edits;
3. `LB-100` and `LB-101` — add explicit policies;
4. `LB-102` — enforce repository validation;
5. `LB-200` and `LB-201` — master narration and timebase;
6. `LB-202` — single final narration;
7. `LB-300` and `LB-301` — clean intervals and silence padding;
8. `LB-700` and `LB-701` — B-roll semantic contract and routing.

After Sprint 1:

- the hero/lipsync implementation path and B-roll planning path may proceed in parallel;
- integrated assembly and cutover must wait for both paths;
- real paid generation must wait until deterministic integration tests pass.

---

# 26. Final Engineering Judgment

The lipsync defect must be treated as a production blocker, not an acceptable finishing flaw.

The correct system is not:

```text
many independently generated talking clips
+ their baked audio
+ duration trimming
```

It is:

```text
one immutable narration master
+ exact non-overlapping conditioning slices
+ temporally locked hero video
+ flexible picture-only B-roll
+ deterministic graphics/composites
+ evidence-backed runtime QA
```

The B-roll defect cannot be solved by adding adjectives to prompts. It requires schema changes, semantic planning, prompt preflight, diversity memory, render-mode routing, text-safe compositing, runtime relevance validation, and cause-specific repair.

This plan implements those changes while preserving the same engineering governance used for the broader system rebuild: one implementing Software Engineer role, independent Software Auditor review, and independent Software Validator sprint gates.
