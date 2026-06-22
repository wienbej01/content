# DB Alignment & Cutover Sprint Plan

**Status:** Proposed delivery plan to FULLY align end-to-end production with the DB-centered system
**Date:** 2026-06-16
**Governing architecture:** `docs/plans/DB_CENTERED_VIDEO_PRODUCTION_SYSTEM_PLAN.md`
**Build status reference:** `docs/plans/DB_CENTERED_VIDEO_PRODUCTION_IMPLEMENTATION_STATUS.md`

---

## 0. Purpose & Scope

The DB-centered **services and schema are built and unit-tested** (Sprints 0–9 of the system
plan). What does **not** yet exist is **alignment**: `scripts/produce.py` still runs the old
file-based pipeline and only *mirrors* state into the production DB (dual-write). The database
is a shadow, not the execution authority.

This plan covers the **cutover only**: making the DB the single source of truth for execution,
wiring the existing services as the real stage implementations, removing file-based handoffs as
authority, and proving the result end-to-end (including the multi-slot identity, coverage, and
stale-state failure modes surfaced on 2026-06-16).

It does **not** re-implement the services — those exist. It connects them, flips authority, and
retires the legacy ledgers.

### 0.1 Definition of "fully aligned"

A run is fully aligned when ALL are true:

1. A production is driven start-to-finish by `production_id` through `produce_db.py`; no stage
   reads `state.json`, `gates.json`, `media_plan.json`, `beat_timing_map.json`, or a manifest
   file as authority.
2. Identity is split: `creative_beat_id`, `timeline_span_id`, `render_unit_id`, `artifact_id`
   are distinct. `beat_id` / `B009-s0` are display labels only. (This eliminates the root cause
   of the 2026-06-16 multi-slot bugs.)
3. Coverage, validity, approval staleness, and spend gates are computed from DB records and
   their exact revision hashes — not from filenames or report files.
4. A crash at any stage boundary resumes from committed DB state with no duplicate paid work.
5. Deleting all JSON/exports from a project directory does not break execution or resume.
6. Legacy `state.json` / `gates.json` / `clips.db` / `leverage_mind.db` are no longer written.
7. One clean fresh production completes through assembly + final QA with multi-slot beats,
   proven with stubbed (zero-cost) providers, and once for real.

---

## 1. Current-State Inventory (verified 2026-06-16)

| Layer | Built? | Authority today | Target authority |
|---|---|---|---|
| Schema + migrations (`db/migrations`) | yes | — | production DB |
| Repository / transactions (`production_db.py`, `production_repo.py`) | yes | shadow | sole DB authority |
| Stage graph (`stage_runner.STAGE_REGISTRY`, 16 stages) | yes | not driving | the orchestrator |
| Idempotent stage runner (`run_stage`) | yes | unused by produce.py | core executor |
| Authoring service (`authoring_service.py`) | yes | shadow | stage executor |
| TTS/timing/plan/spend (`tts_service.py`) | yes | shadow | stage executor |
| Media gen/QA/repair (`media_service.py`) | yes | shadow | stage executor |
| Assembly/deliverable/Gate B (`assemble_db.py`) | yes | shadow | stage executor |
| Publish/atomize/analytics (`publish_service.py`) | yes | shadow | stage executor |
| Legacy importer + consolidation (`migrate_legacy.py`) | partial | — | one-shot migration |
| **`produce.py`** | yes | **EXECUTION AUTHORITY (file-based)** | replaced by `produce_db.py` |
| **`produce_db.py`** | **MISSING** | — | **the only entry point** |

**Key gap:** the stage *execute* functions that bind the existing scripts (`tts.py`,
`generate_media.py`, `assemble.py`, `qa_media.py`, `compile_media_prompts.py`, …) to the
services and the runner do not exist. `produce.py` calls the scripts directly with file paths.

### 1.1 Stage-graph alignment note

`STAGE_REGISTRY` and `produce.py STEPS` are NOT 1:1. Reconcile before wiring:

| produce.py STEP | STAGE_REGISTRY stage | Notes |
|---|---|---|
| research | research | |
| script_create / script_review_loop | write_script / review_script | |
| (gate) | gate_a_content | content approval — split from spend |
| tts | tts | |
| build_timing_map | audio_timing | |
| storyboard_create / storyboard_review_loop | storyboard / review_storyboard | |
| production_storyboard | (fold into storyboard reconcile) | reconcile beats↔spans |
| compliance_check | (fold into review_storyboard) | |
| compile_media_plan | compile_media | |
| slice_lipsync | (fold into compile_media / tts) | |
| gate_a_budget | gate_a_spend | |
| generate_media | generate_media | |
| qa_media | qa_media | |
| reconcile_duration | (fold into qa_media coverage) | per-span coverage |
| render_graphics | (sub-step of generate_media) | local assets |
| build_manifest | (deleted — assembly reads DB) | |
| assemble | assemble | |
| qa_final | qa_final | |
| build_quality_report | (export, not authority) | |
| gate_b_review | gate_b_review | |
| — | publish / analytics | new capability |

---

## 2. Principles for the Cutover

1. **Strangler, not rewrite.** Migrate one stage family at a time behind `produce_db.py`; keep
   `produce.py` runnable until every stage is DB-native and proven.
2. **Adapter first, native second.** Each stage gets a thin `execute()` that calls the existing
   script via `stage_runner.LegacyAdapter`, then is refactored to read/write repository objects
   directly. The legacy script's pure compute is reused; only its I/O contract changes.
3. **Authority flips per stage, gated by a shadow-comparison test.** A stage is "DB-native" only
   after a shadow run shows DB projection == legacy file output for the same input.
4. **Identity split is a hard prerequisite** for the media/assembly stages — those are where the
   2026-06-16 bugs lived. Do it before migrating generation/QA/assembly.
5. **No new paid spend to test.** Every integration test runs with stubbed providers
   (ElevenLabs, Higgsfield) and `ffmpeg`-generated fixtures.
6. **Fail closed on staleness.** A migrated stage must refuse stale documents, approvals,
   artifacts, and validations by revision hash.

---

## 3. Sprints

Estimates are engineering-days for one experienced engineer, excluding paid-provider wait time.
Total: **approximately 24–34 engineering-days**. Useful (resumable DB-native run) after Sprint C.

### Sprint A — Orchestrator entry point & stage contract (foundation)

**Goal:** A DB-native runner can execute the full stage graph using legacy adapters, end-to-end,
with crash/resume — even before any stage is "native."

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-A1 | Reconcile `STAGE_REGISTRY` with the real pipeline (fold `production_storyboard`, `compliance_check`, `slice_lipsync`, `reconcile_duration`, `render_graphics`, `build_manifest` per §1.1); split `gate_a_content` vs `gate_a_spend`. | Graph matches the true pipeline order; topological sort is stable; tests assert prerequisites. | 1.5 |
| ALN-A2 | Build `scripts/produce_db.py`: `create`, `run <production_id>`, `resume`, `status`, `--from-stage`. Drives `stage_runner.run_stage` over the graph; reads next runnable stage from DB, not files. | `produce_db.py create --seed ... --format short` then `run` walks the graph; `status` shows the DB blocker. | 2 |
| ALN-A3 | Define the `Stage` execute interface (`load_inputs`/`validate_preconditions`/`execute`/`commit`) and a `LegacyStage` wrapper that runs each existing script via `LegacyAdapter` and commits parsed output as a document revision. | Every stage has a registered executor; a full run completes via adapters with files materialized in a run-scoped temp dir. | 3 |
| ALN-A4 | Crash/resume harness: kill the runner at each stage boundary; resume re-leases and continues. | Injected crash at every boundary resumes with no duplicate stage run and no duplicate provider job. | 2 |

**Exit:** `produce_db.py` runs and resumes the entire pipeline through legacy adapters, DB-driven.

---

