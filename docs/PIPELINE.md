# Production Pipeline — `produce.py`

Single-command orchestrator that takes a seed idea through the full production pipeline
to a finished video. Human interaction required only at two explicit gates.

```
python3 scripts/produce.py --seed "topic idea" --format short
python3 scripts/produce.py --resume Videos/Projects/<project_dir>
python3 scripts/produce.py --resume Videos/Projects/<project_dir> --from-step compile_media_plan
```

Formats: `short` (≤3 min, $25 cap), `explainer` (6–12 min, $60 cap), `teaser` (≤1 min, $5 cap).

---

## Pipeline overview

```
seed + format
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. research             → research_brief.json                              │
│  2. script_create        → script.json                                      │
│  3. script_review_loop   → script.json (revised, review passed)             │
│  4. storyboard_create    → storyboard.json                                  │
│  5. storyboard_review_loop → storyboard.json (revised, review passed)       │
│  6. tts                  → narration/continuous.mp3 + per-segment mp3s       │
│  7. build_timing_map     → narration/beat_timing_map.json                   │
│  8. compliance_check     → (validation gate, no output artifact)            │
│  9. compile_media_plan   → media_plan.json                                  │
│ 10. slice_lipsync        → media_plan.json (+ audio slices for hero beats)  │
│ 11. gate_a_budget        → [HUMAN: approve spend in terminal]               │
│ 12. generate_media       → assets/media/{segment}/{beat}.mp4                │
│ 13. qa_media             → media_qa_report.json                             │
│ 14. build_manifest       → manifest.json                                    │
│ 15. assemble             → {project}_16x9.mp4                               │
│ 16. gate_b_review        → [HUMAN: video sent to Telegram]                  │
└─────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
  ✓ DONE
```

---

## Step details

### 1. research
**Script:** `scripts/research.py`
**Input:** seed topic + format
**Output:** `research_brief.json` — angle, key claims (each with citation: title, URL, year), suggested titles
**Method:** Brave web search → fetch pages → LLM synthesis. Enforces ≥3 independent primary sources. TED/popular content = trend input only.

### 2. script_create
**Script:** `scripts/write_script.py`
**Input:** research_brief.json + channel bibles
**Output:** `script.json` — title, segments (id + spoken text), key_points, sources
**Method:** LLM (sonnet_creative) writes a script grounded in the research brief, obeying the format word-count constraint and brand voice rules.

### 3. script_review_loop
**Script:** `scripts/review.py` (review_loop)
**Input:** script.json + research source text
**Output:** script.json (revised)
**Method:** Multi-persona LLM review → aggregation → revision (see Review Loop Model below)
**Personas:** audience (weight 2.0, veto), brand_voice (weight 1.2)

### 4. storyboard_create
**Script:** `scripts/direct_storyboard.py`
**Input:** script.json + source research text + all channel bibles
**Output:** `storyboard.json` — schema v2.0, typed beats with creative fields + hydrated routing fields
**Method:** LLM director outputs creative fields (shot_type, visual_brief, narrative_function, subject, action, camera, setting, continuity_anchor, graphic). Then `hydrate_beats()` fills routing fields deterministically (model, asset_type, cost, duration clamping, word spans, prompt_class, fallback).

### 5. storyboard_review_loop
**Script:** `scripts/review.py` (review_loop)
**Input:** storyboard.json + source text
**Output:** storyboard.json (revised)
**Method:** Same loop model as script review
**Personas:** audience (2.0, veto), filmmaker (1.5), visual_director (1.5), technical (0.8)

### 6. tts
**Script:** `scripts/tts.py`
**Input:** script.json
**Output:** `narration/continuous.mp3` + per-segment mp3s
**Method:** ElevenLabs API (eleven_v3 model, James Harrington voice). Concatenates segment audio into one continuous master file.

### 7. build_timing_map
**Script:** `scripts/audio_timing.py`
**Input:** narration/continuous.mp3 + storyboard beats
**Output:** `narration/beat_timing_map.json` — each beat_id mapped to [start_sec, end_sec] in the master audio
**Method:** ffmpeg silencedetect → sentence boundary detection → word-proportional alignment to beats.

