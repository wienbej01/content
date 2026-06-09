# Prompt Rules — Media Generation Prompt Specification

**Version:** 1.0
**Status:** Active
**See also:** `TECHNICAL_BIBLE.md`, `UNIVERSE_BIBLE.md`, `REFERENCE_ASSET_MANIFEST.md`, `QA_RUBRIC.md`

---

## 1. Purpose

This document defines how media generation prompts must be constructed for the James channel. It exists because raw `visual_brief` text fed directly to a video model produces inconsistent results — each clip invents its own world.

Prompts compiled according to these rules produce clips that:
- Belong to the same visual universe
- Obey the technical production grammar
- Reference the correct approved assets for consistency
- Block the most common generation failures before they occur

---

## 2. Prompt Source Hierarchy

**After M5 and M8 are implemented, prompts must come from this chain:**

```
Script
  → Storyboard beat (M5)
    → Universe Bible constraints
    → Technical Bible constraints
    → Reference Asset Manifest (for A-roll and studio shots)
      → Media Prompt Plan (M8 compiler output)
        → Media generation call
```

**Prompts must NOT be compiled directly from raw `visual_brief`** after M5/M8 exist. The M3-era `visual_brief` path is preserved for backward compatibility and test purposes only.

### Scene type distinction (important for implementers)

| Scene type | Camera address | Lipsync | Audio policy | Model |
|---|---|---|---|---|
| `A_ROLL_TALKING_HEAD` | Direct; James looks at camera | Yes — from final approved narration only | `keep_lipsync` | `seedance_2_0` |
| `A_ROLL_CHARACTER_PRESENT_VOICEOVER` | James in frame, NOT addressing camera | No | `strip` — audio comes from the continuous master narration file | `seedance_2_0` |

### Storyboard beat → prompt field mapping

When the M8 compiler maps storyboard beats to prompt entries:
- Storyboard `camera` (angle name/description) → prompt `camera_angle_id` (for studio shots) or `camera_movement` (for b-roll)
- Storyboard `movement` → prompt `camera_movement`
- Storyboard `reference_assets[]` → prompt `reference_assets[]` (pass through unchanged)

### Continuous narration note

`continuous_voiceover` is required for final publish. Assembly support for continuous narration is an **M7 task** — it does not exist today. M5 storyboards should declare `narration_mode: continuous_voiceover` to express the intent, but actual continuous assembly will not work until M7 is complete.

---

## 3. Required Prompt Fields

Every compiled prompt (entry in `media_prompt_plan.json`) must include these **universal fields**:

| Field | Type | Notes |
|---|---|---|
| `beat_id` | string | Links to storyboard beat |
| `scene_type` | enum | From the storyboard scene type list |
| `a_roll_or_b_roll` | enum | `a_roll` \| `b_roll` \| `insert` |
| `james_presence` | enum | `present_speaking` \| `present_silent` \| `absent` |
| `location_id` | string | From the approved environment list |
| `camera_movement` | string | From the Technical Bible allowed-movements list |
| `lighting` | string | Reference the Technical Bible lighting type |
| `palette` | string | Warm-neutral; navy/gold/ivory; reference the palette |
| `text_policy` | enum | `none` \| `soft_focus_only` \| `post_overlay` |
| `audio_policy` | enum | `strip` (for `generated_tts`) \| `keep_lipsync` (for `baked_in`) |
| `crop_safety` | enum | `center_safe` \| `full_frame_16x9` |
| `duration_target_sec` | number | |
| `output_path` | string | |
| `positive_prompt` | string | The compiled positive prompt text |
| `negative_prompt` | string | Must include the default negative block |
| `model` | string | `seedance_2_0` for A-roll lipsync; `wan2_7` for grounded b-roll |

**Studio/library prompts additionally require:**

| Field | Type | Notes |
|---|---|---|
| `camera_angle_id` | string | One of the 7 approved IDs. **Required only when `location_id` is a studio location** (`ENV_STUDIO_LIBRARY` or `ENV_PRIVATE_STUDY`). Set to `null` for b-roll and exterior shots. |

**A-roll prompts additionally require:**

| Field | Type | Notes |
|---|---|---|
| `reference_assets` | array | At least one approved James reference ID. Required for all A-roll; omit only for abstract b-roll without James. |

---

## 4. A-roll Prompt Rules

A-roll prompts generate shots where James is the subject. These are the most constrained prompt type.

