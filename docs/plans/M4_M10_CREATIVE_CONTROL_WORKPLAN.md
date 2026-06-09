# M4–M10 Creative Control Work Plan

**Author:** Architecture/planning run (Opus-class)
**Date:** 2026-06-09
**Status:** Planning only — no code, no media, no API calls, no credits spent
**Repo:** /home/jacobw/YTchannel
**Environment rule:** use `python3`, not `python`
**Governing architecture:** `strategy/ARCHITECTURE_MVP.md` (MVP-simple; no n8n / provider abstraction / DB / state machine / dashboard / CI unless pain justifies)

> This plan defines M4–M10. It does not implement them. Implementation is done later, one sprint at a time, by cheaper coding models using the prompts in §11 and `docs/plans/M4_M10_IMPLEMENTATION_PROMPTS.md`.

---

## 1. Executive Summary

**Why M3 worked technically but failed creatively.** The M1–M3 pipeline is sound: `assemble.py` (timing, WPS alignment, gap-concat, 16:9+9:16), `tts.py` (ElevenLabs narration → manifest), and `generate_media.py` (Higgsfield b-roll, audio stripped for `generated_tts`) all do exactly what they were built to do. The smoke test proved a clip can be generated, audio-policed, and assembled end-to-end. But the full teaser looked like AI slop: all b-roll, no James, broken continuity, futuristic generic visuals, gibberish on-screen text, and each clip independently "directed" by the video model.

**Why this is not a prompt-tuning problem.** Tweaking individual `visual_brief` strings cannot fix it because the *architecture* lets each clip invent its own world. The pipeline jumps `script → visual_brief → video prompt → clip` with no shared creative state between clips. Eight prompts produce eight unrelated micro-films. No amount of per-prompt wording enforces a consistent room, a consistent James, a consistent palette, or a coherent A-roll/B-roll rhythm. The missing thing is a **bounded creative universe** and a **production grammar** that every prompt is compiled against.