### 8. compliance_check
**Script:** `scripts/direct_storyboard.py` (validate_director_output)
**Input:** storyboard.json + source text
**Output:** None (pass/fail gate)
**Method:** Python-side structural validation — shot_type validity, anachronism guard, duration limits, required fields, narrative_function specificity. No LLM.

### 9. compile_media_plan
**Script:** `scripts/compile_media_prompts.py`
**Input:** storyboard.json + constraints.json + model_routing.yaml
**Output:** `media_plan.json` — each beat enriched with full positive/negative prompts, exact cost, reference images, output paths
**Method:** Deterministic compilation. Injects negative prompts from constraints.json, validates against banned models, assigns reference rotation for hero beats.

### 10. slice_lipsync
**Script:** `scripts/slice_continuous_lipsync.py`
**Input:** media_plan.json + narration/continuous.mp3 + beat_timing_map.json
**Output:** `media_plan.json` (updated with audio_slice entries) + sliced mp3 files
**Method:** Extracts audio slices from the continuous master for each hero_lipsync beat. Pads to meet Seedance 4s minimum. Records SHA-256 provenance for QA verification.

### 11. gate_a_budget (HUMAN GATE)
**Input:** media_plan.json totals
**Output:** Human approval in terminal (input: "go" or "stop")
**Method:** Displays beat count, estimated cost, budget cap. Sends Telegram notification. Blocks until human approves.

### 12. generate_media
**Script:** `scripts/generate_media.py`
**Input:** media_plan.json
**Output:** MP4 clips at `assets/media/{segment_id}/{beat_id}.mp4`
**Method:** Higgsfield CLI calls — Seedance 2.0 for hero_lipsync (with `--audio` for lip sync), Kling 3.0 for b-roll. Skips local_graphic beats. Respects duration limits (4–10s hero, ≤6s b-roll).

### 13. qa_media
**Script:** `scripts/qa_media.py`
**Input:** media_plan.json + generated clips
**Output:** `media_qa_report.json`
**Method:** Per-clip validation: readable video stream, correct dimensions (1280×720), duration coverage, audio-stream policy (lipsync = has audio, others = silent), provenance hash verification. Hard fail if any beat fails.

### 14. build_manifest
**Input:** media_plan.json + narration paths
**Output:** `manifest.json` — assembly instructions for assemble.py
**Method:** Pure Python. Maps each beat to its media file, audio policy, speech length, graphic overlays. Sets continuous_voiceover mode.

### 15. assemble
**Script:** `scripts/assemble.py`
**Input:** manifest.json + all media clips + continuous.mp3
**Output:** `{project}_16x9.mp4`
**Method:** ffmpeg-driven deterministic assembly. Lipsync beats keep their baked audio (never overlaid with narration). B-roll/graphic beats get narration voiceover from the timing map. Music bed mixed at −24dB. Loudnorm pass.

### 16. gate_b_review (HUMAN GATE)
**Input:** Assembled MP4
**Output:** Video sent to Telegram for human review
**Method:** If ≤50MB, sends video directly via Telegram bot. Otherwise notifies with file path.

---

## Review loop model

Both script and storyboard stages use the same feedback loop (N=1):

```
artifact ──▶ REVIEW (all personas, weighted scores)
                │
                ├── no mandatory issues → PASS (proceed)
                │
                └── has mandatory/recommended fixes
                        │
                        ▼
              REVISE (creator LLM gets ALL fixes: mandatory + recommendations)
                        │
                        ▼
              RE-REVIEW (N+1 review)
                        │
                        ├── no mandatory issues → PASS
                        │
                        └── mandatory issues remain → ESCALATE TO HUMAN (hard stop)
```

- **Round 0:** Initial review. If clean, pass immediately.
- **Round 1:** Creator receives ALL fixes (mandatory + recommendations). Revises.
- **Round 2 (N+1):** Final review. Any remaining mandatory issues = human escalation (pipeline stops with resume capability).

Reviewer output is structured JSON: `{overall_score, blocking_issues[], recommended_fixes[], ...}`.
Aggregation: weighted mean across personas. Audience persona has veto power (any blocking_issue from audience = mandatory).

---

## Resume / recovery

State is persisted to `<project_dir>/state.json` after every step. On failure:

```bash
# Resume from where it stopped:
python3 scripts/produce.py --resume Videos/Projects/my_project_short

# Resume from a specific step (re-run that step):
python3 scripts/produce.py --resume Videos/Projects/my_project_short --from-step compile_media_plan
```

State tracks: seed, format, completed_steps[], per-step results, last error. The orchestrator finds the first incomplete step and resumes from there.

After human escalation (review loop failure), fix the artifact manually, then resume from the review step to re-validate.

---

## Cost model

| Model | Use | Tokens/sec | Cost |
|-------|-----|-----------|------|
| seedance_2_0 | Hero lipsync | 9 tok/s | $0.049/token |
| kling3_0 | B-roll, hero cutaway | 6 tok/s | $0.049/token |
| local_graphic | Graphics, kinetic text | 0 | Free |

**Pricing:** 1000 tokens = USD $49 → $0.049/token

**Budget caps by format:**
| Format | Token cap | USD cap |
|--------|----------|---------|
| short | ~510 | $25 |
| explainer | ~1224 | $60 |
| teaser | ~200 | $5 |

**Example:** A 5-second hero_lipsync beat = 5 × 9 = 45 tokens = $2.21. A 5-second b-roll = 5 × 6 = 30 tokens = $1.47.

---

## Architectural decisions

### LLM fills creative, Python fills routing
The storyboard director LLM outputs only creative fields: shot_type, visual_brief, narrative_function, subject, action, camera, setting, continuity_anchor, graphic layout/text. Then `hydrate_beats()` in `direct_storyboard.py` deterministically fills all routing/mechanical fields (model, asset_type, cost, duration clamping, word spans, prompt_class, audio_mode, fallback strategy) based solely on shot_type. This separation means:
- LLM cannot route to banned models or mis-price a beat
- Duration limits are enforced mechanically
- Cost estimates are always consistent with the routing table

### project_id enforcement
After every step, `_enforce_project_id()` ensures all JSON artifacts (script.json, storyboard.json, media_plan.json) have `project_id` equal to the directory name. Downstream scripts derive paths as `ROOT/Videos/Projects/{project_id}/...`, so a mismatch would break the pipeline.

### Continuous voiceover mode
One master narration file (continuous.mp3) serves the entire video. The timing map slices it per-beat for assembly. Hero lipsync beats get audio slices from this master for Seedance generation, but at assembly time their baked audio is used verbatim (never overlaid with narration).

### No monolithic orchestrator
Each step is a standalone CLI that reads JSON in, writes JSON out. `produce.py` is a thin sequencer — it calls functions, saves state, and enforces project_id. The scripts remain independently testable.

### Gate system
Gate A (budget) and Gate B (review) are the only human touchpoints. Everything else is fully automated. The pipeline hard-fails (never silently degrades) on: review escalation, QA failure, compliance errors, or generation failure.

---

## Project directory layout

```
Videos/Projects/<slug>_<format>/
├── state.json              # Pipeline state (resume point)
├── transcripts/            # LLM prompt/output logs per step
├── research_brief.json     # Step 1 output
├── script.json             # Steps 2-3 output
├── storyboard.json         # Steps 4-5 output
├── narration/
│   ├── continuous.mp3      # Step 6 output (master)
│   ├── *.mp3               # Per-segment audio
│   └── beat_timing_map.json # Step 7 output
├── media_plan.json         # Steps 9-10 output
├── media_qa_report.json    # Step 13 output
├── manifest.json           # Step 14 output
├── review_rounds/          # Review loop transcripts
├── *_16x9.mp4             # Final assembled video
└── assets/media/           # Generated clips (step 12)
```

---

## LLM interaction

All LLM calls go through `scripts/llm_call.py`, which wraps `kiro-cli --no-interactive --agent pipeline`. The pipeline agent is lightweight (no hooks, no auto-loading). Model routing is controlled by `configs/llm_models.yaml`:
- Creative tasks (script writing, storyboard direction, review): `sonnet_creative` profile
- Utility tasks: `auto` profile

Creative-authority enforcement: only Sonnet-class (or higher) models may make creative decisions.

---

## First successful run

- **Topic:** "using AI to help memory retention"
- **Format:** short
- **Beats:** 10
- **Spend:** $6.48
- **Output:** 44.7MB MP4
