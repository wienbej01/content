# Contract Audit — S22_T001

## Objective

Read-only audit of current storyboard generation path, review path, media compiler dependencies, DB document/creative_beats projection, stage dependencies, artifact duration fields, validation/change-request surfaces, and exact gaps S22 must close.

## Files Inspected

| File | Role |
|------|------|
| `scripts/direct_storyboard.py` | Current LLM-assisted storyboard director (bible-grounded) |
| `schemas/storyboard_v2.schema.json` | Current storyboard v2 JSON schema |
| `scripts/review_storyboard.py` | Current structural storyboard validator + G2 gate |
| `scripts/compile_media_prompts.py` | Current media prompt compiler from storyboard v2 |
| `scripts/produce_db.py` | DB-native production orchestrator |
| `scripts/authoring_service.py` | Document revision/approval service (research, script, storyboard) |
| `scripts/stage_runner.py` | Stage registry, dependency graph, invalidation |
| `docs/plans/storyboard_rebuild.txt` | Linked rebuild plan |
| `db/migrations/001_production_ledger.sql` through `012_product_contract_audio_policy.sql` | DB migrations (via S22_CONTEXT.md references) |

## 1. Current Storyboard Generation Path

### 1a. `direct_storyboard.py` — LLM-assisted director

- Invokes `llm_call.py` with profile `storyboard_director` (prompt: `build_director_prompt`).
- Prompt includes: approved script JSON, source research text, channel bibles (UNIVERSE_BIBLE, JAMES_CHARACTER_BIBLE, RECORDING_STUDIO_LIBRARY, TECHNICAL_BIBLE, FORBIDDEN_PATTERNS).
- Output: JSON array of beat objects with `beat_id`, `shot_type`, `est_duration_sec`, `visual_brief`, `narrative_function`, `graphic`, etc.
- Post-processing: `hydrate_beats()` fills routing/mechanical fields deterministically from `shot_type` (model, asset_type, prompt_class, audio_mode, crop_safety, costs).
- Validation: `validate_director_output()` checks shot type validity, model/asset consistency, anachronism guard, duration limits, text-surface policy, required fields, narrative function specificity.

**Key observations:**
- LLM-authored creative content (visual_brief, shot_type selection) is created by the LLM, not Python.
- Python hydrates routing fields deterministically (acceptable per S22_Layer2).
- No claim inventory, no segment work orders, no overlay timeline, no timing drift policy.
- `visual_brief` is the primary prompt carrier; b-roll instructions are embedded in visual_brief text rather than structured `narrative_alignment` fields.

### 1b. `produce_db.py` — DB-native storyboard (Option B)

- `invoke_storyboard()` at line 620: deterministic, review_storyboard-band-compliant shot mix.
- No LLM call; purely Python-derived using `_assign_shot_mix()` (line 396).
- Shot types assigned by index rotation from `_BODY_POOL`.
- `visual_brief_for()` generates generic briefs from narration first clause.
- `_visual_intent_for()` creates R7 B-roll semantic contract (structured dict).

**Key observations:**
- This is the current production path (DB-native, no LLM storyboard authorship).
- S22 requires Sonnet 5 to author the storyboard; this path must be replaced for creative authority.
- `visual_brief_for()` at line 469 is Python-authored creative content — exactly the pattern S22 forbids.
- `_assign_shot_mix()` uses deterministic index-based rotation — confirmed failure pattern from `docs/plans/storyboard_rebuild.txt`.

## 2. Current Storyboard Review Path

### 2a. `review_storyboard.py` — Python validator

- Validates: schema_version, shot-mix bands (hero%, broll%, graphics%), anti-patterns, trigger coverage, coverage minimums.
- Checks: continuous hero chain length, consecutive identical shot types, banned models, front-facing close-up under voiceover, empty visual_brief, generated readable text requests, generic narrative function for b-roll.
- Output: `blocking_issues[]`, `warnings[]`, `fixes[]`, `may_proceed` boolean.
- Gate recording via `record_gate()`.

**Key observations:**
- Good structural/technical validation but no creative quality checks.
- Does not validate: narrative alignment, B-roll specificity, overlay purpose, claim refs, segment work orders, timing drift policy.
- S22 must extend this to enforce semantic fields from canonical storyboard.

### 2b. `produce_db.py` — `invoke_review_storyboard()` (line 683)

- Uses `review_loop` from `review.py` with a simple in-place reviser.
- Storyboard review in DB-native path is a Python structural pass.

## 3. Current Media Compiler Dependencies

### 3a. `compile_media_prompts.py`

- Consumes storyboard v2 `beats[]`.
- For each beat: compiles positive/negative prompt, checks vagueness lint, enforces text-surface policy, computes costs.
- `_compose_positive()` at line 347: builds prompt from `visual_brief` + palette/lighting/identity boilerplate.
- Readable text detection: reroutes to `local_graphic` if visual_brief requests readable text.
- Vagueness lint: checks for specific subject, action, era/place in generated b-roll prompts.

**Key observations:**
- Still reads `visual_brief` as primary source — S22_T014 must ensure canonical shots are the only source.
- Text-surface policy enforcement is solid but needs to work from structured overlay data rather than keyword scanning.
- No overlay plan compilation — overlays are embedded in beat field `overlay`/`graphics` as dicts, not first-class timeline objects.

## 4. Current DB Document and `creative_beats` Projection

### 4a. `authoring_service.py`