### Sprint B — Identity split (root-cause elimination)

**Goal:** Remove the overloaded `beat_id`. This is the fix that makes the 2026-06-16 class of bug
*structurally impossible*, not patched.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-B1 | Promote `creative_beat_id` (storyboard), `timeline_span_id` (post-TTS interval), `render_unit_id` (physical clip/slot), `artifact_id` (file) as the only keys across services. Demote `beat_id`, `B009-s0` to display labels. | No service maps `beat_id → clip_id`; all lookups use the split IDs; grep gate in CI. | 3 |
| ALN-B2 | Coverage is computed over `timeline_span` → `render_unit` edges with per-unit windows; aggregation is structural, not a sum-by-label heuristic. Port the 2026-06-16 multi-slot regression tests to the DB model. | A beat split into N spans/units validates by exact window coverage; the 2026-06-16 false-deficit and clip_id-collision cases cannot recur (tested). | 2 |
| ALN-B3 | Validation/approval staleness keyed to exact artifact + revision hash; re-qualifying a unit auto-resolves its open change requests in one transaction. | A unit that passes QA cannot retain an open change request; build/assembly never blocked by a dangling request. | 1.5 |

**Exit:** Identity is split end-to-end; multi-slot beats are first-class; today's three bug classes
are eliminated at the model level.

---

### Sprint C — Pre-TTS stages DB-native (research → approved storyboard)

**Goal:** Idea through approved storyboard runs with project JSON deleted.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-C1 | Wire `research`, `write_script`, `review_script` to `authoring_service` (revisions + citations). Enforce ≥3 primary sources in code. | Reviewer loops create revisions; source log is a DB join; deleting `script.json` does not break resume. | 2 |
| ALN-C2 | Wire `storyboard` + `review_storyboard` to `authoring_service`; fold `production_storyboard` into a beats↔spans reconcile. Carry the short-format relaxed bands by `video_type`. | Direct/review loops operate by `production_id`; G2 reads DB; storyboard format bands honor `video_type`. | 2.5 |
| ALN-C3 | `gate_a_content` durable approval via outbox→Telegram; stale-SHA reset; forced-override audit. | Duplicate notifications suppressed; exact approved revision recorded; stale on content change. | 2 |
| ALN-C4 | Shadow-comparison test: DB projections == legacy JSON for the same seed; flip authority for pre-TTS stages. | Pre-TTS stages read DB; legacy JSON becomes export-only. | 1.5 |

**Exit:** Research→approved-storyboard is DB-native and resumable with no JSON authority.

---

### Sprint D — TTS, timing, plan, spend DB-native

**Goal:** Measured audio and temporal coverage are authoritative in DB; spend is gated on the
exact render-plan revision.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-D1 | Wire `tts` to `tts_service.record_tts_artifact` (provenance, voice config, cost). Stub ElevenLabs in tests. | TTS reuse requires exact script + voice/config fingerprint; no live API in CI. | 2 |
| ALN-D2 | Wire `audio_timing` to `commit_timing_spans_from_map`; timing map becomes an export. Reconcile storyboard beats → spans (split lineage). | No stage reads `beat_timing_map.json`; spans are legal (no gap/overlap, integer ms). | 2 |
| ALN-D3 | Wire `compile_media` to `compile_render_plan`; derive render-unit durations from **measured spans** (not `duration_target_sec`). Fold `slice_lipsync`. | Every render unit has exact timing from TTS; the "clips too short" cascade is structurally impossible. | 2.5 |
| ALN-D4 | Wire `gate_a_spend` to `request_spend_approval`; bind to render-plan SHA; cost events append-only. | A changed plan invalidates spend approval before any paid submission. | 1.5 |

**Exit:** Approved audio → spend-approved render units is DB-native; the duration-mismatch root
cause from 2026-06-16 is gone by construction.

---

### Sprint E — Media generation, QA, repair DB-native

