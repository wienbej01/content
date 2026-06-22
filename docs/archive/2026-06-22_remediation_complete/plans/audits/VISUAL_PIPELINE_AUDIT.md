# Visual Pipeline Audit — Root Causes of AI-Slop Output

**Date:** 2026-06-13
**Trigger:** poc_short_focus 56s cut rejected as AI slop.
**Scope:** Visual layer only (audio is approved). Report → grounds the storyboard-LLM rebuild.

## How a beat becomes a clip today

```
script → storyboard.py:route() [deterministic shot-typing + chunking]
       → storyboard.py:llm_refine() [OPTIONAL --optimize: rewrites visual_brief]
       → compile_media_prompts.py:_compose_positive() [wraps brief + ident + framing + palette]
       → generate_media.py:_generate_beat_clip() [seedance hero / kling b-roll]
       → assemble (continuous master, muted clips) + render_graphics overlays
```

## Root causes (ranked), each mapped to the gap

| # | Slop symptom | Root cause | Where |
|---|--------------|------------|-------|
| 1 | **Anachronism (1800s man for a 2008 study)** | The storyboard LLM (`llm_refine`) is fed ONLY `constraints.json` + the beat's narration. It never sees UNIVERSE_BIBLE, TECHNICAL_BIBLE, FORBIDDEN_PATTERNS, PROMPT_RULES, the source research text, or the era/setting. No anachronism/modern-professional enforcement exists anywhere. | `storyboard.py:llm_refine()` (~1004); nothing reads the bibles |
| 2 | **Hero lip-sync lag / static** | Continuous-master architecture: hero clip rendered to a slice of length L, but placed in a master span of different length (B001 7.08s clip vs 5.97s span = 1.1s mismatch). Mouth drifts; clip runs out → frozen-still look. | `R2` continuous assembly; slice padding in `slice_continuous_lipsync.py` / `compile` |
| 3 | **Generic / disconnected b-roll** | `llm_refine` has no source text or bible grounding, so "specificity" is shallow; b-roll not tied to the actual research content or the channel's visual grammar. | `storyboard.py:llm_refine()` prompt |
| 4 | **Static full-screen graphic cards** ("high-school slide") | `render_graphics.py` makes full-frame cards; no side-by-side speaker+graphics composition. No TED-style integrated layout. | `render_graphics.py`; assembly |
| 5 | **Lighting/character discontinuity between shots** | No seed-lock / continuity carry-over between beats; each clip generated independently. | `generate_media.py` (no seed param threaded) |
| 6 | **Frozen / robotic motion** | Static cards + clips shorter than spans held/padded; no motion-injection (handheld/breathing). | assembly; `generate_media.py` |
| 7 | **Hand warping / uncanny** | Raw model-quality limit (Kling/Seedance) — mitigated by better prompts + curation, not eliminable. | model limit |
| 8 | **B-roll too long (single 13s clip)** | One clip stretched over a long narration span instead of multi-shot coverage. | `storyboard.py` chunking |

## Bibles/context the storyboard LLM SHOULD receive but currently does NOT
(all exist in `docs/channel_universe/`, ~2,780 lines total)
- `UNIVERSE_BIBLE.md` (195) — the bounded world, era, setting, tone
- `TECHNICAL_BIBLE.md` (507) — production grammar, shot rules, model routing, durations
- `FORBIDDEN_PATTERNS.md` (206) — anti-patterns incl. anachronism, text, slop
- `PROMPT_RULES.md` (275) — how to write a compliant prompt
- `JAMES_CHARACTER_BIBLE.md` (231) — James's exact look/age/wardrobe/behavior
- `JAMES_RECORDING_STUDIO_LIBRARY.md` (297) — the canonical setting (desk, shelves, lamp)
- `PEOPLE_AND_EXTRAS_BIBLE.md` (108) — no real public figures; how extras appear
- `REFERENCE_ASSET_MANIFEST.md` (133) — approved reference frames
- `QA_RUBRIC.md` (223) — the bar each beat must hit
- `constraints.json` (318) — machine-readable bands, negatives, render rules
- **THE SOURCE RESEARCH TEXT** (e.g. `/home/jacobw/chi08-mark.pdf` / research brief) — so b-roll depicts the ACTUAL content, era, and subjects accurately

## The fix the owner directed
Build a **specialized storyboard LLM stage** that is fed ALL the above + the approved script, and produces a **bulletproof, elaborate storyboard**: every hero shot, b-roll, and graphic fully specified (subject, action, era, setting, camera, continuity, reference frame, motion, graphic layout) and pre-validated against the bibles (anachronism guard, character lock, forbidden-pattern check). With a fully-resolved storyboard, downstream generation + compile + assembly become deterministic.