- `save_storyboard()` (line 168): saves storyboard_payload as document revision, extracts `creative_beats` rows.
- Creative beat fields stored: `label`, `shot_type`, `visual_role`, `visual_intent_json`, `graphics_json`, `narration_text_sha256`.
- `get_storyboard()`: returns full active payload.
- `get_creative_beats()`: returns list of beat rows.

**Key observations:**
- `visual_intent_json` and `graphics_json` are stored as JSON blobs — flexible but opaque to schema enforcement.
- No claims, narrative beats, shots[], overlays[], segment work orders, timing policy, or feedback policy tables.
- DB is not storyboard-aware at the canonical level S22 requires.

### 4b. `stage_runner.py` — Document revisions

- `save_document_revision()` (line 414): versioned, superseding document revisions with `payload_json` and `payload_sha256`.
- `invalidate_document_descendants()`: transitive document/approval/stage-run invalidation via `document_dependencies` table.
- Already supports the document lineage model S22 needs.

## 5. Current Stage Dependencies

### 5a. `stage_runner.STAGE_REGISTRY` (line 45)

Stages in canonical order as of S21:
```
research -> write_script -> review_script -> gate_a_content ->
storyboard -> review_storyboard -> tts -> audio_timing ->
reconcile_timing -> compile_media -> gate_a_spend ->
generate_media -> qa_media -> repair ->
graphics_compositing -> assemble -> qa_final ->
gate_b_review -> publish -> analytics
```

**Key observations:**
- `storyboard` and `review_storyboard` exist but are Python-deterministic.
- No `storyboard_generation`, `storyboard_validation`, `storyboard_creative_review`, `gate_storyboard` stages yet.
- S22_T006 will add Sonnet storyboard wrapper; S22_T010 will add repair loop; S22_T011 will add creative review.
- Stage order already has `storyboard` positioned after `gate_a_content` — correct per S22_STRUCTURAL_FRAMEWORK.

## 6. Current Artifact Duration and Render-Unit Duration Fields

### 6a. DB fields (from migrations 001-012)

- `artifacts.duration_ms` — observed duration of TTS or generated media artifacts.
- `render_units.required_duration_ms` — planned duration per render unit.
- `render_units.actual_render_duration_ms` — observed duration after generation.
- `render_units.metadata_json` — flexible metadata blob.

**Key observations:**
- Duration fields exist for both planned and observed values.
- No per-shot `min_usable_duration_sec` / `max_usable_duration_sec` or `duration_drift_policy` storage yet.
- `compile_media_prompts.py` propagates `duration_target_sec` from beats but does not enforce drift policies.

## 7. Current Validation/Change-Request Surfaces

### 7a. `validations` table

- Stores validation results with `artifact_sha256` linkage.
- Used by review_storyboard and compile_media for gate recording.

### 7b. `change_requests` table

- Has `repair_routing_stage` field for routing repair to specific stages.
- S22_T019 will add compliance feedback ingestion using this table.

### 7c. `approval_requests` table

- Gate-based approval system with `gate_name`, `subject_type`, `subject_sha256`, `status`.
- `gate_a_content` and `gate_a_spend` already exist.
- `gate_storyboard` does not yet exist (S22_T012).

## 8. Exact Gaps S22 Must Close

| # | Gap | Ticket(s) | Severity |
|---|-----|-----------|----------|
| 1 | No Sonnet 5 Kilo profile enforcement | T002 | BLOCKER |
| 2 | Python-authored creative storyboard content (visual_brief_for, _assign_shot_mix) | T003-T006 | BLOCKER |
| 3 | No canonical storyboard schema with claims, beats, shots, overlays, work orders | T003 | HIGH |
| 4 | No segment work order requirement | T007 | HIGH |
| 5 | No narrative alignment validation for B-roll | T008 | HIGH |
| 6 | No timing/drift contract validation | T009 | HIGH |
| 7 | No Sonnet repair loop for validation failures | T010 | HIGH |
| 8 | No Sonnet creative review gate | T011 | HIGH |
| 9 | No human `gate_storyboard` approval stage | T012 | HIGH |
| 10 | No canonical-to-legacy projection layer | T013 | HIGH |
| 11 | Media compiler still consumes raw `visual_brief` | T014 | BLOCKER |
| 12 | No overlay timeline compilation from canonical overlays | T015 | HIGH |
| 13 | Overlays not integrated into render/assembly timeline | T016 | MEDIUM |
| 14 | Observed artifact durations not written back systematically | T017 | MEDIUM |
| 15 | Duration drift not detected or resolved | T018 | MEDIUM |
| 16 | Compliance feedback not ingested as change requests | T019 | MEDIUM |
| 17 | Downstream invalidation/rerun not planned | T020 | MEDIUM |
| 18 | Regression fixtures for known failure modes | T021 | MEDIUM |
| 19 | No final end-to-end dry-run gate | T022 | HIGH |

## 9. Model Assumptions (Recorded as Assumptions, Not Facts)

- Sonnet 5 model ID through Kilo is assumed to be discoverable via `kilo model list` or equivalent. S22_T002 will verify.
- The `storyboard_director` profile in `configs/llm_models.yaml` points at DeepSeek v4 Flash — this must be replaced by a Sonnet 5 profile for runtime storyboard authorship.
- No Kilo `--format json` compatibility issues are expected for the Sonnet 5 output, but S22_T006 will need to handle JSON parsing defensively.
- Existing `llm_call.py` infrastructure is expected to work with Sonnet 5 through Kilo's generic model invocation.
- Duration fields in `artifacts` and `render_units` tables are sufficient for drift detection without new migrations.
- `change_requests` table can accept compliance findings without schema changes.
