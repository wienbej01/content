# TKT-001 — Reference-Frame Baseline + Storyboard Validator Gaps

**Ticket:** TKT-001
**Date:** 2026-07-07
**Inspector:** engineer (WCR-2026-07)
**Scope:** Read-only inspection of `configs/james/model_routing.yaml`, `scripts/review_storyboard.py`, `scripts/storyboard_projection.py`, `docs/channel_universe/constraints.json`.

---

## 1. Reference-Frame Sets (configs/james/model_routing.yaml)

### 1.1 Active set

| Field | Value |
|-------|-------|
| `active_set` | `navy_sweater_library` |
| Total sets defined | 2 |

### 1.2 Full set inventory

#### Set: `dark_jacket_library`

| Attribute | Value |
|-----------|-------|
| wardrobe | "navy blazer over white open-collar shirt" |
| setting | "home library, anglepoise lamp, bookshelves, framed print" |
| frame count | 4 |

| Angle | Path |
|-------|------|
| `front` | `assets/reference/james/canonical/JAMES_MEDIUM_FRONT_DARK_JACKET_002.png` |
| `medium_wide` | `assets/reference/james/canonical/JAMES_MEDIUM_WIDE_DARK_JACKET_002.png` |
| `three_quarter` | `assets/reference/james/canonical/JAMES_THREE_QUARTER_DARK_JACKET_SPEAKING_002.png` |
| `side_profile` | `assets/reference/james/canonical/JAMES_SIDE_PROFILE_DARK_JACKET_SPEAKING_002.png` |

#### Set: `navy_sweater_library` (active)

| Attribute | Value |
|-----------|-------|
| wardrobe | "navy fine-knit sweater over white/pale-blue open-collar Oxford shirt" |
| setting | "home library, brass anglepoise lamp at left, white bookshelves, framed print, soft window light" |
| frame count | 4 |

| Angle | Path |
|-------|------|
| `front` | `assets/reference/james/canonical/JAMES_MEDIUM_FRONT_NAVY_SWEATER_002.png` |
| `front_speaking` | `assets/reference/james/canonical/JAMES_MEDIUM_FRONT_NAVY_SWEATER_SPEAKING_002.png` |
| `three_quarter` | `assets/reference/james/canonical/JAMES_THREE_QUARTER_NAVY_SWEATER_002.png` |
| `side_profile` | `assets/reference/james/canonical/JAMES_SIDE_PROFILE_NAVY_SWEATER_002.png` |

### 1.3 Summary statistics

| Metric | Value |
|--------|-------|
| Total distinct sets | 2 |
| Total distinct angles across sets | 6 (front, front_speaking, medium_wide, three_quarter, side_profile) |
| Total frame PNGs | 8 |
| Distinct wardrobes | 2 (blazer, sweater) |
| Distinct settings | 1 (home library — both sets share the same room) |
| Angles in active set | 4 |

### 1.4 Continuity rule

`model_routing.yaml:19`:
> "CONTINUITY RULE: all frames used within ONE episode must share wardrobe + setting (James cannot change clothes between cuts)."

This is a documented constraint, not yet a programmatic validator rule. The compiler enforces it indirectly by only using `active_set`.

---

## 2. Compiler Frame Assignment (scripts/produce_db.py)

### 2.1 Relevant code paths

| File | Line(s) | Function | Role |
|------|---------|----------|------|
| `scripts/produce_db.py` | 1271-1280 | `assign_lipsync_references` | Reads `active_set` from `lipsync_references`, rotates frames |
| `scripts/compile_media_prompts.py` | 699-731 | `assign_lipsync_references` | Assigns frames to hero beats in media plan |
| `scripts/compile_media_prompts.py` | 914-931 | compile path | Validates frame availability, warns on wardrobe drift |

### 2.2 Current rotation logic

The compiler rotates hero_lipsync beats across the `active_set` frames using round-robin, with no two consecutive hero beats reusing the same frame. This is a **within-set** rotation — all beats in an episode draw from the same 4 frames.

### 2.3 Gap: no chapter-based set selection

There is no code path that selects a different `set` per act. The `active_set` is fixed per production. The `visual_chapters` config proposed in TKT-201 does not yet exist.

---

## 3. Storyboard Validator Gaps (scripts/review_storyboard.py)

### 3.1 Existing validator functions

| Function | Line | What it checks | Frame-variety relevance |
|----------|------|----------------|------------------------|
| `_bands_check` | 88-145 | Shot-mix percentages, max hero block, distinct visual setups | Counts `distinct_visual_setups` but does not track which setups or frames |
| `_anti_patterns` | 147-195 | Invalid shot types, banned models, front-facing closeups, empty briefs, readable text, generic narrative_function | No frame-identity or frame-gap check |
| `_trigger_coverage` | 198-210 | Named studies/dates anchored by archival beats, numbered principles by title cards | No frame check |
| `_coverage_min` | 214-224 | Archival/graphic beats present, Act-5 master graphic | No frame check |
| `_max_hero_chain` | 55-85 | Continuous hero chain duration (≤15s, ≤25s Act-6 exception) | Duration only, not frame identity |
| `review` | 227-257 | Top-level orchestrator | No frame-variety check |

### 3.2 Specific gaps for TKT-202 (frame-gap + fatigue)

1. **No frame-gap constraint.** The validator does not track which reference frame is assigned to each hero beat, and cannot enforce a minimum gap between same-frame appearances.

2. **No visual-fatigue score.** The validator does not compute a concentration metric for same-angle or same-wardrobe blocks.

3. **`distinct_visual_setups` is a count, not a tracker.** The validator checks `distinct_visual_setups >= 12` but this field is computed upstream (in the storyboard router/compiler), not from frame identity. It counts "setups" as distinct `shot_type + camera + setting` tuples, not reference-frame identity.

