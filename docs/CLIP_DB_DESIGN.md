# Clip/Slot Authority Database — Design & Analysis

## STATUS: IMPLEMENTED ✅ (CDB-01 through CDB-06 complete, 588 tests green)

| Phase | Status | What it delivered |
|-------|--------|-------------------|
| CDB-01 | ✅ DONE | `scripts/clip_db.py` — manager, schema, change-request API, golden-truth gate |
| CDB-02 | ✅ DONE | `compile_media_plan` orders clips through DB — ONE canonical path |
| CDB-03 | ✅ DONE | `generate_media` uses `can_reuse()` (kills stale reuse) + records actual attrs |
| CDB-04 | ✅ DONE | `reconcile_duration` uses `coverage_for_beat()` (resolves parent→children) |
| CDB-05 | ✅ DONE | `qa_media` interactive — marks valid / raises routed change requests |
| CDB-06 | ✅ DONE | `build_manifest` gated by `assert_all_valid()` + closed-loop E2E proven |

Reports: `reports/remediation/clip_db/CDB-{01..06}/`

---

## The Problem (root cause of recurring failures)

There is **no single authoritative record** of what each clip/slot is. Every pipeline step
independently derives clip IDs, paths, and durations — so they drift apart and produce the
recurring failure classes:

| Failure class | Real example | Cause |
|---------------|-------------|-------|
| Stale reuse | B004.mp4 (10s) reused when plan wanted 15s | Reuse keyed on file-exists, not on plan-required attributes |
| Path mismatch | plan wants `B004_B004-s0.mp4`, only `B004.mp4` exists | Two different path formats in compile_media_prompts.py (line 252 vs 698) |
| Parent/child confusion | reconcile looks for `B005`, plan has `B005a`+`B005b` | No parent→child mapping; each step guesses |
| Slot files never generated | B006/B009 slots missing | Generation reused old single clip, ignored slot paths |
| Wrong directory | line 252 uses `{segment_id}/`, line 698 uses `{project_id}/` | Inconsistent path derivation |

### Current path-derivation drift points (each computes paths independently)

| File | Line | Path format |
|------|------|-------------|
| compile_media_prompts.py | 252 | `assets/media/{segment_id}/{beat_id}.mp4` |
| compile_media_prompts.py | 698 | `assets/media/{project_id}/{beat_id}_{slot_id}.mp4` |
| generate_media.py | (reuse) | globs by beat_id, not plan output_path |
| reconcile_duration.py | — | looks up timing_map beat_id in plan (parent vs child fails) |
| qa_media.py | — | reads media_plan output_path |
| build_manifest.py | 123 | reads media_plan output_path |

Five files, at least three different conventions. This is the disease.

---

## The Solution: One Clip/Slot Authority DB

A single SQLite database (`db/clips.db`) with ONE manager module (`scripts/clip_db.py`)
that **every** pipeline step calls. No step may derive a clip path or ID independently —
they must ask the DB. The DB is the single source of truth for:

- which clips/slots are "ordered" (planned)
- their canonical IDs (parent, child, slot) and lineage
- their canonical file paths
- their required duration, audio policy, model
- their generation status (planned / generating / generated / failed / stale)
- their actual rendered attributes (duration, dimensions, has_audio, sha256)
- when/by which step each was created, accessed, validated, invalidated

### Schema

