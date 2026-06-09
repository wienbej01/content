# James Recording Studio/Library — Set Bible

**Version:** 2.0 — CANONICAL LOCK (derived from actual reference frames)
**Status:** Active — LOCKED
**Last updated:** 2026-06-09
**See also:** `JAMES_CHARACTER_BIBLE.md`, `REFERENCE_ASSET_MANIFEST.md`

---

## ⚠ KNOWN INCONSISTENCY IN TEASER_02

The James teaser_02 clips contain two incompatible studio environments:
- **Segments 001, 003, 007, 008** — off-white/cream painted built-in bookshelves, brass adjustable-arm task lamp
- **Segments 005** — dark walnut wood bookshelves, traditional table lamp with fabric shade, darker ambient

**These are NOT the same room and must not appear in the same production without editorial justification.**

**The canonical environment going forward is defined below.** All new flagship videos must use the canonical spec. When teaser segments are regenerated, they must match this spec.

## ✅ APPROVED CANONICAL REFERENCE FRAMES (2026-06-09)

Both frames below were reviewed and approved by the founder as canonical:

| ID | File | Source | Use |
|---|---|---|---|
| STUDIO_CANONICAL_001_HOOK_FRAME | `assets/reference/studio_library/canonical/STUDIO_CANONICAL_001_HOOK_FRAME.jpg` | teaser_02 segment 001 | Hero shots, 001_hook angle |
| STUDIO_CANONICAL_003_PATTERN_FRAME | `assets/reference/studio_library/canonical/STUDIO_CANONICAL_003_PATTERN_FRAME.jpg` | teaser_02 segment 003 | All standard talking-head shots |

**These are the reference images to pass to Higgsfield (`--image` flag) for all future lipsync generation.**

---

## 1. CANONICAL ROOM IDENTITY

The James recording space is a private study or executive library — his actual working room. It has accumulated over time. Every element is functional, not decorative.

---

## 2. CANONICAL SPATIAL SPEC (PIXEL-EXACT)

### Walls
- **Colour:** Off-white / warm cream — approximately #F2EDE4. NOT pure white, not grey, not dark.
- **Material:** Plain painted plaster or subtle eggshell finish. No wallpaper, no panelling.
- **Visible walls in standard shots:** Left side wall (partially), back wall (behind bookshelf).

### Bookshelves
- **Style:** Built-in floor-to-ceiling shelves with simple painted-wood framework. Pilasters between shelf bays are visible as vertical dividers.
- **Colour:** Same off-white/cream as walls — the shelves are BUILT IN and PAINTED to match. NOT dark wood, NOT stained.
- **Books:** Mixed heights and spines. Predominantly warm tones — tan, ochre, dark red, navy, forest green, with some faded cloth spines. NOT uniform. NOT decorative.
- **Lower section:** Some bays have closed-panel cabinet doors at the base (dark pulls, simple hardware).
- **Framed artwork:** ONE small framed print or document, centre-back wall, positioned above and between bookshelf bays. Light/neutral tones, not prominent.
- **Location:** Bookshelf occupies the ENTIRE BACK WALL as seen from the standard camera position.