4. **No per-beat frame metadata on the storyboard.** The `beats[]` entries in `storyboard.json` do not carry a `canonical_ref_frame` or `reference_frame_id` field. The frame assignment happens later in the compiler (`compile_media_prompts.py`), not in the storyboard itself.

### 3.3 Where frame-gap logic must go

The frame-gap check belongs in `_anti_patterns` (per-beat iteration) or a new `_frame_variety_check` function called from `review`. It requires:
- The storyboard beats to carry a `reference_frame_id` (or similar) field.
- A config constant `MIN_HERO_FRAME_GAP` (default 3).
- A sliding window over hero beats tracking last-seen beat index per frame.

### 3.4 Where visual-fatigue logic must go

The fatigue score belongs in `_bands_check` (aggregate metrics) or a new `_visual_fatigue_check`. It requires:
- Per-beat frame identity.
- A config constant `MAX_VISUAL_FATIGUE_SCORE` (default 0.75).
- A documented formula with weights.

---

## 4. Canonical Shot Schema (storyboard_projection.py)

### 4.1 `visual_chapter` field

The canonical shot schema in `storyboard_projection.py` does **not** carry a `visual_chapter` field. The projection maps `visual_role` → `shot_type` and carries `_SHOT_CARRY_FIELDS` (segment_id, must_show, must_avoid, claim_refs, qa_requirements, planned_duration_sec, etc.) but no chapter reference.

### 4.2 `canonical_shot_id` field

The projection does emit `canonical_shot_id` on each legacy beat (lines 380, 425). This is the lineage key back to the canonical shot.

### 4.3 Gap: `visual_chapter` must be added

To support TKT-201's chapter-based set selection, the canonical shot schema needs a `visual_chapter` field (values 1-6, mapping to acts). The projection must carry it through to the legacy beat so the compiler and validator can reference it.

---

## 5. Constraints Reference (docs/channel_universe/constraints.json)

### 5.1 Existing visual constraints

The `constraints.json` defines:
- `allowed_palette` / `forbidden_palette`
- `allowed_lighting` / `forbidden_lighting`
- `allowed_camera_movements` / `forbidden_camera_movements`
- `approved_studio_angles` (7 named angles)
- `allowed_scene_types` / `scene_type_notes`
- `forbidden_visual_patterns` (17 patterns)

### 5.2 Gap: no `visual_chapter` or frame-variety constraint

There is no `visual_chapter`, `min_frame_gap`, or `max_visual_fatigue_score` key in `constraints.json`. These must be added (either here or in `model_routing.yaml`).

---

## 6. Findings Summary

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| F-1 | Only one `active_set` is used per production; no chapter-based set selection exists | `model_routing.yaml:25`, `produce_db.py:1271-1280` | James cannot visually evolve across acts |
| F-2 | `visual_chapters` config section does not exist | `model_routing.yaml` | TKT-201 must add it |
| F-3 | Storyboard validator has no frame-gap constraint | `review_storyboard.py:88-145, 147-195` | TKT-202 must add it |
| F-4 | Storyboard validator has no visual-fatigue score | `review_storyboard.py:88-145` | TKT-202 must add it |
| F-5 | Storyboard beats do not carry `reference_frame_id` or `visual_chapter` | `storyboard_projection.py` (beat schema) | TKT-201/TKT-202 must add field propagation |
| F-6 | `constraints.json` has no `visual_chapter` or frame-variety keys | `docs/channel_universe/constraints.json` | TKT-201/TKT-202 must add them |
| F-7 | Both reference sets share the same physical setting (home library) | `model_routing.yaml:29,37` | Visual evolution is limited to wardrobe + angle, not environment |
| F-8 | `distinct_visual_setups` counts setups but does not track frame identity | `review_storyboard.py:142-144` | Cannot distinguish "same angle, different time" from "different angle" |

---

## 7. Recommendations for Downstream Tickets

### TKT-201 (Multi-reference-set config + compiler mapping)

1. Add `visual_chapters` section to `model_routing.yaml` mapping acts 1-6 to sets + allowed_angles.
2. Add `VISUAL_VARIATION_MODE = flat|chapter` flag to `smoke_config.py`.
3. In `produce_db.py` compile path: derive chapter from `act_for(beat)` and assign `canonical_ref_frame` from matching set.
4. Add `visual_chapter` to `_SHOT_CARRY_FIELDS` in `storyboard_projection.py`.
5. Add `reference_frame_id` field to the legacy beat schema.

### TKT-202 (Validator frame-gap + fatigue)

1. Add `_frame_variety_check(beats, blocking, warnings)` function in `review_storyboard.py`.
2. Add `MIN_HERO_FRAME_GAP` and `MAX_VISUAL_FATIGUE_SCORE` to `configs/james/model_routing.yaml → visual_variation`.
3. Call `_frame_variety_check` from `review()`.
4. Report `frame_gap_violation` and `visual_fatigue_violation` as named blocking conditions.

---

## 8. Baseline Verification

| Check | Result |
|-------|--------|
| `YT_TEST_MODE=1 python3 -m pytest tests/ -q` | 2,863 tests collected (floor holds) |
| `configs/james/model_routing.yaml` parsed | 2 sets, 8 frames, 1 active |
| `review_storyboard.py` functions inventoried | 6 validator functions, none check frame identity |
| `storyboard_projection.py` fields inventoried | `canonical_shot_id` present, `visual_chapter` absent |
| `constraints.json` keys inventoried | No `visual_chapter` or frame-variety keys |

---

*End of TKT-001 evidence record.*