```sql
CREATE TABLE clips (
    -- Identity & lineage (THE canonical IDs)
    clip_id            TEXT PRIMARY KEY,   -- canonical unique id, e.g. "proj::B004::s0"
    project_id         TEXT NOT NULL,
    source_beat_id     TEXT NOT NULL,      -- timing-map parent, e.g. "B004"
    production_beat_id TEXT NOT NULL,      -- post-split, e.g. "B004" or "B005a"
    slot_id            TEXT,               -- post-expansion, e.g. "B004-s0" (NULL if not slotted)
    split_index        INTEGER,
    split_total        INTEGER,

    -- Canonical location (THE single source of path truth)
    output_path        TEXT NOT NULL,      -- the ONE authoritative path; no step derives its own

    -- Order spec (what was requested)
    asset_type         TEXT NOT NULL,      -- generated_video | local_graphic
    model              TEXT,               -- seedance_2_0 | kling3_0 | local_graphic
    audio_policy       TEXT NOT NULL,      -- keep_lipsync | strip | post_overlay
    lipsync_required   INTEGER NOT NULL,
    required_start_sec REAL NOT NULL,      -- position in master timeline
    required_end_sec   REAL NOT NULL,
    required_dur_sec   REAL NOT NULL,      -- what the clip MUST cover

    -- Audio provenance (for lipsync)
    audio_slice_path   TEXT,
    audio_slice_sha256 TEXT,
    speech_len_sec     REAL,

    -- Generation status (lifecycle)
    status             TEXT NOT NULL,      -- planned | ordered | generating | generated | failed | stale
    status_reason      TEXT,

    -- Actual rendered attributes (filled after generation)
    actual_dur_sec     REAL,
    actual_width       INTEGER,
    actual_height      INTEGER,
    actual_has_audio   INTEGER,
    actual_sha256      TEXT,

    -- Dependency fingerprint (invalidation)
    plan_sha256        TEXT,               -- sha of the media_plan entry that ordered this
    upstream_sha256    TEXT,               -- sha of audio slice / timing inputs

    -- Audit trail
    created_at         TEXT NOT NULL,
    created_by_step    TEXT,
    generated_at       TEXT,
    last_validated_at  TEXT,
    invalidated_at     TEXT,

    UNIQUE(project_id, production_beat_id, slot_id)
);

CREATE TABLE clip_access_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id     TEXT NOT NULL,
    step        TEXT NOT NULL,      -- which pipeline step accessed it
    action      TEXT NOT NULL,      -- order | generate | reuse | validate | invalidate | consume
    detail      TEXT,
    at          TEXT NOT NULL,
    FOREIGN KEY (clip_id) REFERENCES clips(clip_id)
);
```

### Manager API (`scripts/clip_db.py`)

```python
# THE ordering authority — compile calls this; it assigns canonical paths
order_clips(project_id, plan_beats) -> list[clip rows]
    # For each media-plan beat/slot, upsert a clip row with canonical clip_id + output_path.
    # Path is computed HERE, once, by one rule. No other step derives paths.

# THE reuse authority — generation calls this BEFORE generating
can_reuse(clip_id) -> (bool, reason)
    # Returns True only if: file exists at canonical output_path
    #   AND actual_sha256 matches recorded AND plan_sha256 unchanged
    #   AND actual_dur_sec covers required_dur_sec (within tolerance)
    #   AND audio policy satisfied. Otherwise False with reason → regenerate.

record_generated(clip_id, probe_result)   # generation writes actual attributes
mark_failed(clip_id, error)
mark_stale(clip_id, reason)                # invalidation cascades on upstream change

# THE coverage authority — reconcile calls this (resolves parent→children)
coverage_for_beat(project_id, source_beat_id) -> {required, available, slots[], deficit}
    # Sums all clips with source_beat_id == X. No parent/child guessing.

get_clip(clip_id) / get_path(clip_id)      # canonical path lookup — nobody derives paths
list_clips(project_id, status=None)
log_access(clip_id, step, action, detail)  # every read/write logged
```

### How each step uses it (replacing independent derivation)

| Step | Current (drift) | With clip_db (authority) |
|------|-----------------|--------------------------|
| compile_media_plan | derives 2 path formats | calls `order_clips()` — DB assigns ONE path |
| slice_lipsync | writes slice path into plan | records slice in `clips.audio_slice_path` |
| generate_media | globs by beat_id, reuses blindly | calls `can_reuse()`; generates to `get_path()`; `record_generated()` |
| qa_media | reads plan output_path | reads `clips`, checks actual vs required |
| reconcile_duration | parent/child mismatch | calls `coverage_for_beat()` — resolves lineage |
| build_manifest | reads plan output_path | reads `clips` canonical paths |
| assemble | reads manifest paths | reads `clips` canonical paths |

---

## Why This Eliminates the Failure Classes

