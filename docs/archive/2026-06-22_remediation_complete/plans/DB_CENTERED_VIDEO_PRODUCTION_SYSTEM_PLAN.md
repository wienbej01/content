# Database-Centered Video Production System Plan

**Status:** Proposed target architecture and delivery plan  
**Date:** 2026-06-15  
**Scope:** Idea intake through research, authoring, TTS, visual planning, media generation,
assembly, approval, publishing, analytics, and learning feedback  
**Primary decision:** Replace file-to-file process handoffs with a transactional production
ledger. Files remain artifact payloads, but no production stage treats a JSON file or filename
as workflow truth.

## 1. Executive Recommendation

Build one database-centered production platform around the existing stage implementations.
Do not rewrite the creative and media algorithms first. Wrap them behind a shared production
repository and migrate their inputs and outputs one stage family at a time.

The target system has these properties:

1. Every stage is invoked with a `production_id` and optional `stage_run_id`, not a chain of
   input and output paths.
2. Every stage reads authoritative inputs through one repository API and commits outputs,
   lineage, validation evidence, costs, and status in one transaction.
3. Large payloads such as MP3, PNG, MP4, SRT, and rendered reports remain on disk or object
   storage. The database stores their immutable URI, checksum, media metadata, provenance,
   and lifecycle state.
4. Creative documents may be stored as versioned JSON payloads in the database and exported
   to JSON or Markdown for inspection. Exports are never production inputs.
5. Human approvals, retries, provider jobs, change requests, and publication records are
   first-class database records, not side effects hidden in `state.json`, `gates.json`, logs,
   or Telegram messages.
6. Logical content identity, timeline identity, and render identity are separate. `beat_id`
   is not reused as the key for split intervals or coverage slots.
7. The orchestrator is durable and database-backed. A crashed process can be resumed from
   committed state without guessing from file presence.

This should replace, not add to, the current overlapping ledgers:

- `db/leverage_mind.db`
- `db/clips.db`
- `Videos/Projects/<project>/state.json`
- `Videos/Projects/<project>/gates.json`
- fingerprint sidecars used as workflow state

During migration these systems can be dual-written, but the end state is one production
database and one artifact store.

## 2. Important Clarification: "No Handover"

Processes must exchange state. The goal is no serialized file handover, not no handover at
all. The required handover boundary is:

```text
stage process -> production repository transaction -> next stage process
```

It must not be:

```text
stage process -> write JSON -> infer path -> parse JSON -> guess freshness -> next process
```

JSON exports remain useful for debugging, audits, fixtures, external integrations, and human
review. They are projections of database state, not an authority.

## 3. Current-System Diagnosis

The present pipeline has strong individual stage logic but no single system of record.

### 3.1 Split authority

| Concern | Current authority |
|---|---|
| Production progress and resume | `state.json` |
| Human gates | `gates.json` |
| Clip status, path, timing, QA | `clips.db` |
| Content and performance metadata | `leverage_mind.db` |
| Creative and production contracts | Multiple JSON files |
| Dependency freshness | Gate hashes and fingerprint sidecars |
| Runtime evidence | Reports, logs, media probes, and filesystem presence |

These authorities can disagree while each reports success.

### 3.2 Identity is overloaded

The current system uses a logical beat identifier for three different objects:

- a creative beat in a storyboard
- a post-TTS temporal interval, potentially split into children
- a physical render unit, potentially expanded into multiple coverage slots

The stable production model must distinguish those objects.

### 3.3 Current DB integration is incomplete

`clip_db` has become a useful status and path authority for downstream media, but it does not
own the complete production lifecycle. Authoring, reviews, gates, TTS, stage execution,
publishing, analytics, and invalidation remain outside it. `content_db` is a post-hoc logger,
not an execution authority.

### 3.4 Filesystem truth is not transactional truth

A database row can claim an asset is valid while the path, extension, checksum, or semantic
content is wrong. A valid asset therefore requires both database state and validation
evidence tied to the exact artifact version.

## 4. Design Principles

1. **One production ledger.** Workflow state, identity, approvals, costs, and provenance live
   in one database.
2. **Artifact store, not DB blobs.** Media stays in a filesystem or S3-compatible object store.
3. **Immutable revisions.** Approved script, audio, plans, and deliverables are never edited in
   place. A change creates a new revision and invalidates descendants.
4. **Explicit lineage.** Every output records the exact input revisions and configuration used.
5. **Idempotent stages.** Repeating a stage with the same input fingerprint returns or reuses
   the same committed result unless explicitly forced.
6. **Fail closed.** A missing validation, stale approval, unresolved change request, or missing
   artifact blocks consumption.
