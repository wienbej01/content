# James Harrington — Continuity Strategy

**Version:** 1.0
**Date:** 2026-06-09
**Status:** Active

---

## 1. James is a Fictional Host

James Harrington is a **fictional recurring host character**, not a representation of the real channel operator. He is the creative frontman of the Leverage Mind channel — a made-up presenter with a stable, consistent visual identity.

This distinction matters for generation:
- There are no identity-preservation obligations tied to a real person
- The goal is character consistency, not biometric fidelity
- Future generations can vary James slightly in pose, expression, and wardrobe within defined bounds
- Continuity is a brand decision, not a likeness requirement

---

## 2. Existing Foundation Images

**4 James images have been found in the repo** and are designated as the canonical reference base:

| Priority | Asset ID | Source file | Role |
|---|---|---|---|
| **PRIMARY** | `JAMES_FRONT_DESK_001` | `brand/James_harrington_front.png` | The single strongest reference for all A-roll generation |
| **PRIMARY** | `JAMES_THREE_QUARTER_STUDY_001` | `brand/James_harrington_3_4.png` | 3/4 angle; use alongside front for Higgsfield Soul ID sessions |
| Secondary | `JAMES_SIDE_PROFILE_001` | `brand/James_harrington_side.png` | Side angle; use for profile shots |
| Secondary | `JAMES_VERTICAL_CLOSEUP_001` | `brand/James_harrington_vertical.png` | 9:16 close-up compositions |

**Rule:** Every future James image generation session must include `JAMES_FRONT_DESK_001` as the primary reference. For maximum consistency, also include `JAMES_THREE_QUARTER_STUDY_001`.

---

## 3. Continuity Anchors (must not drift)

These elements define James's identity. Any generated image that deviates significantly from these is a continuity failure:

| Anchor | Description |
|---|---|
| **Face structure** | Sharp, refined features; weathered but not gaunt; distinctive without being unusual |
| **Age impression** | Appears approximately 60 years old. Not youthful. Not extreme elderly. |
| **Hair** | Silver-grey, neatly combed back. Not white, not dark, not long, not disheveled |
| **Skin tone** | Warm-cool Caucasian, consistent with RP British male of this age |
| **Build** | Medium-to-tall, moderate build. Not muscular. Not heavy. Not slight. |
| **Posture** | Upright and composed. Never slouched. Never artificially stiff. |
| **Demeanor** | Calm, attentive, thoughtful. The face of someone about to say something considered. |
| **Expression baseline** | Composed with light engagement. Not smiling broadly. Not neutral-blank. |
| **Presence** | Quiet authority. He has seen more than he says. |

---

## 4. Allowed Variations

These may differ between images without being a continuity failure:

- **Wardrobe:** Any outfit within the approved palette (navy, charcoal, cream, grey, forest green). The canonical outfit is navy cashmere over white Oxford — variations within this register are acceptable.
- **Pose:** Seated vs standing, slight angle shifts, looking slightly off-camera.
- **Expression:** Range from composed-neutral to thoughtful-engaged to slight half-smile. No more than this.
- **Setting:** Library/study interior vs occasional quiet exterior.
- **Framing:** Front, 3/4, side, over-shoulder.

---

## 5. Forbidden Variations

These constitute continuity failures and require regeneration:

| Forbidden | Why |
|---|---|
| Major age shift (appears <45 or >75) | Breaks character identity |
| Different hair (dark, long, buzzed, bleached) | Breaks visual anchor |
| Beard or heavy stubble if the base images are clean-shaven | Inconsistency |
| Glasses not in base images | Inconsistency unless explicitly approved |
| Random ethnicity drift | Wrong character |
| Cartoonish or anime-stylized rendering | Wrong register |
| Uncanny valley smoothed AI face | Quality failure |
| Motivational speaker energy (wide grin, pointing) | Wrong personality |
| Futuristic or casual wardrobe | Wrong register |
| Generic business-stock-photo look (forced smile, arms crossed) | Wrong presence |
| Distorted hands | Technical AI failure |
| Significant build change (heavily muscular or very thin) | Breaks identity |

---

## 6. Continuity Policy

### If existing images are usable (current case — they are)
- Treat `JAMES_FRONT_DESK_001` and `JAMES_THREE_QUARTER_STUDY_001` as **canonical anchors**
- All future Higgsfield generation sessions for James must reference at least one of these two
- New James images must be approved before entering the canonical set
- New approved images supplement the canonical set; they do not replace the foundation images

### If a future generation produces a better reference
- A new image may be promoted to primary canonical anchor only after:
  1. It scores ≥ 4.0 on the QA checklist
  2. It passes human review
  3. It is explicitly confirmed as the new canonical anchor in `REFERENCE_ASSET_MANIFEST.md`

### Staged refresh strategy (if needed)
If the existing 4 images are found to be inadequate for production (e.g., too low resolution for future tools):
1. Use the best existing image (front) as input to generate a higher-resolution version
2. Human-review the new image against the existing base
3. Promote the approved new image as the canonical anchor
4. Keep the original as a secondary/fallback reference
5. Never delete the originals

---

## 7. Note on the Large Model Sheet

`brand/be54ce9d-00f5-445c-b70b-7d9dd2ab7d71.png` (896×1200px) appears to be a Higgsfield character composite or model sheet. It provides context but should not be used as a direct generation reference due to its composite nature. It is archived as `JAMES_MODEL_SHEET_001` for reference.
