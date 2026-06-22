# Opus 4.8 Prompt: Independent Post-TTS Corrective Validation

You are Opus 4.8 acting as an independent Principal Software Forensics Engineer and Validation Lead for:

`/home/jacobw/YTchannel`

Perform a read-only end-to-end validation after the corrective sprint in:

`reports/remediation/post_tts_corrective/`

Do not implement fixes. Do not call paid APIs, regenerate TTS, generate media, spend credits, use production credentials, or send Telegram messages. You may create audit reports and local fixtures under a new timestamped `reports/validation/` directory.

## Decision Question

Is the real production pipeline now capable of transforming immutable final narration into a model-legal, fully covered, graphics-aware, costed and compilable visual timeline without invented timing, silent fallback, stale state, or unconsumed fields?

An overall PASS is forbidden if the actual serialized path fails, even when every unit test passes.

## Read First

Read completely:

- `AGENTS.md`
- `docs/PIPELINE.md`
- original forensic reports
- baseline-stabilization reports
- `reports/forensics/video_pipeline_audit_20260614_102622/KIRO_POST_TTS_STORYBOARD_RECONCILIATION_PROMPT.md`
- `reports/remediation/post_tts_storyboard/FINAL_REPORT.md`
- all original PST ticket reports and audited-project preview artifacts
- `reports/remediation/post_tts_storyboard/SPRINT_POST_TTS_CORRECTIVE_REMEDIATION.md`
- all corrective Engineer/Auditor/Validator reports
- `reports/remediation/post_tts_corrective/FINAL_REPORT.md`
- `reports/remediation/post_tts_corrective/OPUS_READINESS.md`
- all corrected audited-project preview artifacts
- the earlier `OPUS_4_8_END_TO_END_SYSTEM_VALIDATION_PROMPT.md`

Inspect the current code and tests directly. Reports are claims, not proof.

## Classification

Classify each requirement as:

- **CONFIRMED PASS**
- **CONFIRMED FAIL**
- **PROBABLE PASS**
- **PROBABLE FAIL**
- **NOT TESTED**
- **NOT APPLICABLE**

No overall PASS is allowed with any P0/P1 CONFIRMED FAIL, PROBABLE FAIL or NOT TESTED.

## Required Validation Phases

### 1. Trace the Actual Orchestrator

Map `produce.py` from final TTS through Telegram review. Confirm reconciliation, repair/reroute, structural review, compilation, graphics, budget gates, generation, QA, manifest and final gates are reachable in the required order.

Prove there is no creative-storyboard fallback, missing subprocess argument, ignored return code, warning-only structural failure, or success state after invalid output.

### 2. Exhaustive Field-Lineage Audit

Inventory every field in:

- creative storyboard;
- timing map/alignment evidence;
- production storyboard;
- repair request/response;
- production review report;
- media plan and coverage-slot entries;
- graphics specification/assets;
- budget and approval records;
- generation metadata;
- media QA;
- duration reconciliation;
- manifest;
- assembly metadata;
- final QA/quality report;
- state and fingerprint ledgers.

For every fully qualified field path, identify producer, authority, type, units, validation, transformations, all consumers, renames, defaults, information loss, stale risk and positive/negative tests.

Pay special attention to:

- `shot_type` versus `treatment`;
- `graphic` versus `graphics`/`overlay`;
- estimated versus measured duration fields;
- audio and timing hashes;
- source/production/slot/media asset IDs;
- coverage slot boundaries;
- model limits and audio policy;
- prompt and reference-image inheritance;
- cost per coverage slot;
- QA and manifest inclusion per slot.

### 3. Timing Authority and Narration Immutability

Prove:

- master audio bytes and hash are unchanged;
- narration text is unchanged and ordered;
- accepted split points come from measured alignment/silence evidence;
- no word-count interpolation becomes an authoritative timestamp;
- no LLM can set or change timestamps;
- ambiguous boundaries fail or reroute without lipsync splitting;
- all boundaries are accurate within one frame;
- no word is cut and no narration interval is lost, duplicated or overlapped.

Inspect B006 and B010 boundaries against the actual waveform. Inspect B001, B008 and B009 resolution and confirm no narration rewrite or TTS regeneration occurred.

### 4. Coverage Geometry and Asset Expansion

For every beat and coverage slot, verify exact start/end continuity, duration arithmetic, unique IDs, legal asset/model assignment and explicit audio policy.

Confirm every generated slot becomes one independently traceable media-plan asset and is included in budget, generation metadata, QA, reconciliation and manifest. Specifically verify expected multi-slot treatment for B003, B005 and B007.

Inject gaps, overlaps, shifted-but-equal duration sums, duplicate IDs, reversed boundaries and omitted slots. Each must fail before provider entry.

### 5. Repair and Feedback Loop

