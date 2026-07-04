# Production Pipeline Data Flow Map — Database-Driven Edition

## Systemic principle: all state flows through the unified production ledger

Every clip's canonical identity, lifecycle, and attributes are registered in the unified
production ledger (`production_db.py`). The ledger enforces **transactional consistency**,
**idempotent writes**, and a **golden-truth invariant**: no downstream stage may proceed
past an unresolved change request.

The `clip_db.py` authority database provides the migration boundary from file-led pipeline
state to the transactional system of record. Media payloads remain in the artifact store;
the database records identity, lifecycle, checksums, lineage, and evidence.

Concrete rule (locked by tests):
- No step may derive clip paths independently — all paths come from `clip_db.get_path(clip_id)`
- No step may determine reuse independently — all reuse checks use `clip_db.can_reuse(clip_id)`
- No step may guess parent→child lineage — all lineage is explicit via `source_beat_id`
- Assembly is gated by `clip_db.assert_all_valid()` and `production_db.blockers()`

---

## Overview

This document maps how media segments flow through the enhanced database-driven pipeline.
It explains the **transactional ledger model**, **change request routing**, and how
**fingerprint harmonization** eliminates stale reuse, path mismatch, and parent/child confusion.

---

## Active Pipeline Stage Sequence (DB-Native)

```
1. research               → document_revisions: research_brief
2. write_script           → document_revisions: script
3. review_script          → review evidence and active script revision
4. gate_a_content         → approval_requests
5. storyboard             → Sonnet 5 canonical storyboard + projected DB beats
6. review_storyboard      → non-mutating canonical creative review
7. gate_storyboard        → approval_requests
8. tts                    → artifacts: narration master
9. audio_timing           → document_revisions: timing_map
10. reconcile_timing      → timeline_spans / timing reconciliation
11. compile_media         → render_units + render_plan
12. gate_a_spend          → approval_requests bound to spend/render plan
13. generate_media        → provider_jobs + artifacts for provider-eligible units
14. qa_media              → validations + change_requests
15. repair                → routed remediation from validation failures
16. graphics_compositing  → local graphic artifacts
17. assemble              → deliverables
18. qa_final              → final-cut validation evidence
19. gate_b_review         → approval_requests
20. publish               → publish state and external IDs
21. analytics             → post-publish performance records
```

The stage graph is authoritative in `scripts/stage_runner.py`; invokers live in
`scripts/produce_db.py`.

---


## Unified Production Ledger Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Unified Production Ledger (production_db.py)                            │
│                                                                         │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐               │
│  │ productions  │  │ stage_runs    │  │ render_units    │               │
│  │ • project_id │  │ • stage_name  │  │ • clip lineage  │               │
│  │ • status     │  │ • status      │  │ • status        │               │
│  │ • seed       │  │ • evidence    │  │ • artifacts     │               │
│  │ • metadata   │  │ • metrics     │  │ • validations   │               │
│  └──────────────┘  └───────────────┘  └─────────────────┘               │
│                                                                         │
│  ┌────────────────┐  ┌─────────────┐  ┌──────────────────┐              │
│  │ approval_requests│ │ change_requests│ │ artifacts      │              │
│  │ • gate         │  │ • type      │  │ • SHA-256        │              │
│  │ • status       │  │ • owner     │  │ • size           │              │
│  │ • evidence     │  │ • reason    │  │ • metadata       │              │
│  │ • decision     │  │ • resolution│  │ • storage        │              │
│  └────────────────┘  └─────────────┘  └──────────────────┘              │
│                                                                         │
│  ┌─────────────────┐  ┌────────────────┐                                │
│  │ document_revisions│ │ production_events│                              │
│  │ • kind         │  │ • event_type  │                                │
│  │ • revision     │  │ • actor       │                                │
│  │ • payload_sha  │  │ • payload     │                                │
│  │ • status       │  │ • timestamp   │                                │
│  └─────────────────┘  └────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
                      │
                      │ Legacy State Mirroring
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Clip Authority Database (clip_db.py)                                    │
│                                                                         │
│  ┌─────────────────────┐  ┌────────────────────┐  ┌──────────────────┐ │
│  │ clips              │  │ clip_change_requests│  │ clip_access_log  │ │
│  │ • canonical_id     │  │ • change_type      │  │ • step           │ │
│  │ • source_beat_id   │  │ • requested_by     │  │ • action         │ │
│  │ • output_path      │  │ • target_step      │  │ • timestamp      │ │
│  │ • required_attrs   │  │ • reason           │  │ • detail         │ │
│  │ • actual_attrs     │  │ • status           │  │                  │ │
│  │ • plan_sha256      │  │ • resolution       │  │                  │ │
│  └─────────────────────┘  └────────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Transactional Guarantees

