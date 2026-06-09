# Universe Bible — The James Channel World

**Version:** 1.0
**Status:** Active
**See also:** `brand/BRAND_SPEC.md` (brand identity source of truth), `JAMES_CHARACTER_BIBLE.md`, `JAMES_RECORDING_STUDIO_LIBRARY.md`

---

## 1. Purpose of the Universe

The Leverage Mind channel exists to translate professional and intellectual leverage — how to learn faster, think more clearly, manage complexity, and use AI effectively — into applied frameworks for ambitious professionals.

The channel is not motivational. It does not sell aspiration. It delivers systems that compound. Every piece of content should feel like it came from someone who has spent decades inside institutions, understood how they actually work, and now has the freedom to share what was never said out loud.

James Harrington is the channel's anchor. The universe is built around his world: his study, his way of thinking, his accumulated experience. The viewer is invited in; they are not being sold at.

### Host-led episode — definition

**Every episode is host-led by default.** A host-led episode is one in which James Harrington is the intellectual anchor and the viewer's primary reason to watch. James must be visually present in a meaningful portion of the episode (see `TECHNICAL_BIBLE.md` §7 for measurable thresholds).

**An episode is non-host-led only if the storyboard explicitly sets `allow_all_broll: true`.** This flag overrides the James-presence requirement and must carry a written justification. It is an exception, not a default — and it must never be used to avoid the effort of generating James's appearance.

This definition is machine-readable in `constraints.json` (`host_led_default: true`).

---

## 2. Audience World

The primary audience is mid-career professionals — founders, executives, senior individual contributors — aged approximately 30–50, with household income above $90k. They are time-poor, analytically oriented, and skeptical of general motivational content. They have likely been disappointed by productivity influencers and are looking for something that respects their intelligence.

The universe should feel like content they would not be embarrassed to watch at work or recommend to a colleague. It should feel earned, not performed.

Secondary audience: technically capable professionals (ages 25–45) who are already using AI tools and want the adjacent frameworks — how to learn, decide, and operate at a higher level.

**The viewer's contract:** they are watching because they believe James has done something genuinely hard, understood something non-obvious, and will share it without wasting their time.

---

## 3. Emotional Tone

The channel's emotional register is calm authority. Not intimidating. Not warm-fuzzy. Not hip. The feeling should be: sitting with someone who has thought about this more carefully than anyone else in the room, and who takes your questions seriously.

**The universe should feel:**
- Premium without being luxurious
- Calm without being slow or passive
- Credible without being cold
- Elegant without being decorative
- Grounded in physical reality (real rooms, real objects, real light)
- Quietly aspirational — the viewer can imagine belonging to this world
- Intelligent without being condescending
- Businesslike without being corporate

**The universe must not feel:**
- Cyberpunk or neon AI startup
- Futuristic or sci-fi
- Motivational guru or life-coach adjacent
- Fake luxury or conspicuous display
- Flashy or high-energy
- Generic corporate stock footage
- Overproduced or trailer-bombastic
- Productivity influencer (rapid-fire, excitable, optimized-for-dopamine)
- Sterile or joyless

---

## 4. Recurring World Elements

### Permanent elements
- **James Harrington** — the presenter, thinker, and anchor. See `JAMES_CHARACTER_BIBLE.md`.
- **The studio/library** — his primary recording and working space. See `JAMES_RECORDING_STUDIO_LIBRARY.md`.
- **The background cat** — an occasional humanizing presence. See `BACKGROUND_CAT_BIBLE.md`.

### Recurring objects
These objects may appear across episodes. Their presence reinforces the universe's identity:
- A well-used leather notebook (unbranded, dark)
- A fountain or ballpoint pen
- Physical books — dense, serious, not decorative coffee-table books
- A printed document with margin annotations
- A modest analogue desk clock
- A warm table lamp (brass or matte black, directional)
- A glass of water or a plain ceramic mug (not branded, not a travel tumbler)
- A laptop (not prominently branded; screen not visible unless post-produced)

### Recurring visual motifs
- Warm lamp light creating directional shadows on a desk or shelf
- A hand holding a pen poised over paper
- Book spines in soft focus (not readable unless deliberately post-produced)
- A slow push toward a document or notebook
- The camera settling on James mid-thought
- The quality of late-morning or late-afternoon window light

---

## 5. Allowed Environments

Environments must be consistent with James's life and work. All environments should feel real, lived-in, and purposeful — not staged.

### Primary
| Environment | ID | Description |
|---|---|---|
| Studio/library | `ENV_STUDIO_LIBRARY` | Fixed recording space. See `JAMES_RECORDING_STUDIO_LIBRARY.md`. |
| Private study | `ENV_PRIVATE_STUDY` | A smaller, similar working space. Same aesthetic as the studio. Warm, wood, books, lamp. |