Trace the targeted repair loop end to end:

- trigger and selected beats;
- immutable context supplied;
- allowed LLM output fields;
- Python-owned timing and routing;
- malformed output behavior;
- final whole-artifact validation;
- review and state transition;
- iteration/escalation limits;
- transcript and fingerprint evidence.

Confirm feedback is actually consumed, not merely logged. Confirm failed repairs cannot overwrite valid production artifacts or exit zero.

### 6. Graphics and Prompt Policy

Verify required graphics survive reconciliation and are assigned explicit display intervals without accidental duplication. Confirm deterministic rendering occurs before strict manifest construction and rendered assets are hashed.

Confirm no text-heavy instructional content is delegated to generative video and all generated-video prompts include the required no-readable-text policy.

### 7. State, Fingerprints and Gates

Change one upstream input at a time in local fixtures and prove correct invalidation for:

- audio bytes;
- timing/alignment evidence;
- creative storyboard;
- model constraints/routing;
- repaired production storyboard;
- graphics specification/asset;
- coverage-slot media;
- QA result;
- music configuration.

Verify stale review, budget, render approval, QA, manifest and final reports cannot be reused.

### 8. Serialized Runtime Proof

Run the exact local subprocess/file path, not only direct function calls:

```text
timing/alignment artifact
→ reconciliation
→ deterministic reroute or mocked targeted repair
→ production review
→ media-plan compilation
→ graphics fixture rendering
→ budget dry-run
→ generation boundary mocked to forbid network
→ QA/reconciliation
→ strict manifest
→ local fixture assembly
→ final QA and quality report
```

All artifacts must be serialized and reread between stages. Patch provider/network functions to raise immediately if reached unexpectedly.

### 9. Audited-Project Proof

Using existing audio and no paid generation, validate the corrected preview for `using_ai_to_help_memory_retention_short`.

Require:

- exact master duration `146.599s` within probe tolerance;
- coverage begins at `0.0` and ends at audio EOF;
- no gaps or overlaps beyond one frame;
- B001/B008/B009 legally resolved without narration changes;
- B003/B005/B007 coverage slots fully compiled;
- required graphics preserved with correct timing;
- production review PASS;
- media-plan compile PASS;
- no unresolved repair flags;
- complete lineage to every planned asset.

The old defective MP4 must continue to fail final QA. Do not treat that expected failure as a new regression.

### 10. Full Regression and Documentation Drift

Run the complete local test suite. Inspect whether tests execute real handoffs or merely construct mutually compatible mock dictionaries. Identify false-green tests, stale reports, placeholder creative review, documentation drift and unimplemented claims.

## Mandatory Failure Injections

At minimum test:

1. narration mutation;
2. LLM-supplied timestamp;
3. unmeasured split boundary;
4. low-confidence alignment;
5. missing compiler-required field;
6. graphics alias mismatch;
7. false required graphic;
8. coverage gap;
9. coverage overlap;
10. omitted coverage slot;
11. slot not costed;
12. slot absent from QA or manifest;
13. stale timing/audio hash;
14. invalid repair with zero exit attempt;
15. missing production-review report;
16. creative-storyboard fallback attempt;
17. stale resume state;
18. provider call attempted before all gates pass.

## Required Outputs

Create:

`reports/validation/post_tts_corrective_validation_<timestamp>/`

with at least:

- `EXECUTIVE_SUMMARY.md`
- `SYSTEM_VERDICT.md`
- `runtime_stage_map.csv`
- `field_lineage_matrix.csv`
- `artifact_contract_matrix.csv`
- `timing_authority_matrix.csv`
- `coverage_slot_matrix.csv`
- `graphics_lineage_matrix.csv`
- `feedback_loop_matrix.csv`
- `state_gate_invalidation_matrix.csv`
- `failure_injection_results.csv`
- `test_quality_assessment.md`
- `documentation_drift.md`
- `residual_risk_register.md`
- `COMMAND_LOG.md`

Preserve raw command output and generated local fixture evidence.

## Final Verdict Rules

Return **GO** only if all of the following are CONFIRMED PASS:

1. immutable narration and audio;
2. measured timing authority;
3. legal rerouting/splitting of every over-limit interval;
4. complete, non-overlapping visual coverage;
5. serialized production-storyboard to media-plan compatibility;
6. every slot costed and tracked through manifest;
7. graphics and music requirements enforced;
8. repair/review loops reachable and fail closed;
9. state/fingerprint/gate invalidation correct;
10. local end-to-end fixture passes;
11. audited-project corrected preview passes;
12. full suite passes without false-green gaps;
13. no network, paid API, Telegram or production side effect occurred.

Otherwise return **NO-GO**, prioritize findings by severity, identify the earliest pipeline stage requiring correction, and propose narrowly scoped tickets. Do not implement them.

