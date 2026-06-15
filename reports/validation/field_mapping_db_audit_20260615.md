# Field Mapping & Clip DB Systems Audit

**Date:** 2025-06-15  
**Auditor:** Independent systems auditor (read-only)  
**Verdict:** SYSTEMICALLY INCOHERENT  
**Scope:** End-to-end field mapping from compile → generate → qa → reconcile → build_manifest → assemble

---

## 1. The Identity Crisis: 7 Identifiers, No Consistent Key

| Field | Created by | Semantics | Uniqueness |
|-------|-----------|-----------|------------|
| `beat_id` | storyboard / production_storyboard | The creative beat. After split: `B003a`, `B003b`. After slot expansion: **DUPLICATED** (all slots share parent `beat_id`) | NOT UNIQUE in media_plan after slot expansion |
| `clip_id` | clip_db (computed) | `{project}::{production_beat_id}::{slot_id\|whole}` | UNIQUE (DB primary key) |
| `slot_id` | compile (_expand_coverage_slots) | Per-slot within a beat: `B003-s0`, `B003-s1` | Unique within a beat, not globally |
| `coverage_slot_id` | compile (_expand_coverage_slots) | Same as slot_id (aliased) | Same as slot_id |
| `source_beat_id` | reconcile_production_storyboard | Original creative beat_id (parent before split) | NOT UNIQUE (children share it) |
| `production_beat_id` | compile (_expand_coverage_slots) | The production storyboard beat (after split, before slot expansion) | NOT UNIQUE in media_plan after slot expansion |
| `media_plan_asset_id` | compile (_expand_coverage_slots) | `{beat_id}-{slot_id}` | UNIQUE per plan |

### Stage × Primary Key Matrix

| Stage | Primary key used | Assumes beat_id unique? | Uses clip_db? | Handles slot-expanded rows? |
|-------|-----------------|------------------------|---------------|---------------------------|
| `audio_timing` (timing map) | `beat_id` | YES (produces 1 row per beat) | No | N/A (pre-expansion) |
| `reconcile_production_storyboard` | `beat_id` | YES (dict indexed by beat_id) | No | N/A (pre-expansion) |
| `compile_media_prompts` | `beat_id` → expands into slots | Creates non-unique beat_ids | YES (CDB-02: orders clips) | YES (creates the expansion) |
| `generate_media` | `beat_id` (iterates plan["beats"]) | NO (iterates list, not dict) | YES (CDB-03: reuse check) | YES (each slot is a list entry) |
| `qa_media` | `beat_id` via `beat.get("beat_id")` | NO (iterates list) | YES (CDB-05: marks valid) | YES |
| `reconcile_duration` | `beat_id` as dict key: `{b["beat_id"]: b}` | **YES — BREAKS** | YES (coverage_for_beat via source_beat_id) | PARTIALLY (DB path works, dict path overwrites) |
| `build_manifest` | `beat_id` as dict key + duplicate check | **YES — HARD FAIL** | YES (CDB-06: assert_all_valid) | **NO — ERRORS ON DUPLICATES** |
| `assemble` | `seg["id"]` (from manifest) | YES (manifest is 1:1 with timing) | NO | N/A (reads manifest only) |

---

## 2. The Slot Expansion Contract Break

When `compile_media_prompts._expand_coverage_slots` expands beat B003 into 3 slots:
- All 3 media_plan entries retain `"beat_id": "B003"` (inherited from `asset = dict(entry)`)
- They get distinct `coverage_slot_id` (`B003-s0`, `B003-s1`, `B003-s2`)
- They get distinct `clip_id` in the DB (`project::B003::B003-s0`, etc.)

### Stages that BREAK on slot-expanded beats:

| Stage | Breakage | Severity |
|-------|----------|----------|
| **build_manifest.py line 127** | `if bid in seen_ids: errors.append(f"Duplicate beat_id in media_plan: {bid}")` | **FATAL** — prevents manifest creation |
| **reconcile_duration.py line 78/124** | `plan_beats = {b["beat_id"]: b for b in plan.get("beats", [])}` — dict comprehension silently overwrites, only last slot survives | **SILENT DATA LOSS** — duration check uses wrong slot |
| **build_manifest.py line 119** | `timing_by_id[t["beat_id"]] = t` — joins timing map (pre-expansion, 1 entry) with plan (post-expansion, 3 entries) — 2 of 3 slots will have "Beat {bid} in media_plan but missing from timing_map" | **LOGIC ERROR** — only 1 timing entry for N plan entries |

