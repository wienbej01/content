# Post-TTS Storyboard Corrective Remediation Sprint

## Mission

Correct the implemented post-TTS storyboard system so it satisfies the original guarantees in real orchestration, not only isolated unit tests.

The current audited-project preview is a **NO-GO**. It contains invalid over-limit hero beats, proposes narration rewriting despite immutable approved audio, invents internal timestamps from word counts, cannot be consumed by the media-plan compiler, loses graphics-field compatibility, and is not connected to the targeted repair stage in `produce.py`.

The sprint must preserve the existing narration audio byte-for-byte. It must never call paid APIs, regenerate TTS, generate media, spend credits, send Telegram messages, or weaken existing fail-closed gates.

## Required Evidence

Read before editing:

- `AGENTS.md`
- `docs/PIPELINE.md`
- `reports/forensics/video_pipeline_audit_20260614_102622/KIRO_POST_TTS_STORYBOARD_RECONCILIATION_PROMPT.md`
- `reports/remediation/post_tts_storyboard/FINAL_REPORT.md`
- all `reports/remediation/post_tts_storyboard/PST-*/{implementation,audit,validation}_report.md`
- all files in `reports/remediation/post_tts_storyboard/audited_project_preview/`
- baseline-stabilization reports
- original forensic reports and duration reconciliation

Reproduce and record these defects:

1. Preview validation fails for B001, B008, and B009.
2. `produce.py` does not invoke `repair_storyboard_beats.py`.
3. `produce.py` invokes production-storyboard review without required `--output`.
4. `compile_plan(preview, ...)` raises `KeyError: 'shot_type'`.
5. Split timestamps are word-proportional estimates rather than measured audio boundaries.
6. `graphics`/`graphic` and other creative fields are not passed consistently.
7. Split children are incorrectly reported as narration mutations.
8. Reconciliation/repair CLIs can exit zero while output remains invalid.
9. Coverage validation sums durations without proving slot continuity.
10. The compiler does not expand `coverage_plan` slots into renderable media-plan assets.

## Non-Negotiable Invariants

- `continuous.mp3` is immutable and authoritative.
- Approved narration text may not be rewritten, shortened, duplicated, reordered, or omitted.
- No TTS regeneration is permitted to solve clip limits.
- Split boundaries must come from measured audio evidence: forced word alignment when available, otherwise validated silence boundaries with explicit confidence. Word-count interpolation alone is not a legal production boundary.
- If no safe split exists, reroute the interval to B-roll, local graphics, hero cutaway, or a sequence of non-lipsync visual slots while retaining continuous narration.
- Every interval from `0.0` to master-audio EOF has exactly one planned primary visual coverage path.
- Required overlays may span selected children/slots, but must not be blindly duplicated unless intentionally specified.
- Every production storyboard must be directly consumable by the real media-plan compiler.
- Every non-local coverage slot becomes a separately costed, generated, QA-checked, manifested asset.
- Invalid or unrepaired output must produce non-zero exit and must not overwrite the last valid production artifact.
- No creative or LLM decision can manufacture authoritative timing values.

## Agent Process

Execute one ticket at a time: **Engineer → Auditor → Validator**. Do not begin the next ticket until both Auditor and Validator pass.

### Engineer

- Implements exactly one ticket and its tests.
- Uses only local fixtures, mocks, FFmpeg, and existing artifacts.
- Writes `reports/remediation/post_tts_corrective/<TICKET>/engineer_report.md`.

### Auditor

- Read-only for production code.
- Traces all callers and artifact handoffs, checks for silent fallbacks and invented timing.
- Writes `reports/remediation/post_tts_corrective/<TICKET>/audit_report.md` with PASS or REVISE.

### Validator

- Does not edit production code.
- Runs focused and integration tests with exact command evidence.
- Writes `reports/remediation/post_tts_corrective/<TICKET>/validation_report.md` with PASS or FAIL.

Allow at most two revision cycles per ticket. Stop with a documented blocker instead of weakening an invariant.

## Tickets

### PTC-01 - Define One Production Storyboard Contract

**Files likely involved:** `scripts/production_storyboard.py`, schema files, `scripts/compile_media_prompts.py`, tests.

Define a versioned contract that carries all downstream-required fields, including:

- IDs and source/split lineage;
- exact audio start/end/duration and timing provenance;
- narration text/hash;
- `shot_type`, `treatment`, `asset_type`, `model`, model limits;
- `segment_id`, visual brief/prompts, references, crop safety and routing metadata;
- one canonical graphics/overlay representation;
- explicit coverage slots with stable slot IDs;
- cost/generation/QA/manifest traceability fields.

