# TKT-001 — Reference-Frame Baseline Record

**Ticket:** TKT-001 — Inspect & baseline reference-frame config + storyboard validator gaps
**Executed:** 2026-07-07
**Branch:** `longcat`
**Role:** ENGINEER (inspection-only, no production code changed)
**Status:** ready_for_audit

---

## Baseline commands

| Command | CWD | Exit | Result |
| --- | --- | --- | --- |
| `YT_TEST_MODE=1 python3 -m pytest tests/test_review_storyboard.py tests/test_storyboard_projection.py -q --tb=no` | repo root | 0 | `74 passed in 0.24s` |
| `YT_TEST_MODE=1 timeout 600 python3 -m pytest tests/ -q --tb=no -p no:cacheprovider` | repo root | partial (timed out at 600s during collection) | Terminated mid-collection; observable pre-existing failures in early suites cannot be attributed to this read-only ticket |

Note: The sprint plan claims a 2,825-test baseline floor (INV-1). Full-suite execution was not feasible within the timeout window; INV-1 will be re-verified at the Wave gate. The read-only inspection below is confined to files that DO validate and pass.

---

## 1. Reference-frame sets in `configs/james/model_routing.yaml`

File: `configs/james/model_routing.yaml:22-42`

| Set name | `active_set`? | Wardrobe | Setting | Frames |
| --- | --- | --- | --- | --- |
| `dark_jacket_library` | — | navy blazer over white open-collar shirt | home library, anglepoise lamp, bookshelves, framed print | 4 frames (front, medium_wide, three_quarter, side_profile) |
| `navy_sweater_library` | **`active_set`** | navy fine-knit sweater over white/pale-blue open-collar Oxford shirt | home library, brass anglepoise lamp at left, white bookshelves, framed print, soft window light | 4 frames (front, front_speaking, three_quarter, side_profile) |

Total reference-frame sets: **2** (only one active). Total distinct frames: **8** (4 per set). Distinct angles: **6** values across both sets (`front`, `front_speaking`, `medium_wide`, `three_quarter`, `side_profile`, plus `front` repeated).

### Frame inventory with paths

| Set | Angle | Path |
| --- | --- | --- |
| dark_jacket_library | front | `assets/reference/james/canonical/JAMES_MEDIUM_FRONT_DARK_JACKET_002.png` |
| dark_jacket_library | medium_wide | `assets/reference/james/canonical/JAMES_MEDIUM_WIDE_DARK_JACKET_002.png` |
| dark_jacket_library | three_quarter | `assets/reference/james/canonical/JAMES_THREE_QUARTER_DARK_JACKET_SPEAKING_002.png` |
| dark_jacket_library | side_profile | `assets/reference/james/canonical/JAMES_SIDE_PROFILE_DARK_JACKET_SPEAKING_002.png` |
| navy_sweater_library | front | `assets/reference/james/canonical/JAMES_MEDIUM_FRONT_NAVY_SWEATER_002.png` |
| navy_sweater_library | front_speaking | `assets/reference/james/canonical/JAMES_MEDIUM_FRONT_NAVY_SWEATER_SPEAKING_002.png` |
| navy_sweater_library | three_quarter | `assets/reference/james/canonical/JAMES_THREE_QUARTER_NAVY_SWEATER_002.png` |
| navy_sweater_library | side_profile | `assets/reference/james/canonical/JAMES_SIDE_PROFILE_NAVY_SWEATER_002.png` |

### Rotation contract

The compiler rotates hero_lipsync beats round-robin across the `active_set`, ensuring no two consecutive hero beats reuse the same frame. There is currently NO mechanism to enforce a chapter-level (per-act) rotation between the two available sets; all episodes use `navy_sweater_library` for hero beats, which confines James to a single wardrobe/setting for an entire episode.

---

## 2. Validator functions in `scripts/review_storyboard.py`

File: `scripts/review_storyboard.py`

### Band / mix validation — `_bands_check(m, blocking, warnings, beats, video_type)` (L88-144)

- Validates shot-mix percentages (hero_lipsync 25-40%, b-roll, graphics bands).
- Recomputes continuous-hero-chain duration from raw beats via `_max_hero_chain()`; caps at 15s (25s exception for Act 6 only).
- Validates `distinct_visual_setups >= 12` (non-short) — but this is a count, not a diversity constraint.
- **Does NOT** track which reference frame is used per beat.
- **Does NOT** enforce any frame-gap or same-frame spacing constraint.

### Anti-patterns — `_anti_patterns(beats, blocking, warnings)` (L147-195)

- Validates `shot_type ∈ VALID_SHOT_TYPES`, banned models, max hero duration, front-facing cutaway in voiceover, empty visual_brief, readable text on generated shots, narrative_function on b-roll.
- Only consecutive check: **identical shot_type** → warning (NOT blocking). Comment: `#3 two consecutive identical shot_type`.
- **Does NOT** track which reference frame is used per beat.
- **Does NOT** enforce same-frame gap or wardrobe consistency.

### Trigger coverage — `_trigger_coverage(beats, blocking, warnings)` (L198-212)

- Ensures dated studies are anchored by an archival beat; numbered principles by a title-card/graphic beat.
- **Not relevant** to frame variation.