### Stages that work despite expansion:

| Stage | Why it works |
|-------|-------------|
| `generate_media` | Iterates `plan["beats"]` as a list; never indexes by beat_id |
| `qa_media` | Iterates list; uses clip_id for DB operations |

### Confirmed in production data:

```
# From how_to_use_ai_to_better_organize_your_de_short/media_plan.json:
beat_id "B003" appears 3 TIMES (slot-expanded)

# From same project's beat_timing_map.json:
beat_id "B011" exists (single entry)

# From same project's production_storyboard.json:
beat_ids "B011a" and "B011b" exist (split) — NOT in timing map
```

This confirms the contract is already broken in the only production project that reached compile.

---

## 3. DB Integration Completeness: Is clip_db Actually Authoritative?

| Stage | Uses clip_db? | How? | Bypasses DB? |
|-------|--------------|------|-------------|
| `compile_media_prompts` | YES | CDB-02: `order_clip()` for every plan beat. Writes canonical path. | NO — but media_plan.json still carries `output_path` which downstream reads directly |
| `generate_media` | YES | CDB-03: `can_reuse(clip_id)`, `get_path(clip_id)`, `record_generated()` | PARTIALLY — falls back to legacy fingerprint if no clip_id |
| `qa_media` | YES | CDB-05: `mark_valid(clip_id)`, `request_change(clip_id)` | NO |
| `reconcile_duration` | YES | DB path: `clip_db.coverage_for_beat()` | ALSO has legacy ffprobe path that reads plan directly |
| **build_manifest** | YES (gate only) | CDB-06: `assert_all_valid()` — but then reads `output_path` from **media_plan.json**, NOT from clip_db | **YES — reads paths from plan, not DB** |
| **assemble** | **NO** | Reads manifest.json only. Never imports clip_db. | **COMPLETE BYPASS** |

### Verdict on DB authority:

**The DB is a STATUS authority but NOT a PATH authority end-to-end.** 

- compile writes paths to both DB and media_plan.json
- build_manifest reads paths from media_plan.json (line ~149: `b.get("output_path", "")`)
- assemble reads paths from manifest.json (which came from build_manifest)
- **Nobody downstream of compile reads `clip_db.get_path(clip_id)` for the actual file location at assembly time**

The comment in clip_db.py says "No pipeline step may derive clip paths independently — they must ask this module." This is **aspirational, not enforced**. The actual path flow is:

```
clip_db.order_clip() → output_path → media_plan.json → build_manifest → manifest.json → assemble
                                     ↑ THIS IS THE REAL AUTHORITY
```

---

## 4. Field Carry-Through Gaps

### Known broken (previously hit):
- `shot_type` — not written to media_plan by compile for some code paths
- `audio_start_sec` — missing when fallback storyboard path is used
- `model` / `asset_type` orphan — inconsistent producer (now guarded by ORPHAN_BEAT check)

### Latent gaps discovered in this audit:

| Gap | Where | Impact |
|-----|-------|--------|
| `segment_id` in timing map | timing map doesn't carry `segment_id`; build_manifest takes it from plan | If a beat is in timing_map but not plan (timing map mismatch), segment_id is lost |
| `words` field | build_manifest calculates `len(narration_text.split())` but only for non-lipsync beats | If narration_text is missing from the plan beat, `words` = 0 → pacing breaks |
| `speech_len_sec` | Carried in `audio_slice` subobject of plan, read by build_manifest | If slice_lipsync step didn't run or failed silently, this is None → assembly can't trim |
| Beat timing for split children | Production storyboard gives `B011a`/`B011b` timing in `audio_start_sec`/`audio_end_sec` fields directly | build_manifest reads from `beat_timing_map.json` which only has `B011` — split children are ORPHANED from timing |
| `graphic.asset_path` | build_manifest expects this field for overlay resolution | compile doesn't always write it for coverage-slot-expanded local_graphic beats |

---

## 5. The Manifest Model: Per-Beat or Per-Slot?

**build_manifest assumes: 1 manifest segment = 1 media_plan beat = 1 timing_map entry.**

This is a **per-beat** model where beat_id must be globally unique.

