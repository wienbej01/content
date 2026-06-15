# Production Pipeline Data Flow Map

## Systemic principle: stages derive behaviour from the authoritative contract, never re-infer

Every clip's behaviour-determining attributes — `audio_policy`, `asset_type`, `model`,
per-clip timing, and `clip_id` — are set ONCE (by compile/reconcile, recorded in the clip DB
and carried in the media plan + manifest). Downstream stages MUST read these authoritative
fields. They must NOT re-infer behaviour from incidental signals like the media file extension.

Concrete rule (locked by tests):
- Whether a segment needs its own audio is determined by `audio_policy`:
  - `keep_lipsync` → baked audio in the clip
  - `strip` / `post_overlay` in continuous_voiceover mode → silent visual under the master
    narration track; needs NO per-segment audio (even when the media is a .png graphic card)
  - segment_tts mode → each segment carries its own audio
- `words=0` is valid for a silent graphic in continuous mode; required >0 only in segment_tts.
- assemble resolves the media PATH from the clip DB (`get_path(clip_id)`), not from a derived
  filename, and gates on `assert_all_valid`.

This replaces the previous defect class where assemble re-derived "is this an image that needs
audio?" from `media.suffix == .png`, contradicting the DB/plan which had already declared the
clip a silent local_graphic under continuous narration.

---

## Overview

This document maps how media segments are created, referenced, validated, and consumed
through the entire pipeline. It explains how feedback/changes propagate (or fail to
propagate) and identifies the structural mismatches causing stale-data failures.

---

## Pipeline Stage Sequence

```
1. research               → research_brief.json
2. script_create          → script.json
3. script_review_loop     → script.json (revised)
4. storyboard_create      → storyboard.json (creative, estimated timing)
5. storyboard_review_loop → storyboard.json (reviewed)
6. tts                    → narration/continuous.mp3
7. build_timing_map       → narration/beat_timing_map.json (PARENT beat IDs: B001-B011)
8. production_storyboard  → production_storyboard.json (may SPLIT beats: B005→B005a+B005b)
9. compliance_check       → (validation only)
10. compile_media_plan    → media_plan.json (may EXPAND slots: B004→B004_B004-s0, B004_B004-s1)
11. slice_lipsync         → media_plan.json (adds audio_slice entries)
12. gate_a_budget         → (human approval)
13. generate_media        → assets/media/{segment}/{beat_id}.mp4
14. qa_media              → media_qa_report.json
15. reconcile_duration    → duration_reconciliation.csv
16. render_graphics       → assets/overlays/
17. build_manifest        → manifest.json
18. assemble              → {project}_16x9.mp4
19. qa_final              → final_qa_report.json
20. build_quality_report  → run_quality_report.json
21. gate_b_review         → (Telegram)
```

---

## Beat ID Transformations

The beat_id changes form at THREE stages:

| Stage | Input beat IDs | Output beat IDs | Reason |
|-------|---------------|-----------------|--------|
| Timing map (step 7) | — | B001-B011 (parents) | One per script segment |
| Production storyboard (step 8) | B001-B011 | B001, B005a, B005b, B011a, B011b... | SPLIT at silence boundaries |
| Media plan compile (step 10) | B005a, B004, B006... | B004_B004-s0, B004_B004-s1... | SLOT EXPANSION for broll |

**Critical consequence**: downstream steps must resolve these transformations:
- `reconcile_duration.py` uses **timing_map beat IDs** (parents)
- `generate_media.py` uses **media_plan beat IDs** (slot-expanded)
- `qa_media.py` uses **media_plan beat IDs**
- The mapping parent → children → slots must be traceable

---

## Where the Current Failure Occurs

### Failing beats in `reconcile_duration` (step 15):

| Timing Map Beat | Duration Required | Media Plan Entries | Files Exist? | Problem |
|----------------|-------------------|-------------------|--------------|---------|
| B004 | 7.194s | B004_B004-s0, B004_B004-s1 | NO, NO | Slots never generated (old B004.mp4 reused at wrong path) |
| B005 | 19.367s | B005a (11.565s), B005b (7.802s) | YES, YES | reconcile_duration can't find "B005" (only B005a/B005b exist) |
| B006 | 9.190s | B006_B006-s0, B006_B006-s1 | NO, NO | Same as B004 — slots never generated |
| B009 | 17.154s | B009_B009-s0, B009_B009-s1, B009_B009-s2 | NO, NO, NO | Same — slots never generated |
| B011 | 21.027s | B011a (13.14s), B011b (7.887s) | YES, YES | Same as B005 — parent ID lookup fails |

### Root Causes (2 distinct systemic issues):

