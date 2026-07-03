# S22 Context

## Current repo shape

The repo already contains a DB-native production pipeline with:

- `scripts/produce_db.py` as the DB-native orchestrator.
- `scripts/stage_runner.py` for stage dependencies, run records, and descendant invalidation.
- `scripts/authoring_service.py` for immutable research/script/storyboard document revisions and approval requests.
- `scripts/production_db.py` for migrations, productions, artifacts, stage runs, and events.
- `scripts/direct_storyboard.py` for current LLM storyboard direction.
- `schemas/storyboard_v2.schema.json` for the current directorial storyboard contract.
- `scripts/review_storyboard.py` for current structural storyboard checks.
- `scripts/compile_media_prompts.py` for production media plan compilation.
- `scripts/render_graphics.py`, `scripts/assemble.py`, and `scripts/assemble_db.py` for graphics/assembly surfaces.
- `db/migrations/001_production_ledger.sql` through `012_product_contract_audio_policy.sql`, including `render_units.actual_render_duration_ms` and `artifacts.duration_ms`.
- `validations`, `change_requests`, `render_units`, `artifacts`, `provider_jobs`, `stage_runs`, and `approval_requests` tables already exist or are extended by migrations.

## Current storyboard weakness

The current storyboard system is partially LLM-assisted but still too beat-field centric:

- Creative intent is often compressed into beat-level `visual_brief`.
- Compatibility fields such as `shot_type`, `asset_type`, `model`, `graphic`, and `graphics` are mixed with creative intent.
- B-roll and graphics are not guaranteed to be fully tied to the narrative argument, claims, references, and conclusion.
- The DB projection extracts coarse `creative_beats` but not full claims, shots, overlays, timing drift policy, or repair policy.
- Existing gates catch some structural problems but do not fully enforce creative relevance or feedback-driven reruns.

## Linked rebuild plan synthesis

The linked plan at `docs/plans/storyboard_rebuild.txt` identifies the target direction:

- The storyboard layer must become the semantic SSOT.
- LLM should own narrative visual reasoning.
- Python should own validation, approvals, timing, routing, persistence, and spend gates.
- B-roll must be semantically tied to the argument.
- Graphics must become first-class overlays or justified local graphics.
- Spend must be blocked before approved storyboard and prompt plan.
- Database must become storyboard-aware over time.

S22 refines that direction with one additional user requirement: Sonnet 5 through Kilo is the storyboard author, and Python must not design the storyboard.

## Kilo and model context

Current local files show:

- `scripts/llm_call.py` wraps Kilo via `kilo run --model <model> --format json`.
- `configs/llm_models.yaml` currently points creative profiles at `kilo/deepseek/deepseek-v4-flash`.
- Older docs mention Kiro/Claude Sonnet 4.x model names.
- S22 must not guess the final Sonnet 5 model id. `S22_T002` must verify the real accepted Kilo model id and fail if unavailable.

## Existing duration and feedback surfaces

The DB already has useful foundations:

- `artifacts.duration_ms`
- `render_units.required_duration_ms`
- `render_units.actual_render_duration_ms`
- `validations.artifact_sha256`
- `change_requests.repair_routing_stage`
- stage invalidation through `stage_runner.invalidate_document_descendants` and `production_db.invalidate_stages`

S22 must extend these rather than creating a parallel feedback store.

## Implementation boundary

These S22 files are planning artifacts only. The ticket implementation must happen one ticket at a time later. This sprint plan must not implement production code, schemas, tests, or migrations by itself.

