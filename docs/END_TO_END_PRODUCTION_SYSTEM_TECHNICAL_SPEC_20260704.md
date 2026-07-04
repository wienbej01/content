# End-To-End Production System Technical Specification

Date: 2026-07-04  
Repository: `/home/jacobw/YTchannel`  
Purpose: objective technical description of the full video production system for external frontier-LLM architecture review and enhancement recommendations.  
Scope: research engine, scripting, LLM engagements, storyboard, database/ledger, audio rendering, video rendering, graphics, feedback loops, compliance gates, editing/assembly, publish, analytics, and operational test boundaries.

## 1. System Objective

The system is a Python-first production pipeline for educational YouTube videos. Its purpose is to transform a seed idea into a publishable video while preserving a durable audit trail of creative decisions, model calls, approvals, media artifacts, validation evidence, provider jobs, repair actions, and final deliverables.

The current production entry point is:

```bash
python3 scripts/produce_db.py
```

The live production architecture is DB-native. Runtime authority lives in the SQLite production ledger, not in loose JSON files. JSON files still exist as contracts, fixtures, legacy interchange formats, prompt inputs, and developer-facing artifacts, but the orchestrated production flow reads and writes through the database.

## 2. High-Level End-To-End Flow

```text
seed idea
  -> research
  -> script writing
  -> script review
  -> Gate A content approval
  -> canonical storyboard generation
  -> storyboard review
  -> storyboard approval
  -> TTS narration render
  -> audio timing map
  -> timing reconciliation
  -> media/render plan compilation
  -> Gate A spend approval
  -> video/provider render or artifact reuse
  -> media QA
  -> repair loop
  -> deterministic graphics compositing
  -> edit/assembly
  -> final QA
  -> Gate B final review
  -> publish
  -> analytics / learning loop
```

The canonical stage graph is defined in `scripts/stage_runner.py`:

```text
research
write_script
review_script
gate_a_content
storyboard
review_storyboard
gate_storyboard
tts
audio_timing
reconcile_timing
compile_media
gate_a_spend
generate_media
qa_media
repair
graphics_compositing
assemble
qa_final
gate_b_review
publish
analytics
```

Each stage creates a `stage_runs` record and either writes committed output or records an explicit gate/skip/blocker state. Stages with creative or media side effects also write document revisions, render units, artifacts, provider jobs, validations, approvals, cost events, or change requests.

## 3. Primary Runtime Commands

Create a production:

```bash
python3 scripts/produce_db.py create --seed "topic idea" --format short
```

Run and resume:

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

Run full tests:

```bash
python3 -m pytest -q
```

Run current focused storyboard/media integration tests:

```bash
python3 -m pytest \
  tests/test_storyboard_projection.py \
  tests/test_compile_media_from_canonical_shots.py \
  tests/test_produce_db_orchestrator.py \
  tests/test_llm_call.py \
  tests/test_sonnet_storyboard_wrapper.py \
  -q
```

## 4. Production Ledger And Database Specification

### 4.1 Database Engine

The ledger uses SQLite through `scripts/production_db.py`.

Default path:

```text
db/production.db
```

Override:

```bash
PRODUCTION_DB_PATH=/path/to/production.db
```

Connection settings:

- Foreign keys enabled.
- WAL journal mode.
- Busy timeout set to 30000 ms.
- Migrations are applied from `db/migrations/`.
- Applied migrations are tracked in `schema_migrations` with SHA-256 immutability checks.
- Pre-migration backup/restore protects against partial migrations.

### 4.2 Core Tables

The base ledger is created by `db/migrations/001_production_ledger.sql`, then extended by later migrations.

Key tables:

| Table | Purpose |
| --- | --- |
| `productions` | Production identity, seed, format/video type, code revision, status. |
| `stage_runs` | Durable stage attempts, status, input/output/error payloads. |
| `jobs` | Queue-compatible job records for stage execution. |
| `production_events` | Append-only audit events. |
| `document_revisions` | Versioned research/script/storyboard/timing/render-plan documents. |
| `document_dependencies` | Lineage between documents. |
| `source_citations` | Research/source citation records. |
| `script_segments` | Script segmentation used by storyboard, TTS, timing. |
| `creative_beats` | Storyboard beat records and visual roles. |
| `timeline_spans` | Measured timing spans aligned to narration. |
| `render_units` | Unit of media work required for a timeline span. |
| `artifacts` | Immutable local artifact registry with URI, SHA-256, size, media metadata. |
| `artifact_dependencies` | Artifact lineage. |
| `provider_jobs` | External provider submissions, polling status, request/response payloads. |
| `validations` | QA/compliance evidence for artifacts, render units, deliverables. |
| `change_requests` | Routed repair or manual-review tasks. |
| `approval_requests` | Human gates. |
| `cost_events` | Estimated/actual cost accounting. |
| `deliverables` | Assembled video outputs. |
| `publications` | Publish records and platform IDs. |
| `metric_snapshots` | Analytics/performance snapshots. |
| `outbox_messages` | Notification/outbox events. |

### 4.3 Render Unit Fields

`render_units` is the central media execution table. It combines creative intent, timing requirements, provider/render routing, audio policy, text policy, lineage, artifact status, QA status, and repair routing.

Important fields include:

| Field | Meaning |
| --- | --- |
| `timeline_span_id` | Timing span this unit covers. |
| `ordinal` | Assembly order. |
| `label` | Human-readable unit label. |
| `asset_type` | Media type such as generated video, local graphic, reused footage. |
| `model` | Provider model or local/reused marker. |
| `audio_policy` | Contract such as `HERO_SYNC_LOCKED` or `HERO_PROVIDER_AUDIO_ISLAND`. |
| `final_audio_source` | `master_narration`, `provider_audio`, `none`, etc. |
| `provider_audio_usage` | `diagnostic_only`, `final_mix`, `discarded`, etc. |
| `text_policy` | Provider-visible text policy. |
| `lipsync_required` | Whether publish-grade lipsync QA is required. |
| `visual_role` | Editorial role for publish-grade semantic-role gates. |
| `required_start_ms` / `required_end_ms` | Required timeline coverage. |
| `required_duration_ms` | Required unit duration. |
| `slot_index` / `slot_total` | Split coverage for multi-slot units. |
| `status` | `ordered`, `generating`, `generated`, `valid`, `needs_repair`, `failed`, `stale`, etc. |
| `active_artifact_id` | Artifact currently satisfying the unit. |
| `actual_render_duration_ms` | Observed artifact duration. |
| `speech_start_sample` / `speech_end_sample` | Source speech slice. |
| `generation_start_sample` / `generation_end_sample` | Provider-generation audio window. |
| `visible_start_sample` / `visible_end_sample` | Visible assembly window. |
| `master_audio_artifact_id` / `master_audio_sha256` | Master narration provenance. |
| `visual_function` | Narrative function of the visual. |
| `narrative_claim` | Claim this visual supports. |
| `information_to_show` | Specific information the viewer must see. |
| `viewer_takeaway` | Intended viewer inference. |
| `required_action` | Required subject/action/motion. |
| `distinctness_requirement` | Anti-repetition requirement. |
| `semantic_acceptance_criteria` | Post-render semantic QA criteria. |
| `render_mode` | Rendering mode, default currently `generated_video`. |
| `concept_key` / `concept_hash` | Concept identity for repetition control. |
| `graphic_text_content` / `graphic_text_hash` | Deterministic graphic text tracking. |
| `metadata_json` | Prompt, provider prompt, deterministic text spec, image/audio paths, negative prompt, and stage-specific metadata. |

### 4.4 Artifact Registry

`production_repo.register_artifact()` is the canonical artifact insertion API. It:

1. Resolves an absolute path.
2. Verifies the file exists.
3. Computes SHA-256.
4. Probes media metadata with FFprobe for media kinds.
5. Stores MIME type, size, duration, width, height, audio presence, provider job, stage run, and metadata.
6. Enforces uniqueness by production URI and SHA-256.

