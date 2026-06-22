# Database-Centered Production Implementation Status

**Date:** 2026-06-16  
**Governing plan:** `docs/plans/DB_CENTERED_VIDEO_PRODUCTION_SYSTEM_PLAN.md`

## Implemented

### Sprint 0 foundation

- Versioned SQL migration framework.
- Unified schema for productions, jobs, documents, timeline, render units, artifacts,
  validations, approvals, costs, deliverables, publications, analytics, and outbox messages.
- SQLite WAL, foreign keys, busy timeout, migration checksums, and integrity checks.
- Transactional repository API in `scripts/production_db.py`.
- Status/audit CLI: `init`, `create`, `show`, `list`, `events`, `blockers`, `enqueue`, `lease`,
  and `check`.

### Sprint 1 migration bridge

- Idempotent importer for project state, gates, JSON documents, media/report artifacts,
  `clips.db`, and `leverage_mind.db` metadata.
- `produce.py` dual-writes stage state and invalidation.
- `gates.py` dual-writes approvals and records stale approvals on hash mismatch.
- `clip_db.py` dual-writes clip orders, generation, artifact versions, QA evidence,
  invalidation, change requests, and resolutions.
- Immutable artifact versions: a changed checksum creates a new artifact row.

### Sprint 2 — Identity, timeline, and artifact authority (ID-201..ART-204)

**`scripts/production_repo.py`**

- **TimelineSpanService** (`commit_timeline_spans`): no-gap/no-overlap validated timeline spans,
  integer ms enforcement, supersession on revision, audit event.
- **RenderUnitService** (`plan_render_units`, `invalidate_render_units`): convert timeline spans
  into typed render units with exact windows; multi-slot expansion; stale-span guard.
- **ArtifactRegistry** (`register_artifact`, `verify_artifact_on_disk`, `link_artifact_to_render_unit`):
  immutable URI + SHA-256 + media-probe registration; cross-production link prevention;
  idempotency on (uri, sha256).

### Sprint 3 — Durable DB-native orchestrator (ORCH-301..305)

**`scripts/stage_runner.py`**

- **STAGE_REGISTRY** with full pipeline dependency graph (15 stages from research → analytics).
- `downstream_stages()` and `deps_satisfied()` graph traversal.
- **Idempotent stage runner** (`run_stage`): input fingerprint, reuse prior successes (StageSkipped),
  failure recording, audit events.
- **Dependency invalidation** (`invalidate_document_descendants`): recursive document lineage
  traversal → stale documents, approvals, and stage runs.
- **Document revision helpers** (`save_document_revision`, `get_active_document`): versioned
  document service used by authoring and TTS stages.
- **LegacyAdapter** class: materialise temp JSON, invoke legacy fn, commit result — migration shim.

### Sprint 4 — Research, authoring, reviews, and approvals (CREA-401..405)

**`scripts/authoring_service.py`**

- **Research brief** (`save_research_brief`): enforces ≥3 primary sources (NON-NEGOTIABLE #1
  sourcing discipline), records source_citations with full provenance.
- **Script revision service** (`save_script`, `get_script_segments`): immutable revisions,
  segment extraction, word count, propagates invalidation on supersession.
- **Storyboard revision service** (`save_storyboard`, `get_creative_beats`): immutable revisions,
  beat extraction, narration SHA, propagates invalidation.
- **Durable human approvals** (`request_approval`, `record_approval_decision`, `is_approved`):
  single-row-per-gate (UNIQUE constraint respected), stale-SHA reset in-place, Telegram outbox
  notification, forced-override audit log.
- **JSON export** (`export_script_json`, `export_storyboard_json`): projection-only exports,
  never execution authority.

### Sprint 5 — TTS, timing, production storyboard, and planning (AUD-501..BUD-505)

**`scripts/tts_service.py`**

- **TTS artifact + provenance** (`record_tts_artifact`): registers master audio artifact with
  voice config metadata and document dependency link to script revision.
- **Timing spans from map** (`commit_timing_spans_from_map`): normalises sec/ms, delegates to
  `commit_timeline_spans`, saves timing_map document.
- **Storyboard reconciliation** (`reconcile_storyboard_with_timing`): matches creative beats to
  spans by label, links `creative_beat_id`.
- **Render-plan compilation** (`compile_render_plan`): spans → render units → render_plan document
  with cost estimate.
- **Budget + spend approval** (`request_spend_approval`, `record_cost_event`, `get_total_spend`):
  spend gate keyed to render_plan sha256, append-only cost events.

### Sprint 6 — Media generation, QA, and repair loop (MEDIA-601..QA-605)

**`scripts/media_service.py`**

- **Provider-job state machine** (`submit_provider_job`, `poll_provider_job`,
  `complete_provider_job`, `fail_provider_job`): idempotency key, spend-gate enforcement before
  any billable submission, atomic artifact registration on completion, cost event recording.
