# Forbidden Patterns

**Version:** 1.0
**Status:** Active
**See also:** `UNIVERSE_BIBLE.md`, `JAMES_CHARACTER_BIBLE.md`, `QA_RUBRIC.md` (Sprint M4.2)

This document lists explicit universe failures — patterns that break the creative world of the James channel. For each pattern, it explains why it fails, how to detect it, and what to use instead.

These are not style preferences. They are generation failures that must be caught by QA before any clip enters assembly.

---

## 1. All-B-Roll Host-Led Episode

**Description:** An episode where James never appears, or appears only incidentally, while generic b-roll narrates the entire video.

**Why it fails:** The viewer's contract is with James. An all-b-roll episode could come from any faceless channel. It has no credibility anchor, no intellectual personality, and no reason to subscribe. The channel's competitive advantage is the character — removing the character removes the advantage.

**How to detect:**
- `james_presence: absent` on more than **60% of non-transition/title beats** in a host-led storyboard (beat-count method per `TECHNICAL_BIBLE.md` §7).
- No beat has `james_presence: present_speaking` or `present_silent`.

**Preferred replacement:** Ensure the storyboard has A-roll James-present beats at the episode open, at each major framework point, and at the close. B-roll supports the argument between James's on-screen moments.

---

## 2. No James Presence

**Description:** A video in which James does not appear at all — not in A-roll, not in the background, not implied through his space.

**Why it fails:** Same as above, but more severe. See also: Forbidden Patterns #1.

**How to detect:** No beat has `james_presence: present_speaking` or `present_silent` and no studio-library angle appears.

**Preferred replacement:** At minimum, James-present voiceover scene (James at desk, working, while narration plays) to anchor identity in the episode.

---

## 3. Futuristic AI City

**Description:** Cityscape or environment featuring neon, holographic signage, floating vehicles, or any visual language associated with sci-fi futures.

**Why it fails:** Incompatible with the universe's grounded, present-tense, credible register. It signals "AI startup YouTube" — the exact category the channel is differentiating from.

**How to detect:**
- Frame contains neon or electric-color ambient light from architecture.
- Frame contains holographic or floating text or UI.
- Architecture style is visually futuristic (glass megastructures, flying vehicles, ring cities).

**Preferred replacement:** A real financial-district exterior at dawn — long-exposure light trails from vehicles and pedestrians. Classical architecture. Morning blue-grey sky. Motion blur. No neon.

---

## 4. Glowing Hologram Productivity Dashboard

**Description:** A floating, glowing, three-dimensional UI panel showing productivity metrics, task lists, calendars, or abstract data — visualized as if projected into the air.

**Why it fails:** This is the single most overused AI-generated "AI productivity" visual. It signals low-effort content instantly. It is also physically impossible and therefore anti-credible.

**How to detect:** A floating transparent screen or glowing panel is visible. Charts or lists are suspended in air without a physical display.

**Preferred replacement:** A real laptop or printed document showing a structured framework (text not readable). Or James annotating a real notebook. Or a whiteboard diagram in soft focus.

---

## 5. Unreadable Text on Screens or Documents

**Description:** Screens, documents, or signs in frame contain garbled, illegible, or AI-generated pseudo-text that looks like it should be readable but is not.

**Why it fails:** It is immediately recognizable as AI-generated. It breaks the credibility of the scene. It reads as careless.

**How to detect:** Text in frame is close enough to be read but does not form coherent words or sentences. Characters are malformed or inconsistent.

**Preferred replacement:** Keep text elements out of focus (use shallow depth of field so documents are visible but not readable). Or use post-production overlays for any text that must be legible. Mark shots with `text_policy: post_overlay` in the storyboard.

---

## 6. Random Business People Replacing James

**Description:** B-roll that features a confident, forward-facing professional who is not James — styled as if they could be the host — appearing in locations that should be James's world.

**Why it fails:** Creates visual ambiguity about who the host is. Undermines the character. Also typically reads as stock-footage, which breaks authenticity.

**How to detect:** A person is visible in a studio or desk environment, facing camera or near-camera, with enough screen time that a viewer might think they are the presenter.

**Preferred replacement:** If James cannot be generated for a shot, use environment b-roll without people (desk, books, lamp, window). Or use over-shoulder or partial-body inserts where no face is the subject.

---

## 7. Generic Motivational Stock Footage

**Description:** Footage that would be at home in a corporate training video or motivational keynote — generic professionals shaking hands, people on mountain peaks looking determined, sunrise with inspirational light.

**Why it fails:** Instantly identifies the video as generic content. Violates the tone of the universe. The James channel does not sell aspiration through imagery.

**How to detect:** The footage looks like it was purchased from Getty Images without art direction. The emotional register is "inspirational" rather than "credible." People are performing emotions.

**Preferred replacement:** Grounded, specific, purposeful imagery — James's desk, a financial district in realistic morning light, close-up of an annotated document. The test: would this footage feel at home in a long-form journalism piece? If yes, it probably belongs.

---

## 8. Disconnected Scene Style

**Description:** Each clip in the video was generated with a different visual style, lighting, color grade, or spatial logic, making the episode feel like a compilation of unrelated footage.