7. **No inference from filenames.** Media behavior comes from typed database fields.
8. **DB state and external side effects are separated.** Provider calls, Telegram messages,
   and uploads use an outbox and idempotency keys.
9. **Configuration is versioned input.** Each run captures the resolved constraints, routing,
   prompt, model, provider, and code version.
10. **Backwards-compatible migration.** Existing CLIs keep working through adapters until each
    stage family is fully migrated and verified.

## 5. Target Architecture

```text
                         API / CLI / Scheduler
                                  |
                                  v
                    +---------------------------+
                    | Durable Orchestrator      |
                    | stage graph, leases,      |
                    | retries, gates, invalid.  |
                    +-------------+-------------+
                                  |
                        production_id / job_id
                                  |
          +-----------------------+-----------------------+
          |                                               |
          v                                               v
+---------------------------+                 +---------------------------+
| Stage Workers             |                 | Human / External Workers  |
| research, script, TTS,    |                 | Telegram, providers,      |
| compile, QA, assemble     |                 | YouTube, analytics        |
+-------------+-------------+                 +-------------+-------------+
              |                                             |
              +----------------------+----------------------+
                                     v
                    +--------------------------------+
                    | Production Repository          |
                    | transactions + domain rules    |
                    +---------------+----------------+
                                    |
                     +--------------+--------------+
                     |                             |
                     v                             v
             Production Database            Artifact Store
             SQLite local profile           local filesystem
             PostgreSQL scale profile       or S3-compatible storage
```

### 5.1 Deployment profiles

**Local profile**

- SQLite in WAL mode
- one host, one or a small number of workers
- local artifact store
- suitable for development and low-volume production

**Scale profile**

- PostgreSQL
- multiple workers using row leases and `FOR UPDATE SKIP LOCKED`
- S3-compatible artifact store or shared filesystem
- separate worker pools for LLM, media generation, local render, publish, and analytics

The repository API and schema should be designed for both. SQLite is not the long-term
multi-host queue, but it is a valid local implementation.

## 6. Canonical Identity Model

| Entity | Meaning | Stable key |
|---|---|---|
| `content_item` | Business-level topic or episode concept | `content_item_id` |
| `production` | One attempt to produce a publishable video | `production_id` |
| `document_revision` | Versioned brief, script, storyboard, plan, metadata, report | `document_revision_id` |
| `script_segment` | Logical authored narration segment | `script_segment_id` |
| `creative_beat` | Logical visual or narrative beat before exact timing | `creative_beat_id` |
| `timeline_span` | Exact post-TTS interval on the master timeline | `timeline_span_id` |
| `render_unit` | One physical still, clip, overlay, caption stream, or audio unit | `render_unit_id` |
| `artifact` | One immutable stored file or external payload | `artifact_id` |
| `deliverable` | One assembled output such as 16x9 master or 9x16 short | `deliverable_id` |
| `publication` | One platform upload or scheduled post | `publication_id` |

Rules:

- A creative beat may map to one or many timeline spans.
- A timeline span may map to one or many render units.
- A render unit may produce multiple artifact attempts, but only one approved artifact version
  is active at a time.
- Parent, split, slot, and sequence relationships are columns and foreign keys, not encoded in
  string suffixes.
- Human-readable labels such as `B003`, `B003a`, and `s0` remain display fields only.

## 7. Proposed Data Model

Use normal columns for identity, lifecycle, timing, money, and query-critical fields. Use JSON
or JSONB for evolving creative payloads and provider-specific metadata.

### 7.1 Core production tables

#### `content_items`

- `id`, `external_key`, `topic`, `pillar`, `format_archetype`
- `priority`, `target_publish_at`, `created_at`, `archived_at`

#### `productions`

- `id`, `content_item_id`, `project_slug`, `video_type`
- `status`, `current_stage`, `created_at`, `updated_at`, `completed_at`
- `code_revision`, `config_snapshot_id`, `parent_production_id`
- unique active production policy per content item and variant

#### `stage_runs`

- `id`, `production_id`, `stage_name`, `attempt`, `status`
- `input_fingerprint`, `started_at`, `heartbeat_at`, `finished_at`
- `worker_id`, `error_class`, `error_message`, `result_summary_json`
- unique `(production_id, stage_name, input_fingerprint, attempt)`

#### `jobs`

- `id`, `production_id`, `stage_name`, `status`, `priority`
- `available_at`, `leased_by`, `lease_expires_at`, `attempts`, `max_attempts`
- `idempotency_key`, `payload_json`, `last_error`

#### `production_events`

- append-only audit log for transitions, invalidations, overrides, retries, and operator actions
- `id`, `production_id`, `event_type`, `actor`, `payload_json`, `created_at`

