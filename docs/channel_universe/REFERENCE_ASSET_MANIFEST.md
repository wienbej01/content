# Reference Asset Manifest

**Version:** 1.1 (updated with status tracking)
**Date:** 2026-06-09
**See also:** `docs/reference_assets/REFERENCE_ASSET_INVENTORY.md`, `JAMES_CONTINUITY_STRATEGY.md`, `REFERENCE_ASSET_QA_CHECKLIST.md`

---

## Minimum Viable Asset Set (required before teaser_02 generation)

| Asset ID | Expected path | Source type | Status | Purpose | Required for | Center-safe 9:16 | Canonical priority | QA score | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `JAMES_FRONT_DESK_001` | `assets/reference/james/JAMES_FRONT_DESK_001.png` | `existing_repo` | `found` | Primary James anchor for all A-roll | A-roll lipsync, talking head | ✅ | primary | TBD | Source: `brand/James_harrington_front.png` (405×398px) — usable but low-res |
| `JAMES_THREE_QUARTER_STUDY_001` | `assets/reference/james/JAMES_THREE_QUARTER_STUDY_001.png` | `existing_repo` | `found` | 3/4 James angle; voiceover and thinking shots | A-roll voiceover, transitions | ✅ | primary | TBD | Source: `brand/James_harrington_3_4.png` (408×398px) |
| `JAMES_SIDE_PROFILE_001` | `assets/reference/james/JAMES_SIDE_PROFILE_001.png` | `existing_repo` | `found` | Side profile for thinking/transition beats | B-roll with James present | Partial | secondary | TBD | Source: `brand/James_harrington_side.png` (388×552px) |
| `JAMES_STANDING_LIBRARY_001` | `assets/reference/james/JAMES_STANDING_LIBRARY_001.png` | `missing` | `missing` | James standing at bookshelf | A-roll voiceover standing | ✅ | secondary | — | Generate in Batch 2 |
| `STUDIO_LIBRARY_WIDE_001` | `assets/reference/studio_library/STUDIO_LIBRARY_WIDE_001.png` | `missing` | `missing` | Room establishing shot; spatial anchor for all other studio angles | All studio shots | Partial | primary | — | **Generate FIRST — all studio images depend on this** |
| `STUDIO_LIBRARY_MEDIUM_DESK_001` | `assets/reference/studio_library/STUDIO_LIBRARY_MEDIUM_DESK_001.png` | `missing` | `missing` | Default talking-head / A-roll angle | Default A-roll, talking head | ✅ | primary | — | Generate in Batch 1 (after Wide_001) |
| `STUDIO_LIBRARY_OVER_SHOULDER_001` | `assets/reference/studio_library/STUDIO_LIBRARY_OVER_SHOULDER_001.png` | `missing` | `missing` | OTS desk insert; James working | B-roll inserts, voiceover | ✅ | secondary | — | Generate in Batch 2 |
| `STUDIO_LIBRARY_STANDING_BOOKSHELF_001` | `assets/reference/studio_library/STUDIO_LIBRARY_STANDING_BOOKSHELF_001.png` | `missing` | `missing` | James at bookshelf angle | Voiceover standing | ✅ | secondary | — | Generate in Batch 2 |
| `STUDIO_LIBRARY_CAT_BACKGROUND_001` | `assets/reference/studio_library/STUDIO_LIBRARY_CAT_BACKGROUND_001.png` | `missing` | `missing` | Medium shot with cat in deep background | Episodes featuring cat | ✅ | fallback | — | Generate in Batch 3; optional |
| `CAT_LIBRARY_SLEEPING_001` | `assets/reference/cat/CAT_LIBRARY_SLEEPING_001.png` | `missing` | `missing` | Cat sleeping on studio chair background | Any cat background beat | N/A (cat is background) | secondary | — | Generate in Batch 3 |

---

## Additional Existing Assets

| Asset ID | Expected path | Source type | Status | Notes |
|---|---|---|---|---|
| `JAMES_VERTICAL_CLOSEUP_001` | `assets/reference/james/JAMES_VERTICAL_CLOSEUP_001.png` | `existing_repo` | `found` | Source: `brand/James_harrington_vertical.png` (317×552px); 9:16 compositions |
| `JAMES_MODEL_SHEET_001` | `assets/reference/james/JAMES_MODEL_SHEET_001.png` | `existing_repo` | `found` | Source: `brand/be54ce9d-00f5-445c-b70b-7d9dd2ab7d71.png` (896×1200px RGBA); character composite; archive only |

---

## Status Legend

| Status | Meaning |
|---|---|
| `missing` | File does not exist; needs to be generated |
| `found` | File found in repo; not yet formally approved |
| `generated` | Generated in a new session; awaiting review |
| `approved` | Human-reviewed; score ≥ 4.0; canonical |
| `secondary_reference` | Human-reviewed; score 3.0–3.9; supplementary use only |
| `rejected` | Failed QA; do not use; regenerate |

---

## Source Type Legend

| Source type | Meaning |
|---|---|
| `existing_repo` | Found in the repo (brand/, Videos/Input_image/, etc.) |
| `generated_new` | Generated in this project specifically for the reference library |
| `missing` | No file found anywhere in the repo |

---

## Canonical Priority Legend

| Priority | Meaning |
|---|---|
| `primary` | Must be used as reference input for every related generation session |
| `secondary` | Recommended but not mandatory reference input |
| `fallback` | Optional; use when primary/secondary reference is absent |

---

## Usage Rules

1. Every Higgsfield session featuring James must use at least one `primary` James reference as Soul ID input.
2. Every Higgsfield session featuring the studio must use `STUDIO_LIBRARY_WIDE_001` as room reference once approved.
3. Asset IDs are referenced in storyboard beat `reference_assets[]` arrays and in `media_prompt_plan.json` entries.
4. Only `approved` or `secondary_reference` assets may be used in production generation.
5. `found` assets (from existing repo) may be used in development/test; they should be formally reviewed before production use.
6. Existing `brand/James_harrington_*.png` files are usable as-is for Higgsfield Soul ID seeding while formal approval is pending.

---

## Folder Structure

```
assets/reference/
├── james/                    (6 planned, 0 in folder — sources in brand/)
├── studio_library/           (7 planned, 0 in folder)
├── cat/                      (2+ planned, 0 in folder)
├── wardrobe/                 (2 planned, 0 in folder)
├── color_palette/            (1 planned, 0 in folder)
└── props/                    (6 planned, 0 in folder — generate on demand)
```

**Note:** Source files for existing James assets are in `brand/` and `Videos/Input_image/`. They are NOT yet copied to `assets/reference/james/`. Copy them when status is promoted to `approved`:
```bash
cp brand/James_harrington_front.png assets/reference/james/JAMES_FRONT_DESK_001.png
cp brand/James_harrington_3_4.png assets/reference/james/JAMES_THREE_QUARTER_STUDY_001.png
cp brand/James_harrington_side.png assets/reference/james/JAMES_SIDE_PROFILE_001.png
cp brand/James_harrington_vertical.png assets/reference/james/JAMES_VERTICAL_CLOSEUP_001.png
```
