# Sonnet Storyboard Production Pipeline Handoff

Date: 2026-07-04  
Repository: `/home/jacobw/YTchannel`  
Audience: frontier LLM reviewer asked to recommend systemic enhancements  
Scope: active DB-native YouTube production pipeline, including the new Sonnet 5 canonical storyboard method and its downstream video-production integration.

## Executive Summary

The active production system is a Python-first, DB-native educational YouTube video pipeline. `scripts/produce_db.py` is the production orchestrator. It runs an approved seed through research, script, Sonnet-authored storyboard, review gates, text-to-speech, timing reconciliation, render planning, media generation, QA, repair, graphics compositing, assembly, final QA, publish, and analytics.

The most important recent architectural change is the storyboard stage:

- Production storyboard authoring is now performed by Sonnet 5 through Kilo using the profile `storyboard_director_sonnet5`.
- The model produces a canonical `storyboard_v2` payload, validated against `schemas/storyboard_v2.schema.json`.
- Python does not make creative shot decisions in production mode. Python loads context, invokes the model, validates the response, projects the canonical storyboard into DB-compatible beats, and enforces gates.
- The projection layer preserves canonical lineage and maps canonical shot roles into downstream render-unit intent.
- Existing/pre-recorded footage can now be projected as `asset_type=reused`, compiled at zero cost, skipped by provider generation, and blocked fail-closed until a real source artifact is linked.

The system is integrated through the render-plan stage and has focused test coverage. It is not yet proven by a full paid end-to-end production run after real reused-footage artifacts are registered.

## Current Readiness Verdict

Ready for:

- Real Sonnet storyboard generation from a DB-backed approved script.
- Canonical storyboard validation and non-mutating creative review.
- Projection from canonical shots into DB-compatible storyboard beats.
- Render-plan compilation from canonical projected beats.
- Provider spend gating that excludes local and reused assets.
- Provider generation that skips `local_graphic` and `reused` units.
- Fail-closed handling for unlinked reused footage.
- Focused regression testing of storyboard projection, media compilation, orchestration, and LLM availability diagnostics.

Not yet fully proven:

- A complete paid/full video run using the new storyboard method from `create` through `publish`.
- A user-facing CLI to link or register existing footage artifacts for `reused` render units.
- Frontier-grade review of whether the canonical storyboard contract contains every field the downstream video pipeline should need.
- Analytics-driven learning loop on videos produced with the new storyboard path.

## Primary Production Entry Points

Create a production:

```bash
python3 scripts/produce_db.py create --seed "topic idea" --format short
```

Run or resume:

```bash
python3 scripts/produce_db.py run <production_id>
python3 scripts/produce_db.py resume <production_id>
python3 scripts/produce_db.py run <production_id> --from-stage storyboard
python3 scripts/produce_db.py status <production_id>
```

Approve gates:

```bash
python3 scripts/produce_db.py approve <production_id> gate_a_content --pass
python3 scripts/produce_db.py approve <production_id> gate_storyboard --pass
python3 scripts/produce_db.py approve <production_id> gate_a_spend --pass
python3 scripts/produce_db.py approve <production_id> gate_b_review --pass
```

Direct real-LLM storyboard smoke test:

```bash
python3 scripts/sonnet_storyboard_wrapper.py \
  --script scripts/sample_script.json \
  --output /tmp/canonical_storyboard_real_llm.json \
  --verbose \
  --timeout 600
```

Storyboard validators:

```bash
python3 scripts/validate_storyboard_v2.py /tmp/canonical_storyboard_real_llm.json
python3 scripts/storyboard_v2_validator.py /tmp/canonical_storyboard_real_llm.json
python3 scripts/review_storyboard_v2.py /tmp/canonical_storyboard_real_llm.json --dry-run --output /tmp/canonical_storyboard_real_llm.review.json --verbose
```

## Core Architecture

The pipeline is DB-native. Files are artifacts, fixtures, or developer interchange formats; they are not the source of truth for live orchestration.

Key modules:

| Module | Responsibility |
| --- | --- |
| `scripts/produce_db.py` | CLI and stage invokers for DB-native production. |
| `scripts/stage_runner.py` | Stage registry, dependency graph, idempotent stage execution, committed-output checks. |
| `scripts/production_db.py` | Ledger schema, migrations, DB connection, production state. |
| `scripts/production_repo.py` | Artifact and render-unit repository helpers. |
| `scripts/authoring_service.py` | Research/script/storyboard document revisions and active revision lookup. |
| `scripts/llm_call.py` | Model routing, Kilo invocation, storyboard authority enforcement, Sonnet availability diagnostics. |
| `scripts/sonnet_storyboard_wrapper.py` | Canonical storyboard prompt assembly, Kilo call, schema validation, repair loop. |
| `scripts/storyboard_projection.py` | Canonical storyboard to legacy/DB beat projection. |
| `scripts/review_storyboard_v2.py` | Canonical creative review, optionally real LLM or dry-run. |
| `scripts/compile_media_prompts.py` | Media plan compiler from storyboard beats. |
| `scripts/media_contract.py` | Provider eligibility, audio policy, text-risk, and media contract rules. |
| `scripts/media_service.py` | Provider job state machine, QA evidence, repair classification, fake-provider test hooks. |
| `scripts/render_graphics.py` | Deterministic local graphic rendering. |
| `scripts/assemble_db.py` | DB-native final assembly and Gate B request support. |
| `scripts/qa_final.py` | Final deliverable QA evidence. |

The production database records at least these authority objects:

- `productions`: seed, format, status, metadata.
- `stage_runs`: stage attempts, status, result/error payloads.
- `document_revisions`: research, script, storyboard, timing, render-plan and review documents.
- `timeline_spans`: measured audio/timing alignment.
- `render_units`: required visual/audio work units.
- `provider_jobs`: external provider submissions and job state.
- `artifacts`: file outputs, checksums, media metadata.
- `validations`: contract and QA evidence.
- `approval_requests`: human approval gates.
- `change_requests`: routed repair/remediation items.

## Stage-By-Stage Process

### 1. `research`

Purpose: produce a grounded research brief for the topic.

Method:

- Implemented by `produce_db.invoke_research`.
- Uses the research stage tooling and saves a research brief via the authoring service.
- Output is a `document_revisions` row of kind `research_brief`.

Enhancement target:

- Ensure source capture is comprehensive enough to feed storyboard authoring directly, not only script authoring.

### 2. `write_script`

Purpose: create the narration script.

Method:

- Uses `scripts/write_script.py` stage behavior through the DB invoker.
- Stores the active script as a DB document revision.
- Script segments become the authoritative source for TTS and storyboard authoring.

### 3. `review_script`

Purpose: validate and revise the script before visual planning.

Method:

- Uses review-loop style evaluation and revision.
- Produces review evidence and an approved active script revision.

### 4. `gate_a_content`

Purpose: human approval of the reviewed script before storyboard authoring.

Method:

- Creates an `approval_requests` record for the active script.
- Blocks `storyboard` until approved in production mode.

Approval command:

```bash
python3 scripts/produce_db.py approve <production_id> gate_a_content --pass
```

### 5. `storyboard`

Purpose: produce a complete canonical visual plan.

Production method:

- `produce_db.invoke_storyboard` loads the active script and script segments from the DB.
- It calls `sonnet_storyboard_wrapper.generate_canonical_storyboard`.
- The wrapper uses the runtime profile `storyboard_director_sonnet5` from `configs/llm_models.yaml`.
- The model is `kilo/anthropic/claude-sonnet-5`.
- The director prompt is `docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md`.
- Channel grounding comes from `docs/channel_universe/`, including bibles, prompt rules, QA rubric, reference asset manifest, and constraints.
- Output must match `schemas/storyboard_v2.schema.json`.
- The canonical storyboard is projected by `storyboard_projection.project_canonical`.
- The saved DB storyboard preserves canonical fields and adds projected `beats`.

Canonical payload concepts:

- `storyboard_contract_version`
- `claim_inventory`
- `narrative_beats`
- `shots`
- `overlays`
- `segment_work_orders`
- `feedback_policy`
- `timing_policy`
- `approval`
- `_authoring_metadata`

Projection outputs:

- DB-compatible `beats`.
- `canonical_shot_id` lineage.
- `visual_intent` fields used by media compilation.
- `shot_type` mapping for downstream contracts.
- Reused-footage markers when the canonical shot says existing footage should be used.

Important role mapping:

- `host_present_speaking` maps to `hero_lipsync`.
- `host_present_cutaway` maps to `hero_cutaway`.
- Existing or pre-recorded footage markers map to `asset_type=reused`.

Test mode:

- `YT_TEST_MODE=1` keeps a deterministic no-LLM storyboard path so tests do not call paid or external models.

### 6. `review_storyboard`

Purpose: validate the canonical storyboard without mutating it.

Production method:

- If the storyboard has `storyboard_contract_version` and the environment is not `YT_TEST_MODE=1`, `produce_db.invoke_review_storyboard` calls `review_storyboard_v2.creative_review`.
- A failing canonical creative review blocks the stage.
- Passing review records summary evidence and allows `gate_storyboard`.

### 7. `gate_storyboard`

Purpose: human approval of storyboard before TTS and media spend.

Method:

- Approval request is bound to the active storyboard revision and payload hash.
- Blocks `tts` until approved.

Approval command:

```bash
python3 scripts/produce_db.py approve <production_id> gate_storyboard --pass
```

### 8. `tts`

Purpose: create the narration master audio.

Method:

- Uses the active script.
- Production path uses the configured TTS provider, normally ElevenLabs.
- Test/fixture paths can avoid paid calls.
- Registers narration artifacts in the DB.

### 9. `audio_timing`

Purpose: map narration audio to storyboard/script timing.

Method:

- Uses `scripts/audio_timing.py`.
- Builds timing maps from the narration master and storyboard/script beat structure.
- Stores timing output as a DB document revision and/or timing records.

### 10. `reconcile_timing`

Purpose: align creative beats with measured audio spans.

Method:

- Uses `tts_service.reconcile_storyboard_with_timing`.
- Ensures compile-media consumes measured spans, not guessed storyboard duration.
- Produces timeline spans and timing reconciliation evidence.

### 11. `compile_media`

Purpose: convert visual intent and timing spans into render units and a render plan.

Method:

- Uses `tts_service.compile_render_plan` and media-plan compilation logic.
- Reads the active storyboard and timing reconciliation.
- Creates DB `render_units`.
- Carries canonical `visual_intent` fields into render units.
- Honors `asset_type=reused` and `asset_type=local_graphic`.
- Estimates cost and provider credit usage.

Key canonical-to-render fields:

- `visual_function`
- `concept_key`
- `concept_hash`
- `narrative_claim`
- `information_to_show`
- `viewer_takeaway`
- `required_action`
- `distinctness_requirement`
- `semantic_acceptance_criteria`

Reused-footage behavior:

- `asset_type` becomes `reused`.
- `model` becomes `reused`.
- `audio_policy` becomes `HERO_PROVIDER_AUDIO_ISLAND`.
- Cost and provider credits are zero.
- The render unit is not provider eligible.

### 12. `gate_a_spend`

Purpose: human approval of paid media work.

Method:

- Counts only provider-eligible render units through `media_contract.is_provider_eligible_asset_type`.
- Excludes `local_graphic` and `reused` units from provider-job estimates.
- Blocks `generate_media` until approved.

Approval command:

```bash
python3 scripts/produce_db.py approve <production_id> gate_a_spend --pass
```

### 13. `generate_media`

Purpose: submit provider jobs and register generated artifacts.

Method:

- Iterates required render units.
- Skips `local_graphic`; those are created in `graphics_compositing`.
- Skips `reused`; those must already point to active existing artifacts.
- Submits provider jobs for provider-eligible units through `media_service` / `paid_adapters`.
- Records provider jobs, artifacts, validation state, and blockers.

Fail-closed reused behavior:

- If a reused render unit has no active artifact, the stage blocks with `reused_asset_unlinked`.
- It does not monkey-wrench the storyboard item or silently regenerate a reused shot.
- The missing systemic piece is a proper artifact-linking CLI or workflow.

### 14. `qa_media`

Purpose: validate per-unit media output.

Method:

- Uses media contract QA.
- Records validation evidence.
- Routes failures into `change_requests`.
- Hero lipsync paths include lipsync QA; test mode can record fake-provider compensated evidence for fixture artifacts.

### 15. `repair`

Purpose: classify and route fixes from failed validations.

Method:

- Uses repair classification in `media_service` and related tests.
- Routes downstream reruns using `scripts/rerun_planner.py`.
- Current downstream shot invalidation includes `graphics_compositing` so local graphics are regenerated when needed.

### 16. `graphics_compositing`

Purpose: create deterministic local graphic artifacts.

Method:

- Handles `local_graphic` render units.
- Registers artifacts and test-mode semantic role QA where appropriate.
- Does not submit provider jobs.

### 17. `assemble`

Purpose: build the deliverable video.

Method:

- Uses DB render units and registered artifacts.
- Final media assembly is deterministic and FFmpeg-backed.
- Requires upstream artifacts and validations to be in a usable state.

### 18. `qa_final`

Purpose: validate the assembled deliverable.

Method:

- Runs final-cut QA.
- Records evidence in DB.
- Blocks Gate B if final-cut evidence is insufficient.

### 19. `gate_b_review`

Purpose: human approval of the final deliverable before publish.

Method:

- Requests approval for the latest deliverable.
- Blocks if the deliverable is already published or if final QA evidence is not acceptable.

Approval command:

```bash
python3 scripts/produce_db.py approve <production_id> gate_b_review --pass
```

### 20. `publish`

Purpose: publish the approved deliverable.

Method:

- Uses publish-service behavior and records external publish identifiers and state.
- Should only run after Gate B passes.

### 21. `analytics`

Purpose: complete the production learning loop.

Method:

- Ingests or records post-publish performance data.
- Intended to support later creative-performance analysis by script segment, storyboard decision, render method, and retention outcome.

## LLM Runtime Authority

Runtime storyboard authority is intentionally narrow:

```yaml
profile: storyboard_director_sonnet5
model: kilo/anthropic/claude-sonnet-5
```

Rules:

- Storyboard generation, repair, and creative review tasks may not silently fall back to weaker or unrelated models.
- `scripts/llm_call.py` enforces storyboard authority tasks.
- Sonnet availability checks report diagnostic errors from `kilo models` rather than hiding subprocess failures.

This matters because the storyboard is the creative source of truth. If the model is unavailable, the pipeline should fail closed rather than produce low-grade visual plans.

## Existing/Reused Footage Handling

The canonical storyboard can ask for existing baked-in-audio or pre-recorded footage. The projection layer detects markers such as:

- `existing baked-in-audio footage`
- `existing recorded footage`
- `pre-recorded baked-in-audio footage`
- `no new generation required`
- `not a generation task`

Projected behavior:

- `asset_type = reused`
- `model = reused`
- `audio_policy = HERO_PROVIDER_AUDIO_ISLAND`
- `lipsync_required = false`
- `reuse.allowed = true`
- cost = `0`
- provider credits = `0`
- no provider submission

Systemic gap:

- The pipeline needs a formal command or UI to link a reused render unit to an existing artifact with path, checksum, duration, audio policy, and provenance.
- Until that exists, `generate_media` correctly blocks unlinked reused units instead of creating synthetic success.

Recommended artifact-linking shape:

```bash
python3 scripts/produce_db.py link-artifact <production_id> <render_unit_id> \
  --path /abs/path/to/source.mp4 \
  --role reused \
  --audio-policy HERO_PROVIDER_AUDIO_ISLAND
```

The command should validate file existence, duration, media streams, checksum, and required render-unit coverage before marking the artifact active.

## Validation Evidence

Focused regression suite for the Sonnet/canonical integration:

```text
python3 -m pytest \
  tests/test_storyboard_projection.py \
  tests/test_compile_media_from_canonical_shots.py \
  tests/test_produce_db_orchestrator.py \
  tests/test_llm_call.py \
  tests/test_sonnet_storyboard_wrapper.py \
  -q

104 passed
```

Earlier validator/engineer repair loop:

```text
336 focused tests passed
```

Real LLM storyboard smoke:

```text
python3 scripts/sonnet_storyboard_wrapper.py \
  --script scripts/sample_script.json \
  --output /tmp/canonical_storyboard_real_llm.json \
  --verbose \
  --timeout 600

Sonnet 5 storyboard wrapper: SUCCESS
model: kilo/anthropic/claude-sonnet-5
shots: 3
beats: 3
```

Real artifact validation:

```text
python3 -m json.tool /tmp/canonical_storyboard_real_llm.json
python3 scripts/validate_storyboard_v2.py /tmp/canonical_storyboard_real_llm.json
python3 scripts/storyboard_v2_validator.py /tmp/canonical_storyboard_real_llm.json
python3 scripts/review_storyboard_v2.py /tmp/canonical_storyboard_real_llm.json --dry-run --output /tmp/canonical_storyboard_real_llm.creative_review_dry_run.json --verbose
```

Observed projection/compile behavior on the real artifact after reused-footage handling:

```text
projected_asset_types: ['reused', 'reused', 'reused']
projected_models: ['reused', 'reused', 'reused']
compile_errors: []
media_asset_types: ['reused', 'reused', 'reused']
media_models: ['reused', 'reused', 'reused']
totals:
  est_usd: 0.0
  est_higgsfield_credits: 0.0
  budget_cap_usd: 60.0
  beats_requiring_generation: 0
  beats_local_or_reused: 3
  pct_zero_cost_beats: 100.0
```

## Known Gaps And Enhancement Targets

High priority:

- Add a first-class reused-artifact registration/linking command and tests.
- Run a complete paid or production-shaped full-video pass after reused artifacts can be linked.
- Add a DB enum or explicit `render_mode=reused` if future reporting should distinguish reused from generated units without inferring from `asset_type`.
- Feed source research artifacts directly into `produce_db.invoke_storyboard`, not only script text and bibles, so storyboard decisions can cite source-specific visual facts.
- Add an operator-facing storyboard inspection command that prints canonical shots, projected beats, reused requirements, cost summary, and gate status.

Medium priority:

- Add a canonical storyboard diff tool for comparing two Sonnet runs by claim, shot, visual function, and downstream cost.
- Add generated media prompt tracebacks from render units back to canonical shot IDs.
- Expand final QA to assert that reused footage artifacts preserve intended audio policy and timing.
- Add analytics reports that join retention metrics back to canonical storyboard choices.
- Add a production readiness checklist command that verifies model availability, TTS/provider credentials, FFmpeg/FFprobe, DB migration state, and all gate statuses.

Frontier-model review questions:

- Does the canonical storyboard schema contain enough detail for robust video production, or should it explicitly include source-footage link requirements, camera continuity tokens, reference-asset IDs, and motion constraints?
- Should reused footage be represented as a first-class render mode, a first-class artifact requirement, or both?
- Which storyboard fields should be immutable after human approval, and which downstream fields can be repaired without re-approval?
- What validation should happen before `gate_storyboard` so the human reviewer sees all future media blockers, including reused-artifact gaps?
- How should the system balance model-authored creativity against deterministic Python safety checks without Python re-authoring creative content?
- What telemetry should be collected from each production to make the analytics loop actionable for future storyboard prompts?

## Suggested Next End-To-End Test

After implementing artifact linking or manually registering reused artifacts through the DB repository layer, run:

```bash
python3 scripts/produce_db.py create --seed "use AI to manage your time efficiently" --format short
python3 scripts/produce_db.py run <production_id>
python3 scripts/produce_db.py approve <production_id> gate_a_content --pass
python3 scripts/produce_db.py resume <production_id>
python3 scripts/produce_db.py approve <production_id> gate_storyboard --pass
python3 scripts/produce_db.py resume <production_id>
python3 scripts/produce_db.py approve <production_id> gate_a_spend --pass
python3 scripts/produce_db.py resume <production_id>
python3 scripts/produce_db.py approve <production_id> gate_b_review --pass
python3 scripts/produce_db.py resume <production_id>
```

Expected blockers:

- If Sonnet/Kilo is unavailable, storyboard should fail closed with a diagnostic.
- If reused footage is requested but no artifact is linked, `generate_media` should block with `reused_asset_unlinked`.
- If provider credentials or capacity are missing, provider units should block without corrupting DB state.
- If QA fails, repair should route to the owning stage instead of requiring full pipeline restart.

## Bottom Line

The storyboard method is integrated into the active production pipeline at the orchestration, validation, projection, compile-media, spend-gate, and generate-media layers. The system is now suitable for a frontier LLM architecture review. The most important remaining production hardening item is not more storyboard monkey-wrenching; it is a systemic reused-artifact registration workflow plus a complete full-video run using the DB-native stage graph.