### 7.2 Versioned document tables

#### `document_revisions`

- `id`, `production_id`, `kind`, `revision`, `status`
- `schema_version`, `payload_json`, `payload_sha256`
- `created_by_stage_run_id`, `supersedes_id`, `created_at`
- kinds include research brief, script, script review, creative storyboard, production
  storyboard, media plan projection, budget report, QA report, metadata package, and prompt log

#### `document_dependencies`

- `document_revision_id`, `depends_on_document_revision_id`, `dependency_role`

#### `source_citations`

- normalized source URL, title, source type, publication/access dates, excerpt hash, how used,
  primary-source flag, and the research revision that introduced it

### 7.3 Timeline and render tables

#### `script_segments`

- `id`, `script_revision_id`, `ordinal`, `label`, `text`, `word_count`
- immutable within a script revision

#### `creative_beats`

- `id`, `storyboard_revision_id`, `script_segment_id`, `ordinal`, `label`
- `shot_type`, `visual_intent_json`, `graphics_json`, `narration_text_sha256`

#### `timeline_spans`

- `id`, `production_id`, `creative_beat_id`, `parent_span_id`, `ordinal`
- `start_ms`, `end_ms`, `duration_ms`, `split_index`, `split_total`
- `narration_text_sha256`, `timing_source_artifact_id`, `status`
- database constraints require `end_ms > start_ms`

#### `render_units`

- `id`, `production_id`, `timeline_span_id`, `parent_render_unit_id`, `ordinal`
- `asset_type`, `model`, `audio_policy`, `lipsync_required`
- `required_start_ms`, `required_end_ms`, `required_duration_ms`
- `slot_index`, `slot_total`, `prompt_revision_id`, `status`
- `active_artifact_id`, `approved_validation_id`

The assembly sequence is ordered by timeline position and render-unit ordinal, never by parsing
an identifier string.

### 7.4 Artifact and validation tables

#### `artifacts`

- `id`, `production_id`, `kind`, `uri`, `storage_backend`, `mime_type`
- `sha256`, `size_bytes`, `duration_ms`, `width`, `height`, `has_audio`
- `created_by_stage_run_id`, `provider_job_id`, `created_at`, `deleted_at`
- unique `(storage_backend, uri, sha256)`

#### `artifact_dependencies`

- `artifact_id`, `depends_on_artifact_id`, `dependency_role`

#### `validations`

- `id`, `production_id`, `subject_type`, `subject_id`, `validator_name`
- `status`, `ruleset_version`, `evidence_json`, `created_by_stage_run_id`, `created_at`
- a subject is consumable only when required validations pass for its exact revision or hash

#### `change_requests`

- `id`, `production_id`, `subject_type`, `subject_id`
- `change_type`, `requested_by_stage`, `target_stage`, `reason`
- `status`, `resolution_json`, `created_at`, `resolved_at`

### 7.5 Approval, cost, and provider tables

#### `approval_requests`

- `id`, `production_id`, `gate_name`, `subject_type`, `subject_id`, `subject_sha256`
- `status`, `requested_at`, `decided_at`, `actor`, `decision_note`, `forced`
- an approval is stale when its exact subject revision is no longer active

#### `provider_jobs`

- `id`, `production_id`, `render_unit_id`, `provider`, `operation`
- `external_job_id`, `idempotency_key`, `status`, `request_json`, `response_json`
- `submitted_at`, `polled_at`, `completed_at`, `error_json`

#### `cost_events`

- `id`, `production_id`, `stage_run_id`, `provider_job_id`
- `provider`, `operation`, `estimated_usd`, `actual_usd`, `currency`, `created_at`

#### `config_snapshots`

- resolved constraints, model routing, voice configuration, prompt versions, provider versions,
  and relevant environment feature flags, stored with a checksum

### 7.6 Delivery and learning tables

#### `deliverables`

- `id`, `production_id`, `variant`, `artifact_id`, `status`
- `assembly_revision`, `qa_validation_id`, `approved_at`

#### `publications`

- `id`, `production_id`, `deliverable_id`, `platform`, `platform_object_id`
- `status`, `scheduled_at`, `published_at`, `url`, `disclosure_json`, `metadata_revision_id`
- unique `(platform, platform_object_id)` and idempotent publish key

#### `metric_snapshots`

- `id`, `publication_id`, `observed_at`, views, impressions, watch time, retention, CTR,
  subscribers, engagement, conversions, revenue, and raw provider payload

#### `experiments`

- thumbnail, title, hook, format, or schedule experiment definition and assignment

## 8. Stage Execution Contract

Every production stage implements one interface:

```python
class Stage:
    name: str

    def load_inputs(self, repo, production_id): ...
    def validate_preconditions(self, repo, production_id, inputs): ...
    def execute(self, context, inputs): ...
    def commit(self, repo, stage_run_id, result): ...
```

The runner performs:

1. Lease a queued job.
2. Start a `stage_run` and capture code/config versions.
3. Load active input revisions through the repository.
4. Compute an input fingerprint from exact revision IDs and hashes.
5. Return the prior successful result when the fingerprint is already complete.
6. Execute pure computation or submit external work using an idempotency key.
7. Validate produced payloads and media.
8. Commit output revisions, lineage, evidence, costs, and events atomically.
9. Queue newly unblocked downstream jobs.
10. On failure, classify retryable versus permanent and preserve all evidence.

Existing scripts can initially be called through adapters. The adapter materializes a temporary
JSON projection, invokes the current function, parses the result, and commits it. This is a
migration mechanism only; the final stage implementation reads repository objects directly.

## 9. Workflow State Model

### 9.1 Stage-run states

```text
queued -> leased -> running -> succeeded
                    |   |
                    |   +-> waiting_external -> running
                    +-----> waiting_approval -> running
                    +-----> retryable_failed -> queued
                    +-----> failed
```

Additional terminal states: `cancelled`, `superseded`, and `stale`.

### 9.2 Production flow

```text
idea
  -> research
  -> brief
  -> script + review loop
  -> Gate A content approval
  -> TTS + alignment
  -> production storyboard
  -> render plan + budget
  -> Gate A spend approval
  -> media generation + media QA/change loop
  -> assembly + final QA
  -> Gate B final approval
  -> metadata + thumbnail + captions + atomization
  -> schedule/publish
  -> analytics collection
  -> learning feedback
```

Gate A may remain two distinct approvals: content approval and spend approval. They should not
be conflated in one row.

## 10. Hard Invariants

1. Approved narration text and TTS artifacts are immutable. A revision creates a new branch and
   invalidates all dependent timing, render, and delivery records.
2. Timeline spans for one production cannot overlap and must cover the required narration
   interval exactly, excluding explicitly typed non-narration intervals.
3. Every active render unit references exactly one timeline span and has a positive duration.
4. A render unit cannot become `valid` without a present artifact, matching checksum, media
   probe evidence, and the required semantic validation rules.
5. A stage cannot consume a stale or superseded document, artifact, approval, or validation.
6. A billable provider job cannot be submitted without active budget and spend approvals.
7. Cost events are append-only and tied to an idempotent provider job.
8. Assembly reads render units, active artifacts, and timeline order from the database.
9. Publish requires final QA, Gate B approval, metadata revision, thumbnail artifact, and the
   required synthetic-content disclosure fields.
10. The same deliverable revision cannot be published twice to the same platform accidentally.
11. Any manual override creates an append-only event and never silently changes a prior record.
12. Status is not evidence. Every success state references the validation or output that proves it.

## 11. Artifact Storage and Workspace Layout

Do not store MP4 or MP3 blobs in the relational database.

Recommended URI layout:

```text
productions/<production_id>/
  source/<artifact_id>.<ext>
  audio/<artifact_id>.<ext>
  images/<artifact_id>.<ext>
  clips/<artifact_id>.<ext>
  overlays/<artifact_id>.<ext>
  captions/<artifact_id>.<ext>
  deliverables/<artifact_id>.<ext>
  exports/<document_revision_id>.json
```

The artifact ID, not a beat label, is the physical filename authority. Human-readable aliases
may be exported, but no stage derives identity from a filename.

Use atomic writes:

1. Write to a temporary URI.
2. Probe and checksum.
3. Move or upload to the immutable final URI.
4. Commit the artifact row.

Garbage collection deletes only unreferenced, non-active artifacts after a retention period.

## 12. Invalidation Model

Invalidation follows recorded dependency edges, not a hardcoded list of filenames.

Example:

```text
script revision 4 supersedes revision 3
  -> Gate A approval for revision 3 becomes stale
  -> TTS derived from revision 3 becomes stale
  -> timing spans derived from that TTS become stale
  -> render units and media artifacts become stale
  -> assembly and publication become blocked
```

Expensive artifacts are not deleted automatically. They remain reusable only if the new order
spec matches their semantic key, input hashes, timing, policy, and validation rules.

## 13. External Side Effects

Use a transactional outbox for operations that cannot be committed atomically with the DB:

- Telegram gate requests and notifications
- LLM calls where retries could duplicate billing
- Higgsfield or other media-provider submissions
- YouTube uploads
- analytics pulls

The DB transaction writes the domain change and an `outbox_messages` row. A dispatcher performs
the external operation and records the result. Every message carries an idempotency key.

## 14. Migration Strategy