### Allowed secondary environments (occasional, intentional use)
| Environment | ID | When to use |
|---|---|---|
| Quiet professional common area | `ENV_PROFESSIONAL_COMMON` | B-roll of thinking/working/commuting. No prominent faces. |
| City exterior — established financial district | `ENV_CITY_EXTERIOR` | Establishing shots or metaphorical b-roll. Morning or late afternoon only. |
| Hotel or conference-quality workspace | `ENV_TRAVEL_WORKSPACE` | If content involves travel or a specific setting. Must retain the warm neutral palette. |
| Archive or bookshop | `ENV_ARCHIVE_BOOKSHOP` | If content involves research, history, long-form reading. |

---

## 6. Forbidden Environments

These environments are incompatible with the universe. Their appearance is a generation failure.

| Forbidden | Why |
|---|---|
| Open-plan tech startup office (exposed ceiling, primary colors, bean bags) | Wrong class, wrong energy |
| Cyberpunk cityscape or neon-lit street | Sci-fi, wrong decade, wrong world |
| AI research lab or server room | Too on-the-nose; implies "AI future" cliché |
| Corporate glass-tower conference room | Generic, cold, implies hierarchy over insight |
| Generic stock-footage boardroom | Indistinguishable from thousands of other videos |
| Beach, mountains, or outdoor inspiration setting | Belongs to the wellness/travel genre, not this one |
| Overlit white studio with seamless backdrop | Looks like a product shoot; no warmth |
| Futuristic workspace with floating screens or ambient glows | Sci-fi, ungrounded |
| Any setting that looks generated or artificial | Breaks the credibility contract |

---

## 7. Allowed Motifs

- Hands writing in a notebook or on paper
- A page being turned (physical book or document)
- A pen tapping slowly while thinking
- Warm lamp light against dark wood
- Close-up of a document with margin notes (no readable text required or preferred)
- A slow camera movement through a quiet professional space
- City light trails at dawn (not neon; long-exposure, motion blur)
- Books on shelves (soft focus, not readable)
- An empty chair in a quiet study
- The cat, briefly, in the background

---

## 8. Forbidden Motifs

- Glowing holographic data dashboards
- Neon or electric blue/purple ambient lighting
- Floating UI elements, AR interfaces, or gesture-controlled screens
- Abstract AI neural-network visualizations
- Robot hands, robot bodies, or humanoid machines
- Garbled or unreadable generated text that appears to be meaningful
- Stock-photo people in generic "professional" poses (forced smile, handshake, thumbs-up)
- Extreme close-ups of eyes or faces used for drama
- Explosion, lightning, or fast-cut motivational montage
- Confetti or celebration effects
- Visible brand logos on any product
- Any text readable in-frame, unless it is deliberately placed in post-production

---

## 9. Continuity Rules

The following must remain consistent across every episode:

1. **James looks the same.** Age, hair, build, wardrobe palette. If a new Higgsfield session is required, it must use the approved reference assets. See `REFERENCE_ASSET_MANIFEST.md`.
2. **The studio/library is the same room.** Same furniture, same background, same light. See `JAMES_RECORDING_STUDIO_LIBRARY.md`.
3. **The cat, if used, looks the same.** Same breed impression, same fur, same disposition. See `BACKGROUND_CAT_BIBLE.md`.
4. **The palette and mood are consistent.** Warm neutrals, controlled contrast, no sudden shifts to cool/neon/bright. (Technical detail in `TECHNICAL_BIBLE.md`.)
5. **James's voice and tone are consistent.** RP accent, calm, unhurried, evidence-led. ElevenLabs settings are locked. See `brand/BRAND_SPEC.md` §2.

---

## 10. Universe Failure Conditions

Any of the following constitutes a universe failure and should block generation or assembly:

| Failure | Category |
|---|---|
| James is absent from a host-led episode | Character |
| James looks significantly different from established reference | Character |
| The studio/library has been redesigned | Environment |
| A forbidden environment is used | Environment |
| A forbidden motif is present | Motif |
| Prominent garbled or generated text is visible | Content |
| A visible brand logo is present | Content |
| The cat looks different from the established reference | Continuity |
| The cat behaves like a gimmick rather than a background presence | Continuity |
| An unplanned human figure becomes the visual focus | Character |
| The overall look feels like generic motivational content | Tone |
| The overall look feels futuristic or sci-fi | Tone |

See `FORBIDDEN_PATTERNS.md` for detailed detection guidance and `QA_RUBRIC.md` (Sprint M4.2) for the scoring system.