- **QA evidence** (`record_validation_evidence`, `run_render_unit_qa`): mandatory evidence set
  (file_exists, dimensions, duration, audio_policy); valid status requires evidence; approved
  validation ID written to render unit.
- **Change-request routing** (`route_change_request`, `resolve_change_request`,
  `get_open_change_requests`): closed repair loop from QA failure → change_requested status →
  resolve → ordered.

### Sprint 7 — Assembly, final QA, and deliverables (ASM-701..705)

**`scripts/assemble_db.py`**

- **DB timeline assembly query** (`build_assembly_inputs`): builds ordered manifest purely from
  active spans + render units + artifacts; blocks on non-valid units; no manifest file consumed.
- **Deliverable registry** (`register_deliverable`, `get_deliverables`): immutable, idempotent
  registration of 16x9/9x16/preview variants with artifact lineage.
- **Final QA + Gate B** (`run_final_qa`, `request_gate_b`, `is_gate_b_approved`): evidence-based
  QA; Gate B requires prior qa_final validation; deliverable sha256 bound to approval.
- **JSON export compatibility** (`export_assembly_manifest`): audit/debug projection, not live input.

### Sprint 8 — Metadata, publishing, atomization, and analytics (PUB-801..DATA-805)

**`scripts/publish_service.py`**

- **Metadata package** (`save_metadata_package`): versioned title/description/tags/chapters/
  disclosures document.
- **Publication records** (`create_publication`, `record_published`, `get_publications`):
  hard requirements enforced — Gate B, AI-content disclosure, qa_passed deliverable; idempotent
  on idempotency_key; platform_object_id unique index prevents duplicate uploads.
- **Atomization** (`create_atomized_production`): child productions with parent lineage; inherits
  source span artifact dependencies.
- **Analytics** (`record_metric_snapshot`, `get_metric_snapshots`): idempotent on
  (publication_id, observed_at); all standard YouTube metrics + raw payload.

### Sprint 9 — Cutover and operations (CUT-901..SCALE-906)

**`scripts/migrate_legacy.py`**

- **Legacy consolidation** (`consolidate_legacy_dbs`): idempotent import of clips.db and
  leverage_mind.db into production.db; per-record error isolation; audit event.
- **Retirement check** (`check_legacy_retired`): validates state.json/gates.json absence, checks
  clips.db for unmirrored valid clips.
- **Operations dashboard** (`production_status_dashboard`): queue depth, blocked productions,
  pending approvals, open change requests, failed jobs, total spend.
- **Outbox dispatcher** (`outbox_dispatcher_step`): processes pending Telegram outbox messages;
  idempotent re-run safe.

### Durable orchestration primitives

- Idempotent job enqueue, atomic worker leases, expired-lease recovery, retry scheduling,
  terminal failure handling, DB-side stage invalidation and blocker reporting.

## Test Coverage

- **Total tests:** 796 passed (was 667 before these sprints)
- **New sprint tests:** 129 across 8 new test files
- **Regression:** zero — all 667 prior tests continue to pass

## Files Delivered

| File | Sprint | LOC |
|---|---|---|
| `scripts/production_repo.py` | 2 | ~330 |
| `scripts/stage_runner.py` | 3 | ~280 |
| `scripts/authoring_service.py` | 4 | ~290 |
| `scripts/tts_service.py` | 5 | ~230 |
| `scripts/media_service.py` | 6 | ~250 |
| `scripts/assemble_db.py` | 7 | ~220 |
| `scripts/publish_service.py` | 8 | ~200 |
| `scripts/migrate_legacy.py` | 9 | ~160 |
| `tests/test_sprint2_production_repo.py` | 2 | ~190 |
| `tests/test_sprint3_stage_runner.py` | 3 | ~160 |
| `tests/test_sprint4_authoring.py` | 4 | ~200 |
| `tests/test_sprint5_tts_service.py` | 5 | ~170 |
| `tests/test_sprint6_media_service.py` | 6 | ~190 |
| `tests/test_sprint7_assemble_db.py` | 7 | ~190 |
| `tests/test_sprint8_publish.py` | 8 | ~190 |
| `tests/test_sprint9_migrate.py` | 9 | ~160 |

## Still Pending

The following Sprint 9 scale hardening items remain deferred (require infrastructure or
live integration environment beyond local SQLite):

- **SCALE-903** PostgreSQL qualification (repository + worker concurrency tests on PG)
- **SCALE-904** Backup and disaster-recovery drill (restore to clean environment)
- **SCALE-905** Load and failure-injection test (concurrent workers, outbox replay)

The following Sprint 8 items require live platform credentials:
- **PUB-803** YouTube OAuth + resumable upload worker (scaffold is in publish_service.py)

All remaining items are operational/scale concerns. The production business logic
(Sprints 2–8) is fully DB-native and tested.
