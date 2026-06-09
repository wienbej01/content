# James Reference Lock Protocol

**Version:** 1.0 | **Date:** 2026-06-09 | **Status:** ACTIVE — must be followed for all James generation

---

## Core Rules

**1. Canonical source**
The canonical James identity comes from `brand/James_harrington_{front,3_4,side,vertical}.png`. Text prompts alone cannot define James's identity. The brand/ files are the source of truth and must never be modified.

**2. Upscale before variation**
Upscale canonical images before using them as generation references. Topaz with `face_enhancement=true` preserves identity exactly. Use `assets/reference/james/upscaled/` outputs as references, not the 400px originals.

**3. Multi-view anchoring**
When the tool supports multiple reference images, provide ALL 4 upscaled canonical views:
- `JAMES_FRONT_DESK_001_UPSCALED.png`
- `JAMES_THREE_QUARTER_STUDY_001_UPSCALED.png`
- `JAMES_SIDE_PROFILE_001_UPSCALED.png`
- `JAMES_VERTICAL_CLOSEUP_001_UPSCALED.png`

Prompt must include: *"Use these reference images as the same fictional person. Preserve identity exactly. Do not invent a new man."*

If the tool supports only one reference image, use `JAMES_FRONT_DESK_001_UPSCALED.png` and document the limitation.

**4. No prompt-only canonical James**
Text-only generation produces exploration candidates only. It cannot become canonical.

**5. Preferred tools for new James variations**

| Tool | Use for | Why |
|---|---|---|
| `topaz_image` (face_enhancement=true) | Upscaling existing images | Identity-preserving; no creative drift |
| `flux_kontext` + upscaled James ref | Placing James in new settings | Starts from existing image; strongest identity preservation |
| `soul_cinema_studio` + all 4 refs | Studio portrait variations | Designed for character-consistent studio portraits |
| `soul_cinematic` + all 4 refs | Cinematic variations | Alternative to soul_cinema_studio |

**6. One-at-a-time approval**
Generate ONE candidate. Get human approval. Only then generate more. No batch-of-10 until one passes.

**7. Approval threshold**
A new James image is canonical only when:
- Face clearly matches the upscaled canonical images
- Age impression matches (appears ~60)
- Hair matches (silver-grey, combed back)
- Demeanor matches (composed, not generic model)
- Human explicitly approves it

**8. Rejection is sticky**
Files in `assets/reference/rejected/` may NOT be used as identity anchors. Files in `candidates/` are unverified and may not enter production without explicit approval.

**9. Studio first, James second**
Establish the studio environment independently (flux_2, no James). Then add James using canonical references. Do not generate James and studio simultaneously on first attempt.

**10. Wardrobe is secondary**
Only vary wardrobe AFTER identity is confirmed correct. Do not combine identity variation + wardrobe variation in one generation attempt.