### 14.1 Strangler pattern

Do not stop production for a rewrite.

1. Introduce the new production database, migrations, repository, and event log.
2. Import existing `leverage_mind.db`, `clips.db`, `state.json`, `gates.json`, and active project
   JSON artifacts into the new schema.
3. Dual-write existing orchestrator progress, gates, clip updates, and artifacts.
4. Add read adapters so migrated stages prefer DB state but can compare against legacy files.
5. Migrate stage families in order from low-risk authoring to high-risk media and assembly.
6. Run shadow comparisons between DB projections and legacy JSON outputs.
7. Make DB authority mandatory after acceptance tests pass.
8. Keep JSON export commands for audits and fixtures.
9. Remove legacy writes only after one full production completes DB-native and can be resumed
   after injected crashes.

### 14.2 Compatibility boundary

Temporary adapter command:

```text
python3 scripts/produce_db.py run <production_id>
```

Legacy stages may receive temporary paths created under a run-scoped working directory. These
paths are disposable and must never be consulted by another stage.

## 15. Testing Strategy

### 15.1 Unit and repository tests

- schema constraints and migration rollback
- repository transactions and optimistic concurrency
- idempotent stage results
- lineage and recursive invalidation
- approval staleness
- job lease expiry and retry classification
- outbox deduplication

### 15.2 Contract tests

- each stage consumes repository DTOs and returns typed results
- artifact metadata matches media probes
- no production code reads authoritative values from filename extensions
- no stage accepts a loose JSON path after its migration ticket is complete

### 15.3 Integration tests

- local SQLite end-to-end with mocked paid providers
- PostgreSQL end-to-end in CI or a disposable container
- crash after external submission but before result commit
- crash after artifact write but before DB commit
- stale worker lease recovery
- concurrent workers cannot execute the same job twice
- script revision invalidates all descendants
- media QA change request routes to and requeues the owning stage

### 15.4 Golden production test

Maintain one deterministic, no-paid-API fixture that exercises:

- parent beat split into multiple timeline spans
- one span expanded into multiple render units
- still image and generated video assets
- continuous narration
- change request and retry
- assembly of 16x9 and 9x16
- final approval and simulated publish

## 16. Operations, Security, and Recovery

- Enable SQLite WAL, foreign keys, busy timeout, and periodic integrity checks in local mode.
- Use PostgreSQL backups plus point-in-time recovery in scale mode.
- Back up the database and artifact store independently; test restoration quarterly.
- Store secrets outside the DB. Store only provider/account identifiers and redacted request data.
- Add structured logs containing `production_id`, `stage_run_id`, `job_id`, `render_unit_id`,
  and `provider_job_id`.
- Add a `production status` command that reports blockers from database state, not file presence.
- Expose dead jobs, stale leases, pending approvals, open changes, current spend, and missing
  artifacts as first-class operational queries.

## 17. Delivery Roadmap

The estimates below are engineering days for one experienced engineer and exclude paid-provider
waiting time. A realistic full implementation is approximately 60 to 85 engineering days.
The system becomes useful much earlier, after Sprint 3 or 4.

### Sprint 0: Architecture lock and migration foundation

**Goal:** Freeze the domain model before more one-off fixes expand the current split authority.

#### SYS-001 - Architecture decision records

- Document DB authority, artifact storage, identity levels, revision semantics, and SQLite to
  PostgreSQL deployment profiles.
- Acceptance: no unresolved use of `beat_id` as a physical primary key; all core terms defined.
- Estimate: 1 day.

#### SYS-002 - Migration framework and schema v1

- Add versioned SQL migrations and bootstrap commands.
- Add all core, document, timeline, artifact, approval, job, event, and outbox tables.
- Acceptance: empty DB creates from zero; upgrade is repeatable; foreign-key checks pass.
- Estimate: 3 days. Depends on SYS-001.

#### SYS-003 - Production repository transaction layer

- Add connection management, transaction boundaries, repositories, typed row DTOs, and test
  database fixtures.
- Acceptance: no stage writes raw SQL outside the repository package after migration.
- Estimate: 3 days. Depends on SYS-002.

#### SYS-004 - Status and audit CLI

- Implement create/show/list/events/blockers commands.
- Acceptance: one command explains the exact current blocker and owning stage.
- Estimate: 1.5 days. Depends on SYS-003.

**Sprint exit:** a production can be created, queried, transitioned, and audited entirely in DB.

### Sprint 1: Import and dual-write existing authorities

**Goal:** Establish one combined ledger without changing stage behavior.

#### MIG-101 - Legacy importer

- Import both SQLite databases plus project state, gates, creative JSON, media plans, manifests,
  reports, and fingerprints.
