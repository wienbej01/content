# YTchannel — Faceless AI-Native Video Production Pipeline

A fully automated production pipeline for faceless educational YouTube content, targeting mid-career white-collar professionals in the wealth/productivity/self-improvement niche. The system generates MITmonk-style explainer videos (6–12 min) with a consistent AI brand persona (James Harrington), from script through final assembly.

**Owner:** pseudonymous, part-time (~6–10 hrs/wk), online-only
**Brand:** Leverage Mind | Voice: James Harrington (ElevenLabs eleven_v3)
**Status:** 54% of plan complete (30/55 steps); first flagship video in production

---

## Quick start

```bash
pip install pyyaml
npm install                         # Higgsfield CLI
# Add secrets to ~/.config/ytchannel/runtime.env (ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

python3 strategy/plan.py status     # see what's done / next
python3 -m pytest -q                # run the full test suite (247 tests)
```

---

## Repository structure

```
YTchannel/
├── scripts/          # Production pipeline scripts (the core engine)
├── tools/            # Utility scripts (music, narration speed, Telegram notifications)
├── configs/          # Model routing, voice settings, LLM profiles
├── docs/
│   ├── channel_universe/  # Bibles, constraints, QA rubric (creative rules)
│   ├── plans/             # Sprint plans, ticket boards, audits
│   ├── prompts/           # Script/prompt library for LLM content generation
│   ├── reviewer_prompts/  # Persona prompts for LLM review gates
│   ├── reference_assets/  # Reference frame generation docs
│   └── archive/           # Superseded documentation
├── strategy/         # Business plan, execution timeline (TIMEPLAN.yaml + plan.py)
├── assets/           # Generated media, reference images, music
├── brand/            # Brand spec, visual assets, endcards
├── inspi/            # Inspiration/analysis (MITmonk template, competitor extracts)
├── research/         # Source logs, research briefs
├── schemas/          # JSON schemas (storyboard v2)
├── tests/            # pytest suite (247 tests)
├── Videos/Projects/  # Per-project artifacts (storyboard, media plan, gates, clips, narration)
└── db/               # SQLite content performance DB
```

---

## Production pipeline (the workflow)

The pipeline transforms a topic → a published video through these stages:

```
[1. Content Brief]  →  [2. Script]  →  [3. Storyboard]  →  [4. Media Plan]
       ↓                    ↓               ↓                    ↓
  generate_          review_script    storyboard.py +      compile_media_
  content_brief.py   + generate_hooks  review_storyboard   prompts.py
       ↓                    ↓               ↓                    ↓
[5. Narration (TTS)]  →  [6. Media Generation]  →  [7. QA]  →  [8. Assembly]
       ↓                         ↓                     ↓            ↓
    tts.py              generate_media.py          qa_media.py   assemble.py
                        (Seedance/Kling)                         → final MP4
```

### Gate system (spend control)

Every billable action is blocked by `scripts/gates.py` until all prerequisite gates pass:

| Gate | Enforces | Required for |
|------|----------|-------------|
| `script_review` (G1) | LLM script quality review | TTS, storyboard |
| `storyboard_review` (G2) | Structural review + human approval | Compile |
| `media_plan_review` (G3) | LLM review of compiled plan | Generation |
| `budget` (G4) | Cost within cap ($60) | Generation |
| `render_approval` (G7) | Human spend approval (binds to dry-run report) | Generation |
| `canary` | Human review of single test clip | Full render |
| `media_qa` (G8) | Technical QA pass | Assembly |

Gates bind to artifact SHA-256 hashes — editing an artifact after its gate passed invalidates the gate automatically. No `--force-unsafe` in production.

### Key scripts

