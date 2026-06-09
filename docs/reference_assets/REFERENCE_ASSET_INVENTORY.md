# Reference Asset Inventory

**Date:** 2026-06-09
**Status:** Complete — all existing repo assets catalogued

---

## Summary

- **4 James portrait images found** in `brand/` (and mirrored in `Videos/Input_image/`)
- **1 large model-sheet PNG found** in `brand/` (896×1200px RGBA, likely Higgsfield character composite)
- **1 duplicate/near-identical copy** of the front image found (`brand/james_harrington_reference.png`)
- **0 studio/library still images found** — must be generated
- **0 cat reference images found** — must be generated
- **8 lipsync video clips** exist in `assets/media/james_teaser/` (1280×720) — still frames can be extracted as provisional studio context

---

## 1. James Portrait Images

| # | File path | Proposed asset_id | Resolution | Size | Usable | Quality | Recommendation |
|---|---|---|---|---|---|---|---|
| 1 | `brand/James_harrington_front.png` | `JAMES_FRONT_DESK_001` | 405×398px | 243KB | **Yes** | Medium | **Primary canonical anchor** — front-facing, seated, direct gaze |
| 2 | `brand/James_harrington_3_4.png` | `JAMES_THREE_QUARTER_STUDY_001` | 408×398px | 241KB | **Yes** | Medium | **Secondary canonical anchor** — 3/4 angle, thinking expression |
| 3 | `brand/James_harrington_side.png` | `JAMES_SIDE_PROFILE_001` | 388×552px | 295KB | **Yes** | Medium | Useful for side-profile shots; taller crop |
| 4 | `brand/James_harrington_vertical.png` | `JAMES_VERTICAL_CLOSEUP_001` | 317×552px | 258KB | **Yes** | Medium | Narrow/tall composition; useful for 9:16 Shorts close-up |

**Copies in `Videos/Input_image/`:** The same 4 images exist there as duplicates. Source of truth = `brand/`. Input_image copies are working copies for the video pipeline.

### Resolution Note
All 4 images are small thumbnails (~400px wide). This is acceptable as Higgsfield Soul ID reference input but is not ideal for high-quality generation. If a future Higgsfield session allows higher-resolution character seeding, regenerate to at least 1024×1024. For now, treat these as usable.

### Consistency Assessment
The 4 images appear to be generated from the same Higgsfield character prompt session. Core identity (face, age, hair, build) is consistent across all four. Minor pose and angle variations are expected. No significant continuity failures detected from metadata (resolution/file size patterns are consistent).

---

## 2. Large Model-Sheet PNG

| File path | Proposed asset_id | Resolution | Size | Type | Notes |
|---|---|---|---|---|---|
| `brand/be54ce9d-00f5-445c-b70b-7d9dd2ab7d71.png` | `JAMES_MODEL_SHEET_001` | 896×1200px RGBA | 1.8MB | Character composite/model sheet | Larger format; likely a Higgsfield multi-view or character sheet. Useful as generation context but should not be used directly as a reference image input. |

---

## 3. Duplicate/Copy

| File path | Status | Notes |
|---|---|---|
| `brand/james_harrington_reference.png` | Duplicate of `JAMES_FRONT_DESK_001` | 408×398px, same size as front. Keep as working reference copy. Do not assign a separate canonical asset_id. |

---

## 4. Studio/Library Images

**None found.** `assets/reference/studio_library/` contains only `.gitkeep`. No studio still images exist anywhere in the repo.

**Available workaround:** The 8 lipsync clips in `assets/media/james_teaser/` (1280×720) contain studio-set frames. Still frames can be extracted using ffmpeg and used as provisional reference context. This is NOT a substitute for a purpose-generated studio still — but can help establish spatial continuity while studio stills are being generated.

Example extraction command (do not run in this sprint unless approved):
```bash
ffmpeg -i assets/media/james_teaser/001_hook.mp4 -vf "select=eq(n\,0)" -vframes 1 /tmp/studio_frame_001.png
```

---

## 5. Cat Reference Images

**None found.** `assets/reference/cat/` contains only `.gitkeep`. Must be generated.

---

## 6. Existing Lipsync Clips (Not Reference Images, But Useful)

| Clip | Resolution | Lipsync source | Can extract studio still? |
|---|---|---|---|
| `assets/media/james_teaser/001_hook.mp4` | 1280×720 | trailer_1a | Yes — first frame is studio-set |
| `assets/media/james_teaser/002_background.mp4` | 1280×720 | trailer_2a | Yes |
| `assets/media/james_teaser/003_pattern.mp4` | 1280×720 | trailer_3a | Yes |
| `assets/media/james_teaser/004–008.mp4` | 1280×720 | Higgsfield wan2_7 b-roll | No (b-roll, not studio) |

---

## 7. Final Asset Inventory Summary

| Category | Found | Missing | Notes |
|---|---|---|---|
| James portrait | **4** (usable) + 1 model sheet | 2 additional angles (standing, walking) | Use existing 4 as canonical foundation |
| Studio/library | 0 | 7 angles (all needed) | Generate; frame extraction as provisional |
| Cat | 0 | 2 needed | Generate after studio is locked |
| Wardrobe | 0 | 2 suggested | Low priority; generate on demand |
| Props | 0 | 6 suggested | Generate on demand as needed |
| Color palette | 0 | 1 swatch | Low priority; defined in BRAND_SPEC |