- Acceptance: dry-run report shows mappings and conflicts; importer is idempotent.
- Estimate: 4 days.

#### MIG-102 - Dual-write orchestrator state

- Mirror `produce.py` step starts, results, failures, and resume state into `stage_runs` and events.
- Acceptance: DB and `state.json` agree through injected failure and resume tests.
- Estimate: 2 days.

#### MIG-103 - Dual-write gates and approvals

- Mirror gate requests and decisions into `approval_requests` while preserving current gates.
- Acceptance: artifact revision changes stale both representations consistently.
- Estimate: 2 days.

#### MIG-104 - Dual-write clips and artifacts

- Mirror `clip_db` lifecycle changes into render units, artifacts, validations, and change requests.
- Acceptance: every active clip has an imported render unit and artifact record.
- Estimate: 3 days.

**Sprint exit:** the new DB reconstructs the current production state and detects discrepancies.

### Sprint 2: Identity, timeline, and artifact authority

**Goal:** Eliminate the beat/child/slot identity conflict.

#### ID-201 - Stable IDs and labels

- Generate stable IDs for script segments, creative beats, timeline spans, and render units.
- Preserve existing labels only as display metadata.
- Acceptance: split and slot expansion never duplicate a primary key.
- Estimate: 2 days.

#### ID-202 - Timeline span service

- Store exact post-TTS timing and split lineage in `timeline_spans`.
- Add no-gap/no-overlap validation using integer milliseconds.
- Acceptance: adversarial gaps, overlaps, negative durations, and orphan spans fail closed.
- Estimate: 3 days.

#### ID-203 - Render-unit planning service

- Convert production storyboard spans into one or more render units with exact windows.
- Acceptance: coverage slots sequence inside the span and preserve total coverage.
- Estimate: 3 days.

#### ART-204 - Immutable artifact registry

- Centralize URI allocation, checksum, media probe, atomic finalization, and lookup.
- Acceptance: a missing or modified file cannot retain valid status.
- Estimate: 3 days.

**Sprint exit:** the DB is the sole identity, timing, and artifact metadata authority.

### Sprint 3: Durable DB-native orchestrator

**Goal:** Replace `state.json` and filename-based resume logic.

#### ORCH-301 - Stage registry and dependency graph

- Define stage metadata, prerequisites, outputs, retry policy, and invalidation boundaries.
- Acceptance: the full existing pipeline order is represented and queryable.
- Estimate: 2 days.

#### ORCH-302 - Job queue and leases

- Implement queue, worker lease, heartbeat, expiry, retry, cancellation, and dead-job handling.
- Acceptance: two workers cannot commit the same job; expired work is safely reclaimed.
- Estimate: 4 days.

#### ORCH-303 - Idempotent stage runner

- Compute fingerprints, reuse prior successful results, and commit atomically.
- Acceptance: rerunning an unchanged stage produces no duplicate provider job or artifact.
- Estimate: 3 days.

#### ORCH-304 - Dependency invalidation

- Traverse recorded lineage and mark descendants stale after a revision change.
- Acceptance: changing an approved script blocks all dependent audio through publication.
- Estimate: 3 days.

#### ORCH-305 - Legacy stage adapter

- Materialize run-scoped temporary JSON for unmigrated scripts and commit parsed results.
- Acceptance: no temporary artifact becomes an input to another process.
- Estimate: 2 days.

**Sprint exit:** `produce_db.py` can run and resume the current chain without `state.json`.

### Sprint 4: Research, authoring, reviews, and approvals

**Goal:** Move all pre-TTS creative processes to DB-native contracts.

#### CREA-401 - Research and source evidence

- Migrate research brief, transcripts, and citations to versioned records.
- Acceptance: every claim can be joined to source evidence and producer run.
- Estimate: 2 days.

#### CREA-402 - Script revision service

- Store scripts and segments as immutable revisions; support reviewer-driven revisions.
- Acceptance: reviewer loops create revisions rather than overwrite `script.json`.
- Estimate: 3 days.

#### CREA-403 - Storyboard revision service

- Store creative beats, review evidence, and visual intent without path handoffs.
- Acceptance: direct/review loops operate by production ID and active revision.
- Estimate: 3 days.

#### GATE-404 - Durable human approvals

- Implement pending approval records, Telegram outbox messages, decisions, timeout, and stale
  approval handling.
- Acceptance: duplicate notifications are suppressed; exact approved revision is recorded.
- Estimate: 4 days.

#### CREA-405 - Remove pre-TTS JSON authority

- Convert current JSON outputs to optional exports only.
- Acceptance: research through storyboard succeeds with project JSON files deleted.
- Estimate: 2 days.

