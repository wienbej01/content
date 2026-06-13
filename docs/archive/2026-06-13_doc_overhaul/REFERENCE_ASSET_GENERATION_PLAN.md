# Reference Asset Generation Plan

**Version:** 1.0
**Date:** 2026-06-09
**Purpose:** Plan the minimum viable reference image set before rebuilding teaser_02.

Reference images are not optional. Without them, every Higgsfield generation session invents a new James face, a new room, and a new cat. The reference library is what converts AI generation from "random output" to "consistent character."

---

## 1. Generation Order (strict — each step unlocks the next)

```
Step 1: STUDIO_LIBRARY_WIDE_001       → establishes the room; all studio images depend on it
Step 2: JAMES_FRONT_DESK_001           → establishes James; all other James angles depend on it
Step 3: STUDIO_LIBRARY_MEDIUM_DESK_001 → uses Wide + James reference; the default working angle
Step 4: JAMES_THREE_QUARTER_STUDY_001  → uses James + Medium Desk studio reference
Step 5: (Remaining studio angles)      → all use Wide + James as anchors
Step 6: (Remaining James angles)       → all use existing James references
Step 7: CAT_LIBRARY_SLEEPING_001       → first cat reference; use Cat_Background studio angle
Step 8: (Remaining cat + prop refs)    → all use established studio references
```

**Human approval required after Step 1 and Step 2.** If either the studio or James image is wrong, all subsequent generations will inherit the error. Stop and regenerate before proceeding.

---

## 2. James Reference Assets

All James images use the canonical Higgsfield prompt from `brand/BRAND_SPEC.md` §9.

| Asset ID | Path | Purpose | A-roll/B-roll | 9:16 safe | Generation prompt anchor |
|---|---|---|---|---|---|
| `JAMES_FRONT_DESK_001` | `assets/reference/james/JAMES_FRONT_DESK_001.png` | Default talking head; primary generation anchor | A-roll | ✅ | Front-facing, seated, navy sweater, study, 85mm, 16:9 |
| `JAMES_THREE_QUARTER_STUDY_001` | `assets/reference/james/JAMES_THREE_QUARTER_STUDY_001.png` | Voiceover present; slightly angled | A-roll | ✅ | 3/4 right, thoughtful, mid-thought expression |
| `JAMES_SIDE_PROFILE_001` | `assets/reference/james/JAMES_SIDE_PROFILE_001.png` | Side-profile studio shot | A-roll | Partial | Full side, looking slightly left, lamp rim-light |
| `JAMES_STANDING_LIBRARY_001` | `assets/reference/james/JAMES_STANDING_LIBRARY_001.png` | Standing at bookshelf | A-roll | ✅ | Standing, near bookshelf, 3/4 angle, upright posture |
| `JAMES_OVER_SHOULDER_WRITING_001` | `assets/reference/james/JAMES_OVER_SHOULDER_WRITING_001.png` | Writing at desk (OTS) | A-roll | ✅ | Over-shoulder, desk surface, notebook and pen visible |
| `JAMES_WALKING_CITY_001` | `assets/reference/james/JAMES_WALKING_CITY_001.png` | City exterior voiceover b-roll | B-roll | ✅ | Walking, financial district, morning light, consistent wardrobe |

**Allowed use:** Generation anchor for any scene featuring James. Pass as `--image` reference to Higgsfield Soul ID or equivalent.
**Forbidden use:** Direct publication as final video frame (these are reference images only).
**Continuity requirement:** All James generations must use at least `JAMES_FRONT_DESK_001` as the primary reference. If two James images are available, use both for stronger consistency.

---

## 3. Studio/Library Reference Assets

Generated in spatial order — `WIDE_001` must exist before any other studio angle is attempted.

| Asset ID | Path | Camera angle | 9:16 safe | Generation prompt anchor |
|---|---|---|---|---|
| `STUDIO_LIBRARY_WIDE_001` | `assets/reference/studio_library/STUDIO_LIBRARY_WIDE_001.png` | Full room establishing | Partial (James left-center) | Wide shot, dark wood desk + bookshelves, warm lamp, James seated |
| `STUDIO_LIBRARY_MEDIUM_DESK_001` | `assets/reference/studio_library/STUDIO_LIBRARY_MEDIUM_DESK_001.png` | Default talking head angle | ✅ | Medium/chest-up, James at desk, lamp from left, shelf soft-focus |
| `STUDIO_LIBRARY_CLOSEUP_001` | `assets/reference/studio_library/STUDIO_LIBRARY_CLOSEUP_001.png` | Close-up emphasis | ✅ | Shoulders-up, direct gaze or slight 3/4, deep bokeh |
| `STUDIO_LIBRARY_OVER_SHOULDER_001` | `assets/reference/studio_library/STUDIO_LIBRARY_OVER_SHOULDER_001.png` | Desk insert / working angle | ✅ | Behind-above James, looking at desk, notebook visible |
| `STUDIO_LIBRARY_SIDE_PROFILE_001` | `assets/reference/studio_library/STUDIO_LIBRARY_SIDE_PROFILE_001.png` | Thinking / transition moment | Partial | James side-profile, looking away, lamp rim-light |
| `STUDIO_LIBRARY_STANDING_BOOKSHELF_001` | `assets/reference/studio_library/STUDIO_LIBRARY_STANDING_BOOKSHELF_001.png` | Voiceover standing | ✅ | James standing near bookshelf, books soft-focus |
| `STUDIO_LIBRARY_CAT_BACKGROUND_001` | `assets/reference/studio_library/STUDIO_LIBRARY_CAT_BACKGROUND_001.png` | Standard angle with cat in background | ✅ | Medium desk shot, cat sleeping on chair in deep background |

