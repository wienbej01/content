# James Model Assessment

**Date:** 2026-06-09

---

## Models Used for Rejected Assets

`text2image_soul_v2` was used for all 10 generated James candidates. The model supports reference image input (`--image` flag). However, it was given a single 405px reference image — below optimal resolution for strong identity anchoring.

---

## Model Capability Assessment

| Capability | text2image_soul_v2 | flux_kontext | soul_cinema_studio | topaz_image |
|---|---|---|---|---|
| Reference image input | ✅ (single) | ✅ (single, edit-based) | ✅ (multi?) | ✅ (upscale only) |
| Multiple reference images | ❓ untested | ❌ | ❓ untested | N/A |
| Identity consistency | Medium | **High** (edit-based) | Unknown | **Highest** (preserve only) |
| Character generation | Yes | Yes (from existing) | Yes (studio portrait) | No (upscale only) |
| Studio/environment | Yes | Yes | Yes | No |
| Upscaling | No | No | No | **Yes** |
| Video/lipsync | No (image only) | No | No | No |
| Cost | 0.12 credits | 1.5 credits | 0.12 credits | ~2-4 credits |

---

## Verdict: MODEL_UNPROVEN_NEEDS_REFERENCE_LOCK

`text2image_soul_v2` was not used correctly:
- Single low-res reference → insufficient identity signal
- No multi-view anchoring
- No explicit "do not invent a new man" instruction in the prompt

**Recommended next test:** Use `soul_cinema_studio` with all 4 upscaled references to generate one James in studio. If identity drifts again, try `flux_kontext` (edit an existing upscaled image rather than generating from scratch).

**For studio/environment-only images:** `flux_2` is **suitable and proven**. The 6 environment-only studio images (WIDE, EMPTY_ROOM, CLOSEUP_DESK, WINDOW_LIGHT, NIGHT_LAMP, READING_CHAIR) are usable for background reference.

**For cat images:** `flux_2` is **suitable**. Cat images do not require character consistency.

**Do not condemn `text2image_soul_v2` yet.** Retest with upscaled multi-view references and stricter prompt. If identity still drifts, then consider it insufficient for James.
