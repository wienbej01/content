# Technical Bible — Production Grammar

**Version:** 1.0
**Status:** Active
**Companion to:** `UNIVERSE_BIBLE.md` (what exists), `JAMES_CHARACTER_BIBLE.md`, `JAMES_RECORDING_STUDIO_LIBRARY.md`
**See also:** `PROMPT_RULES.md`, `QA_RUBRIC.md`, `constraints.json`, `brand/BRAND_SPEC.md`

---

## 1. Purpose

This document defines **how** the James channel universe is filmed, generated, edited, voiced, and quality-controlled. It is the technical production grammar.

- **Universe Bible** answers: What exists in the James world?
- **Technical Bible** answers: How is that world captured and edited?

Every AI-driven step — storyboard generation, media prompt compilation, media generation, audio processing, and QA — must reference this document alongside the Universe Bible before proceeding. A technically-compliant output that violates the Universe Bible fails; a universe-compliant concept that violates this grammar also fails.

The goal is not to produce identical videos. It is to produce videos that feel like they belong to the same channel — consistent in quality, register, and visual logic — while allowing variation in content, structure, and emphasis.

---

## 2. Visual Grammar

### Overall look
**Restrained cinematic.** Not documentary-handheld, not feature-film bombastic. The visual register is closer to a high-quality long-form magazine editorial or a premium institutional video — controlled, purposeful, premium without calling attention to its own production.

### Realism level
All scenes must feel **plausible and physically real**. Light behaves like real light. Rooms look like real rooms. People move like real people. AI-generated material that reads as synthetic, over-smoothed, or physically impossible is a generation failure.

### What "premium" means technically
- Shallow depth of field on A-roll (background soft but present)
- Consistent warm color temperature; no mixed or accidental color casts
- No visible compression artifacts in final output
- Exposure controlled — no clipped highlights, no crushed shadows unless deliberate
- Motion is smooth and intentional; no jitter, stutter, or drift

### What "grounded" means technically
- All lighting has a practical source (desk lamp, window, ceiling in an interior)
- No light exists without a plausible origin
- No ambient glow without a visible cause
- Surfaces behave like real materials: wood looks like wood; fabric looks like fabric

### Editorial/documentary feel
The look should remind a viewer of a serious documentary profile or a long-form institutional film — not a brand advertisement, not a music video, not an action trailer. Cuts are deliberate. Shots hold longer than YouTube-standard.

---

## 3. Color System

### Allowed palette
*(See `brand/BRAND_SPEC.md` §3 for hex values.)*