1. **Atomic state transitions** - Each stage run is recorded as a transaction
2. **Idempotent writes** - Mirror operations use deterministic event keys
3. **Golden-truth invariant** - `assert_all_valid()` gates downstream progression
4. **Full audit trail** - Every state change has an associated event
5. **Change request routing** - Problems are routed to owning steps automatically

## Beat ID Transformations with Harmonized Lineage

The beat_id changes form at THREE stages, but lineage is now explicit:

| Stage | Input beat IDs | Output beat IDs | Unified Ledger Record | Clip DB Record |
|-------|---------------|-----------------|----------------------|----------------|
| Timing map (step 7) | — | B001-B011 (parents) | `document_revision` (timing_map) | (parent lineage) |
| Canonical storyboard projection (step 5) | Sonnet `shots[]` | DB creative beats with `canonical_shot_id` | `document_revision` (storyboard) | `source_beat_id` and canonical lineage |
| Timing reconciliation (steps 9-10) | Storyboard beats | timeline spans | `timeline_spans` / reconciliation output | span lineage |
| Media plan compile (step 11) | reconciled beats | render units and slots | `render_units` ordered | `slot_id=s0,s1`, `source_beat_id=B004` |

**Critical consequence**: downstream steps no longer guess transformations:
- `coverage_for_beat()` resolves parent→children→slots via explicit `source_beat_id`
- `assert_all_valid()` gates assembly until all lineage is validated
- Change requests are routed based on owning step and change type

## How a Change Propagates (Enhanced Flow)

```
constraints.json change (e.g. max_clip 10→15)
    │
    ↓ invalidates via DAG:
    production_storyboard.json (different split decisions)
        │
        ↓ mirrored to unified ledger:
        document_revision (new storyboard revision)
            │
            ↓ triggers:
            clip_db.mark_stale() for affected clips
            production_db.invalidate_stages(["compile_media_plan", "generate_media"])
                │
                ↓ routed automatically:
                change requests to owning steps
                    │
                    ▼ (golden-truth invariant blocks progression)
                    compile_media_plan resolves → clip_db.order_clips()
                    generate_media resolves → clip_db.record_generated()
                    ↓
                    clip_db.assert_all_valid() passes → assembly proceeds
```

**The fix**: when the media plan changes (new slot paths), old clips are marked `stale`
and `can_reuse()` returns `False`. The `assert_all_valid()` gate blocks assembly until
all change requests are resolved. No silent degradation, no path mismatch.

## How Segments Are Created (Database-Driven)

| Beat Type | Created At | Authority DB | Unified Ledger |
|-----------|-----------|--------------|----------------|
| hero_lipsync (whole) | generate_media | `can_reuse()` → `record_generated()` | `render_units` + `artifacts` |
| hero_lipsync (split child) | generate_media | `source_beat_id` lineage | `render_units` + `artifacts` |
| broll (single) | generate_media | `output_path` canonical | `render_units` + `artifacts` |
| broll (slot-expanded) | generate_media | `slot_id` + `output_path` | `render_units` + `artifacts` |
| local_graphic | graphics_compositing | `asset_type=local_graphic` | `artifacts` (PNG) |
| hero_cutaway (rerouted) | generate_media | `audio_policy=strip` | `render_units` + `artifacts` |
| reused footage | artifact-linking step before generate_media | `asset_type=reused`, no provider job | existing `artifacts`; blocks as `reused_asset_unlinked` if missing |