1. **One path, computed once** — no step derives its own path → no path mismatch.
2. **Reuse checks required attributes** — `can_reuse()` compares actual duration/sha/policy
   against the order spec → no stale reuse.
3. **Lineage is explicit** — `source_beat_id`, `production_beat_id`, `slot_id` are columns,
   not guessed → reconcile resolves parent→children correctly.
4. **Status lifecycle** — a clip is `planned → ordered → generated → validated`; an upstream
   change marks it `stale` → never silently reused.
5. **Full audit trail** — `clip_access_log` records who ordered/generated/reused/consumed each
   clip and when → no doubt about "which clips are ordered, what changed, where accessed".

---

## Migration Plan (phased, each gated by Engineer→Auditor→Validator)

| Phase | Ticket | Scope |
|-------|--------|-------|
| 1 | CDB-01 | Build `clip_db.py` + schema (clips + access_log + change_requests) + tests. Includes the interactive change-request API (request_change / resolve_change / assert_all_valid). No pipeline wiring yet. |
| 2 | CDB-02 | `compile_media_plan` calls `order_clips()` — DB becomes path + ID authority |
| 3 | CDB-03 | `generate_media` uses `can_reuse()` + `record_generated()`; resolves regenerate change requests |
| 4 | CDB-04 | `reconcile_duration` uses `coverage_for_beat()`; raises change requests on deficit instead of crashing |
| 5 | CDB-05 | review/compliance steps (storyboard_review, qa_media) become interactive: read repository, raise change requests routed to owning step |
| 6 | CDB-06 | `build_manifest` + `assemble` call `assert_all_valid()` — cannot proceed with any open change request; full E2E test of the closed loop |

Each phase keeps the pipeline working (DB runs alongside until a step is migrated). The
golden-truth invariant (`assert_all_valid` gating assembly) lands in CDB-06 once all
producers/consumers route through the DB.

---

## Interactive Bidirectional Model (golden-truth invariant)

The DB is **NOT a passive logbook**. It is the interactive golden source. Every review,
compliance, and production step both READS the current clip repository and WRITES changes
back, and any required change is fed to the owning step which then updates the DB. The DB
is updated on EVERY change so it always reflects reality.

### The three interaction modes

**1. READ — every step queries the DB to understand the current repository**
Before acting, a step asks the DB "what is the current truth about these clips?" — their
status, paths, durations, lineage, what's stale, what's missing. No step works from its own
private assumption of clip state.

```python
clips = clip_db.list_clips(project_id)              # current repository snapshot
stale = clip_db.list_clips(project_id, status="stale")
missing = clip_db.list_clips(project_id, status="planned")  # ordered but not generated
```

**2. CHANGE REQUEST — review/compliance push required changes back to the owning step**
When a review or compliance step finds a problem (clip too short, wrong audio policy,
missing slot, over-limit duration), it does NOT fix the clip itself. It records a
CHANGE REQUEST against the clip in the DB and routes it to the step that owns that change.
The owning step picks up the request, makes the change, and writes the result back.

```python
# review_storyboard / qa_media / reconcile finds an issue:
clip_db.request_change(clip_id, requested_by="qa_media", target_step="generate_media",
                       change_type="regenerate", reason="actual 10.1s < required 14.0s")
# This sets clip.status = "change_requested" and logs it. The clip is NOT golden-valid
# until the owning step resolves the request and the DB is updated.
```

**3. UPDATE — the owning step resolves the change and updates the DB**
The step that owns the change (e.g. generate_media for a regenerate, compile for a re-route,
slice for a re-slice) performs the change and writes the new truth back. Only then does the
clip return to a valid status. The DB transition is the authoritative record that the change
happened.

```python
# generate_media resolves the regenerate request:
clip_db.record_generated(clip_id, probe_result)     # writes actual attrs
clip_db.resolve_change(clip_id, resolved_by="generate_media", outcome="regenerated")
```

### Change request lifecycle (state machine)

