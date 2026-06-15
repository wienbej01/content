# Audio System — Approved Recipe (V2 Chunk-and-Stitch)

**Status:** APPROVED 2026-06-13 ("I LOVE IT!"). This is the production audio architecture.
**Validated on:** poc_short_focus (`narration/continuous_APPROVED.mp3`).

## The winning architecture

**CHUNK-AND-STITCH V2 — dynamic emotion + deterministic pacing.**

1. **Few, large LOGICAL blocks (3-5).** Group connected sentences so the model reads
   ahead and preserves the emotional ARC. (Isolating every sentence → flat/PowerPoint.)
2. **Native `<break time="Xs"/>` tags INSIDE blocks** for pacing. The model carries
   pitch/intensity across the break (no pitch reset).
3. **Per-block dynamic voice settings** (the key to non-flat delivery):

   | Block type | stability | style | feel |
   |-----------|-----------|-------|------|
   | intro_hook | 0.40 | 0.20 | intriguing, mysterious |
   | factual_data | 0.65 | 0.0 | crisp, authoritative scientist |
   | the_climax | 0.35 | 0.30 | grave, emotional turn |
   | the_punchline | 0.45 | 0.15 | impassioned but controlled |

4. **Small `pause_ms` (200-500ms) between blocks** — most pacing is internal breaks.
5. Identical voice + model per block → consistent timbre, no seam.

## Verified lessons (hard-won, encoded in code)

- **No phonetic misspellings** (`lee ss` → broke tokens). Keep words intact.
- **Short ALL-CAPS words can garble** ("LESS" → "L-E-S-S") at high style; safe at low/locked
  style. `_sanitize_block_text` keeps caps; the single-call path guards short caps → quotes.
- **`<break>` tags distort prosody in single-call mode** (drag prior word, rush next) — but
  work correctly inside V2 grouped blocks at clause boundaries.
- **List-trap:** a comma-list ending before a paragraph break makes the voice DRAG the last
  item. Fix = em-dash bridge (auto-applied by `_sanitize_tts`).
- **Per-phrase WPS outliers** auto-corrected by `normalize_pacing.py` (the "burn the fuel"
  4.0-WPS rush). Over-long pauses auto-trimmed.
- **Single global style is wrong** — emotion must vary per block.

## Where it lives (code)

- `scripts/optimize_script.py` — LLM emits V2 `tts_blocks` (type, text+breaks, per-block
  stability/style, pause_ms) + key_points for downstream emphasis. Deterministic fallback.
- `scripts/tts.py:generate_chunked` — renders each block with its own settings + native
  breaks, stitches with exact silence.
- `scripts/normalize_pacing.py` — safety net: WPS + pause normalization.
- `scripts/emphasis_pause.py` — clean silence-gap pauses.

## To produce a new video's audio
```
python3 scripts/optimize_script.py <raw_script.json> --output <enriched.json>
python3 scripts/tts.py <enriched.json>   # chunk-and-stitch auto-runs from tts_blocks
```
Per-block tuning (if ever needed) is a single number change in `tts_blocks` — deterministic.