### Mandatory inclusions
- **Reference assets:** at minimum one approved James reference ID (`JAMES_FRONT_DESK_001`, etc.) and one approved studio angle ID
- **Physical description of James:** pulled from `brand/BRAND_SPEC.md` §9 Higgsfield character prompt — 60-year-old British man, silver-grey hair, navy sweater, warm study, etc. Do not paraphrase; use the approved prompt anchor.
- **Studio angle ID:** must match one of the 7 approved angles from `JAMES_RECORDING_STUDIO_LIBRARY.md`
- **Lighting:** warm desk lamp, soft side-key, realistic interior, 2700–3500K
- **Camera:** one of the approved movements; `locked-off medium shot` is the default

### Lipsync-specific
- Lipsync A-roll uses `seedance_2_0`
- Audio reference: the final approved ElevenLabs narration file
- Never use a draft narration for lipsync generation
- `audio_policy: keep_lipsync`

### Example A-roll prompt (direct address)

**Positive:**
> A 60-year-old British man, silver-grey hair neatly combed back, clean-shaven, sharp blue-grey eyes, composed expression. Wearing a navy cashmere sweater over an open-collar white Oxford shirt. Sitting at a dark wood desk in a warm-lit private study. Floor-to-ceiling bookshelves of dark wood behind him, soft and out of focus. A directional desk lamp casts warm golden light from the left. Hyperrealistic, natural skin texture, photographic quality. Camera: Sony A7IV, 85mm portrait lens, eye-level medium shot, shallow depth of field. Aspect ratio 16:9. The man is speaking calmly and directly.

**Negative:**
> no futuristic elements, no neon, no cyberpunk, no hologram, no floating UI, no robots, no garbled text, no readable generated text, no fake logos, no distorted hands, no uncanny valley faces, no random business people, no sci-fi setting, no overdesigned office, no AI dashboard, no motivational poster energy, no ring light catchlight, no seamless white background

---

## 5. James-Present Voiceover Prompt Rules

These are shots where James is in frame but not speaking directly to camera. Lower constraint than talking head; more flexibility in angle and activity.

### Rules
- James must still match established visual identity (wardrobe, age, build)
- Environment must be the studio/library or an approved secondary environment
- Activity must be purposeful: reading, writing, reviewing a document, standing at bookshelf
- Camera typically over-the-shoulder, side-profile, or standing-bookshelf angle
- `audio_policy: strip` (the narration is from the main continuous narration file, not this clip)

### Example James-present voiceover prompt

**Positive:**
> A 60-year-old British man in a navy sweater, seated at a dark wood desk in a warm study, writing in a leather notebook with a pen. Over-the-shoulder camera angle looking down at the desk surface. The desk is lit by a warm brass desk lamp from the left. Dark wood bookshelves are visible in the soft background. Slow, almost static camera. Hyperrealistic photography style, 4K. Aspect ratio 16:9.

**Negative:**
> *(same default negative block)*

---

## 6. B-roll Prompt Rules

B-roll prompts generate supporting visual content. These have more creative latitude but are still constrained by the universe and technical bibles.

### Rules
- Must be grounded and physically plausible — no impossible or sci-fi environments
- Must obey the color and lighting system (warm neutrals; no neon)
- No readable generated text in frame
- Camera movements must be from the allowed list (no spinning, no aggressive zooms)
- `audio_policy: strip` — b-roll audio is never used as narration
- Model: `wan2_7` unless otherwise justified

### B-roll prompt construction
- Start with the physical environment and what is happening in it
- Add the lighting and palette constraints
- Add the camera movement
- End with the negative prompt block

### Example grounded b-roll prompt

**Positive:**
> A financial district at dawn. Long-exposure photography look: light trails from passing vehicles and pedestrians crossing at an intersection. Classical stone or glass office buildings in the background, soft and out of focus. Cool-warm transition sky: pale orange at the horizon, blue-grey above. Slow parallax. No people visible as individuals. Cinematic, restrained. Aspect ratio 16:9.

**Negative:**
> no neon signs, no holograms, no floating UI, no cyberpunk elements, no futuristic architecture, no garbled text, no visible logos, no AI dashboard, no sci-fi elements, no sharp focus on readable signage, no extreme contrast

---

## 7. Reference Image Rules

### A-roll and studio shots: reference required
- Every prompt that generates James's face must include at least one approved James reference asset
- Every prompt that generates the studio/library must include the corresponding approved studio angle reference
- Reference assets are listed in `REFERENCE_ASSET_MANIFEST.md`

### B-roll: reference optional
- Reference images are not required for environment-only b-roll
- If James appears in b-roll (walking, back-of-head), include the appropriate James reference to maintain consistency