**Continuity requirement:** All studio images must depict the same room. Generate from `STUDIO_LIBRARY_WIDE_001` first and use it as reference for all subsequent studio generations.
**QA requirement:** Compare each new angle against `STUDIO_LIBRARY_WIDE_001` to confirm spatial consistency (desk position, bookshelf location, lamp position all match).

---

## 4. Cat Reference Assets

The cat must be identical across all appearances. British Shorthair blue-grey, as defined in `BACKGROUND_CAT_BIBLE.md`.

| Asset ID | Path | Description | Notes |
|---|---|---|---|
| `CAT_LIBRARY_SLEEPING_001` | `assets/reference/cat/CAT_LIBRARY_SLEEPING_001.png` | Cat sleeping on a chair in studio background | Use `STUDIO_LIBRARY_CAT_BACKGROUND_001` as the studio reference |
| `CAT_WINDOW_001` | `assets/reference/cat/CAT_WINDOW_001.png` | Cat on windowsill, looking out | Window must match the studio window |
| `CAT_BOOKSHELF_BACKGROUND_001` | `assets/reference/cat/CAT_BOOKSHELF_BACKGROUND_001.png` | Cat settled at the base of the bookshelf | Use `STUDIO_LIBRARY_WIDE_001` as spatial reference |

**Prompt anchor (all cat images):** British Shorthair, blue-grey solid fur, compact round face, golden/copper eyes, calm/sleeping posture, deep background in a warm private study, not in foreground, not facing camera.

---

## 5. Prop Reference Assets

Props are less critical than James/studio but help keep the environment consistent.

| Asset ID | Path | Description | Priority |
|---|---|---|---|
| `PROP_NOTEBOOK_001` | `assets/reference/props/PROP_NOTEBOOK_001.png` | Dark leather notebook, unbranded, closed | When close-up of notebook is planned |
| `PROP_PEN_001` | `assets/reference/props/PROP_PEN_001.png` | Simple dark pen | When close-up of pen/writing is planned |
| `PROP_DESK_LAMP_001` | `assets/reference/props/PROP_DESK_LAMP_001.png` | Brass directional desk lamp | Useful for studio consistency reference |
| `PROP_LAPTOP_BLANK_SCREEN_001` | `assets/reference/props/PROP_LAPTOP_BLANK_SCREEN_001.png` | Laptop with blank/off screen | When laptop appears in shot |
| `PROP_BOOKS_001` | `assets/reference/props/PROP_BOOKS_001.png` | Stack or shelf of serious books | For close-up book shots |
| `PROP_COFFEE_001` | `assets/reference/props/PROP_COFFEE_001.png` | Plain ceramic mug, no brand | Occasional humanizing detail |

Props are **not required for teaser_02 generation.** Generate on demand when a scene specifically features a close-up of that prop.

---

## 6. How Assets Are Named and Stored

- **File format:** PNG, 1920×1080 (or the highest resolution Higgsfield outputs for static images)
- **Naming:** `{SUBJECT}_{CONTEXT}_{VARIANT}_{INDEX}.png` — uppercase, underscores, as defined in `REFERENCE_ASSET_MANIFEST.md`
- **Storage:** in `assets/reference/{james|studio_library|cat|wardrobe|color_palette|props}/`
- **Existing seeds:** `brand/James_harrington_{front,3_4,side,vertical}.png` — available as provisional seeds but should be reviewed against the canonical spec before use in production (status: `seed_needs_review` in the manifest)

---

## 7. How Assets Are Referenced by Pipeline Tools

- **Storyboard beats:** reference assets by ID string in the `reference_assets[]` field
- **Media prompt plan:** the prompt compiler reads `reference_assets[]` from beats and maps IDs to file paths via `REFERENCE_ASSET_MANIFEST.md`
- **Higgsfield call:** `generate_media.py` passes the resolved file path as `--image` to the CLI
- **QA:** after generation, `qa_media.py` compares the output against the reference image's expected characteristics (manual for now; vision QA deferred to M9.2)

---

## 8. Use of Existing Real Reference Photos

If the operator has real photographs of a person/setting that match the character spec, those should be used instead of AI-generated references. Real photos produce stronger and more consistent Higgsfield output than AI-generated references.

- If a real reference photograph exists → place it directly at the correct asset path with `seed_real_photo` status in the manifest
- If no real photo exists → generate a static image using Higgsfield image generation (nano_banana or equivalent image model)
- Never mix real and AI-generated references for the same character within one generation session

---

## 9. Minimum Viable Set for Teaser-02 Generation

To unblock full teaser generation, only these are strictly required:

1. `STUDIO_LIBRARY_WIDE_001` — generate first
2. `STUDIO_LIBRARY_MEDIUM_DESK_001` — the default A-roll angle
3. `JAMES_FRONT_DESK_001` — the primary James anchor
4. `JAMES_THREE_QUARTER_STUDY_001` — the voiceover variant

Everything else can be generated on demand as specific shots require them.