Remove ambiguous aliases or implement explicit schema-versioned adapters. Do not rely on silent defaults for production-required fields.

**Acceptance criteria:** the audited preview schema can be validated and passed into `compile_plan()` without exceptions; missing required fields fail with structured errors; producer and consumer contract tests use serialized JSON, not only in-memory dictionaries.

### PTC-02 - Replace Estimated Split Timing with Measured Boundaries

**Files likely involved:** `scripts/audio_timing.py`, `scripts/reconcile_production_storyboard.py`, new alignment helper, tests.

Create authoritative legal split points from actual audio. Prefer existing word/sentence timestamps if present. Otherwise use deterministic local alignment or validated silence intervals. Record method, confidence, source audio hash, and boundary evidence.

Word-proportional estimates may be advisory only and must never become production slice boundaries.

**Acceptance criteria:** tests prove boundaries do not bisect speech; low-confidence/ambiguous alignment fails or reroutes without lipsync splitting; B006/B010 preview splits are regenerated from measured evidence; timing remains contiguous within one frame.

### PTC-03 - Implement Deterministic Rerouting for Unsplittable Hero Beats

**Files likely involved:** reconciliation and routing modules, constraints, tests.

For over-limit hero intervals with no safe split, preserve narration and transform visual treatment rather than narration. Support deterministic options such as:

- bounded B-roll slots;
- local graphic plus B-roll sequence;
- hero cutaway with continuous voiceover;
- mixed slots selected from allowed treatment policy.

An LLM may recommend visual concepts but may not provide timestamps or alter immutable fields. Python owns timing, slot count, treatment legality, and coverage.

**Acceptance criteria:** B001, B008, and B009 become model-legal without narration or TTS changes; every slot is within its model limit; no `needs_repair` beat remains in accepted output.

### PTC-04 - Repair Loop Integration and Fail-Closed CLI Semantics

**Files likely involved:** `scripts/repair_storyboard_beats.py`, `scripts/produce.py`, state/fingerprint code, tests.

Wire targeted repair into the orchestrator between reconciliation and production-storyboard review. Supply only unresolved beats and immutable timing evidence. Revalidate the entire artifact after repair.

Fix CLI behavior so reconciliation or repair exits non-zero for unresolved repair, validation errors, malformed LLM output, missing fields, or failed final validation. Write diagnostic previews separately and atomically promote only a valid production storyboard.

**Acceptance criteria:** mocked repair runs in the real orchestrator path; failed repair cannot be marked complete; repair output is fingerprinted to creative storyboard, timing map, audio, constraints and repair policy; no success exit with invalid output.

### PTC-05 - Correct Split Narration and Graphics Validation

**Files likely involved:** `scripts/review_production_storyboard.py`, schema validator, repair validator, tests.

Validate narration at source-beat group level: ordered child narration must concatenate canonically to the complete parent narration. Do not compare each child against the full parent.

Define canonical graphics semantics. Preserve required graphics through reconciliation, but encode intended display interval/slot explicitly. A graphic marked `required: false` must not be treated as required merely because the object exists.

**Acceptance criteria:** valid split children pass narration immutability; missing, mutated, duplicated-without-policy, or mistimed required graphics fail; preview no longer reports false missing-graphic errors.

### PTC-06 - Enforce Exact Coverage Slot Geometry

**Files likely involved:** `scripts/production_storyboard.py`, reconciliation, tests.

Validate coverage by ordered boundaries, not duration sums. Require:

- first slot starts at beat start;
- last slot ends at beat end;
- no gaps or overlaps beyond one frame;
- each slot duration equals end minus start;
- slot IDs are unique;
- asset type/model/audio policy are legal;
- no unresolved placeholder or audio-only slot.

**Acceptance criteria:** equal-duration but shifted, overlapping, duplicated, reversed and gapped slots all fail; complete contiguous slots pass.

### PTC-07 - Expand Coverage Slots into Media-Plan Assets

**Files likely involved:** `scripts/compile_media_prompts.py`, generation, QA, duration reconciliation, manifest builder, budget logic, tests.

Compile each coverage slot into a concrete media-plan entry with stable lineage:

`source_beat_id → production_beat_id → coverage_slot_id → media_plan_asset_id`.

Carry exact timing, prompt/treatment, overlays, audio policy and model limits. Cost every generated slot. Ensure generation, QA, reconciliation and manifest consume every slot rather than one asset per parent beat.

