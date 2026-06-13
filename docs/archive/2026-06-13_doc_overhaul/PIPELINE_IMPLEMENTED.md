# Pipeline — Implemented State

**Generated:** 2026-06-12 (updated 2026-06-12 for V2 gated pipeline)
**Scope:** Factual map of every pipeline stage — what is implemented, what runs, what produces what.

---

## Stage Table

| # | Stage | Status | Entry Point | Inputs | Outputs | Manual step? | Known Issues |
|---|---|---|---|---|---|---|---|
| 1 | Research & sourcing | **Partial** | Manual + SOP | Human research | `research/briefs/*.json`, `research/source_logs/*.json` | YES — fully manual | No automation; SOP exists (`docs/RESEARCH_SOP.md`) but is just a guide |
| 2 | Topic selection / content brief | **Implemented** | `scripts/generate_content_brief.py` | `--topic`, `--pain`, `--pillar` flags | Brief JSON with viability score + titles | YES — operator decides whether to run | Not wired into any workflow gate; ad-hoc only |
| 3 | Hook generation | **Implemented** | `scripts/generate_hooks.py` | `--topic` or `--script` | Scored hook variants JSON | YES — operator selects hook | Not wired into script; hooks are written manually into script JSON |
| 4 | Script writing | **NOT IMPLEMENTED** | None | Research brief, topic, hooks | `scripts/generated/{project_id}.json` | YES — fully manual | **Critical gap.** No `script_writer.py`. Operator writes script JSON by hand. |
| 5 | Script review | **Implemented** | `scripts/review_script.py` | Script JSON | `script_review.json` with per-persona scores + blocking issues | Partial (advisory only) | Not auto-blocking; operator must invoke; does not gate generate_media |
| 6 | Storyboard generation | **Production-grade** | `scripts/storyboard.py` | Script JSON | `Videos/Projects/{id}/storyboard.json` (schema v2) | NO (automated) | V2 router: deterministic chunking (4–10s beats), regex trigger engine, 6-act mapping, shot-mix enforcement, $0 routing for graphics/stills. `--optimize` for LLM brief refinement. |
| 7 | Storyboard review | **Production-grade (hard gate)** | `scripts/review_storyboard.py --record-gate` | `storyboard.json` | Gate ledger entry `storyboard_review` | NO (automated) | **Blocking.** Checks schema v2, §7 shot-mix bands (hero 25–40%, broll ≥25%, graphics ≥10%), max hero block ≤15s, ≥12 distinct setups, anti-patterns. All-hero shape = hard fail. Gates `compile_media_prompts.py`. |
| 8 | Media prompt compilation | **Production-grade (hard gate)** | `scripts/compile_media_prompts.py` | `storyboard.json` + `constraints.json` + `model_routing.yaml` | `Videos/Projects/{id}/media_plan.json` | NO (automated) | **Requires G2 storyboard gate.** Exits 1 if banned model, missing reference image for hero shots, or vague b-roll prompt. Per-beat cost from `model_routing.yaml`. `visual_brief` path is dead as a generation input. |
| 9 | Media plan review | **Partial (advisory)** | `scripts/review_media_plan.py` | Script JSON (not yet updated for `media_plan.json`) | LLM review JSON | NO (automated) | **Does not read `media_plan.json` yet** (reads old script JSON). Gate ledger entry must be recorded manually. See Known Gaps. |
| 10 | TTS narration | **Production-grade** | `scripts/tts.py` | Script JSON | `narration/*.mp3`, `manifest.json` | NO (automated) | `--require-gates` enforces G1 script_review gate. Caches by default; `--force` to regenerate. |
| 11 | Video generation | **Production-grade (hard gate chain)** | `scripts/generate_media.py media_plan.json` | `Videos/Projects/{id}/media_plan.json` | `assets/media/{id}/shots/*.mp4`, `media_generation_log.json` | NO (automated) | **Sole prompt source is `media_plan.json`**. Checks four spend gates before first Higgsfield call: `storyboard_review`, `media_plan_review`, `budget`, `render_approval`. Raw script `visual_brief` path is deprecated/blocked. hero_lipsync → seedance `--image --audio`; still_kenburns → local ffmpeg; local_graphic → skipped (T10 pending). |
| 12 | Media QA | **Production-grade (hard gate)** | `scripts/qa_media.py --record-gate` | Script JSON + generated clips | `*_media_qa.json` + gate ledger entry `media_qa` | NO (automated) | `--scope source` (1280×720) / `--scope assembled_16x9` (1920×1080) / `--scope assembled_9x16` (1080×1920). `--record-gate` writes gate; `assemble.py --require-gates` blocks without it. |
| 13 | Assembly | **Production-grade** | `scripts/assemble.py` | `manifest.json` | `{prefix}_16x9.mp4`, `{prefix}_9x16.mp4`, `{prefix}_log.json` | NO (automated) | Fully working. Handles shots[], continuous_voiceover, music, loudnorm, endcard, lower-third. |
| 14 | Human QA / review | **Partial** | `generate_media.py --review` | Script JSON | `review_frames/*.jpg` | YES — human reviews frames | Extract-frames tool exists; no automated visual pass/fail |
| 15 | Publishing (YouTube) | **NOT IMPLEMENTED** | None | Final MP4 | Published video | YES | No upload script exists |
| 16 | Atomization (Shorts/Reels) | **NOT IMPLEMENTED** | None | Final MP4 | Short clips | YES | Mentioned in plan but no tools built |
| 17 | Newsletter integration | **NOT IMPLEMENTED** | None | Script content | Beehiiv issue | YES | Described in business plan, nothing built |
| 18 | Telegram notification | **Implemented** | `tools/send_telegram_message.py`, `tools/notify.py` | Message / video path | Telegram message | NO (automated) | Working; used in production monitoring |