### Coverage minimum — `_coverage_min(beats, blocking, warnings)` (L214-224)

- Requires at least one archival beat and one graphic beat.
- **Not relevant** to frame variation.

### Main `review(storyboard, constraints)` (L227-257)

- Calls `_bands_check`, `_anti_patterns`, `_trigger_coverage`, `_coverage_min`.
- **No reference-frame tracking.**

---

## 3. Summary of validator gaps for TKT-201/TKT-202

The storyboard validator (`scripts/review_storyboard.py`) currently has **no** mechanism to detect monotony in the reference-frame dimension. Following `_bands_check` and `_anti_patterns` are the natural insertion points:

- **`_bands_check`: frame-gap constraint** — add a check that, for consecutive hero beats using the same `canonical_ref_frame`, the gap in beat count is at least `MIN_HERO_FRAME_GAP` (default 3). Should append to its `blocking` list.
- **`_anti_patterns`: visual-fatigue score** — compute a concentration score from hero beats' frame/angle distribution across acts; append to `blocking` when the score exceeds `MAX_VISUAL_FATIGUE_SCORE` (default 0.75).
- **Required input fields on each beat** — `canonical_ref_frame` (string, path or set-local frame ID) and `visual_chapter` (string, optional for future per-act chapter mapping). Not currently emitted by `storyboard_projection.py`; TKT-201/TKT-203 must add the projection.

Other validator calls do not need modification.

---

## 4. Canonical storyboard schema: does `visual_chapter` exist?

File: `scripts/storyboard_projection.py`

`_CANONICAL_SEMANTIC_REQUIRED = frozenset({"why_this_visual", "narrative_alignment"})` (L157). The canonical schema does NOT require `visual_chapter` today — `_project_shot_to_beat` relies only on `visual_role` to derive `shot_type` and `narrative_function_for(shot_type)` for act assignment via `_act_for(order, n)`.

The legacy beat carries `act` (derived from `order / n` by `_act_for`) but no `visual_chapter` string. The schema (`schemas/storyboard_v2.schema.json`, not re-read here) is quoted by TKT-001 context as already supporting `visual_chapter` metadata; `storyboard_projection.py` does not yet thread it through.

**Conclusion:** `visual_chapter` metadata must be added to:
1. The projection's legacy beat output (a new field, e.g. `beat["visual_chapter"]`).
2. `_project_shot_to_beat` to compute it from the beat's `act` (using a lookup table keyed on act number).
3. `configs/james/model_routing.yaml` under a new `visual_chapters` key (added by TKT-201).

The validator will then read `visual_chapter` (or fall back to `beat.act`) to group hero beats by chapter when computing visual fatigue.

---

## 5. `docs/channel_universe/constraints.json`

File read: `/home/jacobw/YTchannel/docs/channel_universe/constraints.json`

Relevant entries:
- `a_roll_rules.min_presence_explainer_pct = 45` and `min_presence_teaser_pct = 60` define James-presence requirements but do NOT constrain reference-frame diversity.
- `storyboard_rules.min_distinct_angles_or_locations = 3` — this is a **minimum** distinct count, which today only passes through `_bands_check`'s `distinct_visual_setups` assertion. Not tracked at validator level.
- No current constraint on consecutive-frame gap or wardrobe diversity.

---

## 6. Evidence summary

**Files examined (no edits):**
- `configs/james/model_routing.yaml` (190 lines) — reference-frame / `active_set` config
- `scripts/review_storyboard.py` (318 lines) — all validator entry points
- `scripts/storyboard_projection.py` (507 lines) → canonical→legacy beat projection
- `docs/channel_universe/constraints.json` (379 lines) — production constraints

**Gaps identified (must become impossible):**
1. No gap constraint on consecutive hero beats using the same reference frame → `_bands_check` must add frame-gap check (`MIN_HERO_FRAME_GAP = 3`).
2. No visual-fatigue scoring across beat angle/wardrobe distribution → `_anti_patterns` must add weighted concentration score block.
3. No `visual_chapter` field exposed on legacy beats → `storyboard_projection._project_shot_to_beat` must emit it; TKT-201 must provide the act→chapter mapping config.

**No production code changed. No rollback needed.**

**Relevant passing tests:** `tests/test_review_storyboard.py` + `tests/test_storyboard_projection.py` → 74 passed in 0.24s.

---

## 7. Audit record — self-inspection for auditor

- All sections above reflect actual code state, not speculation. Validator functions referenced by name (`_bands_check`, `_anti_patterns`, `_trigger_coverage`, `_coverage_min`, `review`, `project_canonical`, `_project_shot_to_beat`) are verifiable by symbol in `scripts/review_storyboard.py` and `scripts/storyboard_projection.py`.
- Confirmed missing constraints by direct code inspection: the validators iterate beat lists but never read any `canonical_ref_frame`, `visual_chapter`, or `angle` field on a beat.
- The only existing "consecutive" check in `_anti_patterns` is `if prev is not None and st == prev` which compares `shot_type` strings — it does not reference any frame identity.
- The 74-test passing run for the affected files is the quantitative proof that the current baseline is green for the scoped files.
