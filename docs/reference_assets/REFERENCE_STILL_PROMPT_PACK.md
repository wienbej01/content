# Reference Still Prompt Pack

**Version:** 2.0 (expanded to 25 assets: 10 James + 12 Studio + 3 Cat)
**Date:** 2026-06-09
**Foundation:** 4 existing James images in `brand/` — use as Soul ID reference input for all James generations

> James is a **fictional character**. Not the channel operator.
>
> Every James generation must use at minimum `brand/James_harrington_front.png` as `--image` reference. Where possible, also include `brand/James_harrington_3_4.png`.
>
> Tool: Higgsfield CLI — `node node_modules/@higgsfield/cli/bin/higgsfield.js`
> Model for James (character-consistent): `text2image_soul_v2` (0.12 credits)
> Model for studio/environment: `flux_2` (1 credit) or `nano_banana_2` (2 credits)

---

## Default Negative Prompt (all images)

```
no futuristic holograms, no cyberpunk, no neon, no floating UI, no robots, no garbled text,
no readable generated text, no fake logos, no distorted hands, no uncanny valley faces,
no random smiling stock-photo people, no sci-fi setting, no overdesigned office,
no AI dashboard, no motivational poster energy, no seamless white backdrop,
no ring light, no colored gels, no visible brand logos, no heavy beard,
no glasses unless established, no age drift
```

---

## Section 1: James Reference Images

### JAMES_FRONT_DESK_001
**Foundation:** `brand/James_harrington_front.png` (existing — refine with Soul V2)
**Path:** `assets/reference/james/JAMES_FRONT_DESK_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "A 60-year-old British man, silver-grey hair neatly combed back, clean-shaven, sharp blue-grey eyes, warm but composed expression. Wearing a navy cashmere sweater over an open-collar white Oxford shirt. Seated at a dark wood desk in a warm private study. Floor-to-ceiling dark wood bookshelves in soft focus behind. Brass desk lamp casting warm golden light from the left. Camera: eye-level 85mm portrait lens equivalent, medium shot, chest-up, shallow depth of field. Composed, attentive expression. Hyperrealistic photography, 4K, natural skin texture with age detail. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### JAMES_THREE_QUARTER_STUDY_001
**Foundation:** `brand/James_harrington_3_4.png`
**Path:** `assets/reference/james/JAMES_THREE_QUARTER_STUDY_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, 3/4 angle turned slightly right, looking thoughtfully off-camera as if mid-thought. Same private study setting, warm lamp light. Navy cashmere sweater over white Oxford. Slight knowing expression — composed, not smiling broadly. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_3_4.png \
  --wait --json
```

---

### JAMES_SIDE_PROFILE_001
**Foundation:** `brand/James_harrington_side.png`
**Path:** `assets/reference/james/JAMES_SIDE_PROFILE_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, full side profile facing left, looking toward an implied window or slightly downward. Same private study. Warm lamp creates soft rim light from behind. Navy sweater. Composed bearing. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_side.png \
  --wait --json
```

---

### JAMES_VERTICAL_CLOSEUP_001
**Foundation:** `brand/James_harrington_vertical.png`
**Path:** `assets/reference/james/JAMES_VERTICAL_CLOSEUP_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, head and shoulders, facing camera directly. Dark navy background with soft warm key light from left. Navy cashmere sweater, open collar. Composed, direct expression. Slight eyebrow raise as if making a point. Hyperrealistic, 4K. 9:16 portrait." \
  --image brand/James_harrington_vertical.png \
  --wait --json