**Issue A: Generation reuses at WRONG PATHS**
When `compile_media_plan` expands broll beats into slots (B004→B004_B004-s0.mp4, B004_B004-s1.mp4),
the output_path changes. But `generate_media.py` looks for an existing file at the OLD path
(assets/media/.../B004.mp4) — finds it, reuses it, and never generates the slot files.
The old file satisfies the fingerprint check (same project) but is at a different path than
what the plan now expects.

**Issue B: reconcile_duration uses parent IDs, plan uses child IDs**
`reconcile_duration.py` reads `beat_timing_map.json` (parent IDs: B005, B011) and tries to
find them in `media_plan.json` (which has B005a, B005b, B011a, B011b). It can't find the
parent, so it reports the full parent duration as a deficit — even though the children's
clips DO exist and DO cover the interval.

---

## How a Change Propagates (Current State)

```
constraints.json change (e.g. max_clip 10→15)
    │
    ↓ invalidates (via DAG/fingerprint):
    production_storyboard.json (different split decisions)
        │
        ↓ invalidates:
        media_plan.json (different beat structure, paths, costs)
            │
            ↓ SHOULD invalidate:
            ✗ OLD generated clips at OLD paths → NOT invalidated (stale reuse)
            ✗ reconcile_duration comparison → USES WRONG IDs (parent vs child)
```

**The gap**: when the media plan changes (new slot paths), old clips at old paths are NOT
deleted or invalidated. The fingerprint system checks project_id + sha256, but does NOT
check whether the file PATH matches what the current plan expects. So a clip at
`B004.mp4` is "valid" by fingerprint but the plan now expects `B004_B004-s0.mp4`.

---

## How Segments Are Created

| Beat Type | Created At | Source Audio | Expected Duration | Output Path |
|-----------|-----------|--------------|-------------------|-------------|
| hero_lipsync (whole) | generate_media | audio_slice from continuous.mp3 | padded_len (speech + padding) | assets/media/{segment}/{beat_id}.mp4 |
| hero_lipsync (split child) | generate_media | audio_slice for child interval | child speech_len + padding | assets/media/{segment}/{child_id}.mp4 |
| broll (single) | generate_media | none (strip) | duration_target_sec | assets/media/{segment}/{beat_id}.mp4 |
| broll (slot-expanded) | generate_media | none (strip) | slot required_duration_sec | assets/media/{segment}/{beat_id}_{slot_id}.mp4 |
| local_graphic | render_graphics | none | exact beat duration | assets/overlays/{beat_id}_overlay.png |
| hero_cutaway (rerouted) | generate_media | none (strip, continuous VO) | slot duration | assets/media/{segment}/{beat_id}_{slot_id}.mp4 |

---

## Fixes Required

### Fix A: Generation must match PLAN PATHS, not glob for existing files
When determining reuse, `generate_media.py` must check if a file exists at the EXACT
`output_path` specified in the current media_plan entry — not at any legacy path derived
from the beat_id. If the plan says `B004_B004-s0.mp4` and only `B004.mp4` exists, that is
NOT a valid reuse.

### Fix B: reconcile_duration must understand split/slot expansion
`reconcile_duration.py` must resolve parent→children→slots:
- For a timing_map beat "B005" (19.367s), find ALL media_plan entries with `source_beat_id == "B005"`
- Sum their clip durations
- If sum ≥ required (within tolerance): PASS
- If looking up by beat_id alone fails, try source_beat_id before reporting deficit

### Fix C: Media plan entries must carry source_beat_id consistently
Every slot-expanded or split-child entry in media_plan.json must have `source_beat_id`
pointing back to the timing_map parent. This was added in PTC-07 but may not propagate
through all paths.

---

## Validation: This Specific Video

For `how_to_use_ai_to_better_organize_your_de_short`:

**Actually OK (clips exist, just lookup fails):**
- B005: B005a.mp4 (11.5s) + B005b.mp4 (7.8s) = 19.3s ✓ covers B005 timing (19.367s)
- B011: B011a.mp4 (13.1s) + B011b.mp4 (7.9s) = 21.0s ✓ covers B011 timing (21.027s)

**Actually MISSING (slot files never generated):**
- B004: plan expects B004_B004-s0.mp4 + s1.mp4 — neither exists
- B006: plan expects B006_B006-s0.mp4 + s1.mp4 — neither exists
- B009: plan expects B009_B009-s0.mp4 + s1.mp4 + s2.mp4 — none exist

**Why they're missing**: B004/B006/B009 are broll beats that got slot-expanded by the
compiler (PTC-07). Generation found old single clips at the original paths and "reused"
them, but never created the per-slot files. The plan's output_path field was ignored
during reuse matching.