But the media_plan is a **per-slot** model where beat_id is a parent grouping.

**These are fundamentally incompatible.**

The timing map is also per-beat (pre-expansion). A single timing entry `B003: [18.6s, 37.5s]` maps to 3 plan entries (B003-s0, B003-s1, B003-s2) which collectively cover that 18.9s span. Build_manifest has no logic to:
1. Group plan entries by beat_id
2. Sequence the slots within a beat's timing window
3. Emit multiple manifest segments from one timing entry

The manifest model was designed before slot expansion existed. The slot expansion was bolted on without updating the manifest builder.

---

## 6. Does Assembly Actually Use the DB?

**No.**

`assemble.py` imports: `argparse, hashlib, json, math, shutil, subprocess, sys, tempfile, pathlib`. 
It never imports `clip_db`. It reads `manifest.json` and resolves media via `seg["media"]` (a relative path string set by build_manifest).

The "golden truth" pipeline is:
```
clip_db → compile → media_plan.json → build_manifest → manifest.json → assemble
            ↑                               ↑                              ↑
         DB writes path            reads from plan JSON           reads from manifest JSON
```

Assembly is 3 hops removed from the DB. The DB's `output_path` is only authoritative if all intermediate JSON files faithfully propagate it without transformation. And we've already shown that `build_manifest` can fail before producing a manifest (due to the duplicate beat_id check), making the DB authority moot.

---

## 7. Summary Verdict

### Is the field-mapping/DB system SYSTEMICALLY COHERENT?

**NO. It is fundamentally broken in 3 structural ways:**

1. **Identity model conflict:** The timing map and manifest are per-beat (beat_id = unique key). The media plan is per-slot (beat_id = non-unique parent). These cannot be joined without an aggregation/sequencing layer that does not exist.

2. **Timing map is stale after split:** `beat_timing_map.json` is built from the creative storyboard (step 7/21). Production storyboard (step 8) creates new beat_ids (`B011a`, `B011b`). The timing map is NEVER rebuilt to reflect these. Build_manifest then can't find timing for split children.

3. **DB authority is aspirational:** clip_db is consulted for status gates and reuse decisions, but the actual path-of-record flows through JSON files (media_plan → manifest). Assembly never touches the DB. The "single source of truth" claim is false for the assembly stage.

---

## 8. The ONE Structural Decision Required

**The canonical key for a renderable unit must be `clip_id` (or equivalently `media_plan_asset_id`), not `beat_id`.** Every stage downstream of compile must key on this identifier:

1. **Timing map must be rebuilt post-production-storyboard** to include split children, and then post-compile to include per-slot timing windows (required_start_sec / required_end_sec already exist in the plan — they must become the timing authority for build_manifest).

2. **build_manifest must iterate media_plan entries by `media_plan_asset_id` (or `clip_id`)**, not by `beat_id`. The duplicate check must use this key. The manifest segment `id` must be the slot-level ID, not the beat_id.

3. **assemble either reads clip_db directly (preferred) or the manifest must carry clip_id** so provenance is traceable.

In short: **beat_id is a logical grouping (like a "paragraph"). clip_id / media_plan_asset_id is the physical unit (like a "sentence"). Downstream of compile, everything must speak clip_id.**

The system was originally designed for 1 beat = 1 clip. Slot expansion and beat splitting broke that assumption. The downstream stages were never updated to operate on the new granularity.

---

## Appendix: Evidence from Production Data

```
Project: how_to_use_ai_to_better_organize_your_de_short

beat_timing_map.json beat_ids (13):
  B001 B002 B003 B003b B004 B005 B005c B006 B007 B008 B009 B010 B011

production_storyboard.json beat_ids (14):
  B001 B002 B003 B003b B004 B005 B005c B006 B007 B008 B009 B010 B011a B011b
  ↑ B011 was split into B011a/B011b but timing map still has B011

media_plan.json beat_ids (17 entries, 14 unique):
  B001 B002 B003(×3) B003b B004 B005 B005c B006 B007 B008 B009 B010 B011a B011b
  ↑ B003 appears 3 times (slot expansion) — will trigger "Duplicate beat_id" in build_manifest
  ↑ B011a/B011b have no timing map entry — will trigger "missing from timing_map" in build_manifest
```

This is not a theoretical concern. It is a live breakage in the only project that has reached this stage.