### Cat prompts: cat reference required
- Any prompt that includes the background cat must reference `CAT_LIBRARY_SLEEPING_001` or `CAT_WINDOW_001`
- Do not generate a cat without a reference; inconsistency is a QA failure

### What to do when a reference image does not exist yet
- Flag the prompt as `reference_missing: true`
- Block the generation until the reference is created
- Reference generation order is defined in `REFERENCE_ASSET_MANIFEST.md` §10

---

## 8. Negative Prompt Block (Default)

The following negative constraints must be included in **every** generated media prompt. They may be extended but never removed.

```
no futuristic holograms, no cyberpunk, no neon, no floating UI, no robots, 
no garbled text, no readable generated text, no fake logos, no distorted hands, 
no uncanny valley faces, no random smiling stock-photo people, no sci-fi setting, 
no overdesigned startup office, no AI dashboard, no motivational poster energy, 
no random substitute presenter, no inconsistent studio layout, 
no inconsistent cat appearance
```

If a beat has additional `forbidden_elements` from the storyboard, append them to this block.

---

## 9. Text and Screen Policy (in Prompts)

- **Default:** `text_policy: none` — do not generate any text elements
- **Screens:** if a screen must be visible, prompt for it to be off, in sleep mode, or with the display pointed away from camera
- **Books:** prompt for books to be in soft focus; spines not readable
- **Documents:** prompt for documents to be face-down, partially visible, or at an angle that prevents reading
- **If text is needed in the final video:** mark `text_policy: post_overlay`; text is added in post-production by `assemble.py` using the brand typography — never generated in the clip

---

## 10. Audio Policy (in Prompts)

- `generated_tts` segments: `audio_policy: strip` — the clip's audio will be stripped by `generate_media.py` before assembly. This is enforced by code, but must also be explicit in the prompt plan for QA traceability.
- `baked_in` segments (lipsync): `audio_policy: keep_lipsync` — the clip's audio is the synced narration and must not be stripped.
- `silent` segments: `audio_policy: strip` — no audio required.

---

## 11. Crop Safety Policy (in Prompts)

- All A-roll prompts: `crop_safety: center_safe` — James must be within the center 56% horizontal zone
- Insert shots (hands, notebook): `crop_safety: center_safe` — the subject of the insert must be center-safe
- Wide establishing shots that are supplementary (not the primary A-roll): `crop_safety: full_frame_16x9` — the 9:16 crop may sacrifice background, which is acceptable

---

## 12. Model Routing (in Prompt Plans)

| Scene | Model | Rationale |
|---|---|---|
| A-roll / lipsync with James | `seedance_2_0` | Character consistency + audio sync |
| James-present voiceover | `seedance_2_0` | Character consistency |
| Grounded b-roll (city, office, desk) | `wan2_7` | Cost-effective; adequate quality for b-roll |
| Abstract/atmospheric b-roll | `wan2_7` | Cost-effective |

Override via `--model` flag in `generate_media.py` only with documented justification.

---

## 13. Forbidden Prompt Patterns

These are prompt approaches that reliably produce universe failures:

| Forbidden | Why | Replacement |
|---|---|---|
| "AI productivity dashboard" or "data visualization" | Produces glowing holographic UI | Describe the physical action: "annotating a document" |
| "futuristic office" or "tech startup" | Wrong environment | Use `ENV_STUDIO_LIBRARY` or `ENV_PROFESSIONAL_COMMON` |
| "cinematic dramatic lighting" | Produces trailer/action look | Use "warm desk lamp, soft side-light" |
| "text showing [X]" | Produces garbled AI text | Mark `text_policy: post_overlay`; add text in post |
| "AI brain visualization" | Abstract neural net cliché | Use "hand drawing a decision tree on paper" |
| Raw `visual_brief` after M5/M8 exist | No universe/technical constraints injected | Use the prompt compiler |

---

## 14. Prompt Examples — Good vs Forbidden

### Example: forbidden prompt (before M4)
```
visual_brief: "Quick cuts showing a professional reviewing strategies, overlaid with AI data flows and glowing productivity metrics, neon blue ambient lighting"
```
**Failures:** neon blue, glowing metrics (hologram), quick cuts (camera grammar), AI data flows (cyberpunk)

### Corrected prompt (after M4 constraints applied)
```
positive: "A professional at a dark wood desk, reviewing a printed strategy document with a pen in hand. Warm desk lamp light from the left. Slow over-the-shoulder camera angle. No visible screens. Soft bookshelves in the background. Restrained, documentary feel. 16:9."
negative: "no neon, no holograms, no floating UI, no glowing elements, no garbled text, no fast cuts, no cyberpunk, no AI dashboard"
```