```
planned ──order──▶ ordered ──generate──▶ generated ──validate──▶ valid
                                              │                      │
                                              │                      │ review/compliance/reconcile
                                              │                      │ finds a problem
                                              ▼                      ▼
                                           failed            change_requested
                                              │                      │
                                              │   owning step resolves the change
                                              └──────────┬───────────┘
                                                         ▼
                                                   (re-generate / re-slice / re-route)
                                                         │
                                                         ▼
                                                     generated ──▶ valid
```

A clip is **golden-valid** ONLY in the `valid` state. Any change request immediately drops
it out of `valid`, so no downstream step can consume a clip that has an open change request.
This is the invariant that keeps the DB the golden truth: **the DB state always matches
reality, because reality cannot advance past an open change request.**

### Which step owns which change type

| change_type | requested by (typically) | owning step (resolves) |
|-------------|--------------------------|------------------------|
| regenerate | qa_media, reconcile | generate_media |
| re-slice | qa_media (audio mismatch) | slice_lipsync |
| re-route | reconcile (over-limit) | production_storyboard / compile |
| re-path | compile (slot expansion) | compile_media_plan |
| re-render-graphic | qa | render_graphics |
| human-override | gate_b / escalation | human (via clip_db.apply_human_override) |

### Schema additions for change requests

```sql
CREATE TABLE clip_change_requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id       TEXT NOT NULL,
    change_type   TEXT NOT NULL,      -- regenerate | re-slice | re-route | re-path | ...
    requested_by  TEXT NOT NULL,      -- step that found the problem
    target_step   TEXT NOT NULL,      -- step that must resolve it
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL,      -- open | resolved | rejected
    requested_at  TEXT NOT NULL,
    resolved_at   TEXT,
    resolved_by   TEXT,
    outcome       TEXT,
    FOREIGN KEY (clip_id) REFERENCES clips(clip_id)
);
```

### Manager API additions

```python
request_change(clip_id, requested_by, target_step, change_type, reason)
    # Logs a change request, sets clip.status = "change_requested". Clip leaves valid state.

open_change_requests(project_id, target_step=None) -> list
    # The owning step polls for work assigned to it.

resolve_change(clip_id, resolved_by, outcome)
    # Owning step marks the request resolved after updating the clip. Returns clip to flow.

apply_human_override(clip_id, decision, note)
    # Human (via Telegram/escalation) overrides — logged, authoritative.

assert_all_valid(project_id) -> (bool, open_requests)
    # GATE: assembly/manifest call this. Fails if ANY clip is not in 'valid' state
    # or has an open change request. Makes shipping a clip with a pending change impossible.
```

### How review/compliance steps become interactive (concrete)

| Step | Reads from DB | Writes / requests to DB |
|------|---------------|-------------------------|
| storyboard_review | current planned clips + lineage | request_change(re-route) if a beat is over-limit |
| compliance_check | clip durations vs model limits | request_change(re-route/re-slice) |
| qa_media | actual vs required per clip | request_change(regenerate/re-slice) on mismatch; mark valid on pass |
| reconcile_duration | coverage_for_beat (resolves lineage) | request_change(regenerate) for deficits |
| build_manifest | assert_all_valid() | refuses to build if open requests exist |
| assemble | canonical paths, assert_all_valid() | refuses to assemble if not all valid |
| gate_b / escalation | full clip repository summary | apply_human_override |

This closes the loop: a problem found anywhere becomes a tracked change request routed to
the owner, the owner fixes it and updates the DB, and nothing downstream proceeds until the
DB shows every clip valid. The DB is always the golden truth because the pipeline cannot
advance past an unresolved DB state.

---

## Relationship to Existing Components

- **content_db.py (P5-06)**: tracks whole content UNITS + performance metrics (analytics).
  Different scope — keep it. clip_db is per-CLIP production state. They can share `db/`.
- **artifact_fingerprint.py (TKT-01)**: provides sha256 + .fp.json sidecar. clip_db SUBSUMES
  its role for clips (stores sha + plan/upstream hashes in columns). The sidecar approach
  is replaced by the DB for clips; fingerprints remain for non-clip artifacts (plans, etc.).
- **gates.py**: gate ledger stays — it gates SPEND. clip_db tracks clip STATE + change
  requests. Complementary: gates guard money, clip_db guards clip correctness.