**Why the next layer is a bounded creative universe + technical production grammar.** We introduce two control layers *before* media generation:
- A **Universe Bible** (what exists: James, the study/library, the cat, extras, motifs, what's forbidden).
- A **Technical Bible** (how it's filmed: color, lighting, camera, framing, audio, editing, prompt rules).
Then a **storyboard** plans A-roll/B-roll beats, a **reviewer** gates quality, **continuous narration** fixes the audible breaks, a **prompt compiler** turns storyboard beats into strictly-constrained prompts, and **media QA** scores clips before assembly. The video model still creates freely — but only *inside* the universe.

**Why we keep the architecture MVP-simple.** The fix is not a platform. It is a set of markdown bibles, JSON schemas, and small stdlib Python scripts that slot into the existing `script → tts → assemble` flow. No database (JSON files on disk). No state machine (file presence = state, as in M1–M3). No orchestration framework (sequential scripts + the existing manifest contract). No new dependencies unless justified. The creative-control layer is *content and validation*, not infrastructure.

---

## 2. Existing Repo Scan

### Files inspected
- `scripts/assemble.py`, `scripts/tts.py`, `scripts/generate_media.py`, `scripts/media_pack.py`
- `scripts/*.md` (ASSEMBLY_README, TTS_README, MEDIA_README, MEDIA_PACK_README)
- `tests/test_assemble.py`, `tests/test_tts.py`, `tests/test_generate_media.py`, `tests/test_media_pack.py`
- `scripts/generated/james_growth_system_teaser_01.json`, `scripts/generated/m3_smoke_test.json`
- `strategy/ARCHITECTURE_MVP.md`, `strategy/BUSINESS_PLAN.md`, `strategy/TIMEPLAN.yaml`, `strategy/AUTOMATION_PIPELINE.md`
- `brand/BRAND_SPEC.md` (rich, active — single source of brand truth)
- `brand/James_harrington_{front,3_4,side,vertical}.png` (existing reference images)
- `brand/assets/*.png` (endcards, lower-thirds, wordmark)
- `.gitignore`

### Current pipeline (as observed)
```
reviewed_script.json
  → scripts/media_pack.py   (plan/validate media assets; --brief/--validate/--write-ready-script)
  → scripts/generate_media.py (visual_brief → Higgsfield clip → strip audio for generated_tts)
  → scripts/tts.py          (segment text → ElevenLabs mp3 → manifest.json; audio_mode policy)
  → scripts/assemble.py     (manifest → 16:9 + 9:16 MP4 + log; WPS align, gap-concat, music, loudnorm)
```

### Current script JSON structure (per segment)
`id`, `text`, `audio_mode` (`generated_tts`|`baked_in`|`silent`), `media`, optional `visual_brief`, `lower_third`, `trim_end`, `layout`, `trim_start`, optional `media_request` (type/description/orientation/duration_policy/required).

### Current manifest structure (produced by tts.py, consumed by assemble.py)
`id`, `segments[]` (`media`, optional `audio`, `words`, optional `trim_end`/`lower_third`), `pacing` (`reference`, `baseline_speed`), `music` (`mood`/`level_db`/optional `file`), `brand` (endcards, gap_seconds, audio_fade), `render` (fps/crf/grade), `output` (directory/prefix).

### Current media generation behavior
- Higgsfield CLI at `node_modules/@higgsfield/cli/bin/higgsfield.js`, authenticated (token `[configured]`, never printed).
- Default models: `seedance_2_0` (Seedance 2.0 Fast) for `baked_in` lipsync; `wan2_7` for `generated_tts` b-roll.
- For `generated_tts`, downloaded clip audio is **stripped** (`ffmpeg -an`); raw kept transiently as `.raw_*` (gitignored), deleted after strip.
- Path resolution: bare paths → repo-root-relative; `../`-prefixed → script-relative.
- Writes `media_generation_log.json` with provenance: `generated_higgsfield` / `reused_existing` / `missing`.

### Current audio behavior
- `generated_tts`: manifest carries a separate `audio` (ElevenLabs mp3); assemble.py maps `0:v` + `1:a` with `-shortest`; WPS measured on the narration file, not the media. **Proven safe.**
- `baked_in`: no `audio` field; clip's own synced audio used (lipsync). WPS measured on the clip.
- `silent`: no `audio`, no TTS.
- Segment narration only (one mp3 per segment) → this is the source of the audible breaks between segments. **No continuous-narration mode exists yet.**

### Current tests
`test_assemble.py` (7 property tests), `test_tts.py` (13), `test_generate_media.py` (9), `test_media_pack.py` (12). All pass. No live API calls in tests (fake keys/fixtures).

### Current gaps (the M4–M10 targets)
1. No shared creative universe — each clip invents its own world.
2. No technical production grammar — color/light/camera/framing uncontrolled.
3. No storyboard — script maps directly to per-segment prompts; no A-roll/B-roll planning.
4. No reviewer gates — nothing blocks all-b-roll, weak hooks, futurism, garbled text.
5. No continuous narration — segment TTS causes audible breaks.
6. No prompt compiler — `visual_brief` goes raw to the model with no universe/technical constraints.
7. No media QA — clips assembled without consistency/realism scoring.
8. No reference-asset discipline — James images exist in `brand/` but aren't an anchored, ID'd library used by generation.

### Uncertain / to confirm (see §15 Open Questions)
- Whether James A-roll should be lipsync talking-head or James-present voiceover (lipsync stability unknown).
- Whether the studio/library should be generated as still reference images first, then image-to-video.
- Exact cat design.
- Whether the real-person/fictional-host framing matters legally (BRAND_SPEC says "real vs generated unspoken").

---

## 3. Core Design Principle

**Do not hard-code a rigid formula. Define a bounded creative universe.**

The LLM and the video model may create freely *inside* the universe. They may **not** invent:
- a different James (face, age, wardrobe, voice presence)
- a different room / layout / set
- a different cat (or a cat that behaves like a gimmick)
- futuristic / cyberpunk / neon / hologram AI visuals
- readable on-screen text (gibberish or otherwise) — text is post-production overlay
- random camera language (spins, impossible drone moves, aggressive zooms)
- a different tone (motivational, hype, influencer)
- an all-b-roll sequence with no James in a host-led episode

The bibles are *guardrails*, not scripts. Recurring motifs (signature gestures, the cat, specific angles) are **optional and occasional**, never mandatory-per-video. The goal is a recognizable, premium, coherent channel — not a template that makes every video identical.

---

## 4. M4 — Universe Bible & Technical Bible

**Goal:** Establish the two control layers before any further generation. **This is the highest-priority milestone — nail the bibles first, or implementation just automates bad taste at higher velocity.**

**Integration note (important):** `brand/BRAND_SPEC.md` already defines persona, palette, typography, voice, and Higgsfield character prompts. M4 docs must **reference and extend** BRAND_SPEC, not duplicate it. Where BRAND_SPEC already states a rule (e.g., navy+gold palette, RP voice, "no shocked face"), the bible cites it and adds production-grade specificity (camera, lighting, forbidden patterns, reference IDs). The existing `brand/James_harrington_*.png` become the seed of the reference asset library.

### Folder
```
docs/channel_universe/
├── README.md                      # index + how the bibles relate; cites BRAND_SPEC
├── UNIVERSE_BIBLE.md              # what exists in the universe
├── TECHNICAL_BIBLE.md             # how it is filmed/generated/edited
├── JAMES_CHARACTER_BIBLE.md       # James in production detail (extends BRAND_SPEC §2)
├── JAMES_RECORDING_STUDIO_LIBRARY.md  # the fixed recurring set + approved angles
├── BACKGROUND_CAT_BIBLE.md        # the occasional recurring cat
├── PEOPLE_AND_EXTRAS_BIBLE.md     # other humans
├── FORBIDDEN_PATTERNS.md          # explicit anti-patterns
├── PROMPT_RULES.md                # how prompts must be constructed
├── QA_RUBRIC.md                   # scoring before + after generation
└── REFERENCE_ASSET_MANIFEST.md    # the ID'd asset library
```

### A. Universe Bible (`UNIVERSE_BIBLE.md`) — what exists
Must define: channel purpose; target audience (mid-career professionals, founders, execs — per BUSINESS_PLAN personas B/E); emotional promise (calm competence, "the unfair advantage is a system"); worldview; tone; recurring locations (study/library is primary); recurring visual motifs (warm lamp light, dark wood, books, notebook, pen, compounding-curve sketches); recurring objects; **what belongs** in the universe; **what does not**.

Universe should feel: premium, calm, credible, elegant, grounded, businesslike, old-money/classic-institutional, modern but not futuristic, intelligent not motivational, cinematic but restrained.

Universe must not feel: cyberpunk, neon AI-startup cliché, motivational guru, flashy YouTube bro, generic corporate stock, sci-fi, fake luxury, overproduced trailer slop, corporate slideshow filler.

### B. Technical Bible (`TECHNICAL_BIBLE.md`) — how it's filmed
Production grammar (all sub-sections required):
- **Color:** warm neutrals, navy (#1B2A4A), charcoal (#2D2D2D), cream/ivory (#F5F0E8), dark wood, brass, leather, muted green, aged gold (#C8973E) accent, oxblood (#6B1D2A) sparingly; low saturation; controlled contrast. **No** neon/cyberpunk; **no** electric AI blue/purple except rare deliberate accent. (Palette = BRAND_SPEC §3.)
- **Lighting:** warm natural, soft side light, practical lamps, morning/late-afternoon feel, controlled shadows. **No** harsh synthetic glow, overexposed white offices, glossy AI-showroom lighting.
- **Camera:** slow dolly-in, locked-off medium, slow push-in, over-the-shoulder desk, close-up hands writing, close-up notebook/pen/book, slow tracking walk, subtle parallax. **No** spinning camera, impossible indoor drone, aggressive zooms, shaky handheld (unless deliberate documentary).
- **Framing:** 16:9 master with 9:16 center-safe crop (matches assemble.py crop behavior); James center-safe; important props within safe crop; avoid edge text; leave negative space for post-production text overlays.
- **A-roll:** James visible; controlled expression; consistent studio/library; lipsync only if generated from final approved narration; no random talking-head substitutes; no visible speaking face unless James or explicitly planned.
- **B-roll:** supports narration; never the whole video; illustrates not replaces; grounded/realistic; no readable AI text; no screens unless abstract/blurred or post-added.
- **Audio:** prefer continuous narration for finals; segment TTS only for tests/drafts; target WPS (calm 2.2–2.6, teaser 2.6–3.0); pause rules; tone/energy curve; no baked-in b-roll audio; music ducked under narration.
- **Editing:** cuts on sentence/clause boundaries; no abrupt audio breaks; one narration section may cover multiple shots; A-roll/B-roll planned in storyboard; per-scene prompts must not dictate the sequence.

### `PROMPT_RULES.md`
Every compiled prompt must: be built from storyboard beats (not raw `visual_brief`); include universe constraints; include technical constraints; include negative constraints; specify A-roll vs B-roll; specify James presence; environment; lighting; camera movement; text policy; crop safety; whether it uses reference images; whether audio is allowed or must be stripped/ignored.
**Default negatives:** no futuristic holograms, cyberpunk, neon, floating UI, robots, garbled text, readable generated text, fake logos, distorted hands, uncanny faces, random smiling stock people, sci-fi, overdesigned startup office, AI dashboards (unless explicit + text-free).
**Text rule:** generated video avoids readable text; if text needed → post-production overlay.

### `FORBIDDEN_PATTERNS.md`
Explicit anti-pattern list (all-b-roll host-led episode; no-James episode; futuristic AI city; glowing hologram dashboard; unreadable on-screen text; random people replacing James; motivational stock footage; disconnected scene style; random camera/room/wardrobe/cat; trailer lighting; influencer tone; slideshow look; fake luxury; visible logos; sudden sci-fi; generic "AI future" visuals). Each with a one-line "instead, do X."

### `QA_RUBRIC.md`
Storyboard QA (narrative continuity; A-roll/B-roll ratio; James presence; scene evolution; audience relevance; hook strength; visual feasibility; universe compliance). Media QA (James/studio/cat consistency; color/lighting/camera compliance; realism; text contamination; audio contamination; crop safety; narration fit). **Automatic fail conditions** (see §9 for the canonical list).

### `JAMES_CHARACTER_BIBLE.md`, `JAMES_RECORDING_STUDIO_LIBRARY.md`, `BACKGROUND_CAT_BIBLE.md`, `PEOPLE_AND_EXTRAS_BIBLE.md`, `REFERENCE_ASSET_MANIFEST.md`
Content requirements for each are specified verbatim in `docs/plans/M4_M10_SCHEMA_DESIGN.md` §"M4 bible content checklists" so a cheaper model can fill them without inventing structure. Key points:
- **James bible** extends BRAND_SPEC §2/§9: role, personality, visual identity, age impression (~60), posture, expression range, eye-contact rules, movement rules, signature gestures (optional motifs), behavior when not speaking, appearance in A-roll/voiceover/b-roll, how he must never appear; wardrobe (navy cashmere over white Oxford = canonical), grooming, hair consistency, glasses rule (OPEN QUESTION — default: no glasses), watch/pen/notebook/laptop use.
- **Studio/library bible:** ONE spatial layout, multiple approved camera angles (IDs: `STUDIO_LIBRARY_WIDE_001`, `_MEDIUM_DESK_001`, `_CLOSEUP_001`, `_OVER_SHOULDER_001`, `_SIDE_PROFILE_001`, `_STANDING_BOOKSHELF_001`, `_CAT_BACKGROUND_001`). Room identity, layout, furniture, light source, allowed time-of-day looks, forbidden changes. All angles must belong to the same room.
- **Cat bible:** identical every time; appearance/breed-impression/fur/size/temperament; allowed locations (sleeping on chair, deep-background walk, windowsill, near books); frequency (occasional, not every video); forbidden behaviors (distracting, comic, jumping, plot-point, different look).
- **People/extras bible:** when others may appear; background-only default; wardrobe; diversity handled tastefully and realistically; no influencer characters; no real/recognizable public figures; never replace James as anchor.
- **Reference asset manifest:** see §"REFERENCE_ASSET_MANIFEST" in `M4_M10_SCHEMA_DESIGN.md` for the per-asset record (asset_id, file path, purpose, allowed/forbidden use, prompt anchor, A-roll/B-roll flag, 9:16 center-safe flag) and folder layout under `assets/reference/`.

**M4 acceptance:** all 11 docs exist, internally consistent, cite BRAND_SPEC where overlapping, contain no contradictions with TECHNICAL_BIBLE, and a human can read them and produce a compliant prompt by hand. No code. No assets generated.

---

## 5. M5 — Storyboard Generator

**Goal:** Insert a storyboard layer between script and media prompts. The storyboard plans A-roll/B-roll beats so the *sequence* is intentional, not emergent from per-clip prompts.

### Deliverables (plan only; implement in Sprint M5.1/M5.2)
- `scripts/storyboard.py` — generates/validates a storyboard JSON from a reviewed script + bibles. Dry-run capable (no API needed for validation; LLM call only when actually drafting beats).
- `schemas/storyboard.schema.json` — JSON Schema (draft-07) for the storyboard.
- `tests/test_storyboard.py` — property tests (schema validity, ratio guardrails, James-presence rule, no-credit dry-run).
- `docs/storyboard/README.md` — how storyboards are authored/reviewed.

### Storyboard JSON (top level)
`project_id`, `episode_title`, `target_audience`, `narrative_promise`, `total_target_duration`, `narration_mode` (`continuous_voiceover`|`segment_tts`), `beats[]`.

### Beat fields (full list — see `M4_M10_SCHEMA_DESIGN.md` for types)
`beat_id`, `source_script_segment_id`, `narration_text`, `narrative_function`, `scene_type`, `a_roll_or_b_roll`, `james_presence`, `location_id`, `reference_assets[]`, `audio_source`, `audio_continuity_group`, `duration_target_sec`, `start_time_target_sec?`, `end_time_target_sec?`, `camera`, `lighting`, `palette`, `movement`, `props[]`, `text_policy`, `crop_safety`, `forbidden_elements[]`, `transition_in`, `transition_out`, `qa_notes`.

### Scene types (enum)
`A_ROLL_TALKING_HEAD`, `A_ROLL_CHARACTER_PRESENT_VOICEOVER`, `B_ROLL_SUPPORTING_VISUAL`, `B_ROLL_SYMBOLIC_VISUAL`, `INSERT_HANDS_WRITING`, `INSERT_OBJECT_DETAIL`, `TEXT_OVERLAY_POST_ONLY`, `TRANSITION`, `TITLE_CARD`.

### Storyboard rules (enforced by storyboard.py validation, not just docs)
- No all-b-roll host-led episode unless `allow_all_broll: true` is explicitly set.
- James must appear in a meaningful share (see ratios) for host-led episodes.
- One `audio_continuity_group` may map to multiple visual beats (this is how continuous narration spans shots).
- Transitions follow narrative logic.
- B-roll supports the argument.
- Every beat must comply with Universe + Technical bibles (compiler + reviewer enforce; storyboard.py checks the structural rules).

### Recommended A-roll/B-roll ratios (guardrails, not formulas)
- Teaser: 60–75% James/A-roll presence.
- Educational explainer: 45–65% A-roll, 35–55% b-roll.
- Cinematic trailer: 40–60% A-roll/James-present, 40–60% b-roll.
`storyboard.py` should WARN (not hard-fail) when outside these bands, and hard-fail only on 0% James in a host-led episode.

**M5 acceptance:** schema exists; `storyboard.py --validate <storyboard.json>` passes/fails correctly; ratio guardrails enforced; dry-run makes no API calls; tests pass; existing M1–M3 tests still pass.

---

## 6. M6 — Reviewer LLM Gates

**Goal:** Structured LLM review at each creative checkpoint. Blocks bad work *before* spending generation credits.

### Deliverables (plan only)
- `scripts/review_script.py`, `scripts/review_storyboard.py`, `scripts/review_media_plan.py`
- `docs/reviewer_prompts/` (one prompt doc per persona)
- `tests/test_review_gates.py` (uses a fake/stub LLM in tests — no live calls)

### Reviewer personas
1. Filmmaker / story director
2. Technical video-generation specialist
3. Target-audience / retention reviewer
4. Brand-universe compliance reviewer
5. Audio/narration pacing reviewer

### Reviewer output (structured JSON, identical shape across personas)
`pass` (bool), `score` (0–10), `issues[]`, `blocking_issues[]`, `recommended_fixes[]`, `may_proceed` (bool). A run aggregates personas: `may_proceed = all(persona.pass)` and no `blocking_issues` anywhere.

### Review gates (where they run)
- Before TTS (script review)
- Before media generation (storyboard + media-plan review)
- After media generation (clip QA review — overlaps M9)
- Before final assembly (final coherence review)

### Reviewer must block
All-b-roll host-led; weak hook; no narrative promise; excessive futurism; disconnected scene flow; generated-text risk; wrong James/studio/cat universe; audio discontinuity; no clear reason to keep watching.

### Cost/credit safety
Reviewers call an LLM (Claude/OpenAI text) — cheap, no media. Tests use a stub reviewer returning canned JSON. A `--dry-run` prints the prompt + expected schema without calling the API.

**M6 acceptance:** each reviewer emits valid structured JSON; aggregation logic correct; stub-based tests pass; no media/Higgsfield calls; gates can block a deliberately bad fixture (e.g., all-b-roll storyboard).

---

## 7. M7 — Continuous Narration & Audio Timing

**Goal:** Fix the audible breaks by moving from per-segment TTS to one continuous narration file per video, with a timing map that storyboard beats align to.

### Current issue
`tts.py` generates one mp3 per segment; assemble.py gap-concats them → audible breaks + narrative discontinuity.

### Plan
- Keep `segment_tts` for tests/rough drafts (existing behavior — do not break it).
- Add `continuous_voiceover`: generate ONE full narration file for the whole script.
- Build a sentence/beat timing map (start/end per sentence or beat) via silence detection / forced alignment with the known text.
- Measure WPS over the whole narration.
- Align storyboard beats to time ranges in the continuous narration; one narration section may cover multiple visual shots.

### Deliverables (plan only)
- `scripts/audio_timing.py` — builds the timing map from a continuous narration file + the script text.
- Updates to `scripts/tts.py` — add `narration_mode: continuous_voiceover` (additive; default stays `segment_tts` until M10 opt-in).
- `schemas/audio_timing.schema.json`
- `tests/test_continuous_narration.py`

### Audio timing map (per entry)
total duration; WPS; per-sentence duration; pause durations; long-pause flags; narration_mode; mapping `beat_id → [start_sec, end_sec]`.

### Target WPS
Calm premium 2.2–2.6; energetic teaser 2.6–3.0; flag < 2.0 or > 3.2 unless approved. (Consistent with assemble.py's existing WPS machinery; for `continuous_voiceover` the assembly timing model must change so beats are cut against the timing map rather than per-segment speed alignment — see RISK in §14.)

### Rules
Final video normally uses `continuous_voiceover`; b-roll brings no audio; music ducked under narration; pacing adjusted before media generation, not after assembly.

**M7 acceptance:** continuous narration file generated for one test script (only when explicitly run with credentials — not in CI); timing map schema valid; alignment maps beats to time ranges; `segment_tts` path unchanged and its tests still pass; no TTS regenerated unless `--force`.

> **Assembly impact (flag for M7.2 implementer):** `assemble.py` currently assumes one audio file per segment. Continuous narration needs either (a) the timing map to slice the master narration per beat, or (b) a new assembly mode that lays the full narration over a sequence of muted visual beats cut to the timing map. Option (b) is cleaner and matches "one narration section over multiple shots." This is the single biggest technical change in M4–M10 and must be designed carefully — see §14.

---

## 8. M8 — Media Prompt Compiler

**Goal:** Compile strict, universe-constrained media prompts from storyboard beats. No prompt is ever made directly from raw `visual_brief`.

### Deliverables (plan only)
- `scripts/compile_media_prompts.py`
- `schemas/media_prompt_plan.schema.json`
- `tests/test_media_prompt_compiler.py`

### Inputs
script JSON; storyboard JSON; Universe Bible; Technical Bible; Reference Asset Manifest; QA Rubric. (Bibles read as text; the compiler injects their constraint blocks into every prompt. ASSUMPTION: bibles expose a machine-readable "constraints" appendix — see §12.)

### Output: `media_prompt_plan.json`
One entry per beat/shot: `beat_id`, compiled `prompt`, `negative_prompt`, `model` (recommendation: `seedance_2_0` for A-roll/James, `wan2_7` for grounded b-roll), `reference_assets[]`, `expected_duration_sec`, `output_path`, `audio_policy` (`strip`|`keep_lipsync`), `crop_safety`, `qa_checklist[]`.

### Rules
- Prompts compiled from storyboard beats, not raw visual_brief.
- All prompts carry universe + technical + negative constraints.
- A-roll prompts use approved James + studio reference IDs.
- Studio/library prompts use approved angle IDs.
- Cat prompts use the approved cat reference.
- B-roll grounded, realistic, restrained.
- No generated readable text unless explicitly approved; else mark `text_policy: post_overlay`.

**M8 acceptance:** given a fixture storyboard + stub bibles, compiler emits a valid `media_prompt_plan.json` where every prompt contains the negative-constraint block and an A-roll/B-roll tag; A-roll entries reference approved James/studio IDs; tests pass; no API calls.

> **Integration:** `generate_media.py` should gain an input mode that reads `media_prompt_plan.json` instead of raw `visual_brief`. Keep the existing `visual_brief` path for backward compatibility (M3 still works). Additive only.

---

## 9. M9 — Media QA & Clip Scoring

**Goal:** Score every generated clip before assembly; route failures to regeneration.

### Deliverables (plan only)
- `scripts/qa_media.py`
- `schemas/media_qa.schema.json`
- `tests/test_media_qa.py`

### Technical checks (cheap, deterministic — ffprobe)
file exists; ffprobe-readable; video stream exists; duration; width/height; audio-stream presence; codec; 16:9 / 9:16 crop-safety metadata if available.

### Creative checks (LLM/vision pass — flag as optional/deferred if vision cost is a concern)
universe compliance; James consistency; studio consistency; cat consistency; lighting/color/camera compliance; no futuristic slop; no prominent garbled text; no random characters; no visible logos; no audio contamination.

### Output
`media_qa_report.json` + `media_qa_report.md`; pass/fail per clip; blocking issues; clips approved for assembly; clips requiring regeneration.

### Canonical automatic-fail conditions (shared with QA_RUBRIC.md)
- `generated_tts` b-roll has baked-in audio used in final output
- no James presence in a host-led episode
- prominent garbled text
- futuristic hologram / cyberpunk look
- wrong James appearance
- wrong studio/library layout
- different cat
- random character replacing James
- major 9:16 crop failure
- visible logos or copyrighted text
- scene contradicts narration

**M9 acceptance:** technical checks run deterministically on a fixture clip (no API); report files written; fail conditions detected (e.g., a clip with an audio stream tagged for `generated_tts` is flagged); creative checks behind a flag/stub in tests; existing tests pass.

> **Cost note:** technical QA is free (ffprobe). Creative QA via a vision model costs money per clip — implement technical QA first (M9.1), defer/flag creative vision QA (M9.2) and allow a manual-review fallback (clip → Telegram → human approve) to avoid vision-API cost creep.

---

## 10. M10 — Rebuild James Teaser Using the New Pipeline

**Goal:** Plan (not execute) the rebuilt teaser through the full creative-control pipeline.

### Target rebuild pipeline
refine script → script reviewer → storyboard → storyboard reviewer → continuous narration → timing map → prompt compiler → generate A-roll/B-roll → QA clips → assemble → final review.

### Use of existing teaser
- **Preserve** current `james_growth_system_teaser_01` outputs as *technical test artifacts* (proof the plumbing works). Do not treat as creative-final.
- Create a **new** `project_id`: `james_growth_system_teaser_02`.
- **Never overwrite** teaser_01 media or narration.

### Sequencing inside M10 (credit-gated)
- M10.1: rebuild plan only (this section + a concrete teaser_02 script + storyboard draft) — no spend.
- M10.2: controlled one-segment regeneration into a temp path (like the M3-A smoke test) — minimal spend, explicit approval.
- M10.3: full teaser_02 regeneration — only after human approval of the storyboard + one-segment proof.

**M10 acceptance (planning):** a written rebuild runbook exists with exact commands, the new project_id, and the no-overwrite guarantees. No generation in this milestone's planning step.

---

## 11. Implementation Sequencing (sprints for cheaper models)

Each sprint is independently implementable. Full copy-paste implementation prompts live in `docs/plans/M4_M10_IMPLEMENTATION_PROMPTS.md`. Summary table:

| Sprint | Objective | Creates | Must NOT touch | Acceptance | API spend |
|---|---|---|---|---|---|
| **M4.1** | Universe Bible docs | `docs/channel_universe/{README,UNIVERSE_BIBLE,JAMES_CHARACTER_BIBLE,JAMES_RECORDING_STUDIO_LIBRARY,BACKGROUND_CAT_BIBLE,PEOPLE_AND_EXTRAS_BIBLE}.md` | scripts/, tests/, brand/ assets | All 6 docs exist, cite BRAND_SPEC, internally consistent | none |
| **M4.2** | Technical Bible + rules + QA | `docs/channel_universe/{TECHNICAL_BIBLE,FORBIDDEN_PATTERNS,PROMPT_RULES,QA_RUBRIC}.md` | scripts/, tests/ | Docs exist, no contradictions with M4.1, fail conditions match §9 | none |
| **M4.3** | Reference asset manifest + folders | `docs/channel_universe/REFERENCE_ASSET_MANIFEST.md`, empty `assets/reference/{james,studio_library,cat,wardrobe,color_palette,props}/` (+ `.gitkeep`) | media gen | Manifest lists IDs + paths; folders exist; existing `brand/James_*.png` mapped as seeds | none |
| **M5.1** | Storyboard schema + generator (validate/dry-run) | `schemas/storyboard.schema.json`, `scripts/storyboard.py`, `docs/storyboard/README.md` | tts/assemble/generate_media behavior | `storyboard.py --validate` works; dry-run no API; schema valid | none |
| **M5.2** | Storyboard QA checks | extend `storyboard.py`, `tests/test_storyboard.py` | media gen | Ratio guardrails warn; 0%-James host-led hard-fails; tests pass | none |
| **M6.1** | Reviewer prompts + structured output | `scripts/review_{script,storyboard,media_plan}.py`, `docs/reviewer_prompts/*`, `tests/test_review_gates.py` | media gen | Valid JSON output; stub tests pass; blocks bad fixture | none (stub in tests) |
| **M7.1** | Continuous narration timing schema + planner | `schemas/audio_timing.schema.json`, `scripts/audio_timing.py` (offline map builder) | segment_tts path | Timing map from a provided wav; schema valid | none (uses local file) |
| **M7.2** | `tts.py` continuous_voiceover mode | extend `tts.py`, `tests/test_continuous_narration.py` | segment_tts default | New mode additive; default unchanged; tests pass | gated (live only on explicit run) |
| **M8.1** | Media prompt compiler | `scripts/compile_media_prompts.py`, `schemas/media_prompt_plan.schema.json`, `tests/test_media_prompt_compiler.py` | generate_media default path | Compiles valid plan with constraints; tests pass | none |
| **M9.1** | Media QA technical checks | `scripts/qa_media.py`, `schemas/media_qa.schema.json`, `tests/test_media_qa.py` | media gen | ffprobe checks + report; fail conditions detected; tests pass | none |
| **M9.2** | Media QA creative checklist/report | extend `qa_media.py` (vision behind flag) + manual-review fallback | — | Creative checks stubbed in tests; Telegram fallback documented | gated |
| **M10.1** | Rebuild teaser plan only | `docs/plans/TEASER_02_REBUILD_RUNBOOK.md` + `scripts/generated/james_growth_system_teaser_02.json` (script only) | teaser_01 media/narration | Runbook + script exist; no overwrite of teaser_01 | none |
| **M10.2** | Controlled one-segment regen | temp project, temp path | teaser_01 + teaser_02 finals | One clip via new pipeline into temp; QA pass | minimal, explicit |
| **M10.3** | Full teaser_02 regen | teaser_02 outputs | teaser_01 | Only after storyboard + one-segment approval | yes, approved |

For each sprint, `M4_M10_IMPLEMENTATION_PROMPTS.md` gives: objective, files to create/change, files NOT to touch, exact tasks, expected `python3` commands, tests to add, acceptance criteria, rollback notes, and the verbatim implementation prompt.

---

## 12. Repo Integration Design

Proposed folders (additive; none conflict with existing):
```
docs/channel_universe/   # M4 bibles
docs/storyboard/         # M5 docs
docs/reviewer_prompts/   # M6 persona prompts
docs/plans/              # this plan + supporting plans (exists)
schemas/                 # JSON Schemas (new)
assets/reference/        # ID'd reference library (new; seeds from brand/James_*.png)
scripts/                 # new scripts join existing ones
tests/                   # new tests join existing ones
```

**Schema approach — KEEP SIMPLE.** Use JSON files + JSON Schema (draft-07) documents for *documentation/validation reference*, but validate in Python with **stdlib only** (a small hand-written validator or `json` + explicit checks) to avoid adding `jsonschema` as a dependency unless a sprint proves the hand-rolled checks are too painful. **ASSUMPTION:** stdlib validation is sufficient for MVP; revisit only if pain appears. The existing scripts already do hand-rolled validation (`validate_manifest`, `validate_script`) — follow that pattern.

**Bible machine-readability:** bibles are markdown for humans. The compiler (M8) needs constraint text. Plan: each bible ends with a fenced `## CONSTRAINTS (machine-readable)` block the compiler can extract verbatim, OR a sibling `docs/channel_universe/constraints.json` holding the negative-prompt block, palette tokens, approved angle IDs, and forbidden list. **Recommendation:** add `constraints.json` in M4.2 so M8 reads structured data, not parsed prose. (Mark as the one small structured-data file; not a database.)

**Backward compatibility (hard rule):** every new capability is additive. `generate_media.py` keeps the `visual_brief` path; `tts.py` keeps `segment_tts` default; `assemble.py` keeps the current manifest contract. New modes are opt-in via flags/fields. M1–M3 tests must keep passing unchanged.

---

## 13. Acceptance Test Design

Per milestone:

| Milestone | Unit | Dry-run / no-credit | File-output | Regression |
|---|---|---|---|---|
| M4 | n/a (docs) | n/a | docs exist + lint (markdown headings, required sections present) | M1–M3 tests pass |
| M5 | schema validity, ratio math, James-presence rule | `--validate` no API | storyboard.json written | M1–M3 pass |
| M6 | aggregation logic, JSON shape | stub LLM, `--dry-run` prints prompt | review report written | M1–M3 pass |
| M7 | WPS math, timing-map shape | offline map from local wav; no TTS unless `--force` | timing_map.json | segment_tts tests unchanged |
| M8 | constraint injection, A-roll ref rule | compile from fixtures, no API | media_prompt_plan.json | M1–M3 pass |
| M9 | ffprobe checks, fail-condition detection | technical checks no API; creative stubbed | qa_report.{json,md} | M1–M3 pass |
| M10 | n/a (plan) | n/a | runbook + teaser_02 script | teaser_01 untouched |

**Cross-cutting guarantees (must be asserted by tests where feasible):**
- No TTS regeneration unless `--force` (reuse-cache test, as in test_tts).
- No Higgsfield call in dry-run/validate/review/compile stages (no network; stubbed).
- No token logging (grep test: assert no `hf_` prefix or token-like strings in any printed output — extend the redaction check).
- No overwrite of production media unless `--force` + explicit target path.
- Existing `tests/test_assemble.py`, `test_tts.py`, `test_generate_media.py`, `test_media_pack.py` remain green.

`docs/plans/M4_M10_ACCEPTANCE_TESTS.md` holds the concrete per-sprint test list.

---

## 14. Risk Register

| Risk | Likelihood | Impact | Mitigation | Now / Defer |
|---|---|---|---|---|
| Too much rigidity → formulaic videos | Med | Med | Bibles are guardrails; motifs optional; ratios are bands not rules | Now (bake into bible wording) |
| Too little constraint → AI slop (the M3 failure) | High | High | Compiler injects mandatory negatives; reviewer + QA gates | Now (M4/M6/M8/M9) |
| A-roll / lipsync quality unstable | High | High | Default to James-present voiceover over lipsync until proven; one-segment proof before full run | Now (default), prove in M10.2 |
| Continuous narration needs timing data not yet available | High | High | M7 builds timing map via silence detect/alignment; design assembly mode (b) to lay master narration over beats | Now (M7 is the hard part) |
| Studio consistency needs reference images / image-to-video | Med | High | Generate studio still references first (M4.3 + a still-gen step), then image-to-video | Defer to M10.2 decision (OPEN QUESTION) |
| Cat consistency hard without reference asset | Med | Low | Define cat reference image; use occasionally; QA flags mismatch | Defer (cat is optional) |
| Generated in-scene text unreliable | High | Med | PROMPT_RULES: no generated text; post-production overlays | Now (rule) |
| B-roll becomes generic | Med | Med | Bibles + compiler ground every b-roll prompt; QA scores realism | Now |
| Cost creep from regenerating clips | Med | Med | QA before assembly; one-segment proofs; reuse-cache; budget note | Now (process) |
| Reviewer LLMs overcomplicate / over-block | Med | Med | Reviewers WARN vs BLOCK distinction; only canonical fail-conditions block | Now (M6 design) |
| Provider abstraction creep | Low | Med | Explicitly deferred; keep Higgsfield/ElevenLabs hardcoded until a 2nd provider is truly needed | Defer |

**Provider abstraction (deferred, with argument):** A clean port would help if Higgsfield's v0.1.x CLI breaks or a better b-roll model appears. But we have one working provider per capability and no second implementation. Per ARCHITECTURE_MVP "Rule of Three," **defer** until a real switch is forced. Document the seam (the `generate_media.py` model-selection + download functions) so a future swap is localized.

---

## 15. Open Questions for User

Defaults are chosen so the plan is not blocked. Confirm/override later.

1. **James — realistic semi-fictional host vs direct representation of the real you?**
   *Default:* semi-fictional host "James Harrington" (consistent with BRAND_SPEC "real vs generated unspoken"). Affects legal framing + lipsync expectations.
2. **A-roll priority — lipsync talking-head vs James-present voiceover?**
   *Default:* James-present voiceover scenes as primary (more stable, less uncanny), lipsync talking-head only for short hero moments once proven. (Drives M7/M10 design.)
3. **What should the cat look like?**
   *Default:* a calm, dignified British Shorthair (blue-grey) — matches the old-money/study aesthetic. Needs one approved reference image.
4. **Generate the studio/library as still reference images first, then image-to-video?**
   *Default:* YES — generate approved studio stills (the 7 angle IDs) first; use image-to-video for consistency. (Strongly recommended; reduces room drift.)
5. **First rebuilt teaser format — documentary trailer / premium course intro / founder monologue?**
   *Default:* premium founder monologue (James-present), b-roll supporting — best showcases the universe and is most forgiving of lipsync limits.
6. **Post-production text overlay as the default instead of generated in-scene text?**
   *Default:* YES — all readable text is post overlay (Playfair/Inter per BRAND_SPEC); generated video stays text-free.

---

## 16. Final Report

### Files created in this run
- `docs/plans/M4_M10_CREATIVE_CONTROL_WORKPLAN.md` (this document)
- `docs/plans/M4_M10_SCHEMA_DESIGN.md` (schemas + bible content checklists)
- `docs/plans/M4_M10_IMPLEMENTATION_PROMPTS.md` (verbatim per-sprint prompts for cheaper models)
- `docs/plans/M4_M10_ACCEPTANCE_TESTS.md` (per-sprint test lists)
- `docs/plans/` folder

### Repo files inspected
scripts/{assemble,tts,generate_media,media_pack}.py + their READMEs; tests/test_*.py; scripts/generated/*.json; strategy/{ARCHITECTURE_MVP,BUSINESS_PLAN,TIMEPLAN,AUTOMATION_PIPELINE}.md; brand/BRAND_SPEC.md; brand/James_*.png + brand/assets/*.png; .gitignore.

### Current gaps
No creative universe, no technical grammar, no storyboard, no reviewer gates, no continuous narration, no prompt compiler, no media QA, no ID'd reference library. (Detailed in §2.)

### Recommended next implementation sprint
**Sprint M4.1 (Universe Bible docs).** Get the bibles right before any code. Then M4.2, M4.3. Do NOT jump to M5+ code until M4 is human-approved — otherwise implementation automates bad taste faster.

### Exact prompt for the cheaper model — Sprint M4.1
> You are a brand/creative documentation writer for the "Leverage Mind" faceless YouTube channel (persona: James Harrington). Work in /home/jacobw/YTchannel. Use python3 if you run anything (you mostly won't). Read `brand/BRAND_SPEC.md` and `docs/plans/M4_M10_CREATIVE_CONTROL_WORKPLAN.md` §4 and `docs/plans/M4_M10_SCHEMA_DESIGN.md` "M4 bible content checklists". Create these files only: `docs/channel_universe/README.md`, `UNIVERSE_BIBLE.md`, `JAMES_CHARACTER_BIBLE.md`, `JAMES_RECORDING_STUDIO_LIBRARY.md`, `BACKGROUND_CAT_BIBLE.md`, `PEOPLE_AND_EXTRAS_BIBLE.md`. Rules: (1) Cite and extend BRAND_SPEC — never contradict it; do not duplicate its palette/typography tables, link to them. (2) Fill every content requirement listed in §4 for each file. (3) The studio/library bible must define ONE room with the seven approved camera-angle IDs. (4) Use the defaults in §15 (semi-fictional host; James-present voiceover primary; British Shorthair blue-grey cat; studio stills first; founder-monologue teaser; post-overlay text). Mark anything you are unsure about as `ASSUMPTION:` or `OPEN QUESTION:`. Do NOT touch scripts/, tests/, brand/ assets, or any media. Do NOT generate images or call any API. When done, list the files created and any assumptions made.

### Tests not run and why
No tests were run in this planning run. Reason: planning-only; no code was written or changed, so the existing M1–M3 suites are unaffected. (They were green at the end of M3-A.)

### API calls / credit-spending avoided
- No Higgsfield calls.
- No ElevenLabs calls / no TTS regeneration.
- No media generation.
- No credits spent.
- No production media (teaser_01) touched.
- No secrets/tokens printed (Higgsfield token referenced only as `[configured]`).

---

*End of master work plan. See sibling docs in `docs/plans/` for schemas, implementation prompts, and acceptance tests.*
