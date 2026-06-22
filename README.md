# YTchannel — Faceless AI-Native Video Production Pipeline

A fully automated production pipeline for faceless educational YouTube content, targeting mid-career white-collar professionals in the wealth/productivity/self-improvement niche. The system generates MITmonk-style explainer videos (6–12 min) with a consistent AI brand persona (James Harrington), from script through final assembly.

**Owner:** pseudonymous, part-time (~6–10 hrs/wk), online-only
**Brand:** Leverage Mind | Voice: James Harrington (ElevenLabs eleven_v3)
**Status:** DB-native remediation complete. 19-stage pipeline operational (258 tests pass)

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
├── configs/          # Model routing, voice settings, LLM profiles, strict smoke config
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
├── tests/            # pytest suite (258+ tests) — unit, integration, regression, validation
├── Videos/Projects/  # Per-project artifacts (storyboard, media plan, gates, clips, narration)
└── db/               # SQLite content performance DB
```

---

## Production pipeline (the workflow)

The pipeline transforms a topic → a published video through 19 stages orchestrated by `produce_db.py`:

```
                        produce_db.py run <production_id>
 ┌──────────────────────────────────────────────────────────────────────┐
 │ research → write_script → review_script → gate_a_content             │
 │   → storyboard → review_storyboard → tts → audio_timing              │
 │   → reconcile_timing → compile_media → gate_a_spend                  │
 │   → generate_media → qa_media → repair → graphics_compositing        │
 │   → assemble → qa_final → gate_b_review → publish → analytics        │
 └──────────────────────────────────────────────────────────────────────┘
                         Gate A (content approval)
                         Gate A (spend cap enforcement)
                         Gate B (final review)
```

### Gate system (spend control)

Every billable action is blocked by producer gate approval until all prerequisites pass:

| Gate | Enforces | Required for |
|------|----------|-------------|
| `gate_a_content` | Script review + human content approval | Storyboard, TTS |
| `gate_a_spend` | Cost cap enforcement ($ from `configs/strict_smoke.yaml`), forbidden asset type guard, provider job count cap, prompt text-risk detection | Media generation (paid providers) |
| `gate_b_review` | DB-contract QA: render unit validation state, local graphic provenance, assembly preflight evidence | Publish |

All gates are SHA-bound and recorded in the production ledger (no `--force-unsafe` in production).

### Key scripts

| Script | Purpose |
|--------|---------|
| `produce_db.py` | DB-native orchestration CLI (create/run/resume/status/approve) — drives the 19-stage pipeline |
| `media_contract.py` | Pure-python guardrails: provider asset-type eligibility, prompt text-risk classification |
| `smoke_config.py` | Strict smoke test configuration (spend caps, job limits) |
| `production_db.py` | Unified production ledger (schema, migrations, transactions) |
| `production_repo.py` | Artifact registry, render unit planning, timeline management |
| `media_service.py` | Provider job state machine, contract QA dispatch, repair lifecycle |
| `assemble_db.py` | DB-native assembly, deliverable registry, final QA validation, Gate B |
| `qa_final.py` | Final-cut gate (freeze/black/length checks) + DB-contract evidence verification |
| `render_graphics.py` | Deterministic local graphic compositing (no AI providers) |
| `paid_adapters.py` | Real provider adapters (Higgsfield Seedance, ElevenLabs) with capability-gated negative prompts |
| `compile_media_prompts.py` | Compile storyboard → media_plan.json (prompts, costs, audio slices, reference rotation) |
| `generate_media.py` | Render clips via Higgsfield (Seedance 2.0 lipsync, Kling 3.0 b-roll) |
| `assemble.py` | Manifest-driven assembly: lipsync baked audio, narration overlay, music bed, loudnorm |
| `storyboard.py` / `direct_storyboard.py` | Script → typed-beat storyboard (6-Act, shot-mix bands) |
| `review_script.py` / `review_storyboard.py` | Multi-persona LLM reviewer gates |
| `gates.py` | Per-project gate ledger (SHA-256 staleness, spend blocking) |
| `tts.py` / `tts_service.py` | ElevenLabs TTS + artifact recording + cost events |
| `llm_call.py` | Thin kiro-cli wrapper for LLM calls (creative-authority enforcement) |
| `content_db.py` | SQLite content+performance logging |

---

## Architecture principles

1. **DB-native orchestration.** `produce_db.py` drives the 19-stage pipeline through a transactional production ledger. Every render unit, artifact, provider job, and validation is recorded in the DB.
2. **Provider boundary hardening.** Pure-python `media_contract.py` enforces asset-type eligibility and prompt text-risk BEFORE any paid provider call. Three guard layers: contract → service → adapter.
3. **DB-contract QA.** Media QA validates render-method contracts (provenance, text spec, provider job linkage), not just mechanical file properties. Final QA requires DB-contract evidence to pass.
4. **Deterministic assembly.** Same manifest + same clips = same output. Assembly is ffmpeg-driven, no AI in the loop. Only active, validated DB artifacts are consumed.
5. **Human-in-the-loop at three gates:** content approval (gate_a_content), spend approval (gate_a_spend), final review (gate_b_review). Everything else is automated.
6. **Repair preserves history.** Validation failures are classified and repaired. Old artifacts remain in the DB (preserved, not deleted). Repair lifecycle is idempotent.

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

## Implementation status

```
[#####################----------] 42/55 steps complete (76%)
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
| **DB-Native Remediation (10 sprints)** | ✅ **Complete** — 258 tests, 9/9 invariants, all BLOCKER issues resolved |

**Current focus:** First content sprint production.
**Latest milestone:** DB-native remediation validated and approved.
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
python3 -m pytest -q          # 258+ tests, ~15s
python3 -m pytest tests/unit tests/integration tests/regression -v   # full suite
```

Tests cover: provider boundary hardening, prompt text-risk detection, media contract (15 unit test files), assembly preflight + timeline heuristics, local graphic rendering + DB registration, repair lifecycle + classification, final QA contract evidence, hero lipsync QA, temporal edit guards, compile-media prompt splitting, smoke config enforcement, paid adapter contracts (negative prompt capability gate, adapter second guard), plus 8 integration tests for full lifecycle paths and 2 regression tests for forensic fixture structure.

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
| `docs/plans/PRODUCTION_V2_BLUEPRINT.md` | V2 pipeline architecture spec |
| `docs/ENHANCED_DATABASE_SYSTEM_SUMMARY.md` | DB-native architecture overview |
| `docs/DOCUMENTATION_INDEX.md` | Full documentation index |
| `docs/ARCHIVE_INDEX.md` | Archived documentation tracking |
| `reports/validation/db_native_remediation_final_report.md` | Final validation report (10-sprint remediation) |
