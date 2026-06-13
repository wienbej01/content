# Architecture — YTchannel (Leverage Mind)

**Generated:** 2026-06-12
**Status:** Audit-accurate. Describes the implemented system as of this date.

---

## Directory Map

```
~/YTchannel/
├── scripts/              ← All production Python entry points
│   ├── assemble.py           Production: manifest → final MP4s
│   ├── tts.py                Production: script.json → ElevenLabs narration + manifest.json
│   ├── generate_media.py     Production: script.json → Higgsfield MP4 clips
│   ├── storyboard.py         Implemented: script.json → storyboard.json (deterministic rules)
│   ├── review_script.py      Implemented: script.json → LLM review report
│   ├── review_storyboard.py  Implemented: storyboard.json → rule-based QA
│   ├── review_media_plan.py  Implemented: script.json → LLM visual plan review
│   ├── compile_media_prompts.py  Implemented: storyboard.json → prompt plan (has stale model)
│   ├── qa_media.py           Implemented: script.json → technical QA of generated clips
│   ├── shot_router.py        Implemented: shot_type → model routing (tests stale)
│   ├── llm_call.py           Implemented: kiro-cli subprocess wrapper
│   ├── generate_content_brief.py  Implemented: topic → content brief
│   ├── generate_hooks.py     Implemented: topic → hook variants
│   ├── audio_timing.py       Implemented: narration → silence-based timing map
│   ├── media_pack.py         Implemented: asset planning + validation helper
│   ├── generate_reference_assets.py  Implemented: reference asset generation
│   ├── content_db.py         Unknown: content DB helper (not yet audited deeply)
│   ├── audio_qa.py           Implemented: audio QA helper
│   ├── generated/            Generated script JSON files (source of truth for each project)
│   └── archive/              Legacy scripts (not audited in this pass)
│
├── configs/
│   ├── james/
│   │   ├── model_routing.yaml   Higgsfield model → shot_type routing config (canonical)
│   │   └── voice_spec.yaml      Kling TTS voice spec (CLI-only fallback; NOT used in production)
│   └── llm_models.yaml          LLM model routing (kiro-cli profiles + creative authority)
│
├── docs/
│   ├── SYSTEM_OVERVIEW.md        [NEW — this audit]
│   ├── ARCHITECTURE.md           [NEW — this audit]
│   ├── PIPELINE_IMPLEMENTED.md   [NEW — this audit]
│   ├── PIPELINE_GAPS_AND_PENDING_STEPS.md  [NEW — this audit]
│   ├── OPERATING_GUIDE.md        [NEW — this audit]
│   ├── REVIEW_AND_QUALITY_SYSTEM.md  [NEW — this audit]
│   ├── DOCUMENTATION_AUDIT.md    [NEW — this audit]
│   ├── NEXT_LLM_HANDOVER.md      [NEW — this audit]
│   ├── RESEARCH_SOP.md           Active: research sourcing discipline
│   ├── channel_universe/         Active: universe bibles + constraints
│   │   ├── constraints.json          Machine-readable production constraints
│   │   ├── UNIVERSE_BIBLE.md
│   │   ├── TECHNICAL_BIBLE.md
│   │   ├── JAMES_CHARACTER_BIBLE.md
│   │   ├── JAMES_RECORDING_STUDIO_LIBRARY.md
│   │   ├── BACKGROUND_CAT_BIBLE.md
│   │   ├── PEOPLE_AND_EXTRAS_BIBLE.md
│   │   ├── FORBIDDEN_PATTERNS.md
│   │   ├── PROMPT_RULES.md
│   │   ├── QA_RUBRIC.md
│   │   ├── REFERENCE_ASSET_MANIFEST.md
│   │   ├── VOICE_LOCKING.md
│   │   └── README.md
│   ├── plans/                    Operational planning docs (mix of active + stale)
│   ├── reviewer_prompts/         LLM reviewer persona prompts
│   ├── prompts/                  Script prompt library
│   ├── reference_assets/         Reference asset planning docs
│   ├── llm/                      EMPTY (placeholder)
│   ├── pipeline/                 EMPTY (placeholder)
│   ├── media_qa/                 EMPTY (placeholder)
│   ├── storyboard/               EMPTY (placeholder)
│   ├── audio/                    EMPTY (placeholder)
│   └── media_prompting/          EMPTY (placeholder)
│
├── tests/                    Test suite (13 fail, 7 error, 137 pass)
├── tools/                    Utilities: music gen, Telegram notify, narrative speed
├── brand/                    Brand assets (endcards, fonts, BRAND_SPEC.md, prompts)
├── assets/
│   ├── media/                Generated media clips
│   │   ├── flagship_001/     001_hook.mp4 + shots/ (151 clips)
│   │   └── archive/          Old voice test clips
│   ├── music/                Music bed files
│   └── reference/            Character + studio reference images
├── Videos/
│   ├── Projects/             Per-project output dirs (manifest, narration, final MP4s, logs)
│   ├── Completed/            Older completed videos
│   ├── QA/                   Audio compare packs
│   └── Regression/           Regression test fixtures
├── research/
│   ├── briefs/               Research briefs + script drafts
│   └── source_logs/          Research source logs
├── strategy/                 Business plan, timeplan, architecture docs
│   └── archive/              Superseded architecture docs
├── inspi/                    Inspiration / competitive research
├── node_modules/@higgsfield/ Higgsfield CLI (Node.js)
├── .kiro/agents/             ytbuilder agent config
└── schemas/                  JSON schema directory (empty — scaffolding only)
```