```

---

### JAMES_STANDING_LIBRARY_001
**Path:** `assets/reference/james/JAMES_STANDING_LIBRARY_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, standing upright near floor-to-ceiling dark wood bookshelves in his private library. Navy blazer over white Oxford shirt. 3/4 angle toward camera. Hands resting naturally or holding a closed book. Warm lamp light from the left. Books on shelf in soft focus — not readable. Composed, natural standing posture. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### JAMES_OVER_SHOULDER_WRITING_001
**Path:** `assets/reference/james/JAMES_OVER_SHOULDER_WRITING_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Over-the-shoulder view. James's back and shoulder in navy cashmere sweater visible in foreground. Dark leather notebook open on the desk, pen in right hand making an annotation. Warm brass lamp light on the desk surface. Same private study, dark wood desk. Camera slightly above, angled down at the desk. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### JAMES_DESK_THINKING_001
**Path:** `assets/reference/james/JAMES_DESK_THINKING_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, seated at dark wood desk, looking down or slightly off-camera with a pen held lightly in one hand. Thoughtful, absorbed expression — mid-consideration. Navy cashmere sweater, white Oxford. Lamp light warm from left. Bookshelves soft-focus behind. Not speaking, not performing. Quiet intellectual focus. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### JAMES_WALKING_HOME_LIBRARY_001
**Path:** `assets/reference/james/JAMES_WALKING_HOME_LIBRARY_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man in motion — slow, purposeful walk through his private library. Navy blazer over white Oxford. Slight 3/4 angle. Bookshelves and warm lamp visible in background. Unhurried gait, composed bearing. Not looking at camera. Warm ambient library light. Slight motion implied by composition. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### JAMES_CASUAL_HOME_OFFICE_001
**Path:** `assets/reference/james/JAMES_CASUAL_HOME_OFFICE_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, seated, slightly more relaxed but still elegant. Mid-grey fine-knit sweater over cream Oxford shirt, no blazer. Warm private study. Same composed demeanor — perhaps a touch more at ease, as if in a quiet morning working session. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### JAMES_FORMAL_DARK_JACKET_001
**Path:** `assets/reference/james/JAMES_FORMAL_DARK_JACKET_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man, seated, in a dark charcoal or near-black blazer over a white shirt, optional subtle pocket square. More formal register — serious, measured. Same private study. Composed expression with slightly more gravity than usual. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

## Section 2: Studio/Library Reference Images

> Studio images use `flux_2` (1 credit each) for pure environment shots, or `nano_banana_2` (2 credits) for higher fidelity.
>
> **Generate STUDIO_LIBRARY_WIDE_001 first. All other studio angles depend on it.**

### STUDIO_LIBRARY_WIDE_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_WIDE_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Wide establishing shot of a private executive library and home office. A substantial dark wood desk dominates the center-left. Dark wood bookshelves line the walls, filled with serious well-read books — not decorative. A directional brass desk lamp on the desk casts warm golden light. A dark leather upholstered chair behind the desk. A window to one side suggests warm morning or late-afternoon light. On the desk: a dark leather notebook, pen, a small stack of papers, a plain ceramic mug. Palette: deep navy, warm cream, dark wood, aged brass, leather, charcoal. No visible technology. No visible logos. Books in soft focus — spines not readable. Warm, restrained, intelligent atmosphere. Cinematic, hyperrealistic photography. 16:9." \
  --wait --json
```

---

### STUDIO_LIBRARY_MEDIUM_DESK_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_MEDIUM_DESK_001.png`
**Model:** `text2image_soul_v2` (James present) | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Medium shot, chest-up. 60-year-old British man in navy cashmere sweater seated at a dark wood desk. Eye-level 85mm-equivalent. Desk surface visible in lower frame: notebook, pen. Brass lamp glow from left. Dark bookshelves soft-focus behind. Same private library as wide reference. Composed expression, natural eye contact. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### STUDIO_LIBRARY_CLOSEUP_DESK_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_CLOSEUP_DESK_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Close-up of a dark wood desk surface in a warm private library. A dark leather notebook (closed or open with annotations), a pen, a small stack of printed documents with margin notes. A plain ceramic mug. Edge of a brass desk lamp casting warm light. No visible text readable. Warm palette. Shallow depth of field — background bookshelves very soft. Hyperrealistic, still life, 4K. 16:9." \
  --wait --json
```

---

### STUDIO_LIBRARY_OVER_SHOULDER_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_OVER_SHOULDER_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Over-the-shoulder camera angle in a private library. Same 60-year-old British man (back and right shoulder in navy sweater visible in foreground). Looking down at dark wood desk: open leather notebook, pen, papers. Brass lamp light. Same private study. Slightly high angle, static. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### STUDIO_LIBRARY_SIDE_PROFILE_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_SIDE_PROFILE_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Side angle of same 60-year-old British man seated at dark wood desk. Bookshelves behind him in soft focus. Brass lamp creates warm light from behind. Navy sweater. Looking slightly downward or toward an implied window. Composed side-profile. Same private library. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_side.png \
  --wait --json
```

---

