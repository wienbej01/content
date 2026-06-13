# System Overview — YTchannel (Leverage Mind)

**Generated:** 2026-06-12
**Scope:** As-built documentation of the implemented AI video production pipeline
**Repo:** `~/YTchannel`
**Status:** Audit-accurate as of 2026-06-12. Not aspirational.

---

## System Purpose

This repo is an AI-native content production system for a faceless YouTube channel targeting mid-career professionals. The nominal end-to-end flow is:

```
Research → Topic selection → Script (manual) → Storyboard → LLM review →
Media generation (Higgsfield) → TTS narration (ElevenLabs) →
Assembly (ffmpeg) → QA → Upload
```

The channel character is **James Harrington** — an AI-generated British presenter. Content pillars: AI for professional leverage, learning/productivity, career capital.

Evidence: `strategy/BUSINESS_PLAN.md`, `docs/channel_universe/UNIVERSE_BIBLE.md`

---

## Current Maturity Assessment

| Layer | Status |
|---|---|
| Assembly engine (`assemble.py`) | **Production-grade** — fully working, handles shots[], 16x9+9x16, music, loudnorm |
| TTS narration (`tts.py`) | **Production-grade** — ElevenLabs eleven_v3, caching, manifest generation |
| Media generation (`generate_media.py`) | **Production-grade** — Higgsfield CLI, lipsync + b-roll, multi-shot coverage, retries |
| Review gates (`review_script.py`, `review_storyboard.py`) | **Implemented** — but wired manually, not auto-blocking |
| Storyboard generator (`storyboard.py`) | **Implemented** — deterministic rules, optional LLM optimize |
| Prompt compiler (`compile_media_prompts.py`) | **Implemented** — but uses stale model in constraints.json (wan2_7, banned) |
| LLM wrapper (`llm_call.py`) | **Implemented** — kiro-cli subprocess wrapper |
| Content brief (`generate_content_brief.py`) | **Implemented** |
| Hook generator (`generate_hooks.py`) | **Implemented** |
| **Script writing** | **NOT IMPLEMENTED** — scripts are manually hand-crafted JSON |
| Publishing / upload pipeline | **NOT IMPLEMENTED** |
| Atomization (Shorts/Reels/TikTok) | **NOT IMPLEMENTED** |
| Content calendar / scheduling | **NOT IMPLEMENTED** |

**Overall system maturity: ~50%.** The downstream half (media → assemble → final video) is solid. The upstream half (research → script → structured production) is mostly manual or ad-hoc.

---

## Implemented Pipeline Summary

The pipeline that actually works today:

```
[Human writes script.json manually]
        ↓
tts.py — ElevenLabs TTS per segment → narration/*.mp3 + manifest.json
        ↓
generate_media.py — Higgsfield CLI → shot MP4s in assets/media/
        ↓
assemble.py — ffmpeg assembly from manifest → final_16x9.mp4 + final_9x16.mp4
```

The storyboard/review pipeline is implemented but is used ad-hoc, not as a blocking gate.

**First production video completed:** `flagship_001_learn_half_time` — 9 segments, 151 Higgsfield b-roll shots, ElevenLabs narration, fully assembled.

Final files:
- `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_16x9.mp4` (354MB)
- `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_9x16.mp4` (438MB)

Evidence: `Videos/Projects/flagship_001_learn_half_time/manifest.json`, `scripts/assemble.py`, `scripts/tts.py`

---

## Manual vs Automated Steps