## Sonnet Storyboard Data Flow

The live storyboard stage is no longer a deterministic Python visual planner in
production mode. Python loads the approved script from the ledger, invokes Sonnet
5 through Kilo, validates the canonical contract, and then projects the canonical
shots into DB-compatible beats.

```text
document_revisions(script)
    ↓
sonnet_storyboard_wrapper.generate_canonical_storyboard()
    ↓
schemas/storyboard_v2.schema.json validation
    ↓
storyboard_projection.project_canonical()
    ↓
document_revisions(storyboard)
    ↓
review_storyboard_v2.creative_review()
```

The canonical payload preserves source-level creative fields such as
`claim_inventory`, `narrative_beats`, `shots`, `overlays`,
`segment_work_orders`, `feedback_policy`, `timing_policy`, `approval`, and
`_authoring_metadata`. The projected DB beat layer preserves canonical lineage
for downstream compile, QA, and repair.

## Change Request Lifecycle (Interactive Bidirectional)

```
                    ┌─────────────────────────────┐
                    │ review/compliance/qa finds  │
                    │ problem                     │
                    └───────────────┬─────────────┘
                                    │
                                    ▼
               clip_db.request_change()    →  production_db.mirror_change_request()
               │   • change_type             │   • tracked in unified ledger
               │   • target_step             │   • routed to owning step
               │   • reason                  │
               └─────────────────────────────┘
                                    │
                                    ▼
                owning step polls open_change_requests()
                │
                ▼
            resolve_change()        →  production_db.resolve_mirrored_changes()
            │   • outcome             │   • evidence recorded
            │   • new truth           │   • state transition logged
            └─────────────────────────────┘
                                    │
                                    ▼
            mark_valid() / record_generated()
            │
            ▼
        assert_all_valid() passes → assembly proceeds
```

## Harmonized Clip Fingerprint System

### The Problem (Resolved)

| Failure class | Cause | Enhanced Solution |
|---------------|-------|-------------------|
| Stale reuse | Reuse keyed on file-exists, not on plan-required attributes | `can_reuse()` checks: file exists at canonical path, SHA matches, duration covers required, audio policy satisfied, plan SHA unchanged |
| Path mismatch | Multiple path derivation formats (compile line 252 vs 698) | `_canonical_path()` computed once in `clip_db.py`; all steps use `get_path(clip_id)` |
| Parent/child confusion | No explicit mapping; each step guesses | `source_beat_id`, `split_index`, `slot_id` columns; `coverage_for_beat()` resolves lineage |
| Slot files never generated | Generation reused old single clip, ignored slot paths | `can_reuse()` checks exact `output_path`; slot clips have distinct `clip_id` values |

### The Solution (Implemented)

1. **One path, computed once** - `_canonical_path()` rule in `clip_db.py`
2. **Reuse checks required attributes** - `can_reuse()` validates against order spec
3. **Lineage is explicit** - Database columns track parent→child→slot relationships
4. **Status lifecycle** - `planned → ordered → generated → valid` with `stale`/`failed` states
5. **Full audit trail** - `clip_access_log` records every interaction
6. **Interactive change requests** - Problems become tracked work items routed to owners

## Migration Status

✅ **CDB-01 through CDB-06 complete** (588 tests green)
✅ **Unified production ledger implemented** (transactional, idempotent)
✅ **Legacy state mirroring operational** 
✅ **Harmonized fingerprints eliminate drift**
✅ **Golden-truth invariant enforces consistency**

The system now operates with **zero silent degradation** — any mismatch, stale reuse, or
path error becomes a tracked change request that blocks progression until resolved.
