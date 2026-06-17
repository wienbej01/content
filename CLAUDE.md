# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A fully automated production pipeline for faceless educational YouTube videos (MITmonk-style 6–12 min explainers) under the "Leverage Mind" brand with AI persona James Harrington. Each pipeline stage is a standalone Python 3 CLI that reads JSON/DB state and writes JSON or media artifacts; stages compose via file I/O and a transactional SQLite ledger — there is no monolithic in-process orchestrator.

## Commands

```bash
pip install pyyaml                  # the one documented Python dep
npm install                         # Higgsfield CLI (@higgsfield/cli) from package-lock.json
# Secrets live in ~/.config/ytchannel/runtime.env (ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

python3 -m pytest -q                                   # full suite (~900 tests)
python3 -m pytest tests/test_assemble.py -k lipsync    # focused subset
python3 -m pytest tests/test_gates.py::test_name       # single test
python3 strategy/plan.py status                        # milestone state (YAML-backed)
```

- Most stage CLIs accept `--dry-run` to validate without billable output. Use it.
- `assemble.py` / `qa_*` require `ffmpeg` and `ffprobe` on PATH.
- No repo-wide formatter is configured. Match nearby code: 4-space indent, `snake_case`, `UPPER_SNAKE_CASE` constants, `argparse` + `pathlib.Path` + explicit exit codes + useful stderr errors. Pyright runs over `scripts/` and `tools/` (Python 3.13, see `pyrightconfig.json`).

## Two coexisting execution models (important)

The repo is mid-migration from file-led state to a DB-native ledger. Both exist; know which you're touching:

1. **Legacy file-led pipeline** — stages read/write JSON artifacts under `Videos/Projects/<slug>/`, with `scripts/gates.py` enforcing a SHA-256-bound gate ledger. The README documents this model in detail (gate table, key scripts).
2. **DB-native orchestrator** (`scripts/produce_db.py` → `stage_runner.py` → `production_db.py`) — the current single source of truth for execution. `STAGE_REGISTRY` in `stage_runner.py` defines the canonical stage graph with `depends_on`, `produces_kinds`, and `consumes_kinds`. Document lineage drives **dependency invalidation**: editing an upstream document marks downstream stages stale automatically. `production_db.py` records identity, lifecycle, checksums, lineage, and evidence; media payloads stay in the artifact store. Migrations are SQL files in `db/migrations/`.

`stage_runner.LegacyAdapter` wraps legacy file-led stages so they run inside the DB stage graph. `produce_db.py`'s pre-TTS invokers (research/script/storyboard) write directly through `authoring_service.py`, bypassing legacy file authority; later stages still bridge to the legacy scripts.

The canonical stage order: `research → write_script → review_script → gate_a_content → tts → audio_timing → storyboard → review_storyboard → compile_media → gate_a_spend → generate_media → qa_media → assemble → qa_final → gate_b_review → publish → analytics`.

`scripts/run_episode.py` is the LLM creative-chain orchestrator (research → script → reviewers → storyboard → reviewers) with a feedback/revision loop that escalates to the human via Telegram at round 3.

## Architectural invariants

- **Gates are the spend primitive.** No Higgsfield/ElevenLabs call is possible without passing all required gates. Gates bind to artifact SHA-256 hashes — editing an artifact after its gate passed invalidates the gate. There is no `--force-unsafe` in production. Human-in-the-loop exists at exactly two points: storyboard content approval and render spend approval.
- **`media_plan.json` is the single source of truth** post-compile: it carries every prompt, cost, reference image, audio slice, and output path. Generation, QA, and assembly all read it.
- **Assembly is deterministic and AI-free.** Same manifest + same clips = same output (ffmpeg-driven).
- **Clip identity:** `clip_id` is the universal key (UCI contract); the clip authority DB (`clip_db.py`) reconciles DB validity against the filesystem.
- **Lipsync (non-negotiable):** a `hero_lipsync` beat MUST produce a lipsync clip or hard-fail — no silent fallback to stills. Model is Seedance 2.0 (only model with `--audio`); clips 4–10s; baked lipsync audio is preserved verbatim at assembly (`-map 0:a`), never overlaid with narration; provenance hash verified at assembly. Output path `assets/media/{segment_id}/{beat_id}.mp4` is the single source for generation, QA, and assembly.
- **Shot-mix bands** (enforced by `review_storyboard.py`) and the **6-Act MITmonk structure** (`inspi/MITmonk.md`) govern storyboard validity — see README for the band percentages.

## Hard rule for fixes (`.kiro/rules/no-hacks.md`)

When you hit a runtime error or data mismatch: diagnose the **root cause in pipeline code** and fix the script/function that produces or consumes the data. **Never** manually edit intermediate JSON, state files, DB rows, or outputs to work around a bug. The goal is a repeatable, scalable system — patching artifacts defeats it.

## Tests

`tests/test_<stage>.py` mirror pipeline behavior; ticket-scoped suites use the ticket id (e.g. `test_lb301_slicing.py`, `test_uci04_assemble_db.py`). `conftest.py` autouse fixtures isolate every test's clip DB and production DB into tmp dirs (via both in-process `_db_path_override` and `*_DB_PATH` env vars, so subprocess-launched CLIs are isolated too). Tests must avoid paid APIs — use `--dry-run`, mocks, or deterministic fixtures. Add focused regression tests for every behavior change, especially gates, schema validation, audio timing, routing, and generated-file side effects.

## Config & docs that drive behavior

- `configs/james/model_routing.yaml` — voice lock, Higgsfield model routing, lipsync reference sets, budget caps, costs.
- `configs/llm_models.yaml` — LLM profiles; only Sonnet-class+ models may make creative decisions (auto/Haiku blocked from creative approval). `scripts/llm_call.py` wraps `kiro-cli --no-interactive` with this routing.
- `docs/channel_universe/constraints.json` — machine-readable production rules: shot-mix bands, forbidden patterns, negative prompts, text/audio policy, crop safety, `lipsync_render_rules`.
- `docs/reviewer_prompts/` — 5 LLM reviewer personas (filmmaker, technical, universe, audio, audience) that score and can veto.
- `README.md` documents the legacy gate table and full script inventory; `AGENTS.md` has contributor conventions; `strategy/TIMEPLAN.yaml` + `plan.py` track plan state across sessions.

> Note: the README's "247 tests" and 54%-complete figures are stale relative to the DB-native cutover (the suite is now ~900 tests). Trust the code and `plan.py status` over those numbers.