---

## Main Modules

| Module | Path | Role |
|---|---|---|
| Assembly engine | `scripts/assemble.py` | ffmpeg-based video assembly from manifest |
| TTS pipeline | `scripts/tts.py` | ElevenLabs API → narration MP3s + manifest |
| Media generation | `scripts/generate_media.py` | Higgsfield CLI → video clips |
| Storyboard gen | `scripts/storyboard.py` | Script → storyboard JSON |
| Script review | `scripts/review_script.py` | LLM multi-persona review |
| Storyboard review | `scripts/review_storyboard.py` | Rule-based storyboard QA |
| Media plan review | `scripts/review_media_plan.py` | LLM visual plan review |
| Prompt compiler | `scripts/compile_media_prompts.py` | Storyboard → constrained prompts |
| Media QA | `scripts/qa_media.py` | Technical QA on generated clips |
| Shot router | `scripts/shot_router.py` | Shot type → Higgsfield model routing |
| LLM wrapper | `scripts/llm_call.py` | kiro-cli subprocess wrapper |
| Content brief | `scripts/generate_content_brief.py` | Topic → content brief via LLM |
| Hook generator | `scripts/generate_hooks.py` | Topic → scored hook variants |
| Audio timing | `scripts/audio_timing.py` | Narration silence → timing map |
| Asset validator | `scripts/media_pack.py` | Asset existence + format validation |

---

## Data and Artifact Flow

```
research/briefs/{project}.json          ← Human-curated research
        ↓  [Human writes]
scripts/generated/{project_id}.json     ← Source-of-truth script JSON
        ↓
scripts/review_script.py               → Videos/Projects/{id}/script_review.json
scripts/storyboard.py                  → storyboard.json (per project or scripts/generated/)
scripts/review_storyboard.py           → review result (pass/fail)
scripts/compile_media_prompts.py       → *_prompt_plan.json (not yet used in 001)
        ↓
scripts/generate_media.py              → assets/media/{project}/shots/*.mp4
        ↓
scripts/tts.py                         → Videos/Projects/{id}/narration/*.mp3
                                       → Videos/Projects/{id}/manifest.json
        ↓
scripts/assemble.py                    → Videos/Projects/{id}/{id}_16x9.mp4
                                       → Videos/Projects/{id}/{id}_9x16.mp4
                                       → Videos/Projects/{id}/{id}_log.json
```

---

## External Dependencies