| Script | Purpose |
|--------|---------|
| `storyboard.py` | Route a script into a typed-beat storyboard (6-Act, shot-mix bands, trigger engine) |
| `compile_media_prompts.py` | Compile storyboard → media_plan.json (prompts, costs, audio slices, reference rotation) |
| `generate_media.py` | Render clips via Higgsfield (Seedance 2.0 lipsync, Kling 3.0 b-roll) |
| `qa_media.py` | Technical QA: dimensions, audio policy, lipsync provenance, crop safety |
| `assemble.py` | Manifest-driven assembly: lipsync baked audio, narration overlay, music bed, loudnorm |
| `tts.py` | ElevenLabs TTS → narration audio + assembly manifest |
| `gates.py` | Per-project gate ledger (SHA-256 staleness, spend blocking) |
| `approve.py` | Human approval CLI (storyboard, render, canary, budget override) |
| `review_script.py` / `review_storyboard.py` / `review_media_plan.py` | Multi-persona LLM reviewer gates |
| `budget.py` | Budget gate (G4): validates plan cost vs cap |
| `generate_content_brief.py` | Packaging/ideation: topic → title/thumbnail/hook (CTR-scored) |
| `generate_hooks.py` | Hook variant generation + scoring |
| `llm_call.py` | Thin kiro-cli wrapper for LLM calls (creative-authority enforcement) |
| `content_db.py` | SQLite content+performance logging |

---

## Architecture principles

1. **Standalone testable scripts.** Each pipeline stage is a CLI that reads JSON in, writes JSON out. No monolithic orchestrator — stages compose via file I/O.
2. **Gates as the spend primitive.** Higgsfield/ElevenLabs calls are impossible without passing all required gates (SHA-bound, hash-verified). The gate ledger is the single enforcement point.
3. **Media plan as single source of truth.** After compile, the `media_plan.json` carries every prompt, cost, reference image, audio slice, and output path. Generation, QA, and assembly all read it.
4. **Deterministic assembly.** Same manifest + same clips = same output. Assembly is ffmpeg-driven, no AI in the loop.
5. **Human-in-the-loop at two gates:** (a) storyboard content approval, (b) render spend approval. Everything else is automated.

---

## LLM interaction model

The system uses `kiro-cli` (Claude via CLI) as the orchestration brain:

- **Agent:** `.kiro/agents/ytbuilder.json` — auto-loads business plan + time plan on spawn; proposes next step; executes assistant-doable work.
- **LLM calls in pipeline:** `scripts/llm_call.py` wraps `kiro-cli --no-interactive` with model routing (`configs/llm_models.yaml`). Creative tasks require `sonnet_creative` profile; utility tasks use `auto`.
- **Reviewer personas:** 5 LLM reviewer prompts (`docs/reviewer_prompts/`) — filmmaker, technical, universe, audio, audience — each scores a script/storyboard/plan and can block on critical issues.
- **Creative-authority enforcement:** Only Sonnet-class (or higher) models may make creative decisions. Auto/Haiku models are blocked from creative approval.
- **Plan state management:** `strategy/plan.py` (YAML-backed) tracks every step's status, dependencies, and notes across sessions.

---

## Key rules (non-negotiables)

1. **Sourcing discipline** — TED/copyrighted content as research/trend input ONLY. Every video = original framework from ≥3 primary sources + a per-unit source log. Never reformulate a single talk.
2. **Craft bar** — Every video has an original framework + original data point. Human-in-the-loop on script and edit. No AI slop.
3. **Owned audience first** — Email/blog over platform reach. Content is the marketing; products + tool are the sellable asset.
4. **Zero silent degradation** — A hero_lipsync beat MUST produce a lipsync clip or hard-fail. No graceful fallback to stills without explicit approval.
5. **Wardrobe/setting continuity** — All hero reference frames within one episode share a single wardrobe + setting (James cannot change clothes between cuts).

---

## MITmonk template (content formula)

Every flagship video follows the **6-Act master structure** from `inspi/MITmonk.md`:

| Act | Runtime | Function |
|-----|---------|----------|
| 1. Hook & Authority Gap | ~5% | Paradoxical challenge → macro-threat → authority contrast |
| 2. Myth Busting | ~15% | False beliefs → institutional proof → absolution |
| 3. Framework Reveal | ~5% | Introduce architecture + visual map |
| 4. Iteration Loop | ~60% | For each principle: anchor story → thesis → tactical application |
| 5. Synthesis | ~5% | Recap + master tool |
| 6. Identity Shift & CTA | ~10% | Philosophical pivot → motivation → soft CTA |

**Shot-mix bands** (enforced by `review_storyboard.py`):
- Hero (lipsync + cutaway): 25–40% (lipsync alone ≤25%)
- Specific/archival b-roll: ≥25%
- Graphics/UI: ≥10%
- Metaphorical b-roll: 5–15%
- Kinetic text: 2–8%
- Max continuous hero block: ≤15s (single Act-6 closing chain ≤25s exception)

---

## Lipsync production rules