`production_repo.link_artifact_to_render_unit()` links a registered artifact to a render unit and advances the unit to `generated`. It rejects replacing an existing active artifact without a qualified change-request path.

## 5. Orchestration And Stage Execution

`scripts/stage_runner.py` defines `StageDefinition`:

- `name`
- `depends_on`
- `max_attempts`
- `retry_delay_sec`
- `produces_kinds`
- `consumes_kinds`
- `requires_committed_output`

The runner enforces dependency order and committed-output requirements. Document kinds define invalidation boundaries: when an upstream document changes, downstream consumers can be marked stale or blocked. Stage execution is designed to be resumable and idempotent.

`scripts/produce_db.py` maps stage names to invoker functions in `STAGE_INVOKERS`.

## 6. LLM Engagement Specification

### 6.1 Model Routing

Model routing is configured in `configs/llm_models.yaml`.

Profiles:

| Profile | Model | Purpose |
| --- | --- | --- |
| `sonnet_creative` | `kilo/deepseek/deepseek-v4-flash` | General creative/reasoning tasks. |
| `storyboard_director` | `kilo/deepseek/deepseek-v4-flash` | Historical/non-runtime storyboard profile. |
| `storyboard_director_sonnet5` | `kilo/anthropic/claude-sonnet-5` | Runtime storyboard authority through Kilo. |
| `auto_utility` | `kilo/deepseek/deepseek-v4-flash` | Mechanical/low-risk tasks. |

Creative-authority tasks include:

- script review
- storyboard generation
- storyboard review
- media prompt compilation
- brand/universe review
- audience retention review
- hook generation
- framework building
- script writing

Storyboard-authority tasks are restricted to Sonnet 5:

- storyboard generation
- storyboard repair
- storyboard creative review

`scripts/llm_call.py` enforces these constraints. For storyboard-authority tasks, weaker or unrelated models may not silently replace Sonnet 5.

### 6.2 Prompt And JSON Handling

LLM calls flow through `scripts/llm_call.py` and related wrappers. Responsibilities include:

- Resolve the model profile for a task.
- Enforce creative authority rules.
- Invoke Kilo.
- Parse JSON responses.
- Repair truncated JSON as a last resort when applicable.
- Report availability diagnostics for Sonnet 5 rather than hiding subprocess errors.

### 6.3 Storyboard LLM Engagement

`scripts/sonnet_storyboard_wrapper.py` is the production canonical-storyboard wrapper.

Inputs:

- approved script payload
- script segments
- optional source material
- prompt: `docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md`
- channel bibles under `docs/channel_universe/`
- schema: `schemas/storyboard_v2.schema.json`

Outputs:

- canonical storyboard JSON
- model metadata
- validation/repair status

Validation:

```bash
python3 scripts/validate_storyboard_v2.py <storyboard.json>
python3 scripts/storyboard_v2_validator.py <storyboard.json>
python3 scripts/review_storyboard_v2.py <storyboard.json> --dry-run --output <review.json>
```

## 7. Research Engine

Stage: `research`  
Invoker: `produce_db.invoke_research`  
Document kind: `research_brief`

Purpose:

- Convert seed idea into a grounded research brief.
- Capture sources/citations for later script and creative work.
- Store output in the ledger.

Technical flow:

1. Production is created with seed and format.
2. Research tooling collects source material.
3. Research brief is normalized into a DB document revision.
4. Source metadata is stored for lineage where available.

Expected output characteristics:

- topic framing
- source summaries
- citations
- claims and supporting facts
- material usable by the script writer

Enhancement need:

- The storyboard stage should receive structured source research directly, not just script text and channel bibles, so visual decisions can be source-specific and citation-grounded.

## 8. Script Writing And Review

Stages: `write_script`, `review_script`  
Invokers: `produce_db.invoke_write_script`, `produce_db.invoke_review_script`  
Document kinds: `script`, `script_review`

Purpose:

- Transform research into narration.
- Segment the narration for downstream storyboard, TTS, timing, and assembly.
- Review script quality before visual planning.

Technical flow:

1. `write_script` consumes `research_brief`.
2. LLM authoring creates a script payload.
3. The authoring service stores the active script revision.
4. Script segments are saved to `script_segments`.
5. `review_script` performs reviewer checks and revision as needed.
6. `gate_a_content` requires human approval before storyboard.

Compliance concerns:

- Source-grounded factual claims.
- No unsupported medical/legal/financial advice.
- No brand/universe violations.
- No script drift after approval without invalidating downstream work.

## 9. Content Approval Gate

Stage: `gate_a_content`

Purpose:

- Human acceptance of the reviewed script before expensive or high-impact creative work.

Technical behavior:

- Creates an `approval_requests` row.
- Binds approval to the active script subject.
- Blocks `storyboard` in production mode until approved.
- In `YT_TEST_MODE=1`, tests may auto-approve.

## 10. Storyboard System

Stages: `storyboard`, `review_storyboard`, `gate_storyboard`

### 10.1 Canonical Storyboard Generation

`produce_db.invoke_storyboard` is production-mode canonical-first.

Flow:

1. Load active script and script segments from DB.
2. Build approved-script metadata.
3. Call `sonnet_storyboard_wrapper.generate_canonical_storyboard()`.
4. Validate output against `schemas/storyboard_v2.schema.json`.
5. Project canonical storyboard with `storyboard_projection.project_canonical()`.
6. Save a DB storyboard document that preserves canonical fields and adds projected `beats`.

Canonical payload areas:

- contract/version metadata
- claim inventory
- narrative beats
- shots
- overlays
- segment work orders
- feedback policy
- timing policy
- approval fields
- authoring metadata

### 10.2 Projection Layer

`scripts/storyboard_projection.py` maps canonical storyboard objects into DB-compatible beats and render intent.

Responsibilities:

- Preserve canonical lineage via `canonical_shot_id`.
- Map canonical shot roles to downstream `shot_type`.
- Convert overlays into local graphic intent.
- Carry semantic acceptance criteria into `visual_intent`.
- Detect existing/pre-recorded footage and mark it as `reused`.

Important mappings:

| Canonical role | Downstream type |
| --- | --- |
| `host_present_speaking` | `hero_lipsync` |
| `host_present_cutaway` | `hero_cutaway` |
| Existing/pre-recorded footage markers | `asset_type=reused` |

The projection layer is not supposed to monkey-wrench individual storyboard items. Its job is systemic translation and validation.

### 10.3 Storyboard Review

`review_storyboard` calls `review_storyboard_v2.creative_review()` for canonical storyboards in production mode.

Purpose:

- Check creative quality.
- Check schema/contract alignment.
- Check channel/bible compliance.
- Fail closed on review failure.

### 10.4 Storyboard Approval

`gate_storyboard` creates an approval request bound to the active storyboard revision and payload hash. It blocks TTS until human approval.

## 11. Audio Rendering System

Stage: `tts`  
Invoker: `produce_db.invoke_tts`  
Provider adapter: `paid_adapters.ElevenLabsAdapter`  
Legacy script: `scripts/tts.py`

Purpose:

- Render narration audio from the approved script.
- Register master narration as an artifact.
- Preserve audio provenance for lipsync, timing, and assembly.

Technical details:

- Default TTS model in `scripts/tts.py`: `eleven_v3`.
- ElevenLabs REST/API integration is represented by `ElevenLabsAdapter`.
- `ELEVENLABS_API_KEY` is required for paid production TTS.
- Test mode forbids paid ElevenLabs calls unless a fixture audio path is supplied.
- Registered narration artifacts store SHA-256, duration, stream metadata, and stage provenance.

Audio policies used downstream include:

- `HERO_SYNC_LOCKED`: hero/lipsync timing must preserve source speech alignment.
- `HERO_PROVIDER_AUDIO_ISLAND`: provider/reused audio may be preserved as final mix for specific source-footage cases.
- B-roll and graphics policies that avoid provider speech/audio becoming final narration unless explicitly allowed.