| Step | Automation | Notes |
|---|---|---|
| Research / source gathering | Manual | `docs/RESEARCH_SOP.md` defines the SOP; `research/briefs/` holds output |
| Topic selection | Manual | Brief generation via `generate_content_brief.py` is available but not enforced |
| Hook writing | Manual (LLM assist via `generate_hooks.py`) | Tool exists, not integrated into workflow |
| Script writing | **Fully manual** | No `script_writer.py` exists; human writes script.json by hand |
| Script review | Semi-automated (`review_script.py`) | Available but operator must explicitly invoke |
| Storyboard generation | Automated (`storyboard.py`) | Deterministic defaults; LLM optimize is optional |
| Storyboard review | Automated (`review_storyboard.py`) | Rule-based; available but not blocking |
| TTS narration | Automated (`tts.py`) | Fully hands-off if script.json is valid |
| Media generation | Automated (`generate_media.py`) | Requires Higgsfield auth + credits; long-running |
| Media QA | Semi-automated (`qa_media.py`) | Available but not enforced pre-assembly |
| Assembly | Automated (`assemble.py`) | Fully hands-off from manifest |
| QA / review | Manual (frame extraction via `--review`) | Human reviews frames; no automated visual pass/fail |
| Publishing | **Fully manual** | No upload scripts exist |

---

## Main Pain Points

1. **No script generator.** The most labor-intensive step is fully manual. A bad script cannot be fixed by improving the downstream pipeline.

2. **Tests are stale.** 20 tests fail or error. `test_shot_router.py` expects old banned models (veo3, minimax_hailuo). `test_assemble.py` has a missing pytest fixture. `test_generate_media.py` has a code bug (`shot_type` variable undefined). Running `pytest` in CI would give a false failure signal.

3. **constraints.json has a banned model.** `model_routing_policy.grounded_broll` still says `wan2_7` which is banned. `compile_media_prompts.py` reads this — running it would route b-roll to a banned model.

4. **Hook segment still has wrong voice.** `001_hook.mp4` has Kling-native audio, not ElevenLabs. The assembled flagship 001 clips this via the `audio` field in the manifest overriding it, but the source clip is wrong and the published video should be verified.

5. **No publishing workflow.** After assembly, everything is manual: YouTube upload, metadata, shorts cut, newsletter.

6. **Empty placeholder dirs.** `docs/llm/`, `docs/pipeline/`, `docs/media_qa/`, `docs/storyboard/`, `docs/audio/`, `docs/media_prompting/` are all empty. They were created as scaffolding but never filled.

7. **No continuous narration mode for production.** `constraints.json` sets `final_video_narration_mode: continuous_voiceover` but flagship 001 was assembled in `segment_tts` mode with per-segment audio. Continuous voiceover is implemented but never used in production.

---

## What a New Developer/LLM Must Understand First

1. **The script JSON is the source of truth.** All downstream tools consume `scripts/generated/{project_id}.json`. Everything branches from there.

2. **The manifest JSON is the assembly input.** `tts.py` generates `Videos/Projects/{project_id}/manifest.json` from the script. `assemble.py` consumes it.

3. **Media paths are ROOT-relative by convention.** Bare paths in scripts (e.g. `assets/media/…`) are resolved from `~/YTchannel`. Explicit relative paths (starting with `../`) are resolved from the script file's parent.

4. **Two distinct generation paths exist in assemble.py:**
   - `shots[] + audio field` (used for flagship 001 segments 001–009): multiple visual clips are concatenated into a visual bed, then ElevenLabs narration is overlaid.
   - `baked_in` (legacy / single-clip lipsync): the video file already contains the voice. Used only when Higgsfield lipsync is directly generated with `--audio` input.

5. **Higgsfield CLI is the video generation tool.** It runs as a Node.js CLI (`node node_modules/@higgsfield/cli/bin/higgsfield.js`). It must be authenticated. Current live models: `seedance_2_0` (lipsync), `kling3_0` (b-roll). `wan2_7`, `minimax_hailuo`, `veo3` are banned or unavailable.

6. **LLM calls go through kiro-cli.** `llm_call.py` wraps `kiro-cli chat` subprocess. It does not use API keys directly. The creative authority model is `claude-sonnet-4.5`; utility tasks use `auto`.

7. **The channel universe is in `docs/channel_universe/`.** Before any media generation, the bibles (UNIVERSE_BIBLE, TECHNICAL_BIBLE, JAMES_CHARACTER_BIBLE, constraints.json) define what is allowed and what is forbidden.

Evidence: `scripts/assemble.py`, `scripts/tts.py`, `scripts/generate_media.py`, `scripts/llm_call.py`, `docs/channel_universe/constraints.json`, `configs/james/model_routing.yaml`