Defined in `constraints.json → lipsync_render_rules` and `TECHNICAL_BIBLE.md`:

- **Model:** Seedance 2.0 (only model supporting `--audio` for lip sync)
- **Duration:** 4s ≤ clip ≤ 10s. Sub-4s beats are padded; >10s slices are trimmed to 10s before API call.
- **Audio slice:** extracted from segment narration mp3, silence-snapped, 200ms closed-mouth lead-in, padded to `max(ceil(speech+0.2), 4)`.
- **Reference rotation:** hero beats rotate across ≥3 canonical angle frames (no consecutive repeat). Active set: `navy_sweater_library` (4 angles).
- **Assembly:** baked lipsync audio preserved verbatim (`-map 0:a`), never overlaid with narration. Trimmed to `speech_len_sec`. Provenance hash verified at assembly time.
- **Output path:** `assets/media/{segment_id}/{beat_id}.mp4` — single source of truth for generation, QA, and assembly.

---

## Business plan summary

**Thesis:** Build a faceless, brand-fronted content engine → digital product ladder → micro-tool (the sellable asset). Content is marketing; the tool + owned audience + IP are enterprise value.

**Monetization sequence:** Templates → Course → Book + Community → AI Micro-tool (4–8× ARR exit multiple)

**Financial shape (base case):** Y1 ~$70k → Y3 ~$1.15M → Y5 ~$2.5M. Tool at $500k+ ARR = $2M–$9.6M enterprise value.

Full plan: `strategy/BUSINESS_PLAN.md`

---

## Plan implementation status

```
[################--------------] 30/55 steps complete (54%)
```

| Phase | Status |
|-------|--------|
| P0 Foundations & Legal | ✅ Complete |
| P1 Brand & Identity | ✅ Complete |
| P2 Channel Infrastructure | Partial (channels deferred; automation pending) |
| P3 Core Media Engine | ✅ Complete |
| P4 Creative Control & Quality | ✅ Complete |
| P5 Viewership & Packaging | ✅ Complete |
| P6 First Content Sprint | **In progress** (flagship_001 in production) |
| P7–P10 | Todo |

**Current focus:** P6-02 — Produce flagship video #1. Media generated (56/56 QA pass), assembly in progress.

Full timeline: `strategy/TIMEPLAN.yaml` | Manager: `python3 strategy/plan.py status`

---

## Configuration files

| File | Purpose |
|------|---------|
| `configs/james/model_routing.yaml` | Narration voice lock, Higgsfield model routing, lipsync reference sets, budget caps, costs |
| `configs/llm_models.yaml` | LLM model profiles (sonnet_creative, auto_utility) with creative-authority rules |
| `docs/channel_universe/constraints.json` | Machine-readable production rules: shot-mix bands, forbidden patterns, negative prompts, text policy, audio policy, crop safety, lipsync render rules |

---

## Testing

```bash
python3 -m pytest -q          # 247 tests, ~45s
python3 -m pytest tests/test_assemble.py -k lipsync   # targeted
```

Tests cover: storyboard routing, media plan compilation, gate ledger, lipsync assembly (tone-marked fixtures), QA checks, budget enforcement, banned models, reference rotation.

---

## Telegram notifications

`tools/notify.py` pings the owner via `@jacobcontentbot` on step completions, blockers, and deliverables. Auto-fires on agent spawn/stop; explicit calls for significant events.

---

## Docs index

| Doc | Purpose |
|-----|---------|
| `strategy/BUSINESS_PLAN.md` | Full operating blueprint |
| `strategy/TIMEPLAN.yaml` | Execution state (every step + status + dependencies) |
| `strategy/TIMEPLAN_GUIDE.md` | How to use the plan system interactively |
| `inspi/MITmonk.md` | The 6-Act content formula (structural template) |
| `inspi/failed001.md` | Post-mortem of the first failed generation attempt |
| `docs/channel_universe/` | Creative bibles (James, studio, cat, forbidden patterns, QA rubric) |
| `docs/reviewer_prompts/` | LLM reviewer persona prompts |
| `docs/plans/LIPSYNC_TICKETS.md` | Lipsync implementation ticket board |
| `docs/plans/PRODUCTION_V2_BLUEPRINT.md` | V2 pipeline architecture spec |
| `docs/plans/audits/` | Engineer handover packets + Fable validation evidence |