---

## Artifact Flow Detail

### Stage 4 → Stage 10: Script JSON format

`scripts/generated/{project_id}.json` — the source-of-truth file. Consumed by `tts.py`, `generate_media.py`, `review_script.py`, `storyboard.py`, `qa_media.py`.

Required fields per segment:
```json
{
  "id": "001_hook",
  "text": "narration text here",
  "audio_mode": "generated_tts | baked_in | silent",
  "media": "path/to/output/clip.mp4",
  "visual_brief": "description for media generation"
}
```

Optional per segment: `shots[]`, `trim_end`, `lower_third`, `reference_image`, `visual_prompt_override`, `model`

Top-level optional: `narration_mode` (`segment_tts` | `continuous_voiceover`), `music{}`, `output_dir`, `defaults{}`

Evidence: `scripts/sample_script.json`, `scripts/generated/flagship_001_learn_half_time.json`, `scripts/tts.py:validate_script()`

### Stage 10 → Stage 13: Manifest JSON format

`Videos/Projects/{project_id}/manifest.json` — generated by `tts.py`, consumed by `assemble.py`.

Required fields per segment: `media`, `words`
Optional: `audio` (narration file), `shots[]`, `trim_end`, `lower_third`

Two assembly paths:
1. **shots[] + audio:** Visual bed is built by concatenating multiple short clips; ElevenLabs narration is overlaid as a single continuous track. Used in flagship 001 segments 001–009.
2. **Plain video + audio:** Single video clip with narration overlaid. Used for `generated_tts` segments.
3. **baked_in (legacy):** Video already contains voice. No audio overlay. Used for single-clip lipsync only.
4. **continuous_voiceover:** One continuous narration audio + per-segment visual clips timed to narration segments. Implemented but not used in any completed production video.

Evidence: `scripts/ASSEMBLY_README.md`, `scripts/sample_manifest.json`, `scripts/assemble.py:assemble_format()`

### Stage 11: Media generation conventions

- B-roll shot files: `assets/media/{project}/shots/{seg_id}_{NNN}.mp4` (e.g. `002_promise_000.mp4`)
- All b-roll clips are generated at 1280×720, audio-stripped (for `generated_tts`)
- `assemble.py` upscales to 1920×1080 for 16:9 or 1080×1920 for 9:16 via ffmpeg scale+crop
- Lipsync clips (baked_in): include embedded audio from Higgsfield lipsync model