**Why it fails:** The universe has visual continuity. When each scene has a different look, the viewer loses the sense of a consistent world. The episode feels assembled, not authored.

**How to detect:** Lighting color temperature changes significantly between clips. Color grade shifts noticeably. Camera language switches from slow/formal to fast/handheld without narrative reason.

**Preferred replacement:** All prompts must go through the prompt compiler which injects universe and technical constraints. Studio shots must use the same established angle IDs. Technical Bible (Sprint M4.2) defines the allowed visual grammar.

---

## 9. Random Camera Language

**Description:** Camera moves that are inconsistent with the universe's visual grammar — aggressive zooms, spinning drone shots, handheld shaking, impossible perspective shifts.

**Why it fails:** Camera language creates emotional register. The James channel's grammar is slow, deliberate, composed. Aggressive camera work signals a different genre.

**How to detect:** A cut uses a fast zoom or crash-zoom. The camera spins around the subject. The shot is visibly handheld and unsettled without narrative reason. Indoor drone footage.

**Preferred replacement:** Slow dolly in, locked-off medium, slow push-in, or static shot. See Technical Bible (Sprint M4.2) for the camera vocabulary.

---

## 10. Random Room Layout (Studio Redesign)

**Description:** The studio/library in a generated clip has different furniture, a different desk position, a different bookshelf layout, or a different overall spatial logic.

**Why it fails:** The studio is a continuity anchor. When it changes, the viewer loses the sense that James exists in a consistent world. The brand integrity depends on a consistent space.

**How to detect:** Compare the studio layout to `STUDIO_LIBRARY_WIDE_001` reference. If the desk is in a different position, the bookshelf is missing or repositioned, or the room dimensions appear significantly different, it is a failure.

**Preferred replacement:** Regenerate using the approved studio reference images. Always use an approved angle ID and the corresponding reference asset.

---

## 11. Random Wardrobe

**Description:** James is wearing something inconsistent with his canonical wardrobe — wrong color, wrong register, visible logo, or a style that belongs to a different character type.

**Why it fails:** Wardrobe is part of visual identity. An inconsistency signals a different person, which breaks the consistency contract.

**How to detect:** James is not in navy/charcoal/cream. James is wearing something with a visible logo. James is in a suit and tie. James is in casual wear.

**Preferred replacement:** Regenerate with explicit wardrobe specification in the prompt: "navy cashmere sweater over open-collar white Oxford shirt." Include the reference asset.

---

## 12. Random Cat Appearance

**Description:** A cat appears in the background that does not match the established reference — different color, different build, different behavior.

**Why it fails:** The cat is a continuity element. A different cat is a different cat. It also suggests the generation was not using reference assets.

**How to detect:** The cat's fur is not blue-grey. The cat's build is not compact and round-faced. The cat is tabby, orange, or white.

**Preferred replacement:** Either omit the cat (always acceptable) or regenerate the scene using the approved cat reference assets. Do not include a cat in any prompt unless you have high confidence it will match.

---

## 13. Dramatic Trailer Lighting

**Description:** Harsh, high-contrast, over-dramatic lighting — typically a strong single spotlight on James against darkness, or colored rim lighting.

**Why it fails:** This is the lighting of action films and hype content. The James channel uses soft, directional, warm, practical-looking light. Drama comes from ideas, not from lighting effects.

**How to detect:** Strong artificial rim light. Colored light (any color other than warm white/amber). Extreme contrast with blown-out highlights or crushed blacks. Single hard spotlight.

**Preferred replacement:** Soft warm side light, desk lamp as practical, natural window light. See Technical Bible (Sprint M4.2).

---

## 14. AI-Generated Garbled Text in Focus

**Description:** Any text in the frame that is in focus and close enough to read but is AI-generated noise — garbled characters, inconsistent letterforms, words that are almost-but-not-quite legible.

**Why it fails:** The most immediately recognizable sign of AI-generated content. Destroys credibility in one frame.

**How to detect:** Text element is in the center third of the frame at a scale where it would normally be readable, but upon inspection is garbled.

**Preferred replacement:** Ensure all text elements are either: (a) out of focus, (b) not in frame, or (c) marked as `text_policy: post_overlay` and replaced in post-production.

---

## 15. Corporate Slideshow Look

**Description:** The episode looks like a business presentation — animated pie charts, infographics, stock business photography, PowerPoint aesthetics.

**Why it fails:** Signals generic corporate content. No credibility, no character, no visual intelligence.

**How to detect:** The footage looks like it was produced by a company's marketing department. Infographic animations. Grid of photos. Corporate conference room backgrounds.

**Preferred replacement:** Real environments, real objects, real work. If data or frameworks need to be illustrated, use post-production kinetic text (Playfair Display, navy/gold) over a clean background — not AI-generated infographics.

---

## 16. Visible Brand Logos

**Description:** Any visible brand logo — on clothing, on products, on buildings, on documents, on screens.

**Why it fails:** Legal exposure. Also makes the content feel accidentally product-placed.

**How to detect:** Any logo visible and legible in the frame.

**Preferred replacement:** Avoid branded items in prompts. In studio shots, ensure all props are generic. If a screen is visible, ensure it is off or the display is not legible. If a product must appear, choose an unbranded or generic alternative.
