# Execution Plan — Flagship_001 Remediation (Post-Mortem Response)

**Author:** Principal AI Video Engineer (technical lead)
**Date:** 2026-06-13
**Source:** `post_mortem_flagship_001.md`
**Status:** PLAN — no code written yet; no generation spend until all tickets land + tests green.
**Validation target:** A **3-minute SHORT** (`video_type: short`, budget cap $25), NOT a full 12–15 min flagship. We prove the perfected pipeline cheaply before committing flagship render spend.

---

## 0. The central architectural decision (resolve before any ticket)

The post-mortem's audio fix (§2C) **contradicts the lipsync work we shipped (T8)**, and the conflict must be resolved deliberately, not silently:

- **T8 (current):** hero_lipsync spans keep their **baked Seedance audio** (`-map 0:a`) for mouth-sync; voiceover spans overlay narration. → perfect mouth sync, but audio EQ/compression shifts at every A-roll↔B-roll boundary (the §2C complaint).
- **§2C (post-mortem):** mute **all** clips (`-an`); lay one continuous ElevenLabs master MP3; snap video to timing-map timestamps. → consistent audio everywhere, but mouth sync depends on the video being time-aligned to the master.

**Resolution — adopt §2C as the FINAL-PUBLISH path, with a hard precondition:**
The audio slices are cut FROM the master ElevenLabs file. So the master track and each slice are the *same speech at the same timestamps*. If a lipsync clip is (a) rendered to the exact slice it was given and (b) placed at that slice's master timestamp, the mouth matches the master audio — and we get consistent audio quality. This is what `TECHNICAL_BIBLE §10` already mandates ("finals must be continuous_voiceover").

**The precondition that makes it true:** a lipsync clip's video duration must equal its slice's speech duration — **no clamping that changes speech rate**. Our current `min(padded,10)` clamp on >10s beats (B047/B086/B090) breaks this: Seedance compresses 15s of speech into 10s, so the mouth drifts from the 15s master span. **Long beats must be SPLIT at compile into ≤10s lipsync beats, never clamped.** That moves the fix upstream to `compile_media_prompts.py` + `storyboard.py`.

This single decision reorders the whole plan: **fix the audio architecture first (it is the root cause of 2C AND the lipsync desync), then layer QA detection on top.**

---

## 1. Architecture Adjustments

### 1.1 Audio: single continuous master track (final-publish mode)
- **Data flow change:** `assemble.py` final renders use `narration_mode: continuous_voiceover`. One ElevenLabs master MP3 per video is the sole audio source. All video clips are muted (`-an`). Music bed mixes under the master. Loudnorm runs once over the whole track → zero EQ/compression shifts.
- **Timing map is now mandatory.** `tts.py` already emits `timing_map.json` (beat_id → [start,end] in the master). `compile_media_prompts.py` writes each beat's master timestamp. `assemble.py` snaps each muted clip to its `[start,end]` window.
- **Lipsync clips are no longer "audio carriers" — they are time-locked visuals.** The mouth matches because the clip was rendered to the slice = that master span. The T8 baked-audio path is retained ONLY for a `segment_tts` debug mode, never for finals.

### 1.2 Long-speech beats: split, never clamp
- A `hero_lipsync` beat whose speech > `LIPSYNC_MAX_DUR` (10s) is **split at compile** into N consecutive ≤10s lipsync beats (each with its own contiguous slice + a distinct reference angle), forming a render group. No beat is ever sent to Seedance with audio longer than its requested duration. This kills the B047/B086/B090 desync class entirely.