### STUDIO_LIBRARY_STANDING_BOOKSHELF_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_STANDING_BOOKSHELF_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same 60-year-old British man in navy blazer, standing near floor-to-ceiling dark wood bookshelves in his private library. 3/4 angle. Holding a closed book or hands at sides. Warm lamp light. Books in soft focus — not readable. Same room as wide establishing shot. Composed, upright. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### STUDIO_LIBRARY_WINDOW_LIGHT_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_WINDOW_LIGHT_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Same private executive library. Late afternoon golden light streaming through a window on the left side. Warm amber and cream light falls across the desk surface and bookshelves. The room is empty of people — just the environment. Dust motes optional. Warm, contemplative, deeply private atmosphere. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

---

### STUDIO_LIBRARY_NIGHT_LAMP_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_NIGHT_LAMP_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Same private executive library in the evening. The brass desk lamp is the primary light source — warm gold circle of light on the desk surface, falling away into darkness. The window shows dark sky. Bookshelves recede into shadow. The room is intimate, focused, serious. No neon. No screens. Same furniture and layout as the daylight version. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

---

### STUDIO_LIBRARY_CAT_BACKGROUND_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_CAT_BACKGROUND_001.png`
**Model:** `text2image_soul_v2` | **Cost:** 0.12 credits
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create text2image_soul_v2 \
  --prompt "Same medium desk shot: 60-year-old British man in navy sweater at dark wood desk. Warm lamp light. In the deep background — on a dark chair or at the base of the bookshelf — a blue-grey British Shorthair cat is sleeping quietly. The cat is barely noticeable, deep background, low luminance, not facing camera, completely at rest. Hyperrealistic, 4K. 16:9." \
  --image brand/James_harrington_front.png \
  --wait --json
```

---

### STUDIO_LIBRARY_EMPTY_ROOM_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_EMPTY_ROOM_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Same private executive library — but empty of people. The dark wood desk, bookshelves, brass lamp, leather chair all present. Warm morning light. Leather notebook and pen on desk. The quality of the room without its occupant — still, intelligent, waiting. Same palette, same layout as the wide shot. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

---

### STUDIO_LIBRARY_READING_CHAIR_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_READING_CHAIR_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Corner of the same private library. A dark leather wingback or upholstered reading chair, slightly worn with use. A small side table with a plain lamp and a ceramic mug. An open book resting on the arm. Warm practical lamp light. Bookshelves visible in background. No person present. Quiet, intimate reading space. Same palette: dark wood, leather, cream, brass. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

---

### STUDIO_LIBRARY_BOOKSHELF_DETAIL_001
**Path:** `assets/reference/studio_library/STUDIO_LIBRARY_BOOKSHELF_DETAIL_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
**CLI:**
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Close-up of dark wood bookshelves in the private library. Books of varying heights, well-used, not decorative. Spines visible but blurred enough that titles are not readable — shallow depth of field. A small framed photograph or document on one shelf (not readable). Warm lamp light casting side shadows. No garbled AI text. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

---

## Section 3: Cat Reference Images

### CAT_LIBRARY_SLEEPING_001
**Path:** `assets/reference/cat/CAT_LIBRARY_SLEEPING_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "A blue-grey British Shorthair cat sleeping deeply on a dark leather or fabric chair in a warm private library. Compact, round-faced. Fur is solid blue-grey, dense and plush. Curled up, completely at rest, eyes closed. In the background: bookshelves, warm lamp light. The cat is in the background of the room, not the foreground. Quiet, domestic detail. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

### CAT_WINDOW_001
**Path:** `assets/reference/cat/CAT_WINDOW_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Same blue-grey British Shorthair cat, sitting quietly on a windowsill in the private library. Looking out the window — away from camera. Warm afternoon light on its fur. The room is visible in background: dark wood desk, bookshelves. The cat is calm, self-contained. Hyperrealistic, 4K. 16:9." \
  --wait --json
```

### CAT_BOOKSHELF_BACKGROUND_001
**Path:** `assets/reference/cat/CAT_BOOKSHELF_BACKGROUND_001.png`
**Model:** `flux_2` | **Cost:** 1 credit
```bash
node node_modules/@higgsfield/cli/bin/higgsfield.js generate create flux_2 \
  --prompt "Same blue-grey British Shorthair cat, settled on the floor near the base of dark wood bookshelves in the private library. Relaxed posture — sitting or lightly resting. Barely visible in the background. Books above, lamp light from one side. The cat is a minor detail, not a focal point. Hyperrealistic, 4K. 16:9." \
  --wait --json
```
