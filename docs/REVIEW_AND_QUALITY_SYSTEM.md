# Review and Quality System

**Generated:** 2026-06-12 (updated 2026-06-12 for V2 gated pipeline)
**Status:** Documents the quality system as implemented on this date.

---

## Overview

The quality system has five layers:

1. **Script review** — LLM multi-persona review gates
2. **Storyboard review** — Rule-based structural QA (V2: schema v2, shot-mix bands, anti-patterns)
3. **Bible application** — Universe + technical constraints enforced in generation
4. **Asset QA** — Technical validation of generated clips
5. **Final video QA** — Human review of assembled output

All layers are implemented. In the V2 pipeline, layers 2 (G2 storyboard gate), 4 (G8 media QA gate), and the four spend gates (G1/G2/G4/G5 ledger entries that block `generate_media.py`) are enforced as hard blocking gates. Layer 1 (script review) records an advisory exit code and can be wired via `tts.py --require-gates`. Layer 3 (bible application) is enforced through prompt compilation and generation-time risk checks. Layer 5 remains human.

---

## 1. Script Review (`review_script.py`)

**Purpose:** LLM review of a script before TTS or media generation spend.
**Status:** Implemented. Not auto-blocking.

### Personas

| Persona | Weight | Role | Blocking Conditions |
|---|---|---|---|
| `audience` | 2.0 | Retention mechanics — most important | No identifiable hook; >40s dead zone; broken promise; zero energy variation |
| `filmmaker` | 1.5 | Narrative structure | No compelling narrative arc |
| `universe` | 1.2 | Brand voice + identity | Wrong register; violates channel persona |
| `audio` | 1.0 | Pacing + speakability | WPS outside band; not speakable |
| `technical` | 0.8 | Production feasibility | Word count out of range; text-bearing visuals requested; missing audio_mode |

### Aggregation Logic

1. Any persona with `blocking_issues` → auto-fail (hard block) regardless of score
2. Weighted average score must be ≥ 3.0 to proceed
3. `audience` has weight 2.0 — a low audience score nearly always blocks

### Prompt locations

`docs/reviewer_prompts/audience.md`, `filmmaker.md`, `technical.md`, `universe.md`, `audio.md`

### Usage

```bash
python3 scripts/review_script.py scripts/generated/{project_id}.json
python3 scripts/review_script.py scripts/generated/{project_id}.json --output review.json
```

Exit code 1 if review fails. Use in pre-generation check.

### Current gap

Not wired into `tts.py` or `generate_media.py`. Operator must invoke manually. A failed review does not block downstream steps.

Evidence: `scripts/review_script.py`, `docs/reviewer_prompts/`

---

## 2. Storyboard Review (`review_storyboard.py`) — G2

**Purpose:** Rule-based structural QA of a v2 storyboard before media plan compilation.
**Status:** Hard blocking gate (V2). Records `storyboard_review` in the project gate ledger.

### Rules enforced (all blocking)

From `docs/channel_universe/constraints.json` and `PRODUCTION_V2_BLUEPRINT.md §7`:
- Schema version must be `2.0`
- Shot-mix bands: hero total 25–40%, hero_lipsync ≤25%, broll_specific ≥25%, graphics_ui ≥10%, metaphorical 5–15%, kinetic_text 2–8%
- Max consecutive hero block ≤15s (Act-6 close exempt if `justification` present)
- ≥12 distinct visual setups
- No banned models
- No front-facing close-up under voiceover without lipsync (`hero_cutaway` with direct-address brief = blocked)
- No empty `visual_brief` fields
- No generic `narrative_function` on b-roll beats
- All-hero shape (>60% of beats hero) = hard fail with explicit reference to the flagship-001 failure

### Gate recording

```bash
python3 scripts/review_storyboard.py storyboard.json --record-gate
```

Gate is bound to the storyboard file SHA-256. Editing the storyboard after approval invalidates the gate.

Evidence: `scripts/review_storyboard.py`, `schemas/storyboard_v2.schema.json`

---

## 3. Bible Application

**Purpose:** Constrain all media generation within the channel universe.
**Status:** Partially enforced in `generate_media.py`.

### Documents

| Document | Purpose | Status |
|---|---|---|
| `docs/channel_universe/UNIVERSE_BIBLE.md` | What exists in James's world | Active |
| `docs/channel_universe/TECHNICAL_BIBLE.md` | How the world is filmed/edited | Active |
| `docs/channel_universe/JAMES_CHARACTER_BIBLE.md` | James's appearance, character, voice | Active |
| `docs/channel_universe/JAMES_RECORDING_STUDIO_LIBRARY.md` | Studio environment definition | Active |
| `docs/channel_universe/BACKGROUND_CAT_BIBLE.md` | The cat's appearance rules | Active |
| `docs/channel_universe/PEOPLE_AND_EXTRAS_BIBLE.md` | Background character rules | Active |
| `docs/channel_universe/FORBIDDEN_PATTERNS.md` | Banned visual patterns | Active |
| `docs/channel_universe/PROMPT_RULES.md` | Prompt construction rules | Active |
| `docs/channel_universe/QA_RUBRIC.md` | QA scoring rubric | Active |
| `docs/channel_universe/constraints.json` | Machine-readable version of all above | Active (with bug: model_routing_policy uses banned wan2_7) |

### How bibles are applied in production

1. **`generate_media.py`** injects `BROLL_REALISM_PREFIX` and `BROLL_NEGATIVE` into every `generated_tts` prompt. These encode the "no fake text, no cyberpunk, no logos" rules.
2. **`generate_media.py:classify_prompt_risk()`** detects text-surface risk (screens, documents) and close-human risk in visual briefs; blocks generation if detected (unless `--allow-text-surfaces`).
3. **`generate_media.py:route_model()`** enforces model routing (banned models replaced with `kling3_0`).
4. **`storyboard.py`** applies constraints from `constraints.json` during storyboard generation and validation.
5. **`compile_media_prompts.py`** reads `constraints.json` to build constrained prompts (but not yet used in production).