**Sprint exit:** idea through approved storyboard is fully DB-native.

### Sprint 5: TTS, timing, production storyboard, and planning

**Goal:** Make measured audio and temporal coverage authoritative in DB.

#### AUD-501 - TTS artifact and provenance migration

- Record master audio, voice configuration, provider request, costs, and checksums.
- Acceptance: TTS reuse requires exact script and voice/config fingerprints.
- Estimate: 3 days.

#### AUD-502 - Alignment and timing spans

- Write measured timing directly to `timeline_spans`; retain timing-map JSON as an export.
- Acceptance: no downstream stage reads `beat_timing_map.json`.
- Estimate: 3 days.

#### PLAN-503 - Production storyboard reconciliation

- Reconcile creative beats against measured spans and create explicit split lineage.
- Acceptance: narration text hash remains immutable and all intervals are legal.
- Estimate: 3 days.

#### PLAN-504 - Render-plan compilation

- Compile model, prompt, asset type, audio policy, graphics, cost, and coverage into render units.
- Acceptance: every render unit has exact timing and no stage consumes `media_plan.json`.
- Estimate: 4 days.

#### BUD-505 - Budget and spend approval

- Calculate estimated and committed spend from DB and bind approval to the render-plan revision.
- Acceptance: a changed plan invalidates approval before any paid submission.
- Estimate: 2 days.

**Sprint exit:** approved audio through spend-approved render units is DB-native.

### Sprint 6: Media generation, graphics, QA, and repair loop

**Goal:** Move all physical asset work to render-unit jobs and evidence-based validity.

#### MEDIA-601 - Provider-job state machine

- Submit, poll, download, retry, and reconcile external generation jobs via outbox/idempotency.
- Acceptance: crash after submission cannot create a duplicate billable job.
- Estimate: 4 days.

#### MEDIA-602 - Generation worker migration

- Generate or reuse assets from render-unit orders and artifact semantic keys.
- Acceptance: no globbing, filename inference, or media-plan path reads remain.
- Estimate: 4 days.

#### MEDIA-603 - Graphics and overlay migration

- Render typed graphic assets to artifact IDs with correct MIME and extension from registration.
- Acceptance: DB path, MIME, checksum, and actual file always agree.
- Estimate: 2.5 days.

#### QA-604 - Media validation evidence

- Store probe, duration, dimensions, audio policy, identity, text-surface, and semantic QA results.
- Acceptance: `valid` cannot be set without the required evidence set.
- Estimate: 4 days.

#### QA-605 - Change-request routing

- Route regenerate, re-slice, re-plan, and re-render requests to owning stages and requeue them.
- Acceptance: a failed unit completes a closed repair loop without manual file surgery.
- Estimate: 3 days.

**Sprint exit:** all render units are generated, repaired, and validated through DB state.

### Sprint 7: Assembly, final QA, and deliverables

**Goal:** Remove manifest files as an execution contract.

#### ASM-701 - DB timeline assembly query

- Build the ordered assembly input directly from active spans, render units, and artifacts.
- Acceptance: parent splits, multiple slots, stills, lipsync, and overlays assemble without a
  manifest input file.
- Estimate: 4 days.

#### ASM-702 - Assembly worker migration

- Adapt `assemble.py` to repository DTOs while preserving a legacy manifest CLI wrapper.
- Acceptance: production execution never re-reads or overrides a serialized manifest.
- Estimate: 4 days.

#### ASM-703 - Deliverable registry

- Register 16x9, 9x16, preview, captioned, and review outputs as immutable deliverables.
- Acceptance: each output records exact component artifact and config dependencies.
- Estimate: 2 days.

#### QA-704 - Final QA and Gate B

- Store automated QA evidence, review media, human decision, and approval revision.
- Acceptance: publishing cannot query an approved deliverable unless all checks are current.
- Estimate: 3 days.

#### ASM-705 - JSON export compatibility

- Add commands to export manifest, media plan, timing map, and reports for audits only.
- Acceptance: exported documents round-trip for inspection but are rejected as live authority.
- Estimate: 2 days.

**Sprint exit:** a complete video can be produced and approved with no inter-stage JSON handoff.

### Sprint 8: Metadata, publishing, atomization, and analytics

**Goal:** Expand the system from rendering a video to operating the full production business.

#### PUB-801 - Metadata package

- Version title, description, chapters, tags, disclosures, thumbnail brief, and scheduling data.
- Acceptance: metadata and thumbnail are approved subjects with revision history.
- Estimate: 3 days.

#### PUB-802 - Thumbnail and caption assets

- Generate/register thumbnail variants, subtitle files, and burned-caption deliverables.
- Acceptance: each publication references exact approved asset revisions.
- Estimate: 3 days.