### 1.3 QA becomes content-aware, not just structural
- `qa_media.py` gains **perceptual** checks (the post-mortem's core demand): blank-screen detection (histogram/`signalstats`), frozen-video detection (`freezedetect` / first-vs-last SSIM), and audio-presence already exists. These are FATAL at Gate 8. No clip with zero visual variance or zero motion reaches assembly.

### 1.4 Script QA gains a deterministic pre-filter
- `review_script.py` runs a **cheap deterministic N-gram/repetition scan BEFORE the expensive LLM personas**. Machine stutter ("Read it. Sketch it. … Read it. Sketch it.") fails the gate instantly and triggers a re-roll — no LLM spend on obviously broken scripts.

### 1.5 Storyboard structural failsafe
- `storyboard.py` enforces the MITmonk shot-mix bands as a **hard floor at routing time**: if the routed storyboard lacks graphics/UI (≥10%) or kinetic text (2–8%) or an Act-1 hook, it fails the parse (or injects required local-graphic beats) rather than emitting a monotonous A-roll/desk-B-roll plan.

---

## 2. Implementation Tickets (prioritized, file-by-file)

> Priority: **P0 = blocks correct output**, P1 = quality gate, P2 = polish. All tickets are JSON-I/O, no orchestrator, gate-enforced. Each ticket lists tests (see §3).

### TICKET R1 — `scripts/qa_media.py` — Blank-screen + frozen-video detection [P0]
**Post-mortem §1A, §1B.** Add two perceptual checks to `lipsync_checks()` and the general per-unit loop:
- **R1a Blank/solid-color (all clips):** run `ffmpeg -i clip -vf signalstats -f null -` and parse per-frame `YDIF`/luma stddev, OR sample N frames and compute luma histogram spread. If mean luma stddev < threshold (near-solid frame) across the clip → FATAL `BLANK_SCREEN`. Also run `blackdetect`; any black span > 0.5s → FATAL.
- **R1b Frozen video (hero + generated video):** `freezedetect=n=0.003:d=0.5` → if a freeze span ≥ 50% of clip duration → FATAL `FROZEN_VIDEO`. Cross-check with SSIM between first and last frame: SSIM > 0.985 (near-identical) on a clip that should move → FATAL.
- **R1c** Make `--scope source` run these on every generated clip; thresholds in `constraints.json → qa_thresholds` (configurable, not hardcoded).
- **Wiring:** these are added to the existing `entry["issues"]` mechanism (any issue = fail). Gate G8 already blocks assembly on fail.
- **Files:** `scripts/qa_media.py` (+ `constraints.json` thresholds).

### TICKET R2 — `scripts/assemble.py` — Continuous master-audio assembly [P0]
**Post-mortem §2C + architecture §1.1.** This is the biggest change.
- **R2a** Make `continuous_voiceover` the default for `assemble.py` finals. Mute all video (`-an`); build the visual timeline by placing each clip at its `timing_map` `[start,end]`; lay the single master MP3; mix music under; loudnorm once.
- **R2b** Retain the current per-shot baked-audio path behind an explicit `--debug-segment-audio` flag only (never for finals). Update the existing continuous-path guard (line ~686) so it no longer refuses keep_lipsync — instead it IGNORES baked audio and trusts the timing map.
- **R2c** Snap-to-timestamp: if a clip is shorter than its `[start,end]` window, hold last frame (≤ MAX_FREEZE) or extend via the next clip; if longer, trim. No silent gaps, no double audio (single track), boundaries are inaudible (one continuous master).
- **R2d** Manifest builder (`tts.py` / the manifest used by assemble) writes `narration_mode: continuous_voiceover`, `continuous_audio`, `timing_map`, and per-clip `[start,end]`.
- **Files:** `scripts/assemble.py`, `scripts/tts.py` (manifest fields).

### TICKET R3 — `scripts/compile_media_prompts.py` + `scripts/storyboard.py` — Split long lipsync beats [P0]
**Architecture §1.2.** Depends on R2 (timing-locked assembly).
- **R3a (storyboard.py):** when chunking, a hero_lipsync beat whose estimated speech > `LIPSYNC_MAX_DUR` is split into N sub-beats at sentence boundaries (existing `split_hero_block` already does ≤15s; lower the hero target to ≤10s and make it config-driven from `lipsync_render_rules.max_clip_duration_sec`).
- **R3b (compile_media_prompts.py):** remove the render-time clamp reliance; assert at compile that no `hero_lipsync` beat's `padded_len_sec > max_clip_duration_sec`. If found → compile FAIL naming the beats (forces a storyboard re-split). Each sub-beat gets a distinct reference angle (existing rotation) + its own contiguous slice.
- **Files:** `scripts/storyboard.py`, `scripts/compile_media_prompts.py`.

### TICKET R4 — `scripts/review_script.py` — Deterministic stutter pre-filter [P1]
**Post-mortem §2A.** Before any LLM persona call in `run_review()`:
- **R4a** Add `detect_repetition(script_text)`: tokenize, compute repeated-N-gram ratio (3-gram and 5-gram), and detect adjacent-sentence near-duplicates (normalized Levenshtein > 0.9). If repeated-N-gram ratio > threshold (e.g. 12%) or any sentence repeats verbatim within a 5-sentence window → return a hard `blocking_issue` and SKIP the LLM personas (no spend).
- **R4b** Emit the structured reviewer JSON with `status: fail`, `blocking_issues: ["machine repetition detected: …"]` so the gate logic treats it like a failed persona. Record the gate as fail; trigger a re-roll upstream.
- **Files:** `scripts/review_script.py` (+ threshold in `constraints.json → qa_thresholds.max_ngram_repetition`).

### TICKET R5 — `docs/channel_universe/constraints.json` — Text/gibberish negatives [P1]
**Post-mortem §2B.** Strengthen `default_negative_constraints` and `b_roll_rules`:
- **R5a** Add to negatives: `no writing, no handwriting, no text on pages, no reading documents, no books with visible text, no charts with labels, no whiteboards with writing, no spreadsheets, no captions, no subtitles`.
- **R5b** Add `b_roll_rules.content_must_be: ["conceptual","observational","metaphorical"]` and `b_roll_rules.forbid_text_surfaces: true`. The existing `text-surface risk terms` in `generate_media.py` should hard-reject (not just flag) a b-roll prompt containing writing/reading verbs in source scope.
- **Files:** `docs/channel_universe/constraints.json` (+ enforce in `compile_media_prompts.py` vagueness/text lint).

### TICKET R6 — `configs/llm_models.yaml` — Anti-loop generation params [P1]
**Post-mortem §2A root cause.** The Sonnet loop produced the stutter.
- **R6a** Add per-profile generation guardrails to `sonnet_creative`: document a `frequency_penalty`/`presence_penalty` equivalent or an explicit "no verbatim repetition" instruction injected by `llm_call.py` into creative prompts. Since kiro-cli may not expose sampling params, the enforceable lever is (a) the R4 deterministic re-roll and (b) a prompt-level anti-repetition directive. Encode that directive in the profile config so it's applied uniformly.
- **R6b** Add `max_reroll_attempts: 2` to the creative profile; after 2 stutter re-rolls, escalate to human (Telegram) rather than burning tokens.
- **Files:** `configs/llm_models.yaml` (+ `llm_call.py` reads the directive).

### TICKET R7 — `scripts/storyboard.py` — Shot-mix structural failsafe [P1]
**Post-mortem §3B.** After routing, before returning the storyboard:
- **R7a** Compute the realized shot mix from the routed beats. If `graphics_ui_pct < 10` → inject the minimum required `graphic_progressive`/`ui_insert` beats at natural framework points (we already do this for Act-3 master-map; generalize it). If `kinetic_text_pct < 2` → inject kinetic beats on quantified/stat sentences. If Act-1 has no hook beat → FAIL parse.
- **R7b** If injection can't satisfy a band (e.g. no framework content to map) → FAIL the storyboard parse with a named reason, forcing storyboard regeneration rather than shipping a monotonous plan.
- **Files:** `scripts/storyboard.py` (+ `review_storyboard.py` already blocks on bands — keep as the backstop).

### TICKET R8 — `scripts/qa_media.py` + `compile_media_prompts.py` — Reference-frame lock enforcement [P2]
**Post-mortem §3A.** Wardrobe/character hallucination.
- **R8a (compile):** assert every `hero_lipsync` beat's `reference_images[0]` is in the active `lipsync_references` set; reject otherwise (already mostly done by `assign_lipsync_references` — add the assertion).
- **R8b (qa):** we cannot verify wardrobe from pixels deterministically, but we CAN verify the beat USED an approved canonical reference (provenance in `media_generation_log.json`). Flag any hero clip whose generation log shows a reference not in the active set. Wardrobe/identity drift beyond that is a HUMAN canary check (already a gate).
- **Files:** `scripts/compile_media_prompts.py`, `scripts/qa_media.py`.

### TICKET R9 — `short` video-type mode (3-min validation target) [P0 for validation]
**User directive.** Before any flagship spend, prove the pipeline on a cheap 3-min short.
- **R9a** `short` video_type already exists (budget cap $25). Add a `short` profile to `storyboard.py`: target runtime ~180s, ~6–8 beats, still MITmonk-shaped (hook → 1 framework → CTA), hero ≤25% bands honored, ≥1 graphic.
- **R9b** A short has ~2–3 hero_lipsync beats (each ≤10s) → ~$3–5 render, well under the $25 cap. This is the gated dry-run target: compile → review → dry-run → canary (1 clip) → full short render → QA → assemble → human review. Only after a CLEAN short do we authorize a flagship.
- **Files:** `scripts/storyboard.py` (short profile), no new gate logic (reuses all gates with cap=short).

---

## 3. Testing Strategy (validate before spending)

All tests run in `pytest` with **ffmpeg-generated fixtures** — zero Higgsfield/ElevenLabs spend. Target: full suite green (currently 247) + the new tests below, before ANY generation.

### 3.1 QA perceptual tests (`tests/test_qa_media.py`)
- `test_blank_screen_fatal`: synthesize a solid off-white clip (`color=c=0xFAFAF0`) → QA FATAL `BLANK_SCREEN`.
- `test_frozen_video_fatal`: synthesize a 6s clip that is one held frame (loop a single image) → FATAL `FROZEN_VIDEO`.
- `test_moving_video_passes`: synthesize a clip with motion (`testsrc2`/zoompan) → passes the motion check.
- `test_blank_threshold_configurable`: thresholds read from `constraints.json`, not hardcoded.
- Negative controls: a real-motion fixture must NOT trip the freeze/blank checks (no false positives).

### 3.2 Continuous-audio assembly tests (`tests/test_assemble.py`)
- `test_continuous_master_single_audio_track`: assemble a 3-beat fixture in continuous mode → probe output: exactly ONE audio stream, duration == master, no per-clip audio.
- `test_no_audio_eq_shift`: tone-marked master (single 440Hz tone) over muted video clips → probe shows uniform tone across A-roll↔B-roll boundary (no level/spectral jump). Mechanically: band energy at 440Hz is constant ±3dB across boundaries.
- `test_clip_snapped_to_timing_map`: a clip whose source is shorter than its window holds last frame; longer is trimmed; no silent gap.
- `test_finals_ignore_baked_audio`: a lipsync clip with baked audio assembled in continuous mode contributes NO audio (master only).

### 3.3 Long-beat split tests (`tests/test_storyboard.py`, `tests/test_compile_media_prompts.py`)
- `test_hero_beat_over_max_is_split`: a 15s-speech hero beat → routed into ≥2 ≤10s sub-beats.
- `test_compile_rejects_overlong_lipsync`: a hand-built plan with padded_len 16 → compile FAIL naming the beat (no clamp).
- `test_split_beats_get_distinct_angles`: split sub-beats rotate references (no consecutive repeat).

### 3.4 Script stutter pre-filter (`tests/test_review_script.py`)
- `test_repetition_detected_skips_llm`: a script with "Read it. Sketch it. Explain it aloud." ×3 → `detect_repetition` returns blocking; LLM personas NOT called (assert llm_call stubbed, 0 calls).
- `test_clean_script_passes_prefilter`: a clean script passes the N-gram check and proceeds to (stubbed) personas.

### 3.5 Text-negative + shot-mix failsafe
- `test_broll_with_writing_rejected` (`test_compile_media_prompts.py`): a b-roll prompt containing "writing"/"reading document" → compile reject.
- `test_storyboard_injects_graphics` (`tests/test_storyboard.py`): a script routed with 0% graphics → failsafe injects graphic beats OR fails parse.
- `test_short_profile_shape` (`tests/test_storyboard.py`): `video_type=short` → ~6–8 beats, ~180s, ≥1 graphic, hero ≤25%.

### 3.6 Gate-order regression
- Re-run full suite (247 + ~18 new ≈ 265). Confirm no `--force-unsafe`, gates still SHA-bound, render_approval still human-gated. Confirm a dry-run of the SHORT plan reports est ≤ $5 with zero API calls.

### 3.7 Spend-gated rollout (after green)
1. Build a `short` storyboard → review (R4 + personas) → compile → review_media_plan → budget (≤$25) → dry-run.
2. Human approves render → **canary: 1 hero clip (~$1.10)** → human verifies motion + sync + wardrobe.
3. Full short render (~$3–5) → `qa_media --scope source` (R1 perceptual checks must pass) → assemble (R2 continuous) → human final review.
4. Only on a clean short do we authorize flagship spend.

---

## 4. Sequencing

```
R2 (continuous audio) ─┐
R3 (split long beats) ─┼─→ R1 (perceptual QA) ─→ R7/R5/R4/R6 (content gates) ─→ R8 (ref lock)
R9 (short mode) ───────┘                                                          ↓
                                                          TEST GREEN → short dry-run → canary → short render
```
R2 + R3 are the root-cause fixes (audio architecture + desync) and must land first. R1 is the safety net that would have caught the slop. R9 is the cheap validation vehicle. R4–R8 are quality gates layered on a correct foundation.

## 5. Definition of done
- Full pytest green (≈265 tests), including all new perceptual + continuous-audio + split-beat + stutter tests.
- A 3-min SHORT renders end-to-end: zero blank screens, zero frozen lipsyncs (R1 enforced), one continuous audio track (R2), no >10s lipsync beats (R3), no text-surface b-roll (R5), MITmonk-shaped with ≥10% graphics (R7), no script stutter (R4).
- Human canary + final review pass on the short.
- Spend for the validation short ≤ $25 (cap), realistically ~$3–5.
- Flagship render is authorized ONLY after the short passes.