### Desk
- **Style:** Traditional dark-stained hardwood. Rectangular. Solid construction with panel detailing on the front face. NOT glass, NOT light wood, NOT modern.
- **Colour:** Deep mahogany/walnut — dark reddish-brown (#3B1F0F range).
- **Surface items (standard):** Open notebook (dark cover, cream pages), pen resting on page, one ceramic mug (plain, matte grey or dark).
- **Desk mat:** Optional — dark leather rectangle.

### Chair
- **Style:** Traditional upholstered wingback or barrel-back. NOT ergonomic. NOT mesh.
- **Colour:** Deep navy or dark leather. Must NOT be brown leather (that is the 005 variant — inconsistent with canonical).

### Lamp — PRIMARY (CANONICAL)
- **Type:** Adjustable-arm task lamp — classic "banker's lamp" or articulated studio arm style.
- **Finish:** Aged brass / antique gold. NOT matte black. NOT chrome.
- **Shade:** Brass dome or shallow brass reflector bowl — open underneath, directional warm light.
- **Position:** LEFT side of desk, angled to provide side-lighting across the desk surface. Arm extended toward desk centre.
- **Height:** Lamp head approximately at James's mid-chest level when seated.
- **Light quality:** Warm amber pool of light on desk surface. Visible glow. NOT diffuse. NOT ring-light fill.

### Second lamp (FORBIDDEN)
- A second small green-enamel adjustable lamp was visible in some teaser clips. **This is not part of the canonical set.** Only ONE desk lamp is present.

### Window
- **Position:** RIGHT side of frame, partially visible or implied.
- **Style:** Traditional multi-pane sash window. Wood frame, warm-toned.
- **Light:** Soft warm natural light — late morning or late afternoon quality. NOT harsh midday. NOT blue-toned.
- **Curtains/blinds:** NOT present in standard shots, or implied at the edge of frame.

### Floor
- NOT visible in standard medium shots.

### Room atmosphere
- Warm, intimate, slightly dim ambient — the desk lamp provides the key light, the window provides fill.
- Overall colour temperature: warm (~3200K–3800K feel).
- No overhead lighting visible.
- No coloured lights, no neon, no practical monitors glowing.

---

## 3. WARDROBE CANONICAL (LOCKED)

Based on observed clips:
- **Primary:** Navy cashmere crew-neck sweater over white Oxford shirt (collar open, visible at neck). This is the default for all standard episodes.
- **Secondary:** Same sweater with a navy blazer added over it. Use for more formal segments or the hook/intro if higher authority register is required.
- **Forbidden:** Any other wardrobe combination without explicit approval.

---

## 4. APPROVED CAMERA ANGLES

All angles belong to the **same room with the same canonical layout above.**

### STUDIO_LIBRARY_MEDIUM_DESK_001 ← DEFAULT
**Framing:** Chest-up. James at desk, desk surface partially visible below. Lamp visible in left foreground or left frame edge. Bookshelf fills background, off-white with mixed books. Framed print visible above James's left shoulder.
**Use:** Default for all speaking segments.
**9:16 crop:** James centered; bookshelf occupies left and right edges of background.

### STUDIO_LIBRARY_CLOSEUP_001
**Framing:** Shoulders-up. Bookshelf reduced to soft out-of-focus background. Lamp barely visible or off-frame.
**Use:** Key insight delivery; emphasis moments.
**9:16 crop:** Fully center-safe.

### STUDIO_LIBRARY_WIDE_001
**Framing:** Full establishing. Desk in foreground, James seated, entire back-wall bookshelf visible. Window right.
**Use:** Episode openings only.
**9:16 crop:** James must be left-of-center; bookshelf right-of-center must remain.

### STUDIO_LIBRARY_SIDE_PROFILE_001
**Framing:** Side profile, James looking toward window. Lamp provides rim light on left. Bookshelf background.
**Use:** Voiceover / thinking transition shots.

### STUDIO_LIBRARY_OVER_SHOULDER_001
**Framing:** Behind James looking down at desk. Notebook/document in near foreground.
**Use:** Insert b-roll; reading/working shots.

---

## 5. TIME-OF-DAY LOOKS

| Look | Description | Use |
|---|---|---|
| Late morning (DEFAULT) | Warm, balanced natural light from right window. Desk lamp on. | All standard episodes. |
| Late afternoon | Warmer, slightly lower angle. Desk lamp dominant. More amber cast. | Reflective content. |
| Evening (rare) | Desk lamp only. Window dark. Intimate. | Use sparingly. |

---

## 6. GENERATION PROMPT FRAGMENT (copy-paste into every lipsync brief)

```
The room is James Harrington's private study. Off-white/cream painted built-in bookshelves fill the entire back wall, floor to ceiling, with books in mixed warm-toned spines (tan, ochre, navy, dark red). ONE adjustable-arm brass desk lamp with a dome reflector on the LEFT side of the desk provides a warm directional pool of light. A traditional multi-pane sash window is visible on the RIGHT. The desk is dark mahogany. There is one small framed print on the wall above the bookshelf. Walls are off-white painted plaster. Warm ambient, approximately 3400K, no coloured lights, no overhead lighting visible, no second lamp, no screens.
```

---

## 7. FAILURE CONDITIONS

| Observed failure | Correct |
|---|---|
| Dark walnut bookshelves (seen in 005_give_back) | Off-white painted built-ins |
| Traditional table lamp with fabric shade (seen in 005_give_back) | Brass adjustable-arm task lamp, dome reflector |
| Two lamps visible (seen in 003_pattern) | One lamp only |
| Brown leather chair | Navy or dark chair |
| Futuristic monitor on desk | No monitors in standard shots |
| Wallpaper or wood panelling | Plain painted plaster |
| Cold or blue ambient | Warm amber |
| Corporate office proportions | Private study — intimate scale |


---

## 1. Room Identity

The James recording space is a private study or executive library. It is his workspace — the room where he thinks, reads, annotates, and records. It is not a designed studio. It is a real room that happens to be where he works.

The room has accumulated over time. The books are read, not decorative. The desk is used. The lamp is there because the room needs it, not for effect. There is no production crew present; this is his own space.

---

## 2. Spatial Layout (Canonical)

The room is approximately the size of a private home study or a corner office in a good building. It is:

- **Depth:** enough for a bookshelf behind James to be out of focus when he is at the desk, but present and identifiable.
- **Width:** enough for James to stand near the bookshelf without being cramped.
- **Ceiling:** not visible in most shots. If visible, it is plain plaster or modest wood panelling — no exposed ducts, no drop ceilings.

### Key furniture and fixtures

| Element | Description |
|---|---|
| Desk | A substantial dark wood desk. Not a standing desk. Not a glass-topped desk. Functional surface with papers, notebook, pen, possibly an open book. No monitor in standard shots unless the content requires it. |
| Chair | Dark leather or dark fabric. Not ergonomic mesh. Either a traditional upholstered armchair or a solid desk chair with arms. |
| Bookshelves | Floor-to-ceiling or substantial wall-height. Dark wood. Mixed books — professional and literary. Not uniform. Spines are not readable in focus unless intentionally post-produced. No purely decorative objects; a few real items: a small clock, a framed document, perhaps a plant in a dark pot. |
| Lamp | A directional desk lamp. Brass, matte black, or dark bronze. Warm light. Positioned to create controlled side-lighting on the desk surface and on James. Not a ring light. Not overhead. |
| Window/light source | A window implied but not always in frame. Warm natural light (morning or late afternoon feel). When visible, gives a soft depth cue. Curtains or blinds, if present, are dark or neutral — no bright white sheers. |
| Floor | Wood or dark rug. Not visible in most shots. If visible, it is plain. |

### What is on the desk in a standard shot
- Leather notebook (unbranded, dark, partially open or closed)
- A pen
- One or two physical documents (printed, with possible annotations — not readable)
- Possibly an open book
- A plain ceramic mug or glass of water

### What is NOT on the desk in a standard shot
- A visible laptop screen (unless content requires; screen must be off or post-produced)
- A phone
- A tablet propped up
- Multiple monitors
- Branded items
- Cups with corporate logos

---

## 3. Approved Camera Angles

All angles belong to the **same room with the same layout**. There is one studio. There are seven approved ways to film it.

### STUDIO_LIBRARY_WIDE_001
**Description:** Full establishing shot of the room. James seated or standing; desk in foreground; bookshelf in background. James occupies the left-to-center frame; bookshelf creates depth behind and to the right.
**Use:** Episode openings; context establishment; returning from a long b-roll sequence.
**James position:** Seated at desk, or standing slightly left of center.
**9:16 crop safety:** James must be centered or slightly left-of-center; bookshelf background must remain partially visible in the crop.

### STUDIO_LIBRARY_MEDIUM_DESK_001
**Description:** Medium shot, chest-up. James at the desk, desk surface visible in the lower portion of frame. Lamp glow visible. Bookshelf out of focus in the background.
**Use:** Default talking-head and voiceover-present shot for most episodes.
**James position:** Seated. Slight angle (3/4) or direct facing camera.
**9:16 crop safety:** Center-safe. James head and shoulders must be within the center 56% of frame width.

### STUDIO_LIBRARY_CLOSEUP_001
**Description:** Close-up. Shoulders-up. Background reduced to soft bokeh.
**Use:** Emphasis; key insight delivery; intimate moments in narration.
**James position:** Seated or leaning forward. Direct eye contact or slight 3/4.
**9:16 crop safety:** Fully center-safe by definition.

### STUDIO_LIBRARY_OVER_SHOULDER_001
**Description:** Behind-and-above-James, looking over his shoulder down toward the desk surface. Notebook, document, or pen visible in near foreground.
**Use:** Insert-style b-roll; illustrating that James is working or reviewing; pair with narration that references reading, analysis, or revision.
**James position:** Seated, slightly forward.
**9:16 crop safety:** Desk surface is the primary subject; James's shoulder/back of head in frame. Crop must retain the work surface.

### STUDIO_LIBRARY_SIDE_PROFILE_001
**Description:** Side profile. James looking out toward an implied window or looking down at a book. Lamp provides rim light. Bookshelf visible in background.
**Use:** Thinking/transition moments. Voiceover b-roll where James is present but not addressing camera.
**James position:** Seated or standing at the bookshelf.
**9:16 crop safety:** Profile face should be center or right-of-center; bookshelf behind to create depth.

### STUDIO_LIBRARY_STANDING_BOOKSHELF_001
**Description:** James standing near or examining the bookshelf. Could be retrieving a book or simply standing in the space.
**Use:** Voiceover b-roll; transitional shots; establishing the room as a working space.
**James position:** Standing, slightly facing the shelf or turned 3/4 toward camera.
**9:16 crop safety:** James center-of-frame or slightly offset; bookshelf must be present.

### STUDIO_LIBRARY_CAT_BACKGROUND_001
**Description:** Standard medium or medium-close shot of James, with the cat visible in the deep background — typically on a chair, near the base of the bookshelf, or on a windowsill. The cat is visible but not prominent.
**Use:** Rare; when the cat appears. Background must match the studio layout exactly.
**James position:** Foreground; cat is background.
**9:16 crop safety:** James center; cat may fall outside the crop and that is acceptable.

---

## 4. Time-of-Day Looks

| Look | Description | Use |
|---|---|---|
| Late morning | Warm, slightly diffuse natural light from the window. Desk lamp may or may not be on. Balanced and clear. | Standard for most episodes. |
| Late afternoon | Warmer, slightly lower light angle. Desk lamp almost certainly on. Golden hue to the ambient. | Reflective episodes; retrospective content. |
| Evening (rare) | Desk lamp primary source. Window dark or near-dark. Intimate, focused. | Use sparingly; creates an introspective register. |

**Forbidden:** Harsh midday overlit looks. Blue-hour or dawn cold light. Any neon or colored supplemental light. Strobe effects.

---

## 5. Forbidden Changes

The following must not change between videos:

- Desk position, orientation, or style
- Chair type or position
- Bookshelf location, color, and general fill
- Lamp position and style
- Wall color and surface
- Overall warmth and light direction
- The spatial relationship between desk, bookshelf, and window

If a new generation session produces a studio that differs from established reference images, it must be regenerated before use.

---

## 6. Studio Failure Conditions

| Failure | Category |
|---|---|
| Room has a different desk or chair | Layout |
| Bookshelf is absent, repositioned, or redesigned | Layout |
| Futuristic monitors or screens visible | Environment |
| Neon or colored lighting present | Lighting |
| Floating UI or ambient glow visible | Environment |
| Room proportions suggest a corporate office, not a private study | Identity |
| Background is seamless or clearly artificial | Generation |
| Book spines contain readable AI-generated text prominently in frame | Content |
| Visible brand logos on any object | Content |
| Room layout is inconsistent with any other approved angle | Continuity |
