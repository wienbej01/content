# Reference Asset Generation Runbook

**Version:** 1.0
**Date:** 2026-06-09

This runbook defines the exact step-by-step process for building the reference image library. It must be followed in order. Steps cannot be skipped.

---

## Golden Rule

**Do not generate video until Steps 1–8 are complete and human-approved.**
**Do not generate all assets at once. Work in small batches.**
**No overwrite without explicit approval.**
**No secret logging. No token printing.**

---

## Step 1 — Inventory Existing Repo Images

**Status: COMPLETE** (see `REFERENCE_ASSET_INVENTORY.md`)

**Result:**
- 4 James portrait images found in `brand/`
- 1 large model-sheet PNG found in `brand/`
- 0 studio/library stills found
- 0 cat images found

**Action:** Proceed to Step 2.

---

## Step 2 — Identify James Foundation Images

**Status: COMPLETE** (see `JAMES_CONTINUITY_STRATEGY.md`)

**Primary canonical anchors:**
- `JAMES_FRONT_DESK_001` = `brand/James_harrington_front.png`
- `JAMES_THREE_QUARTER_STUDY_001` = `brand/James_harrington_3_4.png`

**Secondary:**
- `JAMES_SIDE_PROFILE_001` = `brand/James_harrington_side.png`
- `JAMES_VERTICAL_CLOSEUP_001` = `brand/James_harrington_vertical.png`

**Action:** Use these in every future James generation session as reference/Soul ID inputs. Proceed to Step 3.

---

## Step 3 — Identify Studio/Library Base Images

**Status: NONE FOUND**

**Action:** `STUDIO_LIBRARY_WIDE_001` must be generated in Step 5 before any other studio images.

**Provisional option:** Extract a still frame from `assets/media/james_teaser/001_hook.mp4` as a reference for spatial context only — not for production use:
```bash
ffmpeg -i assets/media/james_teaser/001_hook.mp4 -vf "select=eq(n\,0)" -vframes 1 /tmp/studio_frame_provisional.png
```
This frame shows the studio used for the teaser. It may help when prompting for the new studio reference, but it is NOT a canonical reference asset.

---

## Step 4 — Prepare Prompt Pack

**Status: COMPLETE** (see `REFERENCE_STILL_PROMPT_PACK.md`)

The prompt pack contains exact generation prompts for all minimum viable assets. Review it before generating.

---

## Step 5 — Generate Still References (Minimum Viable Batch)

Generate **in this exact order**, one at a time. Review and approve each before generating the next.

### Batch 1 (required before teaser_02 generation)

| Order | Asset ID | Type | Estimated credits |
|---|---|---|---|
| 1 | `STUDIO_LIBRARY_WIDE_001` | Room establishing (no James) | ~1 credit |
| 2 | `JAMES_FRONT_DESK_001` (improved) | James front, higher res | ~1 credit |
| 3 | `STUDIO_LIBRARY_MEDIUM_DESK_001` | James at desk (uses both refs) | ~1 credit |
| 4 | `JAMES_THREE_QUARTER_STUDY_001` (improved) | James 3/4 | ~1 credit |

**Stop after Batch 1. Get human approval before continuing.**

If existing James images (400px) are sufficient for Higgsfield Soul ID → use them directly → skip Step 2 and 4 in Batch 1. Test with a trial generation first.

### Batch 2 (generate after Batch 1 approved)

| Order | Asset ID | Type |
|---|---|---|
| 5 | `STUDIO_LIBRARY_OVER_SHOULDER_001` | Desk OTS angle |
| 6 | `JAMES_STANDING_LIBRARY_001` | James standing |
| 7 | `STUDIO_LIBRARY_STANDING_BOOKSHELF_001` | James at bookshelf |

### Batch 3 (optional, generate on demand)

- `STUDIO_LIBRARY_CAT_BACKGROUND_001`
- `CAT_LIBRARY_SLEEPING_001`
- `JAMES_OVER_SHOULDER_WRITING_001`
- `JAMES_WALKING_CITY_001`
- Prop assets (generate individually as needed)

---

## Step 6 — Human Review

For each generated still:
1. Score using `REFERENCE_ASSET_QA_CHECKLIST.md`
2. Calculate average score
3. Check automatic fail conditions
4. Classify: approved / secondary / reject
5. If approved: place in `assets/reference/{category}/ASSET_ID.png`

Do not proceed to Step 7 until at minimum:
- `STUDIO_LIBRARY_WIDE_001` is approved
- `JAMES_FRONT_DESK_001` (or the existing `brand/` version confirmed adequate) is approved

---

## Step 7 — Approve Canonical Set

Update `REFERENCE_ASSET_MANIFEST.md`:
- Set `status` to `approved` for each passing asset
- Set `canonical_priority` to `primary` for the 2 main James anchors and the Wide studio shot
- Set `qa_score` from the checklist result

---

## Step 8 — Update Manifest and Tools

Once canonical set is approved:
- Ensure `REFERENCE_ASSET_MANIFEST.md` has all paths and statuses updated
- The prompt compiler (`scripts/compile_media_prompts.py`) reads `reference_assets[]` from storyboard beats — update beats to use the canonical asset IDs

---

## Step 9 — One-Scene Generation Test

**Only after Steps 6–8 pass for the minimum viable Batch 1 assets.**

Run a single b-roll test clip (no James reference needed):
```bash
python3 scripts/generate_media.py scripts/generated/james_growth_system_teaser_01.json --force
```
*(targeting one segment only — use a separate one-segment test script as done in M3-A)*

Then run a single A-roll James test (with reference images):
- Use `JAMES_FRONT_DESK_001` + `STUDIO_LIBRARY_MEDIUM_DESK_001` as `--image` references
- Target one beat only into a temp path

Get human approval on both before Step 10.

---

## Step 10 — Teaser_02 Full Regeneration

**Only after:**
- Batch 1 reference images approved ✅
- Storyboard James-presence ≥ 60% ✅
- Continuous narration plan in place (M7 or explicit approval of segment mode) ✅
- One-scene tests approved ✅

Create new project:
```
project_id: james_growth_system_teaser_02
```

Never overwrite teaser_01 outputs.

---

## Manual Fallback

If no image-generation CLI is available or Higgsfield is unavailable:
- Use the existing 4 James images from `brand/` directly as Soul ID references for video generation
- Document the limitation in `REFERENCE_ASSET_MANIFEST.md`
- Proceed with the best available references rather than blocking the pipeline
- Flag all outputs as `reference_missing_generation_fallback` in QA logs
