# James Identity Recovery Report

**Date:** 2026-06-09
**Status:** Active

---

## 1. What Was Rejected

| Asset | Rejection reason |
|---|---|
| `assets/reference/rejected/JAMES_FRONT_DESK_001_rejected_identity.png` | Hard user rejection — does not look like James |
| `assets/reference/studio_library/reusable_backgrounds/STUDIO_LIBRARY_MEDIUM_DESK_001_background_only.png` | Hard user rejection for James identity; room/background may be usable |

All 10 generated James candidates in `assets/reference/james/candidates/` are quarantined as **identity_unverified** — generated in the same session with the same workflow, so all are suspect until individually human-reviewed.

---

## 2. Why It Failed

**Verdict: MODEL_UNPROVEN_NEEDS_REFERENCE_LOCK**

The failure was **workflow-related, not proven model failure**. Specifically:
1. **Single weak reference** — `text2image_soul_v2` was given one 405×398px reference image. This is below ideal for identity anchoring. The model may not have had enough signal to lock the face.
2. **Generation at distance from reference** — the prompt asked for a new studio scene while preserving identity. The balance between "new scene" and "same face" favored the new scene.
3. **No multi-view anchoring** — only one angle was provided. Using all 4 canonical views together gives the model a much stronger identity constraint.
4. **Low source resolution** — 400px thumbnails are marginal reference inputs. Upscaled sources (now available) will perform significantly better.

The model was NOT condemned — it was used incorrectly. The correct workflow is:
- Upscale first → Use all 4 upscaled views as references → Strict identity lock in prompt → Single candidate at a time → Human approval before expanding.

---

## 3. What Remains Canonical

| Asset | Status | Path |
|---|---|---|
| `brand/James_harrington_front.png` | **canonical_foundation** (never modify) | brand/ |
| `brand/James_harrington_3_4.png` | **canonical_foundation** | brand/ |
| `brand/James_harrington_side.png` | **canonical_foundation** | brand/ |
| `brand/James_harrington_vertical.png` | **canonical_foundation** | brand/ |
| `JAMES_FRONT_DESK_001_UPSCALED.png` | **upscaled_pending_review** | assets/reference/james/upscaled/ |
| `JAMES_THREE_QUARTER_STUDY_001_UPSCALED.png` | **upscaled_pending_review** | assets/reference/james/upscaled/ |
| `JAMES_SIDE_PROFILE_001_UPSCALED.png` | **upscaled_pending_review** | assets/reference/james/upscaled/ |
| `JAMES_VERTICAL_CLOSEUP_001_UPSCALED.png` | **upscaled_pending_review** | assets/reference/james/upscaled/ |

Studio environment images (flux_2, no James): usable — see manifest.
Cat images: usable — see manifest.

---

## 4. What Must Change Before Further James Generation

1. Human visual approval of the 4 upscaled images (sent to Telegram now)
2. If upscales pass: use ALL 4 upscaled images as multi-view anchors for every new James generation
3. Use `soul_cinema_studio` (designed for studio character portraits) instead of or in addition to `text2image_soul_v2`
4. OR use `flux_kontext` (image-to-image edit) — starts from an existing James image and edits in the new context; the strongest identity preservation available
5. One candidate at a time; human review before expanding to full library
6. Candidates go to `assets/reference/james/candidates/`; only approved ones to `assets/reference/james/canonical/`