## 12. Audio Timing And Reconciliation

Stages: `audio_timing`, `reconcile_timing`

Purpose:

- Convert narration audio into measured spans.
- Align storyboard beats with real audio timing.
- Prevent downstream media generation from relying on guessed durations.

Technical behavior:

- `audio_timing` uses the active storyboard and narration master.
- `audio_timing.build_storyboard_timing_map()` creates timing maps.
- `reconcile_timing` uses `tts_service.reconcile_storyboard_with_timing()`.
- The output is timeline spans with start/end times and creative beat linkage.

The key invariant is that `compile_media` consumes reconciled measured timing, not raw intended duration.

## 13. Media Plan Compilation

Stage: `compile_media`  
Invoker: `produce_db.invoke_compile_media`  
Compiler: `scripts/compile_media_prompts.py` and `tts_service.compile_render_plan`

Purpose:

- Convert reconciled storyboard/timing data into concrete render units.
- Decide provider eligibility, local graphics, reused footage, prompt material, audio slices, cost estimates, and render-plan artifacts.

Inputs:

- active storyboard document
- timeline spans
- TTS master artifact
- visual intent projected from canonical storyboard
- smoke/spend configuration

Outputs:

- `render_units`
- active `render_plan` document revision
- estimated cost and provider job count
- prompt metadata and deterministic graphic specs
- audio slice metadata for hero/lipsync work

Important behavior:

- `asset_type=reused` compiles to zero cost and no provider prompt generation.
- `asset_type=local_graphic` is reserved for deterministic graphics.
- Provider-eligible asset types are determined by `media_contract.is_provider_eligible_asset_type()`.
- Provider-visible prompts are checked for text-risk before spend approval.
- Render units preserve source/canonical lineage and semantic acceptance criteria.

## 14. Spend And Provider Compliance Gate

Stage: `gate_a_spend`

Purpose:

- Prevent paid provider execution unless the render plan is within configured spend and compliance boundaries.

Checks:

- Total estimated USD does not exceed `SmokeConfig.max_total_usd`.
- Provider-eligible job count does not exceed `SmokeConfig.max_paid_provider_jobs`.
- Local graphic units are not sent to paid providers.
- Provider-eligible prompts do not contain forbidden visible-text risks.
- Approval is bound to the render plan hash.

Human approval command:

```bash
python3 scripts/produce_db.py approve <production_id> gate_a_spend --pass
```

## 15. Video Rendering System

Stage: `generate_media`  
Invoker: `produce_db.invoke_generate_media`  
Provider service: `scripts/media_service.py`  
Adapters: `scripts/paid_adapters.py`

### 15.1 Provider Adapter Layer

Provider adapters implement the external paid rendering boundary.

Current adapters:

| Adapter | Class | Provider | Purpose |
| --- | --- | --- | --- |
| Higgsfield | `HiggsfieldSeedanceAdapter` | Higgsfield CLI | Video generation. |
| ElevenLabs | `ElevenLabsAdapter` | ElevenLabs REST API | TTS audio. |

Higgsfield dependency:

```json
{
  "dependencies": {
    "@higgsfield/cli": "^0.1.40"
  }
}
```

Higgsfield execution is capacity-gated and wave-submitted:

- `PROVIDER_SUBMISSION_WAVE_SIZE`, default `3`
- `HIGGSFIELD_CAPACITY_<MODEL>`
- `HIGGSFIELD_MAX_CONCURRENT`

Provider jobs are submitted with idempotency keys based on DB provider job records.

### 15.2 Generate-Media State Machine

`generate_media` performs:

1. Recover already-linked artifacts.
2. Poll in-flight `generating` units.
3. Download completed provider jobs.
4. Validate downloaded media.
5. Register artifacts.
6. Link artifacts to render units.
7. Submit new provider jobs for eligible ordered units.
8. Skip local graphics and reused units.
9. Block if required units remain incomplete.