| Role | Description |
|---|---|
| Primary dark | Deep navy (#1B2A4A) — backgrounds, depth, authority |
| Primary warm | Aged gold (#C8973E) — accent, highlight, editorial emphasis |
| Neutral base | Warm ivory (#F5F0E8) — light surfaces, paper, lamp glow |
| Text/shadow | Charcoal (#2D2D2D) — neutral dark for surfaces and grounding |
| Accent | Oxblood (#6B1D2A) — used sparingly; adds depth without warmth |
| Incidental | Dark wood, aged leather, brass, muted sage/green — environmental neutrals |

**Saturation:** low to moderate. Colors are muted. The palette reads as "restrained" against a typical YouTube video — no primary-color pops.

**Contrast:** controlled. Blacks are lifted slightly (not crushed to 0). Highlights are kept below clipping. The look should have visible shadow detail and no blown whites.

### Forbidden palette

| Forbidden | Why |
|---|---|
| Neon purple/blue/pink | Cyberpunk register; signals AI startup cliché |
| Electric glows or ambient lighting without a source | Physically unreal; looks generated |
| Oversaturated corporate primaries (electric blue, red, yellow) | Generic motivational content |
| Cool-toned blue/teal grading | Common in mass-market corporate video; wrong register |
| High-contrast cyberpunk split-toning | Sci-fi, wrong era |

### Color continuity rules
- Color temperature must remain consistent within an episode
- If an episode contains both studio and exterior shots, both must be graded to the same warm-neutral register — no sudden shift to cool tones
- B-roll must not introduce an alien palette that contradicts the studio look
- The channel's color grade is a consistent property of every output

### Color failure conditions
- Any clip that introduces neon, electric blue, or glow-ambient lighting
- Any clip whose saturation or contrast makes it visually incompatible with adjacent studio footage
- A raw Higgsfield output with the default AI "vivid" palette that has not been graded to match the channel

---

## 4. Lighting System

### Guiding principle
Light has a source. Every light in the frame should be traceable to a practical origin: a desk lamp, a window, a ceiling fixture. Unmotivated fill, ambient glow, or colored light that has no source is a technical failure.

### Allowed lighting
| Type | Description |
|---|---|
| Warm desk lamp | Primary practical light in studio; directional, warm white (2700–3200K) |
| Natural window light | Soft, diffuse, from the side; morning or late afternoon |
| Reflected warm fill | Light bounced from walls or paper surface; subtle, not flat |
| Practical ceiling | Ambient background fill only; not the key light |

### Studio/library lighting rules
- Key light: desk lamp or window light from one side; never frontal flat
- Fill: soft, secondary, warm; reduces shadow but does not eliminate it
- Background: bookshelf and room are darker than James; depth through controlled falloff
- Color temperature: 2700–3500K; warmer is preferred over cooler
- Shadows: present and directional; no shadowless flat-lit look

### A-roll lighting rules
- James's face has one clear key light direction; fill from the other side is soft
- No hard catchlight from a ring-light (gives a perfectly round reflection in the eyes — wrong register)
- The warmth of the lamp is visible in the scene — it is a character element, not just illumination

### B-roll lighting rules
- Must share the same warm-neutral color temperature as the studio
- Exterior b-roll: morning or late-afternoon light; overcast diffuse is acceptable; harsh midday is not
- City b-roll: practical streetlights; no neon signs dominating the frame

### Forbidden lighting
| Forbidden | Why |
|---|---|
| Colored ambient glow (blue, purple, teal) | Sci-fi register |
| Ring light catchlight in eyes | Product-shoot aesthetic |
| Overexposed white background (studio seamless) | Looks like a product video |
| Hard single-source spotlight against black | Action/drama; wrong register |
| Neon signs as primary light | Cyberpunk |
| Strobe or flicker effects | Never appropriate |

### Lighting failure conditions
- Any clip where the light source is clearly synthetic and unmotivated
- Colored glow in background or on James without a practical source
- Studio scene where lighting temperature does not match the established warm-lamp standard

---

## 5. Camera Grammar

### Allowed camera movements

| Movement | Description | Use |
|---|---|---|
| Locked-off medium shot | Static camera; James fills center frame | Default for talking head; deliberate stillness |
| Slow push-in | Camera moves toward subject over 3–8 seconds | Building emphasis; arriving at a key idea |
| Slow dolly in | Same as push-in but lateral + toward | Elegant; premium feel |
| Subtle parallax | Minimal lateral drift; suggests depth without obvious movement | Establishing shots |
| Over-the-shoulder toward desk | Static or very slow push | Insert; shows James working |
| Close-up hands/pen/notebook | Tight static or very slow push | Illustrative insert; grounds the content in physical work |
| Slow tracking walk | Camera follows James walking at his pace | Voiceover b-roll; thoughtful transit |
| Motivated slow pan | Across bookshelf or across desk surface; slow and deliberate | Only when revealing a new element or closing a scene |

### Forbidden camera movements

| Forbidden | Why |
|---|---|
| Spinning camera / 360 orbit | Drama register; signals action or hype |
| Aggressive zoom or crash zoom | YouTube bro/hype content |
| Handheld shaking without clear documentary intent | Unstable; wrong register |
| Indoor drone-style impossible angles | Physically absurd in a study |
| Random gimbal wander | The camera must always have a reason to move |
| Hyperactive cut rhythm (<1.5s average shot length in A-roll) | Destabilizes trust; wrong pacing |
| Unmotivated cinematic swoop | Looks like a trailer for an action film |

### A-roll camera rules
- Shot must be stable or have a controlled, motivated movement
- The approved angle IDs from `JAMES_RECORDING_STUDIO_LIBRARY.md` define the allowed framings: `STUDIO_LIBRARY_WIDE_001`, `_MEDIUM_DESK_001`, `_CLOSEUP_001`, `_OVER_SHOULDER_001`, `_SIDE_PROFILE_001`, `_STANDING_BOOKSHELF_001`, `_CAT_BACKGROUND_001`
- No new studio framings without a new approved angle ID

### B-roll camera rules
- Movement must be motivated and consistent with the universe's calm register
- Slow tracking, locked-off, or subtle parallax only
- Exterior shots may use wider FOV but camera movement must remain controlled
- No fast pans, dramatic reframes, or aggressive motion in b-roll

### Camera failure conditions
- Any clip containing a forbidden movement
- A studio shot using an angle that is not one of the approved seven IDs
- Motion inconsistent with the surrounding edit (a fast move between two slow clips)

---

## 6. Framing and Composition

### Master format
**16:9** for all generation. 9:16 is derived by center-crop in `assemble.py`.

### Center-safe rule
- James must be within the center **56% of horizontal width** for any A-roll shot to survive the 9:16 crop
- Key props (notebook, pen, document) must also be within the center 60% if they are the shot's subject
- Background elements (bookshelf, lamp) may fall outside the crop zone

### Eye-line
- For direct address (talking head), James's eyes should be at approximately **1/3 from the top of frame** (upper rule-of-thirds)
- For over-the-shoulder or insert shots, the compositional anchor (the work surface or document) should occupy the lower 2/3

### Headroom
- Talking head: approximately 1.5–2 head-heights of space above James's head
- Close-up: tighter; forehead may approach top of frame but should not be cut

### Negative space for post-production
- In wide and medium shots, leave a clear area (typically the right half of the frame, or above James) where post-production text overlays can be placed without covering James's face or key props

### Background depth
- Background should have visible depth — the bookshelf should be recognizably a bookshelf, not a flat wash
- Bokeh/focus falloff is expected; James is sharp, background is soft

### Failure conditions
- James's face outside the center 56% horizontal zone in A-roll
- Key prop cut off by the 9:16 crop
- Shot so tightly composed that post-production text overlays would cover James's face
- Background entirely out of focus to the point of being unidentifiable

---

## 7. A-roll Production Rules

A-roll means James is visible and serving as the visual anchor of the video. The term covers:
- Direct-to-camera talking head
- James-present voiceover (James in frame, not addressing camera directly)
- James at the desk in a close-up or over-shoulder insert

### Generation rules
- Talking-head A-roll with lipsync must be generated from the **final approved ElevenLabs narration** for that episode — not a draft, not placeholder audio
- James-present voiceover may use any approved studio angle
- No substitute speakers; no random person instead of James

### Minimum James-presence guardrails (for host-led episodes)

**Measurement:** James-presence % = (beats where `james_presence` is `present_speaking` or `present_silent`) ÷ (total storyboard beats excluding `TRANSITION` and `TITLE_CARD`). Measured by **beat count**, not by duration.

These are guardrails, not formulas. Episodes may vary; these prevent total absence of James.

| Episode type | James minimum % | Hard-fail below |
|---|---|---|
| Teaser | ≥60% | 0% |
| Educational explainer | ≥45% | 0% |
| Cinematic trailer | ≥40% | 0% |
| Short (9:16, <60s) | ≥70% | 0% |

If a proposed storyboard falls below these thresholds, the storyboard reviewer must issue a **warning**. 0% James presence is a **hard fail** for any host-led episode (`allow_all_broll` not set).

### Failure conditions
- James absent from a host-led episode
- Lipsync generated without final approved narration
- Substitute presenter in any A-roll position
- A-roll shot using a non-approved studio angle

---

## 8. B-roll Production Rules

B-roll illustrates, extends, and contextualizes the narration. It does not replace the argument. It does not become the entire video.

### Purpose of b-roll
- Grounding abstract concepts in physical reality
- Providing visual breathing room between A-roll beats
- Introducing environmental context (the city, a professional space, objects)

### Allowed b-roll categories

| Category | Notes |
|---|---|
| James-present voiceover (in studio or walking) | James in frame but not addressing camera |
| Desk/work inserts (close-up hands, pen, notebook) | Grounded, specific, believable |
| City exterior — established financial district | Morning or late-afternoon; no neon; controlled motion |
| Professional environment background | Realistic workplace; background figures only |
| Environmental abstraction (bokeh lamp, books, window) | Metaphorical; can be purely atmospheric |
| Archival-style documents or data (in soft focus or post-overlay) | Grounded; text must be soft or post-produced |

### Forbidden b-roll categories

| Forbidden | Reason |
|---|---|
| Futuristic AI cityscape | Cyberpunk; incompatible with universe |
| Holographic or floating UI | Physically impossible; AI cliché |
| Generic stock-photo professionals (posed, smiling) | Indistinguishable from a thousand other channels |
| Close-up of AI-generated readable text | Garbled text failure; see §9 |
| Any environment that contradicts the universe | e.g., beach, gym, sci-fi lab |

### Text/screen policy (b-roll)
- See §9 for the full policy
- Default: screens and documents are out of focus, abstract, or not visible
- Required text uses post-production overlay, not in-scene generation

### B-roll failure conditions
- B-roll with generated garbled text prominently in focus
- Forbidden category used (futuristic, holographic, stock-photo-posed)
- B-roll audio baked in and not stripped for `generated_tts` segments
- B-roll constitutes 100% of a host-led episode

---

## 9. Text and Screen Policy

### Default rule
**No readable generated text in any AI video clip.** This is a hard default.

Generated video models cannot reliably produce legible, correctly-spelled text in a specific font. Attempting to generate text in-scene results in garbled characters that are immediately recognizable as AI-generated and destroy credibility.

### Allowed text cases

| Case | How to handle |
|---|---|
| Post-production kinetic text (Playfair Display / Inter per brand spec) | Added in `assemble.py` or post; never generated in the clip |
| Documents/books visible but out of focus | In-shot is acceptable if text is not legible |
| Whiteboard or notebook annotation (abstract / not readable) | Acceptable; must not be close enough to read |
| Lower-thirds (James Harrington / Leverage Mind) | Post-production only; never generated |

### Forbidden text cases

| Forbidden | Why |
|---|---|
| In-scene text that attempts to be readable | Will be garbled; instant credibility failure |
| Screens displaying legible content generated in the clip | Same |
| Book spines in focus with visible titles | AI cannot render legible text on spines reliably |
| Signs, presentations, or displays with readable content | Same |

### Failure conditions
- Garbled or semi-legible text is prominently visible in the center of frame
- Book titles, signs, or screens are close enough to read and contain malformed characters
- A visible screen shows AI-generated content attempting to be meaningful

---

## 10. Audio and Narration System

### Narration mode policy
- **Final videos: `continuous_voiceover`** — one narration file covers the entire episode; cuts are visual, not audio
- **Development/test: `segment_tts` is allowed** — but not for any video that will be published without a re-render
- Mixed-mode is not permitted in a final published video

### WPS guardrails
| Mode | Target range | Action |
|---|---|---|
| Calm premium narration | 2.2–2.6 wps | Pass |
| Energetic teaser | 2.6–3.0 wps | Pass |
| Below 2.0 wps | Any | Flag for review; usually a pacing error |
| Above 3.2 wps | Any | Flag for review; may be appropriate for short teaser bursts |

### Pause rules
- Pauses between sentences: 0.3–0.8s; natural speech rhythm
- Pause before a key idea: 0.5–1.5s; deliberate; can be left in the narration
- Pause longer than 3s: flag for review; likely a segment-mode gap artifact

### Tone and energy curve
- **Opening:** calm, direct, slightly elevated energy for hook
- **Middle:** measured; building case; unhurried
- **Close:** slightly lower energy; weight of conclusion; not energetic uplift

### B-roll audio contamination rule
- `generated_tts` segments: media file audio must be stripped (`ffmpeg -an`) before assembly
- Baked-in Higgsfield ambient audio may never be the final narration source
- This is enforced by `generate_media.py` and `assemble.py`; must also be a QA check

### Voice consistency
- ElevenLabs James Harrington voice settings are locked: speed 1.05, stability 50%, similarity 75%, style 12% — see `brand/BRAND_SPEC.md` §2
- Do not regenerate narration with altered settings without explicit approval and a version note

### Failure conditions
- Published video uses `segment_tts` mode and has audible inter-segment breaks
- B-roll ambient audio appears in the final mix as narration
- WPS is outside the 2.0–3.2 range without explicit approval
- Narration ElevenLabs settings were altered without a version note

---

## 11. Music and Sound Design

### Character
Understated cinematic bed. Present but not distracting. The narration is the spine; the music is the atmosphere.

### Allowed music register
- Slow, sparse piano or strings — simple, not complex
- Minimal ambient texture with warmth (not cold drone)
- Slightly uptempo in final third if the content builds toward a conclusion
- Original generated music (`generate_music.py`) or licensed royalty-free with confirmed commercial license

### Forbidden music
| Forbidden | Why |
|---|---|
| Corporate ukulele / positive-productivity pop | Wrong class; signals generic content |
| Epic trailer drums | Hype register; wrong for this channel |
| Motivational piano crescendo (Hans Zimmer-lite) | Overused; signals inspirational YouTube category |
| Music that competes with narration | Volume or melodic interest distracts from narration |
| Random generated clip audio passed through as music | Never; b-roll audio contamination |

### Mixing rules
- Music ducks to approximately -26 to -30 dB under narration (using loudnorm and MUSIC_BED_DB in `assemble.py`)
- Music is fully under narration; narration is never drowned
- The generated piano+violin bed from `scripts/tools/generate_music.py` is the current default
- Music fades in at episode open and fades out at close; not hard-cut

---

## 12. Editing Grammar

### Cuts
- Cuts happen at sentence boundaries or clause boundaries — not mid-sentence
- A cut should not interrupt a thought in progress unless the visual change is motivated by the narration
- The visual beat (the cut) and the audio beat (the clause/sentence break) should align within ±0.3s

### Shot duration
- A-roll (talking head): minimum 3s; typical 6–15s before cutting to b-roll or new angle
- B-roll: minimum 2s; typical 4–8s; a cut that comes too quickly reads as hyperactive
- Insert shots (close-up hands, pen, document): 2–4s; used for emphasis, not decoration

### Lipsync render minimum (Seedance 2.0 — hard floor)
- **Seedance 2.0 rejects any clip with `duration < 4s`** (API error: `duration: Input should be greater than or equal to 4`). A sub-4s `hero_lipsync` beat that reaches the renderer will hard-fail, then degrade to a `still_kenburns` — losing the talking head entirely.
- **Rule:** every `hero_lipsync` audio slice is padded so that `padded_len_sec = max(ceil(speech_len_sec + 0.200), min_clip_duration_sec)`, where `min_clip_duration_sec = 4` (see `constraints.json → lipsync_render_rules`). The 200 ms is the closed-mouth lead-in; the padding tail is room tone.
- If a beat's speech is so short that padding to 4s would feel like a held mouth, **merge it into an adjacent hero beat** as a `render_group` instead of rendering it alone.
- **Enforcement:** the pad floor is applied at compile (`compile_media_prompts.py`, T3 slicing). `generate_media.py` additionally clamps the `--duration` of any `hero_lipsync` render up to the minimum as defense-in-depth, so a stale or hand-edited plan can never send a sub-4s duration to the API.

### Hero lipsync reference angles (anti-monotony)
- Seedance composition **follows the reference image** — prompt-text angle changes ("three-quarter") do not materialize unless the reference FRAME is that angle.
- `hero_lipsync` beats must rotate across **≥3 approved canonical angle frames**, never all anchoring to one frame (that reproduces the failed001 visual repetition). Enforced by `compile_media_prompts.py` (round-robin, no two consecutive hero beats reuse the same frame; honors a beat's explicit `camera_angle_id`).
- The approved frame set is config-driven: `configs/james/model_routing.yaml → lipsync_references.active_set`. Registered frames are in `REFERENCE_ASSET_MANIFEST.md`.
- **Wardrobe + setting continuity is mandatory within an episode** — every frame in an `active_set` shares one wardrobe and one setting (James cannot change clothes between cuts). Do not mix wardrobes across hero beats of the same episode.
- If the desired wardrobe lacks ≥3 angle frames (gap G14), the compiler emits a warning; escalate for a small image-gen budget to fill the missing angles rather than mixing wardrobes.

### Clip output paths (single source of truth)- Every beat's `output_path` in `media_plan.json` is the **one canonical location** for that clip (e.g. `assets/media/{segment_id}/{beat_id}.mp4`).
- **Generation, technical QA, reuse-detection, and assembly all read `output_path`.** `generate_media.py` writes each clip to its beat's `output_path` (never a separate hardcoded `shots/` directory). If a beat lacks `output_path`, generation falls back to `assets/media/{project_id}/shots/{beat_id}.mp4`, but a compiled plan always carries `output_path`.
- Consequence: do not move or rename a generated clip without updating the beat's `output_path` (it would orphan the clip from QA + assembly).

### Continuity
- One continuous narration section may span multiple visual shots — this is normal and preferred
- The narration does not need to be interrupted to cut between studio angles or to b-roll
- The visual sequence should *illustrate* the narration, not attempt to *match* it word-for-word

### Scene evolution
- Shots must evolve through the episode — returning to the same angle repeatedly without purpose is lazy and visually flat
- An episode should use at minimum 3–4 different angles/environments
- The evolution should follow the narrative: wide → medium → close as a section builds; pull back when opening new territory

### Transition rules
- Cuts: default; preferred for clean narrative transitions
- Fade to black then fade in: acceptable between major sections or at the episode close
- Dissolves: acceptable but use sparingly; max 1 per episode unless deliberate
- No flashy transitions (swipe, spin, whoosh, glitch)

### Failure conditions
- A cut happens mid-sentence without narrative purpose
- The episode uses only one angle for the majority of its runtime
- Shot duration in A-roll averages below 3s (feels hyperactive for this register)
- Transition type is inconsistent with the episode's editorial register

---

## 13. Model and Media Generation Constraints

### Prompt source requirement
Once M5 (Storyboard) and M8 (Prompt Compiler) are implemented, **no media generation prompt may come directly from `visual_brief`**. All prompts must come from the compiled media prompt plan, which is derived from the storyboard and constrained by this Technical Bible and the Universe Bible.

*Exception: M3-era `generate_media.py` using `visual_brief` is preserved for backward compatibility and testing. Do not remove it. Do not use it for final episodes after M5/M8 are built.*

### Model assignment
| Scene type | Recommended model | Notes |
|---|---|---|
| A-roll / lipsync (James talking) | `seedance_2_0` (Seedance 2.0 Fast) | Requires approved James + studio reference images + final narration audio |
| B-roll grounded | `wan2_7` | Cheaper; text-to-video; must still follow constraints |

### Spend gate
No generation credits may be spent until the storyboard and media prompt plan have passed their respective review gates. This is a process rule, not just a QA note.

### Failure conditions
- Credits spent before the storyboard review passes
- A-roll generated without final approved narration
- Media prompt compiled directly from `visual_brief` after M5/M8 are deployed

---

## 14. LLM Calls via Kiro-CLI

Per `docs/plans/LLM_KIRO_CLI_INVOCATION_PLAN.md`, future programmatic LLM calls use Kiro-CLI as a subprocess. Model routing applies to all review and compilation tasks in this pipeline:

| Task type | Profile | Model |
|---|---|---|
| Creative/reasoning-heavy (storyboard gen/review, script review, prompt compile, brand compliance, audience review) | `sonnet_creative` | `claude-sonnet-4.5` |
| Mechanical/utility (JSON normalization, checklist pre-screen, report formatting) | `auto_utility` | `auto` |

**Policy:** `auto_utility` must never be the final approval gate for creative tasks (storyboard quality, media prompt plan approval, or final assembly sign-off). A Sonnet-class model must sign off on all creative gates.

Authorization: existing Kiro-CLI session. No API tokens in repo. No credential files read or printed.

---

## 15. Technical Failure Conditions (Canonical List)

The following are automatic fails at any QA gate. They block assembly or require regeneration.

| Failure | Category |
|---|---|
| `generated_tts` b-roll audio present in final mix | Audio contamination |
| James absent from host-led episode | Character |
| All-b-roll host-led video | Character/structure |
| Prominent garbled/AI-generated text in focus | Content |
| Cyberpunk / futuristic hologram visuals | Universe |
| Wrong James appearance (wardrobe, face, age) | Character |
| Wrong studio/library layout | Environment |
| Cat looks different from established reference | Continuity |
| Visible logo or copyrighted text | Legal |
| Major 9:16 crop failure (James's face cropped) | Framing |
| Abrupt audible break between narration segments in final | Audio |
| Scene content contradicts what narration is saying | Coherence |
| Random substitute presenter in A-roll position | Character |
| Neon / electric-glow lighting present | Visual |
| Unmotivated camera movement type (forbidden list) | Camera |
| Media generated without approved storyboard (after M5) | Process |