**Acceptance criteria:** B003 produces four separately tracked slots, B005 four, B007 two; total budget reflects all generated assets; omission of any slot fails before generation; manifest reconstructs the exact continuous timeline.

### PTC-08 - Fix Orchestrator Ordering and Strict Adoption

**Files likely involved:** `scripts/produce.py`, gate/state modules, tests.

Use this effective order:

```text
TTS → exact timing → reconcile → targeted repair/reroute → structural review
→ compliance → compile all coverage slots → render required graphics
→ budget/review approvals → generation → QA → duration reconciliation
→ strict manifest → assembly → final QA → quality report → Telegram gate
```

Fix the production-review CLI invocation, require its report artifact, and remove creative-storyboard fallback from production compilation. Ensure graphics precede strict manifest construction.

**Acceptance criteria:** missing production storyboard or review report fails; `produce.py` cannot compile the creative storyboard as fallback; state invalidation includes repair/review/coverage-slot artifacts and downstream gates.

### PTC-09 - Real Serialized Handoff Integration Tests

**Files likely involved:** new integration tests and local fixtures.

Build tests that invoke the actual CLIs/subprocess path and exchange files on disk. Include:

- audited-project dry-run using existing audio only;
- over-limit single-sentence hero rerouted without narration mutation;
- measured safe split;
- low-confidence boundary;
- graphics-required split;
- multi-slot B-roll compilation;
- malformed repair output;
- missing compiler field;
- stale timing/audio fingerprint;
- coverage gap/overlap;
- failed review report;
- resume after upstream timing change.

Patch all network/provider boundaries to raise if called.

**Acceptance criteria:** the exact local chain `reconcile → repair/reroute → review → compile` completes for valid fixtures and fails before provider entry for every invalid fixture.

### PTC-10 - Audited-Project Corrected Preview and Sprint Exit Gate

Generate new preview artifacts without overwriting production artifacts:

- `reports/remediation/post_tts_corrective/audited_project_preview/production_storyboard.preview.json`
- `duration_coverage_preview.csv`
- `media_plan.preview.json`
- `review_report.preview.json`
- `reconciliation_preview.md`
- `field_handoff_preview.csv`

The preview must preserve all narration and the exact 146.599-second master timeline. It must resolve B001, B008 and B009 through legal visual rerouting or measured splitting, preserve all genuinely required graphics, and compile every coverage slot.

Run focused tests and the full suite. Re-run the defective MP4 QA to confirm it remains blocked.

**Acceptance criteria:** all preview artifacts validate; review passes; media-plan compilation succeeds; zero unresolved repair flags; exact coverage from `0.0` to `146.599`; no paid calls; full suite has zero unexplained failures.

## Mandatory Negative Tests

- LLM changes narration, timing, source ID or required graphics.
- LLM invents a split boundary not supplied by Python.
- Single long sentence has no safe split.
- Timing map and audio hash disagree.
- Coverage durations sum correctly but boundaries overlap or leave a gap.
- Production beat lacks a downstream-required compiler field.
- Graphics alias is missing or contradictory.
- A coverage slot is omitted from cost, generation, QA or manifest.
- Repair CLI leaves an invalid artifact but exits zero.
- Production compilation falls back to creative storyboard.
- State resume uses stale reconciliation or repair approval.

## Required Reports

Create:

- `reports/remediation/post_tts_corrective/SPRINT_STATUS.md`
- per-ticket Engineer, Auditor and Validator reports
- `reports/remediation/post_tts_corrective/FINAL_REPORT.md`
- `reports/remediation/post_tts_corrective/OPUS_READINESS.md`
- corrected audited-project preview artifacts
- full command/test log

`OPUS_READINESS.md` must say GO or NO-GO and provide evidence for every invariant.

## Definition of Done

The sprint is complete only when:

1. Existing narration and TTS are unchanged.
2. All accepted timing boundaries are measured and provenance-recorded.
3. Unsplittable hero narration is legally rerouted without rewriting audio.
4. Repair is reachable from `produce.py` and cannot set timing.
5. Production review correctly understands split narration and graphics.
6. Production storyboard and media-plan schemas interoperate through serialized files.
7. Every coverage slot is costed, generated, QA-checked and manifested independently.
8. Exact visual coverage is continuous and non-overlapping for the full master audio.
9. Invalid output cannot exit successfully or become the current production artifact.
10. The audited-project corrected preview passes review and compilation locally.
11. Full tests pass with no paid/network calls.
12. Engineer, Auditor and Validator pass every ticket.
13. `OPUS_READINESS.md` says GO.