| Dependency | Purpose | Config |
|---|---|---|
| ElevenLabs API | TTS narration | `ELEVENLABS_API_KEY` in `~/.config/ytchannel/runtime.env`; voice ID in script JSON or `ELEVENLABS_VOICE_ID` env |
| Higgsfield CLI | Video generation | `node_modules/@higgsfield/cli` — must be authenticated via `higgsfield.js auth login` |
| ffmpeg / ffprobe | Video processing, probing, assembly | System install (must be in PATH) |
| kiro-cli | LLM calls (creative tasks) | Must have active session — wraps via subprocess |
| Node.js | Higgsfield CLI runtime | System install |

---

## Configuration Model

| File | Purpose | Status |
|---|---|---|
| `configs/llm_models.yaml` | LLM model profiles + creative authority routing | Active, current |
| `configs/james/model_routing.yaml` | Higgsfield model routing by shot type | Active, current (updated 2026-06-09) |
| `configs/james/voice_spec.yaml` | Kling native TTS voice spec | Stale — documents CLI-only fallback not used in production |
| `docs/channel_universe/constraints.json` | Machine-readable production constraints | Active but has stale model (wan2_7 in model_routing_policy) |
| `~/.config/ytchannel/runtime.env` | API keys (not in repo) | Required for TTS and Telegram |

---

## Execution Model

Scripts are invoked directly as Python CLI commands from the repo root. There is no orchestration framework, no scheduler, no Makefile. Each script is standalone.

```bash
# Standard production sequence for a new video:
python3 scripts/tts.py scripts/generated/{project}.json --validate-only
python3 scripts/generate_media.py scripts/generated/{project}.json --dry-run
python3 scripts/generate_media.py scripts/generated/{project}.json
python3 scripts/tts.py scripts/generated/{project}.json
python3 scripts/assemble.py Videos/Projects/{project}/manifest.json
```

No CI/CD. No containers. No database. State is managed via file presence on disk (if the output file exists, the step is considered done).

---

## Mermaid Architecture Diagram

```mermaid
graph TD
    A[Human: research + script.json] --> B[tts.py]
    A --> C[generate_media.py]
    B -->|narration/*.mp3| D[manifest.json]
    C -->|shots/*.mp4| D
    D --> E[assemble.py]
    E -->|16x9.mp4 + 9x16.mp4| F[Final Video]

    subgraph Review Layer (advisory)
        A --> G[review_script.py via llm_call.py]
        A --> H[storyboard.py]
        H --> I[review_storyboard.py]
        H --> J[compile_media_prompts.py]
    end

    subgraph External Services
        B --> EL[ElevenLabs API]
        C --> HF[Higgsfield CLI]
        G --> KC[kiro-cli]
    end
```

---

## Known Fragile Areas

1. **`compile_media_prompts.py` routes b-roll to `wan2_7`** (banned). Model comes from `constraints.json → model_routing_policy.grounded_broll`. Must be updated to `kling3_0`.
   Evidence: `docs/channel_universe/constraints.json:model_routing_policy`, `scripts/compile_media_prompts.py:compile_prompt()`

2. **`test_shot_router.py` expects dead models.** Tests assert `veo3` and `minimax_hailuo` — both banned/unavailable. Running the test suite gives a misleading 13-fail result.
   Evidence: `tests/test_shot_router.py` lines 32, 43

3. **`test_assemble.py` has a missing pytest fixture `log`.** All 7 assemble tests error out at setup. Not a code bug — a test design issue.
   Evidence: `tests/test_assemble.py` line 40

4. **`generate_media.py` has a `shot_type` variable reference before assignment** in the segment-level fallback path (line ~530: `elif shot_type and not model`). Variable is only set if segment has `shot_type` field, but there's no guard. Causes `UnboundLocalError` in some script shapes.
   Evidence: `scripts/generate_media.py` — look for `elif shot_type and not model:` in `run()`

5. **Higgsfield CLI is authenticated via a stored token**, not a config variable. Token must be refreshed periodically. No error handling for expired tokens beyond "Not authenticated" detection.