### Gaps

- `compile_media_prompts.py` is the designed bridge between bibles and prompts, and **is now the production path** (V2). It reads `constraints.json` for routing, negative prompts, text policy, and crop safety, and is gated on G2.
- `constraints.json:model_routing_policy.grounded_broll` is now `kling3_0` (fixed in V2 config update).

Evidence: `scripts/compile_media_prompts.py`, `scripts/generate_media.py:run_from_media_plan()`, `docs/channel_universe/constraints.json`

---

## 4. Asset QA (`qa_media.py`) — G8

**Purpose:** Technical validation of generated video clips before assembly.
**Status:** Hard blocking gate (V2) when `--record-gate` is passed. `assemble.py --require-gates` blocks without the `media_qa` gate.

### Checks performed

| Check | Policy |
|---|---|
| File exists | Fatal if missing |
| Readable by ffprobe | Fatal if unreadable |
| Dimensions | `--scope source` = 1280×720 (Higgsfield output); `--scope assembled_16x9` = 1920×1080; `--scope assembled_9x16` = 1080×1920 |
| Duration ≥ 2.0s | Fatal if too short |
| `generated_tts` clips must NOT have audio stream | Blocking |
| `baked_in` clips MUST have audio stream | Blocking |

### Gate recording

```bash
python3 scripts/qa_media.py scripts/generated/${PROJECT}.json --scope source --record-gate
```

### Usage

```bash
python3 scripts/qa_media.py scripts/generated/{project_id}.json --scope source
python3 scripts/qa_media.py scripts/generated/{project_id}.json --segment 004_wrong_approach --output qa_report.json
```

Evidence: `scripts/qa_media.py:run_qa()`, `scripts/qa_media.py:DIMS_BY_SCOPE`

---

## 5. Final Video QA (Human)

**Purpose:** Gate B — visual quality check before publishing.
**Status:** Manual. Frame extraction tool available.

### How to extract review frames

```bash
python3 scripts/generate_media.py scripts/generated/{project_id}.json --review
```

This writes `Videos/Projects/{project_id}/review_frames/*.jpg` (at 20%, 50%, 80% of each clip's duration).

### Human gate B criteria (from `docs/plans/FLAGSHIP_001_HANDOVER.md`)

1. **Lipsync quality** — mouth movement matches audio; no desync; no rubber mouth
2. **Identity consistency** — James looks the same across all segments
3. **Studio consistency** — same room in every shot
4. **Audio timing** — no gaps, smooth transitions, music doesn't clip
5. **Brand** — endcard present (3s), lower-third if applicable
6. **Music mix** — audible but not competing with narration (-24dB target)
7. **No AI artifacts** — no text hallucinations, no warped faces, no extra fingers

### Automatic fail conditions (from `constraints.json`)

- `generated_tts_broll_audio_in_final_output` — b-roll audio must be stripped
- `james_absent_from_host_led_episode`
- `all_broll_host_led_video`
- `prominent_garbled_text_in_focus`
- `cyberpunk_or_futuristic_hologram_visuals`
- `wrong_james_appearance`
- `wrong_studio_layout`
- `cat_looks_different_from_reference`
- `visible_logo_or_copyrighted_text`
- `major_9x16_crop_failure`
- `audible_break_between_narration_segments_in_final`
- `scene_contradicts_narration`
- `credits_spent_before_storyboard_approved`

---

## Review System: Wire State

| Gate | Implemented | Blocking | How it blocks |
|---|---|---|---|
| Script LLM review (G1) | YES | Advisory exit code | `tts.py --require-gates` enforces; record gate manually with `gates.py record` |
| Storyboard rule review (G2) | YES | **HARD** | `compile_media_prompts.py` calls `require_gates([storyboard_review])`; exits 1 if absent/stale |
| Budget gate (G4) | YES | **HARD** | `generate_media.py` calls `require_gates([budget])`; exits 1 before any Higgsfield call |
| Media plan review (G3) | Partial | **HARD** (ledger) | `generate_media.py` requires `media_plan_review` gate; must be recorded manually until `review_media_plan.py` is updated |
| Human render approval (G5/G7) | YES | **HARD** | `generate_media.py` requires `render_approval` gate; `approve.py --gate render` is the only way to record it |
| Asset technical QA (G8) | YES | **HARD** (opt-in) | `assemble.py --require-gates` blocks without `media_qa` gate |
| Text-surface block in generation | YES | **HARD** | `generate_media.py:run()` |
| Banned model enforcement | YES | **HARD** | `generate_media.py`, `compile_media_prompts.py`, `review_storyboard.py` |
| SHA-256 staleness detection | YES | **HARD** | `gates.py:require_gates()` re-hashes artifacts; edit-after-approval = gate invalidated |
| Final video human gate | Manual | Human decision | Required before publishing |

---

## Known Gaps (advisory, not yet enforced)

1. **`review_media_plan.py` reads old script JSON**, not `media_plan.json`. G3 gate must be recorded manually. Planned update pending.
2. **`validate_lipsync_provenance()`** exists in `generate_media.py` but is not called automatically at assembly time. `media_generation_log.json` records provenance per beat; manual check only.
3. **Automated identity consistency check**: no tool validates James looks the same across clips. Human frame review is required.
4. **`graphics.py` (S7 local graphic rendering)** not yet implemented (T10). Graphic/kinetic/UI beats are skipped by `generate_media.py`.
5. **`assemble.py --require-gates`** must be passed explicitly; forgetting the flag assembles without the QA gate check.
