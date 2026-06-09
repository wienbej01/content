# James — 10 Canonical Reference Variation Plan

**Version:** 1.0 | **Date:** 2026-06-09

James Harrington is a **fictional host character**, not the channel operator.

---

## Why 10 References

A single reference image produces a single visual register. Ten controlled variations give the storyboard and prompt compiler the flexibility to:
- Use different studio angles (front, 3/4, side, standing, over-shoulder)
- Cover different episode tones (formal, casual-elegant, thinking, active)
- Support both 16:9 and 9:16 (Shorts) crops
- Maintain strict visual consistency across all these situations

The 4 existing images remain the continuity foundation. The 6 new references extend the library without replacing it.

---

## Continuity Foundation (existing — use as reference input for all new generations)

| Asset ID | Source file | Status | Role |
|---|---|---|---|
| `JAMES_FRONT_DESK_001` | `brand/James_harrington_front.png` | found | **PRIMARY** — all sessions must include this |
| `JAMES_THREE_QUARTER_STUDY_001` | `brand/James_harrington_3_4.png` | found | **PRIMARY secondary** |
| `JAMES_SIDE_PROFILE_001` | `brand/James_harrington_side.png` | found | Secondary |
| `JAMES_VERTICAL_CLOSEUP_001` | `brand/James_harrington_vertical.png` | found | 9:16 reference |

---

## The 10 Canonical James References

| # | Asset ID | Wardrobe | Pose/Expression | Priority |
|---|---|---|---|---|
| 1 | JAMES_FRONT_DESK_001 | Navy cashmere + white Oxford | Front-facing, seated, composed | PRIMARY |
| 2 | JAMES_THREE_QUARTER_STUDY_001 | Same | 3/4 right, mid-thought | PRIMARY |
| 3 | JAMES_SIDE_PROFILE_001 | Same | Side, looking toward window | Secondary |
| 4 | JAMES_VERTICAL_CLOSEUP_001 | Same | Head+shoulders, 9:16, direct | Secondary |
| 5 | JAMES_STANDING_LIBRARY_001 | Navy blazer over white Oxford | Standing near bookshelf, 3/4 | Secondary |
| 6 | JAMES_OVER_SHOULDER_WRITING_001 | Navy cashmere | OTS, hands on desk with pen | Secondary |
| 7 | JAMES_DESK_THINKING_001 | Same | Seated, thoughtful, pen in hand, looking down/off | Secondary |
| 8 | JAMES_WALKING_HOME_LIBRARY_001 | Navy blazer | Slow walk through private library, purposeful | Fallback |
| 9 | JAMES_CASUAL_HOME_OFFICE_001 | Grey fine-knit sweater + cream shirt | Relaxed but composed, seated | Fallback |
| 10 | JAMES_FORMAL_DARK_JACKET_001 | Dark charcoal blazer + white shirt, pocket square | Formal seated, high-stakes topic register | Fallback |

---

## Allowed Variation Policy

| Element | Allowed variation |
|---|---|
| Wardrobe | Navy, charcoal, dark brown, deep green jackets; cream/off-white/muted blue shirts; dark turtleneck if old-money register |
| Pose | Seated vs standing; front vs 3/4 vs side vs OTS |
| Expression | Composed → thoughtful → slight half-smile. No wider range. |
| Setting | Studio library interior (primary); quiet exterior (walking only, tasteful) |

## Forbidden Variation Policy

Major age change, beard/glasses inconsistency, ethnic drift, bright wardrobe, startup casual, uncanny face, distorted hands, sci-fi outfits, generic business-stock pose.

---

## Upscaling Policy

The 4 existing images are ~400px wide — adequate for Higgsfield Soul ID seeding but not ideal at large scale. Options:
1. **Use existing images directly** as `--image` Soul ID reference → outputs at full resolution → place in `assets/reference/james/`
2. **Upscale first** using `flux_kontext` or similar (upscale the 400px source before using as reference)
3. For this sprint: option 1 is sufficient. The 400px images are adequate for Soul V2 / character seeding.

Do NOT overwrite `brand/James_harrington_*.png`. Save all outputs under `assets/reference/james/`.

---

## Generation Order

Batch A → Batch D → Human review → canonical promotion
