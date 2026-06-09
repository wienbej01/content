# M4–M10 Implementation Prompts (for cheaper coding models)

Each prompt is self-contained. Run one sprint at a time. All prompts assume working dir `/home/jacobw/YTchannel` and `python3`. Every prompt ends by requiring the model to (a) run the relevant tests, (b) confirm M1–M3 tests still pass, (c) print files changed, (d) confirm no API calls / no credits / no token printed.

**Hard rules injected into every sprint:** Do not touch `scripts/{assemble,tts,generate_media,media_pack}.py` behavior except where the sprint explicitly says (additive only). Do not call Higgsfield or ElevenLabs. Do not regenerate TTS. Do not overwrite `assets/media/james_teaser/*` or any teaser_01 output. Do not add n8n / database / provider abstraction / state machine. Never print API tokens (use `[configured]`).

---

## Sprint M4.1 — Universe Bible docs
(See verbatim prompt in `M4_M10_CREATIVE_CONTROL_WORKPLAN.md` §16.)
Creates the 6 universe docs under `docs/channel_universe/`. No code. Acceptance: docs exist, cite BRAND_SPEC, fill all checklists in `M4_M10_SCHEMA_DESIGN.md`.

---

## Sprint M4.2 — Technical Bible + rules + QA + constraints.json
> Writer role. Read `brand/BRAND_SPEC.md`, workplan §4B/§4 rules/§9, and the M4 checklists. Create `docs/channel_universe/{TECHNICAL_BIBLE,FORBIDDEN_PATTERNS,PROMPT_RULES,QA_RUBRIC}.md` and `docs/channel_universe/constraints.json` (exact content in `M4_M10_SCHEMA_DESIGN.md`). Ensure zero contradictions with M4.1 docs. The automatic-fail list in QA_RUBRIC must match workplan §9 verbatim. No code beyond writing the JSON file. Report files created.

---

## Sprint M4.3 — Reference asset manifest + folders
> Read workplan §4 + `M4_M10_SCHEMA_DESIGN.md` "REFERENCE_ASSET_MANIFEST". Create `docs/channel_universe/REFERENCE_ASSET_MANIFEST.md` and empty folders `assets/reference/{james,studio_library,cat,wardrobe,color_palette,props}/` each with a `.gitkeep`. Map existing `brand/James_harrington_{front,3_4,side,vertical}.png` as seed entries (`JAMES_FRONT_DESK_001` etc., status `seed_needs_review`). Do NOT move or modify the brand PNGs — reference them by path. No image generation. Report files created.

---

## Sprint M5.1 — Storyboard schema + generator (validate/dry-run)
> Coding role, python3 + stdlib only. Read workplan §5 and `M4_M10_SCHEMA_DESIGN.md` storyboard schema. Create `schemas/storyboard.schema.json` (draft-07, documentation), `scripts/storyboard.py` (CLI: `--validate <file>` runs hand-rolled stdlib validation matching the schema; `--dry-run` prints what an LLM beat-draft would request, no API call), and `docs/storyboard/README.md`. Mirror the validation style of `scripts/tts.py:validate_script`. Create `tests/test_storyboard.py` with property tests (valid storyboard passes; missing required field fails; unknown scene_type fails). Run `python3 tests/test_storyboard.py`. Confirm `python3 tests/test_tts.py`, `test_assemble.py` (against an existing log), `test_generate_media.py`, `test_media_pack.py` still pass. No API calls. Report files + test results.

---

## Sprint M5.2 — Storyboard QA checks
> Extend `scripts/storyboard.py` with a `--qa <file>` mode that checks: A-roll/B-roll ratio against bands (WARN outside band), james_presence (hard-FAIL if 0% present in a host-led episode where `allow_all_broll` is false), audio_continuity_group consistency. Add tests to `tests/test_storyboard.py`: ratio-warning fixture, zero-James hard-fail fixture. Read `constraints.json` for the bands. Run tests; confirm M1–M3 green. Report.

---

## Sprint M6.1 — Reviewer prompts + structured output
> Coding role. Read workplan §6. Create `docs/reviewer_prompts/{filmmaker,technical,audience,universe,audio}.md` (the persona system prompts). Create `scripts/review_script.py`, `scripts/review_storyboard.py`, `scripts/review_media_plan.py` — each takes an input JSON + `--dry-run` (prints the assembled prompt, no API) and (when not dry-run) calls an LLM and emits the reviewer output schema (`M4_M10_SCHEMA_DESIGN.md`). Use a pluggable `call_llm(prompt)` function that reads `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` from env/runtime.env; in tests, monkeypatch/stub it to return canned JSON. Create `tests/test_review_gates.py`: stub LLM, assert aggregation (`may_proceed`), assert an all-b-roll storyboard fixture is blocked. No live API in tests. Never print keys. Run tests; confirm M1–M3 green. Report.