Provider job statuses are normalized through `media_service.normalize_provider_status()`.

Failure behavior:

- Retryable provider submit/poll failures are routed for repair/resume.
- Permanent provider errors fail the stage.
- Missing artifacts or unlinked reused units block the stage.

### 15.3 Reused Footage Path

The pipeline supports storyboard-planned reuse of existing/pre-recorded footage.

Projection/compile behavior:

- `asset_type = reused`
- `model = reused`
- `audio_policy = HERO_PROVIDER_AUDIO_ISLAND`
- `lipsync_required = false`
- estimated provider cost = `0`
- provider credits = `0`

Generate behavior:

- No provider submission.
- If no artifact is linked, `generate_media` blocks as `reused_asset_unlinked`.

Known missing tool:

- There is repository API support for artifact registration/linking, but the system still needs a production-facing `produce_db.py link-artifact` command or equivalent UI to link reused render units safely.

## 16. Graphics Engine

Stage: `graphics_compositing`  
Renderer: `scripts/render_graphics.py`

Purpose:

- Render deterministic local graphics instead of sending text-heavy graphic work to video providers.
- Avoid provider-visible text rendering failures.
- Preserve graphic content and text hashes for QA.

Supported graphic renderers include:

- lower third
- key line
- stat callout
- side-by-side
- comparison card
- three-step framework
- decision tree
- cost stack
- before/after
- timeline
- annotated UI mock
- quote card
- reveal/fade animation templates
- overlay timeline

Technical behavior:

- Local graphics are rendered as local artifacts.
- `local_graphic` render units are skipped by `generate_media`.
- `graphics_compositing` registers artifacts and can record test-mode semantic-role QA.
- Publish-grade assembly can require visual role and semantic-role QA for render units.

## 17. Media QA And Compliance

Stage: `qa_media`  
QA service: `scripts/media_service.py`

Purpose:

- Validate each render unit before assembly.
- Record evidence in `validations`.
- Route failures to repair.

QA dispatch includes:

| Render method / asset | QA path |
| --- | --- |
| deterministic graphic | `_qa_local_graphic` |
| hero lipsync | `_qa_hero_lipsync` |
| generated video | `_qa_provider_video` |
| still Ken Burns | `_qa_still` |

Validation concerns:

- artifact exists
- SHA matches
- FFprobe can read media
- duration coverage
- dimensions
- audio presence/absence policy
- lipsync quality
- provider-text policy / OCR where available
- semantic role evidence
- publish-grade vs review-only contract boundary

Hero lipsync:

- Publish-grade hero units require stronger lipsync evidence.
- Test mode can record explicit fake-provider evidence only for fixture/test artifacts.
- Review-only human acceptance is explicitly not publish-grade SyncNet success.

## 18. Repair And Feedback Loops

Stage: `repair`  
Service: `media_service.run_repair_lifecycle()`  
Rerun planner: `scripts/rerun_planner.py`

Purpose:

- Convert failed validations and provider errors into targeted repairs.
- Avoid full pipeline restart when a smaller downstream rerun is sufficient.

Repair flow:

```text
validation failure or provider failure
  -> classify failure
  -> choose repair action
  -> create/update change_request
  -> route to owning stage
  -> reset or resubmit if appropriate
  -> rerun QA
  -> resolve or keep blocked
```

Repair actions include:

- resubmit provider job
- recover artifact
- rerun QA
- block for manual review
- route to a downstream gate/stage

Feedback loops exist at multiple levels:

- script review can revise script before approval
- storyboard review can block/repair canonical storyboard
- spend gate can block unsafe or too-expensive render plans
- provider job retries and repair lifecycle handle generation failures
- QA failures generate change requests
- final QA blocks Gate B
- analytics records performance data for later creative optimization

## 19. Editing And Assembly

Stage: `assemble`  
Assembly module: `scripts/assemble_db.py`

Purpose:

- Create final deliverable video from DB-approved artifacts and timing.

Technical behavior:

- Reads active render units and artifacts.
- Enforces publish-grade visual role and semantic-role QA where required.
- Enforces product/audio assembly mode.
- Distinguishes `publish_grade` from `review_only`.
- Uses FFmpeg-style deterministic assembly.
- Registers deliverable artifacts and deliverable rows.

Important gates:

- Every publish-grade render unit must declare a valid `visual_role`.
- Publish-grade render units need passing semantic-role QA.
- Review-only exceptions cannot satisfy publish-grade final requirements.

## 20. Final QA

Stage: `qa_final`  
Modules: `scripts/qa_final.py`, `assemble_db.run_final_qa()`

Purpose:

- Validate the assembled output, not individual source clips.
- Record final-cut evidence before Gate B.

Checks include:

- deliverable artifact exists
- final media is probeable
- final QA report is written
- DB contract checks pass
- all required render-unit QA evidence exists
- no unresolved publish-grade contract failures

Gate B requires the latest `qa_final` validation to pass.

## 21. Final Review Gate

Stage: `gate_b_review`

Purpose:

- Human review of the finished video before publish.

Gate B blocks if:

- no deliverable exists
- latest final QA is missing
- latest final QA status is not `pass`
- required per-unit media QA is missing or failed
- deliverable is already published

Approval command:

```bash
python3 scripts/produce_db.py approve <production_id> gate_b_review --pass
```

## 22. Publish

Stage: `publish`

Purpose:

- Mark approved, QA-passed deliverables as published and record publish events.

Current technical behavior:

- Requires `gate_b_review` pass.
- Requires deliverable status `qa_passed` or `valid`.
- Verifies the deliverable file exists.
- Updates deliverable status to `published`.
- Appends a `published` production event.

The current implementation records publication state. If external YouTube upload integration is required, it should be treated as a provider boundary with resumable upload state, platform IDs, AI disclosure enforcement, and failure recovery.

## 23. Analytics

Stage: `analytics`

Purpose:

- Record a production-level analytics snapshot and complete the audit loop.

Current recorded fields:

- total render units
- generated units
- valid units
- total artifacts
- total validations
- passing validations
- total change requests
- open change requests
- stage status timeline

Enhancement direction:

- Ingest real YouTube analytics.
- Join retention, CTR, watch time, and audience feedback to script segments, storyboard shots, render units, visual roles, and provider models.
- Feed results into prompt and planning improvements.

## 24. Compliance And Safety Boundaries

Compliance is distributed across stages rather than centralized in one file.

Key compliance boundaries:

- Research and script must be source-grounded.
- Human Gate A content approval before storyboard.
- Storyboard schema and creative review before TTS.
- Human storyboard approval before TTS and timing.
- TTS paid calls are blocked in test mode unless fixture audio is supplied.
- Spend gate enforces cap and provider-job count.
- Provider text-risk checks prevent text-heavy graphics from going to video providers.
- Local graphics are deterministic and provider-excluded.
- Reused footage cannot silently generate substitute content.
- QA evidence must exist before assembly and final review.
- Publish-grade hero sync cannot be satisfied by review-only human acceptance.
- Gate B blocks publish without final QA and human acceptance.

## 25. External Dependencies

Runtime dependencies visible in the repo:

- Python 3.
- `pyyaml` for documented Python dependency.
- `pytest` for tests.
- FFmpeg and FFprobe for media probing, slicing, and assembly.
- Kilo CLI for LLM invocation.
- Sonnet 5 access through Kilo for runtime storyboard authority.
- ElevenLabs API key for production TTS.
- Higgsfield CLI package `@higgsfield/cli` for paid video generation.

Common setup:

```bash
pip install pyyaml
npm install
```

## 26. Test Mode And Paid-Call Boundaries

`YT_TEST_MODE=1` changes behavior to keep tests deterministic and non-billable.

Test-mode behaviors include:

- no paid Sonnet/TTS/provider calls unless explicitly invoked outside tests
- deterministic storyboard fallback for tests
- auto-approval for gates where tests require it
- fake-provider lipsync QA evidence for test artifacts
- local graphics test-mode semantic-role QA where applicable