Evidence: `scripts/generate_media.py:generate_segment()`, `assets/media/flagship_001/shots/`

### Stage 12 → 13: QA policy

`qa_media.py` checks (V2):
- File exists
- Has video stream
- Dimensions: parameterized by `--scope`: `source` = 1280×720 (Higgsfield output); `assembled_16x9` = 1920×1080; `assembled_9x16` = 1080×1920
- Duration ≥ 2.0s
- Audio policy: `generated_tts` clips must NOT have audio; `baked_in` clips MUST have audio
- `--record-gate` writes the `media_qa` gate; `assemble.py --require-gates` blocks without it

Evidence: `scripts/qa_media.py:run_qa()`, `scripts/qa_media.py:DIMS_BY_SCOPE`

---

## Production Evidence: Flagship 001

- Script: `scripts/generated/flagship_001_learn_half_time.json` (9 segments, `baked_in` in original script, but actual production used `voiceover` + `shots[]` via v2)
- Manifest: `Videos/Projects/flagship_001_learn_half_time/manifest.json` (9 segments, all have `audio` + `shots[]`)
- Narration: `Videos/Projects/flagship_001_learn_half_time/narration/` (9 MP3 files)
- Shots: `assets/media/flagship_001/shots/` (151 clips @ 5.04s each)
- Final: `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_16x9.mp4` (354MB), `_9x16.mp4` (438MB)
- Log: `Videos/Projects/flagship_001_learn_half_time/flagship_001_learn_half_time_log.json`

---

## Naming Conventions

| Artifact | Pattern | Example |
|---|---|---|
| Project ID | `{channel}_{nnn}_{slug}` | `flagship_001_learn_half_time` |
| Script JSON | `scripts/generated/{project_id}.json` | `scripts/generated/flagship_001_learn_half_time.json` |
| Segment ID | `{nnn}_{slug}` | `001_hook`, `008_ai_layer` |
| Shot file | `assets/media/{project}/shots/{seg_id}_{NNN}.mp4` | `002_promise_000.mp4` |
| Narration | `Videos/Projects/{project}/narration/{seg_id}.mp3` | `001_hook.mp3` |
| Manifest | `Videos/Projects/{project}/manifest.json` | — |
| Final video | `Videos/Projects/{project}/{project}_{format}.mp4` | `flagship_001_learn_half_time_16x9.mp4` |

---

## Validation Rules in Force

| Rule | Where enforced | Status |
|---|---|---|
| `image media requires audio field` | `assemble.py:validate_manifest()` | Active |
| `ENG-04: segment duration vs narration ±0.5s` | `assemble.py:assemble_format()` | Active |
| `shots coverage ≥ narration + 0.25s` | `generate_media.py:run()` | Active |
| `No Higgsfield spend without four spend gates` | `generate_media.py:run_from_media_plan()` | **Active (hard gate)** |
| `media_plan.json is sole prompt source` | `generate_media.py:main()` | **Active (raw script visual_brief deprecated)** |
| `storyboard v2 schema + shot-mix bands` | `review_storyboard.py` (G2) | **Active (hard gate, records ledger)** |
| `budget cap ≤$60 explainer / ≤$25 short` | `budget.py` (G4) | **Active (hard gate, records ledger)** |
| `generated_tts clips must not have audio` | `qa_media.py:run_qa()` | Active; gate recorded with `--record-gate` |
| `baked_in requires audio stream` | `tts.py:validate_script()` | Active (validation only) |
| `text-surface risk blocks generation` | `generate_media.py:run()` | Active (can override with `--allow-text-surfaces`) |
| `banned models never routed` | `generate_media.py`, `compile_media_prompts.py`, `review_storyboard.py` | Active |
| `SHA-256 artifact staleness invalidates gates` | `gates.py:require_gates()` | **Active (hard gate)** |
| `assemble refuses without media_qa gate` | `assemble.py --require-gates` | Active (opt-in flag required) |
