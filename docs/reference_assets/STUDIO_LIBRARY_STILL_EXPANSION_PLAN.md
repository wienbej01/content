# Studio/Library Still Expansion Plan

**Version:** 1.0 | **Date:** 2026-06-09

---

## Design Intent: James' Private Home Office / Library

This is not a generic studio. It is a private room that has accumulated over 35 years — James's actual working space, where he reads, annotates, thinks, and occasionally records. The room should feel:

- **Exclusive:** private, not shared; not open-plan; not corporate
- **Warm:** amber and gold lamp light; cream and dark wood; leather and brass
- **Lived-in:** books are read, not decorative; documents have margin notes; the lamp is there because the room needs it
- **Premium without performing it:** no status symbols, no visible brands, no flashy objects; the taste is evident in what is absent
- **Intelligent:** the bookshelves suggest decades of serious reading; the desk is a working surface

---

## Master-Room Principle

All 12 stills are different angles or moments from **the same room**. Any image showing a different layout, different furniture, or different architecture fails the studio continuity rule.

`STUDIO_LIBRARY_WIDE_001` is generated first and becomes the spatial anchor for everything else. If Wide_001 looks wrong, stop and regenerate before creating any other angles.

---

## The 12 Canonical Studio/Library Stills

| # | Asset ID | Description | James? | Priority |
|---|---|---|---|---|
| 1 | STUDIO_LIBRARY_WIDE_001 | Full room establishing shot | Optional | **FIRST — spatial anchor** |
| 2 | STUDIO_LIBRARY_MEDIUM_DESK_001 | Default A-roll; James seated, chest-up | Yes | Primary |
| 3 | STUDIO_LIBRARY_CLOSEUP_DESK_001 | Desk details: notebook, pen, lamp, papers, coffee | No | Secondary |
| 4 | STUDIO_LIBRARY_OVER_SHOULDER_001 | OTS; James reviewing notes, desk surface | James (back) | Secondary |
| 5 | STUDIO_LIBRARY_SIDE_PROFILE_001 | Side angle; James seated, bookcases behind | Yes | Secondary |
| 6 | STUDIO_LIBRARY_STANDING_BOOKSHELF_001 | James standing near bookshelf, 3/4 | Yes | Secondary |
| 7 | STUDIO_LIBRARY_WINDOW_LIGHT_001 | Late-afternoon warm side light through window | Optional | Fallback |
| 8 | STUDIO_LIBRARY_NIGHT_LAMP_001 | Evening; lamp as primary source; introspective tone | Optional | Fallback |
| 9 | STUDIO_LIBRARY_CAT_BACKGROUND_001 | Standard desk angle; cat quietly in deep background | Yes + cat | Fallback |
| 10 | STUDIO_LIBRARY_EMPTY_ROOM_001 | Room without James; pure environment | No | Secondary |
| 11 | STUDIO_LIBRARY_READING_CHAIR_001 | Leather reading chair + side lamp + open book | Optional | Fallback |
| 12 | STUDIO_LIBRARY_BOOKSHELF_DETAIL_001 | Close-up books/shelf/objects; no readable text in focus | No | Fallback |

---

## Room Spec (for every generation prompt)

**Mandatory elements in all studio images:**
- Dark wood desk (substantial; not glass, not standing)
- Floor-to-ceiling or substantial dark wood bookshelves
- Books: mixed, serious, not uniform; spines NOT readable/garbled
- Directional brass desk lamp (warm, from the left)
- Dark leather or upholstered chair
- Implied window (warm side/back light; morning or late afternoon)
- Leather notebook, pen, papers visible (on desk when in frame)
- Palette: deep navy, warm cream, dark wood, aged brass, leather, charcoal, muted sage

**Forbidden in all studio images:**
- Futuristic monitors or screens unless explicitly off/turned away
- Neon lighting
- Visible logos
- Garbled book spine text in focus
- White seamless backdrop
- Corporate open-plan look
- Floating UI or ambient glow
- Messy clutter (selective purposeful clutter only)
- Random room redesign

---

## Cat Integration Policy

The cat appears only in `STUDIO_LIBRARY_CAT_BACKGROUND_001`. Rules:
- British Shorthair blue-grey, sleeping or sitting quietly
- Deep background only — at least 2/3 of the depth behind James
- Occupies <5% of the frame area
- Lower luminance than the foreground
- Not looking at camera
- Not interacting with James or objects