Production mode should fail closed instead of silently substituting weak models, missing artifacts, or fake QA.

## 27. Current Validation Evidence

Focused Sonnet/storyboard/media integration suite:

```text
104 passed
```

Command:

```bash
python3 -m pytest \
  tests/test_storyboard_projection.py \
  tests/test_compile_media_from_canonical_shots.py \
  tests/test_produce_db_orchestrator.py \
  tests/test_llm_call.py \
  tests/test_sonnet_storyboard_wrapper.py \
  -q
```

Docs verifier:

```text
python3 docs/verify_docs.py
Overall Status: PASS
```

Real Sonnet storyboard smoke test previously succeeded:

```text
Sonnet 5 storyboard wrapper: SUCCESS
model: kilo/anthropic/claude-sonnet-5
shots: 3
beats: 3
```

## 28. Known System Gaps

These are objective gaps or areas needing architectural review:

1. Reused footage has backend artifact registration/linking primitives, but lacks a production CLI/UI for safe operator linking of source footage to render units.
2. Storyboard receives active script and bibles, but source research should be passed in structured form to improve visual specificity and citation grounding.
3. Publish currently records DB publish state; full YouTube upload integration should be treated as an external provider subsystem if not already enabled elsewhere.
4. Analytics currently records production metadata snapshots; real platform analytics ingestion and creative-decision attribution are not complete.
5. `render_mode` defaults to `generated_video`; reused footage is currently authoritative by `asset_type=reused`, but a first-class render-mode enum may improve reporting and validation.
6. Operator-facing inspection commands should expose storyboard shots, render units, blockers, costs, approvals, artifacts, and QA evidence in one report.
7. Full paid end-to-end validation from seed through final publish is still needed after reused-artifact linking is implemented or source footage is supplied.

## 29. Recommended Frontier-LLM Review Tasks

Ask the reviewer to evaluate:

1. Whether the stage graph has correct approval placement and invalidation boundaries.
2. Whether the DB schema sufficiently captures creative lineage from research to final video.
3. Whether source research should become a first-class input to storyboard and media QA.
4. Whether the canonical storyboard schema should include explicit artifact requirements for reused footage.
5. Whether render units need stronger normalized enums for render mode, asset type, audio policy, and QA requirements.
6. Whether the repair loop should operate by render-unit only, or also by storyboard shot, timeline span, and provider job.
7. Whether compliance should be centralized into a policy engine or remain distributed by stage.
8. Whether final assembly can prove every second of output is covered by valid artifact and audio provenance.
9. Whether analytics can be joined back to storyboard shots and script claims without additional identifiers.
10. Whether the system should add a single `inspect-production` command that emits a complete evidence bundle for human operators.

## 30. Minimal Production Readiness Checklist

Before a real full-video run:

```bash
python3 scripts/production_db.py check
python3 scripts/produce_db.py status <production_id>
python3 scripts/llm_call.py --check-availability
python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q
ffmpeg -version
ffprobe -version
npm ls @higgsfield/cli
```

Operational checks:

- `ELEVENLABS_API_KEY` is present for production TTS.
- Higgsfield CLI is authenticated and has provider capacity.
- Sonnet 5 is available through Kilo.
- `PRODUCTION_DB_PATH` points to the intended DB.
- Gate approvals are understood and not bypassed in production.
- Existing/reused footage artifacts are linked before `generate_media`.
- Final QA and Gate B evidence are inspected before publish.

## 31. Bottom Line

The system is a DB-native, staged, resumable production pipeline with explicit creative, media, QA, repair, approval, and artifact records. The most important technical strengths are durable orchestration, model authority enforcement for storyboard, artifact hashing, render-unit lineage, provider-job state tracking, deterministic graphics separation, and fail-closed gates. The most important next improvements are reused-artifact operator tooling, stronger source-to-storyboard grounding, real platform analytics ingestion, a unified inspection command, and a full paid end-to-end production validation run.
