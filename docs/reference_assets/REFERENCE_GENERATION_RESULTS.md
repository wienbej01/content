# Reference Generation Results

**Date:** 2026-06-09
**Status:** Generated — awaiting visual review/approval

---

## Credits Spent

| Model | Rate | Images | Estimated cost |
|---|---|---|---|
| `text2image_soul_v2` | 0.12 credits | 21 (10 James + 8 studio with James + 3 studio OTS) | ~2.5 credits |
| `flux_2` | 1 credit | 5 (studio environment-only + 3 cat) | ~5 credits |
| **Total** | | **25 images** | **~7.5 credits** |

Account had 392 credits before this sprint. Estimated remaining: ~384.

---

## Generation Results

| Asset ID | Output path | Model | Status | Notes |
|---|---|---|---|---|
| JAMES_FRONT_DESK_001 | assets/reference/james/JAMES_FRONT_DESK_001.png | text2image_soul_v2 | generated | 5033KB |
| JAMES_THREE_QUARTER_STUDY_001 | assets/reference/james/JAMES_THREE_QUARTER_STUDY_001.png | text2image_soul_v2 | generated | 4817KB |
| JAMES_SIDE_PROFILE_001 | assets/reference/james/JAMES_SIDE_PROFILE_001.png | text2image_soul_v2 | generated | 5739KB |
| JAMES_VERTICAL_CLOSEUP_001 | assets/reference/james/JAMES_VERTICAL_CLOSEUP_001.png | text2image_soul_v2 | generated | 4757KB |
| JAMES_STANDING_LIBRARY_001 | assets/reference/james/JAMES_STANDING_LIBRARY_001.png | text2image_soul_v2 | generated | 4593KB |
| JAMES_OVER_SHOULDER_WRITING_001 | assets/reference/james/JAMES_OVER_SHOULDER_WRITING_001.png | text2image_soul_v2 | generated | 5086KB |
| JAMES_DESK_THINKING_001 | assets/reference/james/JAMES_DESK_THINKING_001.png | text2image_soul_v2 | generated | 4713KB |
| JAMES_WALKING_HOME_LIBRARY_001 | assets/reference/james/JAMES_WALKING_HOME_LIBRARY_001.png | text2image_soul_v2 | generated | 4860KB |
| JAMES_CASUAL_HOME_OFFICE_001 | assets/reference/james/JAMES_CASUAL_HOME_OFFICE_001.png | text2image_soul_v2 | generated | 4533KB |
| JAMES_FORMAL_DARK_JACKET_001 | assets/reference/james/JAMES_FORMAL_DARK_JACKET_001.png | text2image_soul_v2 | generated | 5106KB |
| STUDIO_LIBRARY_WIDE_001 | assets/reference/studio_library/STUDIO_LIBRARY_WIDE_001.png | flux_2 | generated | 1877KB |
| STUDIO_LIBRARY_MEDIUM_DESK_001 | assets/reference/studio_library/STUDIO_LIBRARY_MEDIUM_DESK_001.png | text2image_soul_v2 | generated | 5131KB |
| STUDIO_LIBRARY_CLOSEUP_DESK_001 | assets/reference/studio_library/STUDIO_LIBRARY_CLOSEUP_DESK_001.png | flux_2 | generated | 1575KB |
| STUDIO_LIBRARY_OVER_SHOULDER_001 | assets/reference/studio_library/STUDIO_LIBRARY_OVER_SHOULDER_001.png | text2image_soul_v2 | generated | 5032KB |
| STUDIO_LIBRARY_SIDE_PROFILE_001 | assets/reference/studio_library/STUDIO_LIBRARY_SIDE_PROFILE_001.png | text2image_soul_v2 | generated | 5197KB |
| STUDIO_LIBRARY_STANDING_BOOKSHELF_001 | assets/reference/studio_library/STUDIO_LIBRARY_STANDING_BOOKSHELF_001.png | text2image_soul_v2 | generated | 4272KB |
| STUDIO_LIBRARY_WINDOW_LIGHT_001 | assets/reference/studio_library/STUDIO_LIBRARY_WINDOW_LIGHT_001.png | flux_2 | generated | 2314KB |
| STUDIO_LIBRARY_NIGHT_LAMP_001 | assets/reference/studio_library/STUDIO_LIBRARY_NIGHT_LAMP_001.png | flux_2 | generated | 1463KB |
| STUDIO_LIBRARY_CAT_BACKGROUND_001 | assets/reference/studio_library/STUDIO_LIBRARY_CAT_BACKGROUND_001.png | text2image_soul_v2 | generated | 4473KB |
| STUDIO_LIBRARY_EMPTY_ROOM_001 | assets/reference/studio_library/STUDIO_LIBRARY_EMPTY_ROOM_001.png | flux_2 | generated | 2246KB |
| STUDIO_LIBRARY_READING_CHAIR_001 | assets/reference/studio_library/STUDIO_LIBRARY_READING_CHAIR_001.png | flux_2 | generated | 1642KB |
| STUDIO_LIBRARY_BOOKSHELF_DETAIL_001 | assets/reference/studio_library/STUDIO_LIBRARY_BOOKSHELF_DETAIL_001.png | flux_2 | generated | 2002KB |
| CAT_LIBRARY_SLEEPING_001 | assets/reference/cat/CAT_LIBRARY_SLEEPING_001.png | flux_2 | generated | 2070KB |
| CAT_WINDOW_001 | assets/reference/cat/CAT_WINDOW_001.png | flux_2 | generated | 2330KB |
| CAT_BOOKSHELF_BACKGROUND_001 | assets/reference/cat/CAT_BOOKSHELF_BACKGROUND_001.png | flux_2 | generated | 2082KB |

---

## Visual Approval Status

**5 key images sent to Telegram for immediate review:**
1. JAMES_FRONT_DESK_001 — PRIMARY anchor
2. STUDIO_LIBRARY_WIDE_001 — MASTER ROOM (review first)
3. STUDIO_LIBRARY_MEDIUM_DESK_001 — Default A-roll angle
4. JAMES_FORMAL_DARK_JACKET_001 — Wardrobe variation
5. CAT_LIBRARY_SLEEPING_001 — Cat reference

**All 25 images: status = `generated` (pending approval)**

Review using `REFERENCE_ASSET_QA_CHECKLIST.md`. Approve each with score ≥4.0. Promote to `approved` in manifest after review.

---

## Next Actions

1. **Human visual review** — approve or reject each image
2. **If STUDIO_LIBRARY_WIDE_001 is rejected** — regenerate before approving any other studio angles
3. **If James identity is inconsistent** — regenerate affected images with stronger reference seeding
4. **Promote approved images** — update manifest status, set canonical_priority
5. **After Batch 1 approved** — run one-scene generation test (see `TEASER_02_REBUILD_READINESS_REPORT.md`)