#### PUB-803 - YouTube publish worker

- Add OAuth setup, resumable upload, scheduling, idempotency, disclosure enforcement, and
  publication records.
- Acceptance: retry cannot duplicate an upload; Gate B and disclosure are hard requirements.
- Estimate: 5 days.

#### PUB-804 - Atomization workflow

- Create short-form candidates as child productions with inherited source and timeline lineage.
- Acceptance: each short has independent gates, deliverables, schedule, and performance data.
- Estimate: 4 days.

#### DATA-805 - Analytics collection

- Collect metric snapshots at defined intervals and join them to creative, render, and publish
  attributes.
- Acceptance: views, retention, CTR, costs, and content attributes are queryable per revision.
- Estimate: 4 days.

**Sprint exit:** the ledger covers idea through publication and measurable performance.

### Sprint 9: Cutover and scale hardening

**Goal:** Remove split authority and prove operational resilience.

#### CUT-901 - Disable legacy authoritative reads

- Fail CI when migrated stages read `state.json`, `gates.json`, `media_plan.json`, timing maps,
  or manifests as production inputs.
- Acceptance: repository search and contract tests enforce the boundary.
- Estimate: 2 days.

#### CUT-902 - Consolidate legacy databases

- Freeze and archive `clips.db` and `leverage_mind.db`; remove dual writes.
- Acceptance: all supported queries and operations use the unified DB.
- Estimate: 2 days.

#### SCALE-903 - PostgreSQL qualification

- Run migrations, repository tests, worker concurrency tests, and full mocked E2E on PostgreSQL.
- Acceptance: SQLite and PostgreSQL produce equivalent domain outcomes.
- Estimate: 4 days.

#### SCALE-904 - Backup and disaster-recovery drill

- Document and execute DB plus artifact restore to a clean environment.
- Acceptance: one approved production is restored and its final deliverable checksum matches.
- Estimate: 2 days.

#### SCALE-905 - Load and failure-injection test

- Queue multiple productions, kill workers, expire leases, inject provider failures, and replay
  outbox messages.
- Acceptance: no duplicate spend, no duplicate publish, no lost approval, no corrupt lineage.
- Estimate: 4 days.

#### SCALE-906 - Operations dashboard or status API

- Expose queue depth, blockers, spend, approvals, failures, and throughput.
- Acceptance: an operator can diagnose and retry without opening project directories.
- Estimate: 3 days.

**Sprint exit:** one database is authoritative, the legacy ledgers are retired, and concurrent
production is supported.

## 18. Recommended Ticket Order

The critical path is:

```text
SYS-001 -> SYS-002 -> SYS-003
  -> MIG-101..104
  -> ID-201..ART-204
  -> ORCH-301..305
  -> CREA-401..405
  -> AUD-501..BUD-505
  -> MEDIA-601..QA-605
  -> ASM-701..705
  -> PUB-801..DATA-805
  -> CUT-901..SCALE-906
```

Parallel work is safe only after the repository and identities are locked:

- Authoring migration can run in parallel with artifact-registry work.
- Publishing work can begin after deliverable and approval contracts stabilize.
- PostgreSQL qualification can start after the repository API and migrations are complete.

## 19. Definition of Done for the System

The redesign is complete only when all of the following are true:

1. A production starts from a topic and reaches a published test record using only a
   `production_id` between processes.
2. Deleting JSON exports does not break execution or resume.
3. Every final frame and audio interval traces back through render unit, timeline span,
   creative beat, script revision, research source, code revision, and configuration snapshot.
4. A worker crash at every stage boundary resumes without duplicate paid work.
5. A script or TTS revision invalidates all dependent approvals, assets, and deliverables.
6. No valid asset can be missing, modified, semantically rejected, or attached to stale inputs.
7. Publishing is mechanically impossible without current final QA, Gate B, metadata, thumbnail,
   and disclosure records.
8. Cost and performance can be queried by stage, provider, production, format, creative choice,
   and publication.
9. The database and artifact store can be restored into a clean environment and reproduce the
   same approved deliverable checksum.
10. The old state, gate, clip, and content ledgers are archived and no longer written.

## 20. Immediate Next Sprint Recommendation

Start with Sprint 0 and Sprint 1 only. Do not first expand `clip_db` with more unrelated tables.
Create the unified database and repository boundary, import the existing authorities, and prove
dual-write consistency. Once that foundation is stable, migrate the post-TTS identity and timing
model before adding publishing or analytics.

The highest-risk architectural mistake would be to wire more stages directly to `clip_db` while
leaving `state.json`, `gates.json`, `content_db`, and creative JSON as separate authorities. That
would increase coupling without producing a coherent production system.