---

## Sprint M7.1 — Continuous narration timing schema + offline map builder
> Coding role, python3 + ffmpeg/ffprobe (already used). Read workplan §7 + audio_timing schema. Create `schemas/audio_timing.schema.json` and `scripts/audio_timing.py` that takes a LOCAL narration audio file + the script text and builds a timing map (sentences via silence detection like `tools/narrative_speed.py`, WPS, pauses, flags). No TTS, no API — operates on a provided file. Create `tests/test_continuous_narration.py` using a locally-generated test tone/wav (ffmpeg lavfi) — no ElevenLabs. Run tests; confirm M1–M3 green. Report.

---

## Sprint M7.2 — tts.py continuous_voiceover mode (ADDITIVE)
> Coding role. Extend `scripts/tts.py`: add support for `narration_mode: continuous_voiceover` in the script JSON. When set, generate ONE narration file for the concatenated script text (single ElevenLabs call) instead of per-segment, and write a timing map via `audio_timing.py`. DEFAULT remains `segment_tts` — existing behavior and tests must not change. Live ElevenLabs only runs on explicit non-dry execution with credentials; tests stub it and assert the default path is untouched. Add `tests/test_continuous_narration.py` cases for mode selection (no API). Confirm `test_tts.py` still 13/13. Reuse-cache + `--force` semantics preserved. Never print keys. Report. NOTE: assembly consumption of continuous narration is a SEPARATE later task — coordinate with the §14 assembly-mode design before wiring assemble.py.

---

## Sprint M8.1 — Media prompt compiler
> Coding role, python3 + stdlib. Read workplan §8 + media_prompt_plan schema + `docs/channel_universe/constraints.json`. Create `scripts/compile_media_prompts.py` that takes a storyboard JSON, reads `constraints.json` + bibles, and emits `media_prompt_plan.json` where every prompt embeds the default negative block + beat forbidden_elements, tags a_roll/b_roll, sets model (`seedance_2_0` for A-roll/James-present, `wan2_7` for b-roll), lists reference_assets for A-roll/studio/cat, and sets audio_policy/crop_safety/text_policy. Create `schemas/media_prompt_plan.schema.json` and `tests/test_media_prompt_compiler.py` (fixture storyboard → assert negatives present, A-roll has James refs, b-roll grounded). No API. Confirm M1–M3 green. Report.

---

## Sprint M9.1 — Media QA technical checks
> Coding role, python3 + ffprobe. Read workplan §9 + media_qa schema. Create `scripts/qa_media.py` (technical checks only: readable, has_video, has_audio, dimensions, duration, codec, crop heuristic) → `media_qa_report.{json,md}`. Implement the canonical fail conditions that are deterministically checkable (e.g., `generated_tts` clip that still has an audio stream → fail; wrong dimensions → fail). Create `schemas/media_qa.schema.json` and `tests/test_media_qa.py` using ffmpeg-generated fixture clips (a clip WITH audio tagged generated_tts must fail). No API. Confirm M1–M3 green. Report.

---

## Sprint M9.2 — Media QA creative checklist + manual fallback
> Extend `scripts/qa_media.py` with creative checks BEHIND a `--creative` flag (vision model). Default OFF (cost). Provide a `--manual-review` mode that sends each clip to Telegram via `tools/send_telegram_message.py` for human approve/reject (reuse existing). Tests stub the vision call. No vision API in CI. Report.

---

## Sprint M10.1 — Rebuild teaser plan only
> Writer/coding-light role. Create `docs/plans/TEASER_02_REBUILD_RUNBOOK.md` (exact command sequence for the full pipeline) and `scripts/generated/james_growth_system_teaser_02.json` (refined script ONLY — no media, audio_mode set, visual intent noted as storyboard input, NOT raw visual_brief). Guarantee in the runbook: new project_id, no overwrite of teaser_01. No generation. Report.

---

## Sprint M10.2 — Controlled one-segment regeneration
> Run the new pipeline (storyboard→compile→generate→QA→assemble) for ONE beat into a temp project/path, like the M3-A smoke test. Minimal credits, explicit. Do not touch teaser_01/02 finals. Send result to Telegram. Report credits spent + QA result.

---

## Sprint M10.3 — Full teaser_02 regeneration
> Only after human approval of the storyboard + the M10.2 one-segment proof. Generate teaser_02 end-to-end. Never overwrite teaser_01. Send to Telegram. Report.