**Goal:** All physical asset work flows through render-unit jobs and evidence-based validity.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-E1 | Wire `generate_media` to `media_service` provider-job state machine (submit/poll/complete, idempotency, spend-gate enforcement). Stub Higgsfield in tests. | Crash after submission cannot create a duplicate billable job; reuse honors render-unit semantic key. | 3 |
| ALN-E2 | Fold `render_graphics` as local-asset render units (PIL); register as artifacts with correct MIME/checksum. | DB path, MIME, checksum, and file always agree; local assets skipped in source-scope generation QA. | 1.5 |
| ALN-E3 | Wire `qa_media` to `record_validation_evidence` / `run_render_unit_qa`. Coverage aggregates per span/unit (port today's fix natively); frozen/blank/lipsync checks as evidence. | `valid` impossible without evidence; multi-slot coverage correct; B008b-style freeze caught and routed. | 2.5 |
| ALN-E4 | Wire change-request routing to `route_change_request`/`resolve_change_request`; fold `reconcile_duration` into coverage. | A failed unit completes a closed repair loop with no manual file surgery; no `media_plan.json` path reads. | 2 |

**Exit:** Generation, repair, and validation are fully DB-state-driven.

---

### Sprint F — Assembly, final QA, Gate B DB-native

**Goal:** Remove manifest files as an execution contract.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-F1 | Wire `assemble` to `assemble_db.build_assembly_inputs` (ordered from active spans/units/artifacts). Delete `build_manifest` as a step. | Parent splits, multi-slot, stills, lipsync, overlays assemble with no manifest input file. | 3 |
| ALN-F2 | Adapt `assemble.py` compute to repository DTOs; keep a legacy manifest CLI wrapper for audit only. | Execution never re-reads a serialized manifest; manifest export round-trips for inspection only. | 2.5 |
| ALN-F3 | Wire `qa_final` + `gate_b_review` to `run_final_qa` / `request_gate_b`; bind Gate B to deliverable SHA; `build_quality_report` becomes an export. | Publishing cannot query an approved deliverable unless all checks are current; report is projection-only. | 2 |

**Exit:** A complete video is produced and approved with zero inter-stage JSON handoff.

---

### Sprint G — Publish, atomize, analytics (new capability, optional for first aligned run)

**Goal:** Extend the aligned ledger from rendering to operating the channel. May run after the
first aligned internal video if launch is deferred.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-G1 | Wire `publish` to `publish_service`; YouTube OAuth + resumable upload; mandatory AI-disclosure + Gate B as hard requirements (PUB-803). | Retry cannot duplicate an upload; disclosure non-optional; publication record written. | 4 |
| ALN-G2 | Atomization as child productions with inherited span/artifact lineage. | Each short has independent gates, deliverables, schedule, and metrics. | 2 |
| ALN-G3 | `analytics` metric snapshots joined to creative/render/publish attributes. | Views, retention, CTR, cost queryable per revision — seeds P5-07 learning loop. | 2 |

**Exit:** Idea→publication→measurement is one aligned ledger.

---

### Sprint H — Cutover, legacy retirement, and proof

**Goal:** Make the DB the only authority; prove resilience; retire the shadow ledgers.

| Ticket | Work | Acceptance | Est |
|---|---|---|---|
| ALN-H1 | CI gate: fail the build if any stage reads `state.json`, `gates.json`, `media_plan.json`, timing maps, or manifests as a production input (CUT-901). | Repository search + contract tests enforce the boundary. | 1.5 |
| ALN-H2 | Migrate active in-flight projects (incl. `using_ai_to_help_memory_retention_short`, `flagship_001`) into productions via `migrate_legacy`; verify reconstruction. | Each active project resumes under `produce_db.py` from imported state. | 2 |
| ALN-H3 | **Zero-cost integration proof:** fresh short, stubbed providers, multi-slot beat, crash-injected, run to Gate B; assert deliverable + lineage + no duplicate work. | One deterministic golden run is green in CI with no paid API. | 2 |
| ALN-H4 | **One real aligned run** end-to-end (real ElevenLabs + Higgsfield), human Gate A/B, to a deliverable. Record true cost vs estimate. | A real video is produced fully DB-native; cost reconciles to plan. | 1.5 |
| ALN-H5 | Freeze + retire: stop legacy writes; archive `clips.db`, `leverage_mind.db`, per-project `state.json`/`gates.json` (CUT-902). Re-pin or delete the brittle audited-project snapshot tests (`test_audited_project_fails`, `test_existing_defective_mp4_fails`) to frozen fixtures. | No legacy ledger is written; CI no longer depends on a mutable live project as a fixture. | 1.5 |

**Exit:** One database is authoritative; legacy ledgers retired; aligned run proven in CI and once
for real.

---

## 4. Critical Path & Parallelism

```text
Sprint A (orchestrator + adapters)
  -> Sprint B (identity split)            [HARD prerequisite for E/F]
     -> Sprint C (pre-TTS native)         [parallel-safe with D after B]
        -> Sprint D (TTS/plan/spend native)
           -> Sprint E (media/QA native)
              -> Sprint F (assembly native)
                 -> Sprint H (cutover + proof)
Sprint G (publish/analytics)              [parallel after F contracts stabilize]
```

- Sprint B must land before E/F (it removes the bug class those stages exhibited).
- Sprint C can proceed in parallel with D once B is done.
- Sprint G is independent once F's deliverable/approval contracts are stable.
- Sprint H closes only after A–F (G optional for the first aligned run).

---

## 5. Per-Stage Migration Checklist (applied to every ALN ticket)

A stage is **DB-native (authority-flipped)** only when all are true:

1. `execute()` loads inputs via repository (active revisions), not file paths.
2. Output committed as document/timeline/render/artifact revision + lineage + evidence in one
   transaction.
3. Input fingerprint computed; unchanged input reuses prior committed result (idempotent).
4. Refuses stale/superseded inputs and approvals by hash (fail closed).
5. External effects (LLM/ElevenLabs/Higgsfield/Telegram/YouTube) go through outbox + idempotency.
6. JSON exports remain available but are rejected as live inputs.
7. Shadow-comparison test green (DB projection == legacy output for same input) before the flip.
8. Crash/resume test green at this stage boundary.

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Big-bang temptation | Strangler order enforced; `produce.py` stays runnable until Sprint H. |
| Hidden file-authority reads | ALN-H1 CI grep gate fails the build on any forbidden read. |
| Paid spend during testing | All integration tests stub providers; only ALN-H4 spends, once, with human gates. |
| Identity migration breaks in-flight projects | ALN-H2 imports + verifies before retirement; dual-write stays on until H5. |
| Assembly ordering of multi-slot beats | ALN-F1 acceptance explicitly covers parent-split + multi-slot ordering from DB. |
| Brittle snapshot tests flip during repair | ALN-H5 re-pins them to frozen fixtures, not live projects. |

---

## 7. Definition of Done (the cutover)

1. `produce_db.py` is the only production entry point; `produce.py` is removed or a thin shim.
2. A topic reaches an approved deliverable using only `production_id` between processes.
3. Deleting all project JSON does not break execution or resume.
4. Every frame/audio interval traces to render unit → timeline span → creative beat → script
   revision → research source → code revision → config snapshot.
5. A crash at every stage boundary resumes with no duplicate paid work.
6. The 2026-06-16 failure classes (multi-slot coverage, clip_id collision, stale change requests,
   duration mismatch) are structurally impossible and covered by DB-model regression tests.
7. Legacy `state.json` / `gates.json` / `clips.db` / `leverage_mind.db` are archived and unwritten.
8. One zero-cost golden run (CI) and one real aligned run are both green.

---

## 8. Immediate Next Action

Start **Sprint A** (orchestrator entry point + legacy-adapter stage contract) and **Sprint B**
(identity split) — in that order. Do not migrate media/assembly stages before the identity split;
that is the work that converts today's hand-patched bugs into structural impossibilities.
