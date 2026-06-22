# Data Lineage Matrix — Recovery Program (S1-T01)

Inventory of all data stores, their authority class, and every reader/writer.
Classification: `AUTHORITY` | `CACHE` | `EXPORT` | `MIGRATION_INPUT` | `TEST_FIXTURE` | `OBSOLETE`.

## 1. Database stores

| Store | Path | Authority class | Writers | Readers | Notes |
|---|---|---|---|---|---|
| Production ledger | db/production.db | AUTHORITY | production_repo, tts_service, authoring_service, media_service, stage_runner, produce_db | all DB-native stages | Single system of record for productions, revisions, artifacts, render units, hero groups, timeline spans, provider jobs, validations, approvals, costs. FK enforced (PRAGMA foreign_keys=ON). |
| Clip store | db/clips.db | AUTHORITY (clip identity) | clip_db | assemble (UCI-04 path resolution), media_pack | Clip IDs, canonical paths, status, change requests. FK now enforced (D-008 fixed). |
| Content/perf log | db/leverage_mind.db | AUTHORITY (analytics) | content_db | content_db CLI | Content-unit attributes + performance metrics. FK now enforced (D-008 fixed). |
| db/test_migrate.db, db/test_produce_db.db | db/*.db | TEST_FIXTURE | tests | tests | Ephemeral test artifacts (gitignored). |

## 2. JSON files written by the orchestrator (produce_db)

| File | Authority class | Writer | Downstream reader? | Risk |
|---|---|---|---|---|
| research_brief.json | EXPORT | produce_db.invoke_research | none in DB-native path | low |
| script.json | EXPORT (legacy authority in legacy paths) | produce_db.invoke_write_script / invoke_review_script | run_episode.py, audio_timing.py, generate_hooks.py, review_media_plan.py, produce_db.invoke_storyboard (reads it back) | **HIGH — D-001**: produce_db writes script.json AND reads it back in invoke_storyboard; legacy modules treat it as authority. |
| narration/beat_timing_map.json | EXPORT (legacy authority in legacy paths) | produce_db.invoke_audio_timing | reconcile_duration.py, reconcile_production_storyboard.py, slice_continuous_lipsync.slice_hero_from_master | **HIGH — D-001**: legacy slicer reads it as authoritative. |
| media_plan.json | EXPORT (legacy authority in legacy paths) | compile_media_prompts | upscale_media, render_graphics, review_media_plan, slice_continuous_lipsync.slice_hero_from_master, assemble (legacy) | **HIGH — D-001**: legacy slicer writes it back as authority. |
| production_storyboard.json | EXPORT | direct_storyboard / reconcile | reconcile_production_storyboard (legacy) | medium |
| assembly_inputs (temp) | CACHE | produce_db.invoke_assemble | assemble | low (temp) |

## 3. Legacy JSON authority conflicts (D-001)

The DB-native path (production_db + production_repo + stage_runner) is the intended authority, but several legacy modules still READ/WRITE JSON as authority:

- `scripts/slice_continuous_lipsync.py::slice_hero_from_master` — reads `media_plan.json` + `beat_timing_map.json`, writes `media_plan.json` back. **Authority conflict.**
- `scripts/produce_db.py::invoke_storyboard` — reads `script.json` back after writing it.
- `scripts/run_episode.py` — orchestrates via `script.json`/`storyboard.json` files (legacy entry point).
- `scripts/reconcile_duration.py`, `reconcile_production_storyboard.py` — read `beat_timing_map.json`/`media_plan.json`/`storyboard.json`.
- `scripts/audio_timing.py`, `generate_hooks.py`, `review_media_plan.py` — read `script.json`.

## 4. CI gate weakness

`tools/check_forbidden_file_reads.py` only inspects AST `open("literal")` / `Path("literal").read_text()` with an allowlist. Dynamic path construction (`project_dir / "media_plan.json"`) bypasses detection. **S1-T02 must add a dynamic-read CI gate** (e.g., runtime file-read tracing in tests + a gate that detects `Path(...) / "<forbidden>"` patterns).

## 5. Authority-conflict resolution plan (S1-T02)

1. Remove live fallback reads of legacy JSON from DB-native stages (research brief, script, storyboard, timing map, media plan, manifest, gates, state).
2. Keep JSON only as exports where downstream production code does NOT read them.
3. Add runtime file-read tracing in tests; prove execution succeeds after all export JSON deleted.
4. The legacy `slice_hero_from_master` / `run_episode` entry points either migrate to DB-native inputs or are marked migration-only (not on the release path).

## 6. Migration inputs

- `scripts/migrate_legacy.py`, `import_legacy_production.py` — read legacy `state.json`/`gates.json`/clips.db/legacy DBs as MIGRATION_INPUT (one-time). Allowed.

## Open questions for S1-T02/S1-T03
- Whether `clip_db` and `content_db` should be folded into the unified production ledger or remain separate authority stores with enforced FK (current: separate, FK now on).
- Migration rollback/backup/restore procedure (D-007) — not yet implemented; S1-T03.
