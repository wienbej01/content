# Sprint: Unified Clip Identity (clip_id) — Architecture Correction

## STATUS: COMPLETE ✅ (UCI-01..07, 628 tests green, audited project reaches clean 16-segment manifest)

| Ticket | Status | Delivered |
|--------|--------|-----------|
| UCI-01 | ✅ | build_manifest keyed by clip_id (removed false duplicate-beat_id check) |
| UCI-02 | ✅ | per-clip timing; killed stale timing-map cardinality gate; split-child timing from parent |
| UCI-03 | ✅ | reconcile keyed by clip_id + count guard (no silent slot drops) |
| UCI-04 | ✅ | assemble reads paths from DB + assert_all_valid gate (golden truth to the end) |
| UCI-05 | ✅ | text-policy false-positive fixed (out_of_focus broll not rerouted to static card) |
| UCI-06 | ✅ | phantom sub-frame (<0.1s) beats merged into neighbor, never emitted as clips |
| UCI-07 | ✅ | full slot+split E2E + clip_id feedback loop (sibling-slot independence proven) |

All 7 invariants hold and are locked by tests. Reports: `reports/remediation/uci/UCI-{01..07}/`

---

## Root cause (confirmed by two independent audits, 2026-06-15)

`beat_id` is non-unique after slot expansion (B003 → 3 rows sharing beat_id=B003) and
after splitting (B011 → B011a/B011b). But downstream stages use `beat_id` as a primary key:
- `build_manifest` hard-fails on duplicate beat_id
- `reconcile_duration` builds `{beat_id: beat}` → silently overwrites, only last slot survives
- `beat_timing_map` is frozen at the creative storyboard and never rebuilt after splits
- `clip_db` is a status gate only; `assemble` never reads it (golden truth stops at compile)

This is a schema/architecture flaw, not a bug. Patching symptoms has failed repeatedly.

## The correction

**`clip_id` is the single canonical unique identifier for a physical renderable clip.**
It is assigned once (by `clip_db.order_clip`) and propagates through EVERY downstream stage.
`beat_id` is demoted to a logical grouping label (the paragraph a clip belongs to) and is
NEVER used as a key downstream of compile. The feedback loop (change requests) keys on `clip_id`.

### The identity model (after this sprint)

```
source_beat_id   = creative/timeline grouping (e.g. "B003") — label only, NON-UNIQUE
production_beat_id = post-split grouping (e.g. "B003", "B011a") — label only, NON-UNIQUE
clip_id          = THE unique physical clip key (e.g. "proj::B003::B003-s0") — UNIQUE, canonical
```

Every downstream artifact (media_plan rows, timing entries, manifest segments, QA results,
reconciliation rows, assembly inputs, change requests) is keyed by `clip_id`.

## Tickets (each gated Engineer → Auditor → Validator, with slot/split E2E tests)

### UCI-01 — clip_id is the manifest key
`build_manifest` iterates and keys by `clip_id`, not `beat_id`. Remove the duplicate-beat_id
check (it's wrong); add a duplicate-`clip_id` check (the correct uniqueness invariant). Each
manifest segment carries `clip_id`, `source_beat_id`, and per-clip timing (from the plan's
`required_start_sec`/`required_end_sec`, not the stale timing map).
**Test:** a plan with B003×3 slots + B011a/B011b builds a manifest with 5 distinct segments.

### UCI-02 — per-clip timing, rebuilt after split (kill the stale timing map)
Timing for each clip comes from its own `required_start_sec`/`required_end_sec` (already in the
plan/DB), NOT from a beat_timing_map keyed by parent beat_id. The production storyboard already
has exact per-clip intervals. Either (a) rebuild beat_timing_map keyed by clip_id after
production reconciliation, or (b) make all consumers read per-clip timing from the plan/DB.
Prefer (b) — single source. Remove the "beat in timing_map but missing from plan" check that
breaks on split children.
**Test:** split children (B011a/B011b) have correct contiguous timing; no timing-map mismatch error.

### UCI-03 — reconcile_duration keys by clip_id
`reconcile_duration` must not build `{beat_id: beat}` (silent overwrite). It already uses
`coverage_for_beat(source_beat_id)` via the DB (CDB-04) — verify it sums ALL clips per
source_beat_id correctly and never collapses slots. Add a guard that the number of clips
reconciled equals the number of clips in the DB (no silent drops).
**Test:** B003 (3 slots) + B011 (2 children) reconcile with all 5 clips counted, zero dropped.

### UCI-04 — assemble reads clip paths from the DB (extend golden truth to the end)
`assemble` resolves each segment's media path via `clip_db.get_path(clip_id)`, and calls
`clip_db.assert_all_valid(project_id)` before muxing. The DB is authoritative through final
assembly, not just through compile.
**Test:** assemble uses DB paths; a non-valid clip blocks assembly even if a manifest exists.

### UCI-05 — text-surface policy respects text_policy=out_of_focus (P1 false-positive fix)
The reroute-to-local_graphic must NOT fire when the beat's `text_policy` is `out_of_focus`/`none`
(no readable text requested). A cinematic b-roll with "writing" as a physical action and
out-of-focus text must stay generated_video with the terms negated, not become a static card.
**Test:** a broll beat with text_policy=out_of_focus + "writing/document" in brief stays
generated_video (negated), is NOT rerouted to local_graphic.

### UCI-06 — phantom-duration guard (P2)
Beats assigned < ~0.2s (sub-frame, e.g. the 0.01s B003b/B005c) must be flagged: either merged
into a neighbor or dropped with a logged reason. A sub-frame clip is not renderable.
**Test:** a 0.01s beat is caught (merged or dropped), never passed to generation as a clip.

### UCI-07 — full slot+split E2E + golden-truth closed loop
One local-fixture E2E (no paid APIs) that runs a project containing BOTH a slot-expanded beat
AND a split beat through: compile → order (DB) → generate (mock) → qa → reconcile → manifest →
assemble → assert_all_valid. Plus a feedback-loop case: a clip fails QA → change request keyed
by clip_id → regenerate → resolve → valid → assembly proceeds.
**Test:** the whole chain works on slot+split beats; the feedback loop closes on clip_id.

## Invariants this sprint must establish (and lock with tests)

1. `clip_id` is unique and present on every clip at every stage after compile.
2. No stage uses `beat_id` as a uniqueness key or dict key.
3. Per-clip timing is read from the clip's own interval, never a parent-keyed map.
4. The clip DB is the path + status authority from compile through assemble.
5. Change requests (feedback loop) key on `clip_id`.
6. Slot-expanded and split beats pass end-to-end with zero silent drops.
7. text_policy=out_of_focus beats are not falsely rerouted.

## Definition of done
- All 7 invariants hold and are covered by tests.
- The audited project (how_to_use_ai_to_better_organize_your_de_short) builds a manifest and
  reaches assembly with no duplicate-key / missing-timing / orphan errors.
- Full suite green. No paid APIs in tests.
- Both auditors' P0 findings are resolved.
