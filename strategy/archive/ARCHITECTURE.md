# ARCHITECTURE.md — Production System Implementation Architecture

**System:** Leverage Mind AI-Powered Educational Influencer Production System
**Author:** Workflow Architect / Principal Automation Architect
**Date:** 2026-06-08
**Status:** Architecture specification (no implementation code)
**Depends on:** BUSINESS_PLAN.md, TIMEPLAN.yaml, AUTOMATION_PIPELINE.md

---

## Design Principles

1. **n8n is orchestration only.** Business logic lives in Python modules.
2. **Buildable, testable, runnable locally** before orchestration is added.
3. **Each stage is a standalone CLI** — provable in isolation, composable by n8n.
4. **Two human gates** (A: script+sources, B: final cut) via Telegram. Posting is impossible without a recorded Gate B approval.
5. **Sourcing discipline enforced in code** — TED text never enters the script; ≥3 primary sources with a source log per unit.
6. **Craft bar enforced in code** — original framework + data per unit; programmatic check before Gate A.
7. **Provider-agnostic boundaries** — every external service behind a swappable adapter port.
8. **Fail loud, retry smart** — no silent failures; dead-letter + Telegram alert.
9. **Cost-aware** — per-unit and monthly budget guards; cost logged per API call.
10. **Data from day one** — SQLite captures attributes + metrics from unit #1 (IDEA-002 moat).

---

## 1. Recommended Build Order

Follows AUTOMATION_PIPELINE.md §8 and TIMEPLAN P2-05..P2-09. Each milestone is buildable and testable independently before the next starts.

```
M0  Foundation (core scaffolding)
 │
 ├─► M1  Assembly engine (P2-05) — local, no API keys
 │
 ├─► M2  Media generation chain (P2-06) — TTS + images + lipsync + music
 │    │
 │    └─► M3  Gate B + Telegram endorsement (part of P2-06)
 │
 ├─► M4  Research front-end + Gate A (P2-07)
 │
 ├─► M5  SQLite logging + cost tracking (P2-09) — woven into M1-M4
 │
 └─► M6  Local end-to-end runner (the "runnable locally" checkpoint)
      │
      ├─► M7  Posting + AI-disclosure (P2-08)
      │
      ├─► M8  n8n orchestration (P2-03) — orchestrate proven CLIs
      │
      └─► M9  Analytics + atomization (P2-04, IDEA-002)
```

**Critical path:** M0 → M1 → M2 → M3 → M6. Research (M4) and posting (M7) can proceed in parallel once M0 is done.

---

## 2. Repository Structure

```
YTchannel/
├── leverage_mind/              # Python package — ALL business logic
│   ├── __init__.py
│   ├── core/                   # Cross-cutting infrastructure
│   ├── research/               # Stage 1-4: trend scan, discovery, web research
│   ├── authoring/              # Stage 5: script, critic, prompts
│   ├── media/                  # Stage 6-8,11: TTS, images, lipsync, music, captions
│   ├── assembly/               # Stage 9-10: video assembly, narrative speed
│   ├── publishing/             # Stage 13: YouTube, social, disclosure
│   ├── analytics/              # Metrics collection + ingestion
│   └── pipeline/               # Stage registry, state machine, local runner
├── cli/                        # Thin CLI entrypoints (one per stage)
│   ├── lm_assemble.py
│   ├── lm_tts.py
│   ├── lm_research.py
│   ├── lm_script.py
│   ├── lm_post.py
│   ├── lm_gate.py             # Local gate approve/reject (for testing)
│   └── lm_run.py              # End-to-end local runner
├── config/
│   ├── brand.yaml              # Brand-locked params (voice, palette, render profile)
│   ├── pipeline.yaml           # Providers, thresholds, retry, budgets
│   └── manifests/              # Per-video editor manifests (JSON/YAML)
├── db/
│   ├── schema.sql              # SQLite schema (versioned migrations)
│   └── leverage_mind.db        # gitignored runtime DB
├── content/                    # Per-content-unit workspaces (gitignored)
│   └── <unit_id>/             # brief, script, assets, final, run.log
├── orchestration/
│   └── n8n/                    # Exported n8n workflow JSON (orchestration only)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/               # Provider adapter contract tests
│   └── fixtures/               # Recorded API responses (VCR-style)
├── brand/                      # Existing: assets, fonts, specs
├── strategy/                   # Existing: plans, architecture docs
├── tools/                      # Legacy scripts (migrate into package; keep shims)
├── pyproject.toml              # Package definition, deps, scripts
└── Makefile                    # build/test/lint shortcuts
```

**Migration of existing files:**

| Current location | New home | Notes |
|---|---|---|
| `tools/narrative_speed.py` | `leverage_mind/assembly/narrative_speed.py` | CLI shim in `cli/` |
| `tools/generate_music.py` | `leverage_mind/media/music.py` | CLI shim in `cli/` |
| `tools/send_telegram_message.py` | `leverage_mind/core/telegram.py` | Absorb + extend |
| `tools/notify.py` | `leverage_mind/core/notify.py` | Thin wrapper over telegram |
| `brand/build_trailer.py` | `leverage_mind/assembly/assemble_video.py` | Generalized (P2-05) |
| `brand/prompts/` | `leverage_mind/authoring/prompts/` | Prompt library |

---

## 3. Python Package Structure

```
leverage_mind/
├── core/
│   ├── config.py           # Layered config loader (defaults→brand.yaml→pipeline.yaml→env)
│   ├── secrets.py          # runtime.env loader (existing pattern, never log values)
│   ├── logging.py          # Structured JSON logs, run_id correlation, redaction
│   ├── db.py               # SQLite connection pool, migrations, repositories
│   ├── errors.py           # Exception taxonomy
│   ├── retry.py            # Backoff/retry decorators, poll-until-done
│   ├── artifacts.py        # Content-unit workspace layout, path helpers
│   ├── telegram.py         # Send message/video/buttons (absorbs existing)
│   ├── gates.py            # Gate request/await/resolve abstraction
│   ├── models.py           # Dataclasses: Brief, SourceLog, Script, Segment, AssetSet
│   └── budget.py           # Per-unit + monthly cost ceiling enforcement
├── research/
│   ├── ted_scan.py         # yt-dlp TED trend signal (topics only; text discarded)
│   ├── discovery.py        # Idea engine combinatorics (pillar × format × persona)
│   ├── web_research.py     # Provider-agnostic research (Exa/Perplexity/Tavily)
│   ├── source_log.py       # ≥3-source enforcement + log writer + legal guardrail
│   └── brief.py            # Outline/brief builder (LLM)
├── authoring/
│   ├── script.py           # Script generation (James Harrington voice)
│   ├── critic.py           # Audience-persona critic + craft-bar checker
│   └── prompts/            # Prompt templates (brand voice, hooks, frameworks)
├── media/
│   ├── tts.py              # ElevenLabs adapter (locked voice+settings)
│   ├── images.py           # Higgsfield Soul ID / Flux adapter
│   ├── lipsync.py          # Provider-agnostic: Higgsfield → Sync.so → HeyGen
│   ├── music.py            # Original music generator (piano+violin)
│   └── captions.py         # faster-whisper local word-level subtitles
├── assembly/
│   ├── narrative_speed.py  # WPS measurement + per-clip speed alignment
│   ├── assemble_video.py   # Manifest-driven editor (the core tool)
│   └── brand_render.py     # Grade, lower-third, endcard, loudnorm primitives
├── publishing/
│   ├── youtube.py          # YouTube Data API v3 upload + metadata
│   ├── social.py           # Postiz/Ayrshare adapter for multi-platform
│   ├── disclosure.py       # Non-optional AI-content disclosure enforcement
│   └── atomize.py          # Long-form → shorts/clips selection logic
├── analytics/
│   ├── collect.py          # Pull metrics from platform APIs
│   └── ingest.py           # Write to SQLite performance tables
└── pipeline/
    ├── stages.py           # Stage registry: name → function mapping
    ├── state.py            # Content-unit state machine + transition rules
    └── runner.py           # Local sequential runner (honors gates, retries)
```

---

## 4. Major Modules and Responsibilities

| Module | Responsibility | Inputs | Outputs | External deps |
|---|---|---|---|---|
| `research/ted_scan` | Extract trending topics from TED (yt-dlp). **Text discarded** — only topic keywords/signals forwarded. | TED channel URL | Topic list + trend scores | yt-dlp |
| `research/web_research` | Gather ≥3 independent primary sources with citations | Topic + questions from brief | Source log entries (URL, snippet, how-used) | Exa / Perplexity / Tavily |
| `research/source_log` | **Enforce** ≥3 source rule; reject units that fail; persist log | Source entries | Validated source_log.json | None (pure logic) |
| `research/brief` | Generate structured content brief (hook, framework skeleton, questions) | Topic + sources | Brief JSON | Claude API |
| `authoring/script` | Generate full script in James Harrington voice using prompt library | Brief + source log | Script JSON (with per-segment word counts) | Claude API |
| `authoring/critic` | Score script against craft bar + audience personas; auto-revise loop | Script + brief | Pass/fail + revision notes | Claude API |
| `media/tts` | Generate narration audio (ElevenLabs, locked voice) | Script segments | Audio files (WAV/MP3) per segment | ElevenLabs API |
| `media/images` | Generate persona-consistent still images for each scene | Script scene descriptions | Image files (PNG) | Higgsfield / fal.ai |
| `media/lipsync` | Generate talking-head video from image+audio (async polling) | Image + audio pairs | Lipsync video clips (MP4) | Higgsfield CLI / Sync.so / HeyGen |
| `media/music` | Generate original piano+violin ambient bed to exact duration | Duration + mood | Music WAV | None (local numpy) |
| `media/captions` | Generate word-level subtitles from audio | Audio files | Caption SRT/ASS + burned-in video | faster-whisper (local) |
| `assembly/narrative_speed` | Measure WPS per clip; compute alignment speeds programmatically | Clips + word counts | Per-clip speed multipliers | ffmpeg (local) |
| `assembly/assemble_video` | Manifest-driven video editor: normalize, grade, gaps, lower-third, endcard, music, loudnorm → 16:9 + 9:16 | Manifest JSON + assets | Final MP4 (both formats) | ffmpeg + PIL (local) |
| `publishing/youtube` | Upload to YouTube with metadata + mandatory AI-disclosure flag | Final video + metadata | Publication record (video ID, URL) | YouTube Data API v3 |
| `publishing/social` | Distribute atomized clips to Shorts/TikTok/Reels/X | Clips + captions | Per-platform publication records | Postiz / Ayrshare |
| `publishing/disclosure` | **Non-optional gate**: verify AI-disclosure flag is set before any post proceeds | Publication request | Pass/reject | None (pure logic) |
| `analytics/collect` | Pull view/retention/CTR metrics from platform APIs | Publication records | Raw metric rows | YouTube API |
| `analytics/ingest` | Write metrics + content attributes to SQLite for IDEA-002 | Metrics + attributes | DB rows | SQLite |
| `pipeline/state` | Content-unit state machine (DRAFT→RESEARCHED→SCRIPTED→GATE_A→PRODUCING→ASSEMBLED→GATE_B→POSTED→TRACKING) | State transitions | Validated state changes | SQLite |
| `pipeline/runner` | Run all stages sequentially for a unit, honoring gates + retries | Unit ID + config | Completed unit or halted-at-gate | All of the above |
| `core/gates` | Abstract gate request/await/resolve. Telegram in prod; CLI approve in tests. | Gate request | Approval/rejection event | Telegram / CLI |
| `core/budget` | Enforce per-unit ($30 default) and monthly ($500 default) cost ceilings | Cost events | Pass or BudgetExceeded | SQLite |

---

## 5. Database Schema

SQLite. Single file (`db/leverage_mind.db`, gitignored). Schema versioned via numbered migration files in `db/migrations/`.

### Core Tables

| Table | Purpose | Key columns |
|---|---|---|
| `content_unit` | Central entity — one row per flagship/short/post | id (ULID), type, pillar, format_archetype, hook_type, topic, title, status, created_at, updated_at |
| `run` | Pipeline execution record per unit | id, unit_id FK, started_at, finished_at, status(running/done/failed), config_hash, total_cost |
| `stage_execution` | Per-stage within a run | id, run_id FK, stage_name, attempt, status, started_at, finished_at, error_message, cost |
| `source_log` | Per-unit sourcing evidence (defensibility) | id, unit_id FK, url, source_type, title, published_date, accessed_date, snippet, how_used, is_primary(bool) |
| `script` | Script versions per unit | id, unit_id FK, version, text, word_count, segment_count, wps_target, approved_at, gate_event_id FK |
| `segment` | Per-segment within a script | id, script_id FK, ordinal, text, word_count, wps_measured, speed_applied, trim_to |
| `asset` | Every generated artifact | id, unit_id FK, kind(audio/image/video/music/caption/final), provider, path, duration_s, cost, checksum, created_at |
| `gate_event` | Human approval record | id, unit_id FK, gate(A/B), action(approve/edit/reject), actor, message, requested_at, decided_at |
| `publication` | Per-platform post record | id, unit_id FK, platform, platform_id, url, disclosure_set(bool NOT NULL), posted_at, status |
| `metric` | Performance data (IDEA-002) | id, publication_id FK, metric_name, value, captured_at |
| `cost_event` | Per-API-call cost tracking | id, unit_id FK, stage, provider, amount_usd, recorded_at |
| `config_snapshot` | Config hash → full YAML for reproducibility | hash PK, yaml_text, created_at |

### Key Constraints

- `publication.disclosure_set` is `NOT NULL CHECK(disclosure_set = 1)` — physically impossible to record a post without confirming AI-disclosure was set.
- `gate_event` with action='approve' required before `content_unit.status` can transition past GATE_A or GATE_B (enforced in `pipeline/state.py`).
- `source_log` count ≥ 3 WHERE is_primary = 1, per unit — enforced at the research stage (hard reject if not met).

### Indexes

- `content_unit(status)` — find actionable units.
- `metric(publication_id, metric_name)` — IDEA-002 queries.
- `cost_event(unit_id)`, `cost_event(recorded_at)` — budget checks.
- `gate_event(unit_id, gate)` — gate lookup.

---

## 6. API Boundaries

### 6.1 External Provider Ports (adapter pattern)

Each external service is behind a port interface. Implementations are swappable via `config/pipeline.yaml`.

| Port | Methods | Implementations |
|---|---|---|
| `ResearchProvider` | `search(query, n_results) → SourceEntry[]` | ExaAdapter, PerplexityAdapter, TavilyAdapter, BraveAdapter |
| `LLMProvider` | `generate(system, user, schema?) → text/structured` | ClaudeAdapter, OpenAIAdapter |
| `TTSProvider` | `synthesize(segments[], voice_profile) → AudioFile[]` | ElevenLabsAdapter |
| `ImageProvider` | `generate(prompt, reference_images?, style?) → ImageFile` | HiggsfieldImageAdapter, FluxAdapter |
| `LipsyncProvider` | `submit(image, audio) → JobID`, `poll(job) → Status/URL`, `download(url) → VideoFile` | HiggsfieldLipsyncAdapter, SyncSoAdapter, HeyGenAdapter |
| `PublishProvider` | `upload(video, metadata, disclosure=True) → PublicationRecord` | YouTubeAdapter, PostizAdapter, AyrshareAdapter |
| `MetricsProvider` | `fetch(publication_ids[]) → MetricRow[]` | YouTubeAnalyticsAdapter |

### 6.2 Internal: CLI Contract (n8n ↔ Python boundary)

n8n calls Python via `Execute Command` node. The contract:

```
INVOCATION:  python3 -m cli.lm_<stage> --unit <unit_id> [--config pipeline.yaml]

STDOUT:      JSON {"status": "ok"|"gated"|"failed", "unit_id": "...",
              "stage": "...", "outputs": [...], "cost_usd": 0.12,
              "next_gate": "B"|null, "error": null|"message"}

EXIT CODES:  0 = success or gated (check status field)
             1 = permanent failure (do not retry)
             2 = retryable failure (n8n retries with backoff)
             3 = budget exceeded (alert owner, halt)
```

### 6.3 n8n Responsibilities (ONLY)

- Schedule triggers (cron for weekly cadence).
- Sequence CLI calls per the stage graph.
- Retry on exit code 2 (exponential backoff, max 3).
- Route Telegram webhook callbacks to resume Wait nodes.
- Alert on exit code 1 or 3.
- **Never**: validate sources, check craft bar, compute WPS, decide on providers, hold state beyond "waiting for gate." All of that is in Python.

---

## 7. Human Approval Gate Architecture

### 7.1 Gate Flow

```
Pipeline stage completes
  → gate_event row inserted (status=pending, requested_at=now)
  → Telegram message sent (script + source log for A; video for B)
  → Pipeline PAUSES (state = AWAITING_GATE_A or AWAITING_GATE_B)

Owner responds (Telegram reply or inline button):
  → approve / edit / reject
  → gate_event row updated (action, decided_at)
  → If approve: state transitions forward; pipeline resumes.
  → If edit: state returns to authoring; human notes appended to context; re-generate.
  → If reject: state → REJECTED; unit archived; alert logged.
```

### 7.2 Mechanisms

| Environment | Gate satisfaction mechanism |
|---|---|
| Production (n8n) | Telegram inline buttons → webhook → n8n Wait node resumes |
| Local runner | Telegram + manual reply parsing, OR `cli/lm_gate.py approve <unit>` for testing |
| Integration tests | Auto-approve (test mode flag); no Telegram sent |

### 7.3 Hard Rules

- **Gate B approval row must exist** before `publishing/` accepts a unit. Enforced as a DB check in the publish function, not just orchestration — defense in depth.
- **Gate A approval row must exist** before media generation starts.
- **Timeout**: if no response within 24h, re-ping via Telegram (notify.py --kind action). Never auto-approve.
- **Idempotent**: re-running a gated unit does not re-send the Telegram message if a pending gate_event already exists.

---

## 8. Logging Architecture

### 8.1 Structure

Every log line is structured JSON with:
- `ts` (ISO timestamp)
- `run_id` (correlation ID for the full unit pipeline run)
- `stage` (current stage name)
- `level` (DEBUG/INFO/WARN/ERROR)
- `msg` (human-readable)
- `data` (structured payload: provider, latency_ms, cost, attempt, etc.)

### 8.2 Three Sinks

| Sink | Purpose | Retention |
|---|---|---|
| Console (stderr) | Developer during local runs | ephemeral |
| `content/<unit_id>/run.log` | Per-unit audit trail | permanent (part of defensibility) |
| `stage_execution` + `cost_event` DB rows | Queryable history, observability | permanent |

### 8.3 Rules

- **Secrets never logged.** Redaction filter strips any value matching `*_TOKEN`, `*_KEY`, `*_SECRET` patterns before writing.
- **Every external API call** logs: provider, endpoint, latency_ms, HTTP status, cost_usd, attempt number.
- **Gate events** logged with full context (what was sent, what was decided, turnaround time).
- **Telegram pings** (via notify.py) for operational milestones (step done, blocker, budget alert) — not debug noise.

---

## 9. Failure Handling Architecture

### 9.1 Error Taxonomy

| Exception class | Meaning | Retry? | Action |
|---|---|---|---|
| `RetryableError` | Network timeout, 5xx, 429 rate-limit, queue full | Yes (backoff) | Retry up to max_attempts |
| `PermanentError` | 4xx auth/config error, invalid input, schema violation | No | Dead-letter + alert |
| `GateRejected` | Human rejected at Gate A or B | No | Archive unit, log reason |
| `BudgetExceeded` | Per-unit or monthly cost ceiling hit | No | Halt pipeline + alert |
| `ValidationError` | Craft bar / source count / disclosure check failed | Conditional | Auto-revise loop (max N), then fail |
| `ProviderUnavailable` | Primary provider down after retries exhausted | Fallback | Try next provider in chain |

### 9.2 Retry Policy

- **Exponential backoff** with jitter: base 2s, max 120s, max 3 attempts (configurable per stage in pipeline.yaml).
- **Lipsync polling**: separate poll loop — check every 15s, timeout at 10 min, then ProviderUnavailable → fallback.
- **Circuit breaker** per provider: after 3 consecutive failures within 5 min, skip to fallback for 10 min.

### 9.3 Idempotency

- Each stage checks for existing valid output (file exists + checksum matches manifest) and **skips** if already done. Safe re-runs.
- State machine prevents re-doing work: a unit in ASSEMBLED state cannot re-enter PRODUCING without explicit reset.
- Publications deduplicated by `(unit_id, platform)` unique constraint — prevents double-posting.

### 9.4 Dead-Letter

- Failed unit → status = FAILED, error preserved in `stage_execution`, all artifacts retained in `content/<unit_id>/`.
- Telegram alert (notify.py --kind block) with unit ID + stage + error summary.
- Manual inspection + `lm_gate.py retry <unit>` to re-enter from failed stage.

### 9.5 Provider Fallback Chains

| Capability | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| Lipsync | Higgsfield CLI | Sync.so API | HeyGen API |
| Research | Exa | Perplexity Sonar | Tavily |
| Images | Higgsfield Soul ID | fal.ai (Flux) | Replicate |

Fallback selection is automatic on ProviderUnavailable; logged as a cost/quality event.

---

## 10. Testing Strategy

### 10.1 Test Pyramid

| Layer | What | Speed | Network? | Runs in CI? |
|---|---|---|---|---|
| **Unit** | Pure logic: WPS math, source-log enforcement, craft-bar rules, state transitions, disclosure check, config loading, budget math | Fast (<1s) | No | Yes |
| **Contract** | Each provider adapter against its port interface, using recorded fixtures (VCR/cassette pattern) | Fast | No (fixtures) | Yes |
| **Integration** | Full pipeline with stub adapters (FakeTTS, FakeLipsync producing tiny files), auto-approved gates | Medium (~30s) | No | Yes |
| **Golden-file** | Assembly output assertions: duration, stream layout, silence map (no VO overlap), loudness target | Medium | No | Yes |
| **Smoke (live)** | Real providers, tiny inputs, cost-capped ($1 max) — validates auth + contracts are current | Slow | Yes | Manual/nightly |

### 10.2 Key Test Cases (non-exhaustive)

- Source log rejects unit with < 3 primary sources.
- TED text is provably discarded (never reaches script context).
- Craft-bar checker rejects script missing original framework.
- Disclosure enforcement rejects a publish call with disclosure_set=False.
- State machine prevents GATE_B→POSTED without gate_event(approve).
- Budget guard halts at ceiling.
- Narrative speed alignment produces clips within ±5% of target WPS.
- Assembly produces both 16:9 and 9:16 with no audio overlap (silence-gap verification).
- Retry logic respects max attempts and backoff intervals.
- Idempotent re-run skips completed stages.

### 10.3 Fixture Management

- Provider contract fixtures stored in `tests/fixtures/<provider>/` as JSON response recordings.
- Updated quarterly or on provider API version change.
- Golden files for assembly: tiny synthetic clips (1s duration) + expected output characteristics (duration, stream count, loudness range).

---

## 11. Observability Strategy

### 11.1 CLI Tools

| Command | Purpose |
|---|---|
| `lm status <unit>` | Show unit state, current stage, cost so far, gate status |
| `lm status --summary` | Count units by state, weekly throughput, total spend |
| `lm doctor` | Check env (API keys present, ffmpeg version, DB accessible, Telegram reachable) |
| `lm cost --period month` | Cost breakdown by provider and stage |
| `lm log <unit> [--stage X]` | Tail/search the unit's run log |

### 11.2 Operational Metrics (queryable from SQLite)

| Metric | Source | Use |
|---|---|---|
| Stage success rate | `stage_execution.status` | Spot unreliable providers |
| P50/P95 stage latency | `stage_execution` timestamps | Identify bottlenecks |
| Per-provider error rate | `stage_execution` WHERE status=failed GROUP BY provider | Trigger fallback tuning |
| Cost per unit (total + breakdown) | `cost_event` | Budget management |
| Gate turnaround time | `gate_event` decided_at - requested_at | Owner responsiveness |
| Units/week throughput | `content_unit.created_at` | Cadence tracking |
| % units needing edit at gate | `gate_event` WHERE action='edit' | Quality trend |

### 11.3 Alerts (via Telegram notify.py)

| Trigger | Kind | Action |
|---|---|---|
| Unit completed (posted) | done | Celebrate / log |
| Stage failed (permanent) | block | Investigate |
| Budget 80% threshold | warn | Review spend |
| Gate pending > 12h | action | Nudge owner |
| Provider circuit-breaker open | warn | Check provider status |

### 11.4 Not Built Yet (scale-time)

- Web dashboard (defer until ≥50 units or team > 1).
- Prometheus/Grafana (SQLite queries sufficient at this scale).
- Distributed tracing (single-machine, sequential pipeline — unnecessary).

---

## 12. Configuration Management Strategy

### 12.1 Layered Precedence (highest wins)

```
Environment variables / CLI flags
  ↑
~/.config/ytchannel/runtime.env    (secrets: API keys, tokens, chat_id)
  ↑
config/pipeline.yaml               (providers, thresholds, retry, budgets, cadence)
  ↑
config/brand.yaml                  (brand-locked: voice, palette, render profile, persona)
  ↑
Package defaults (hardcoded)       (sane fallbacks for non-critical params)
```

### 12.2 brand.yaml (locked — rarely changes)

Contains the decisions made in P1-01 through P1-04:
- Voice: James Harrington, ElevenLabs ID, speed 1.05, stability 50%, similarity 75%, style exaggeration 12%
- Palette: navy #1B2A4A, gold #C8973E, ivory #F5F0E8, charcoal #2D2D2D, oxblood #6B1D2A
- Typography: Playfair Display (headings), Inter (body)
- Render: 1920×1080 / 1080×1920, 24fps, warm grade params, lower-third position, endcard duration
- Music: mood=calm, bed_level_db=-16
- Persona: James Harrington character description + Higgsfield Soul ID reference images

### 12.3 pipeline.yaml (tunable — changes as system evolves)

- Provider selections + API base URLs
- Retry: max_attempts, backoff_base, backoff_max per stage
- Budget: per_unit_max_usd, monthly_max_usd
- Thresholds: min_sources=3, craft_bar_min_score=7, wps_tolerance=0.05
- Cadence: flagships_per_week=1, shorts_per_flagship=10
- Posting: platforms enabled, disclosure text templates, schedule offsets

### 12.4 Secrets

- **Only in** `~/.config/ytchannel/runtime.env` (existing pattern) or process environment.
- **Never** in repo, config YAML, logs, or Telegram messages.
- `.gitignore` enforces exclusion.
- Key names: `ELEVENLABS_API_KEY`, `ANTHROPIC_API_KEY`, `HIGGSFIELD_TOKEN`, `YOUTUBE_OAUTH_JSON`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `EXA_API_KEY`, etc.

### 12.5 Per-Video Manifests

Each video's editor inputs are a JSON/YAML manifest in `config/manifests/<unit_id>.yaml`:
- Clip list (paths, word counts, trim points)
- Reference clip index + baseline speed
- Music mood + level
- Output formats (16:9, 9:16, both)
- Lower-third text, endcard variant

This is the deterministic-edit contract: same manifest + same assets = same output (reproducible, version-controlled). Generated by the pipeline after Gate A; reviewed at Gate B.

---

## 13. Milestone Breakdown

### M0 — Foundation & Scaffolding

| | |
|---|---|
| **Objective** | Establish the core infrastructure all stages depend on: config loading, structured logging, SQLite schema + migrations, error/retry framework, Telegram integration, content-unit state machine, artifact workspace layout, and test harness. |
| **Deliverables** | `leverage_mind/core/` complete and tested; `db/schema.sql` + migration runner; `config/brand.yaml` + `pipeline.yaml` templates; `pyproject.toml` with deps; `Makefile` (lint, test, migrate); `lm doctor` CLI. |
| **Dependencies** | None (greenfield). Existing `tools/send_telegram_message.py` and `runtime.env` pattern absorbed. |
| **Acceptance criteria** | `make test` passes; `lm doctor` validates env; a content_unit can be created, transitioned through states, and queried; structured logs written to console + file; secrets loaded from runtime.env and redacted in logs. |
| **Complexity** | **Medium** (~12–16h). Foundational but well-scoped; no external APIs. |

---

### M1 — Assembly Engine (TIMEPLAN P2-05)

| | |
|---|---|
| **Objective** | Generalize `brand/build_trailer.py` into a manifest-driven, reusable video editor that any future pipeline stage can call. Absorbs `narrative_speed.py` and `generate_music.py`. |
| **Deliverables** | `leverage_mind/assembly/assemble_video.py` (manifest-driven); `assembly/narrative_speed.py`; `assembly/brand_render.py`; `media/music.py`; manifest JSON schema; `cli/lm_assemble.py`; golden-file tests (duration, no overlap, loudness). |
| **Dependencies** | M0 (config, logging, artifacts, models). |
| **Acceptance criteria** | Given a manifest JSON + clip set, produces correct 16:9 and 9:16 outputs. WPS alignment automatic (no manual speed). VO-overlap impossible by construction (gap-concat). Silence-map assertion passes. Music generated to exact duration (piano+violin, no loop). Round-trip reproducible (same manifest = same output). `cli/lm_assemble.py --manifest x.json` works standalone. |
| **Complexity** | **Medium** (~10–14h). Most logic exists in build_trailer.py; needs generalization + tests. |

---

### M2 — Media Generation Chain (TIMEPLAN P2-06)

| | |
|---|---|
| **Objective** | Build the chain: approved script → TTS audio → persona images → lipsync video → assemble → Gate B delivery. One provider at a time, each behind a port interface with retry + fallback. |
| **Deliverables** | `media/tts.py` (ElevenLabs); `media/images.py` (Higgsfield/Flux); `media/lipsync.py` (provider-agnostic with Higgsfield primary, Sync.so/HeyGen fallback); `media/captions.py` (faster-whisper); per-provider contract tests with fixtures; `cli/lm_tts.py`, `cli/lm_images.py`, `cli/lm_lipsync.py`. |
| **Dependencies** | M0, M1 (assembly called at the end of the chain). |
| **Acceptance criteria** | From a script JSON, the chain produces a finished branded video delivered to Telegram (Gate B) with no manual web-tool interaction. Each provider adapter passes its contract tests against fixtures. Retry/backoff works for transient failures. Lipsync polling handles async jobs correctly. Fallback triggers on provider unavailability. Cost logged per call. |
| **Complexity** | **Large** (~25–35h). Lipsync async polling + retries + fallback = dominant complexity. Multiple provider APIs to integrate. |

---

### M3 — Gate B + Telegram Endorsement Loop

| | |
|---|---|
| **Objective** | Implement the Gate B (final-cut approval) interaction: send video to Telegram, pause pipeline, await owner response (approve/edit/reject), resume or loop. |
| **Deliverables** | `core/gates.py` (gate abstraction); Gate B flow integrated into media chain; `cli/lm_gate.py` (local approve/reject for testing); Telegram inline-button or reply-parsing flow; gate_event DB persistence. |
| **Dependencies** | M0 (telegram, state machine, DB), M2 (produces the video to gate). |
| **Acceptance criteria** | Pipeline halts after assembly and sends video to Telegram. Owner approve → state transitions to ENDORSED → ready for posting. Owner edit → returns to authoring with notes. Owner reject → archived. Re-run of a gated unit is idempotent (no duplicate messages). Test mode auto-approves without Telegram. |
| **Complexity** | **Small–Medium** (~8–12h). Clear flow; Telegram send already proven; main work is state management + webhook resume. |

---

### M4 — Research Front-End + Gate A (TIMEPLAN P2-07)

| | |
|---|---|
| **Objective** | Automated research stage: TED trend-scan (topic signal only), primary-source gathering (≥3 independent sources), source log, LLM brief, LLM script in brand voice, audience-critic + craft-bar check, then Gate A (Telegram script-approval). |
| **Deliverables** | `research/ted_scan.py`, `research/web_research.py`, `research/source_log.py`, `research/brief.py`, `research/discovery.py`; `authoring/script.py`, `authoring/critic.py`, `authoring/prompts/`; Gate A flow (same pattern as Gate B); `cli/lm_research.py`, `cli/lm_script.py`. |
| **Dependencies** | M0, M3 (gate pattern reused). |
| **Acceptance criteria** | Produces an approved brief + source log on demand. **TED text never enters the script** (verified by test: mock TED transcript → assert absent from script output). Source log has ≥3 primaries or stage rejects. Craft-bar checker rejects scripts without original framework. Gate A works via Telegram. Owner can approve/edit/reject. Script generated in James Harrington voice. |
| **Complexity** | **Large** (~20–28h). Multiple LLM calls, legal guardrail is critical (must be provably correct), prompt engineering for voice + critic. |

---

### M5 — SQLite Logging + Cost Tracking (TIMEPLAN P2-09)

| | |
|---|---|
| **Objective** | Wire every pipeline stage to log runs, costs, and content attributes to SQLite. Seeds the IDEA-002 performance DB and the future micro-tool. |
| **Deliverables** | Repository classes for each table; cost_event logging wired into every provider adapter; stage_execution logging in runner; attribute capture (pillar, format, hook_type, etc.) at unit creation; `lm cost` and `lm status` CLI queries working against real data. |
| **Dependencies** | M0 (schema exists), M1-M4 (stages to instrument). |
| **Acceptance criteria** | After one full pipeline run, all tables populated. `lm cost --period month` shows breakdown. `lm status <unit>` shows full history. Each produced/posted unit creates a row with its attributes + source-log refs. Data is queryable for IDEA-002 analysis (deferred to P5/P6). |
| **Complexity** | **Medium** (~10–14h). Schema exists from M0; this is wiring + queries. |

---

### M6 — Local End-to-End Runner

| | |
|---|---|
| **Objective** | A single command (`lm_run.py`) that runs the FULL pipeline locally — research through assembly — honoring gates (via Telegram or CLI approve), retries, budget, and logging. This is the **"runnable locally before orchestration"** checkpoint. If this works, n8n only adds scheduling and webhook routing. |
| **Deliverables** | `pipeline/runner.py`; `cli/lm_run.py --unit <id> [--auto-approve]`; integration test (full pipeline, stub providers, auto-approve); documentation of the run flow. |
| **Dependencies** | M1, M2, M3, M4, M5 (all stages must work). |
| **Acceptance criteria** | `python3 -m cli.lm_run --unit test_001 --auto-approve` runs research → script → media → assembly → "post" (dry-run) end-to-end with stub providers in < 60s. With real providers + real gates, produces a finished video awaiting Gate B. All DB tables populated. Cost tracked. Idempotent re-run skips completed stages. |
| **Complexity** | **Medium** (~8–12h). Mostly glue; stages already work individually. Main effort is sequencing + idempotent resume. |

---

### M7 — Posting + Mandatory AI-Disclosure (TIMEPLAN P2-08)

| | |
|---|---|
| **Objective** | Publish endorsed videos to YouTube (Data API v3) and atomize to Shorts/TikTok/Reels/X with the platform AI/synthetic-content disclosure flag set as a non-optional field on every post. |
| **Deliverables** | `publishing/youtube.py`, `publishing/social.py` (Postiz/Ayrshare), `publishing/disclosure.py`, `publishing/atomize.py`; `cli/lm_post.py`; YouTube OAuth setup docs; AI-disclosure unit test. |
| **Dependencies** | M3 (Gate B must exist — publish refuses without it), M5 (publication records). External: YouTube OAuth (one-time), TikTok/IG app review (one-time). |
| **Acceptance criteria** | An endorsed video posts to YouTube with AI-disclosure flag set. Disclosure enforcement test: `disclosure_set=False` → hard reject, cannot proceed. Atomized units distribute to configured platforms. Publication deduplicated (no double-post on re-run). Per-platform status tracked. |
| **Complexity** | **Large** (~16–22h). YouTube OAuth complexity; multi-platform posting; TikTok/IG app review is an external blocker (not code complexity but calendar time). |

---

### M8 — n8n Orchestration (TIMEPLAN P2-03)

| | |
|---|---|
| **Objective** | Wrap the proven local CLIs in n8n: schedule, sequence, retry, gate webhooks. n8n is the CONDUCTOR, not the brain. |
| **Deliverables** | n8n workflow JSON (exported, version-controlled in `orchestration/n8n/`); Telegram webhook configuration; schedule trigger (weekly flagship cadence); retry logic (Execute Command + IF exit code); Wait-for-webhook nodes for Gate A/B; alert nodes on failure. Setup documentation. |
| **Dependencies** | M6 (local runner proven — n8n wraps the same CLIs). n8n installed (verified available). |
| **Acceptance criteria** | n8n triggers a full pipeline run on schedule. Gates pause workflow and resume on Telegram webhook. Retries fire on exit code 2. Alerts fire on exit codes 1/3. Owner interaction is unchanged (Telegram approve/reject). Entire business logic remains in Python (n8n has zero Python/logic nodes). |
| **Complexity** | **Medium** (~10–14h). n8n is visual + JSON config; complexity is in webhook routing and the Wait-node flow, not code. |

---

### M9 — Analytics + Atomization Automation (TIMEPLAN P2-04, IDEA-002)

| | |
|---|---|
| **Objective** | Pull performance metrics from platforms, ingest into SQLite, correlate with content attributes. Automate the atomization (long-form → 8–12 shorts selection + scheduling). The capture layer is complete; the analysis/recommendation layer is deferred to P5/P6. |
| **Deliverables** | `analytics/collect.py` (YouTube Analytics API), `analytics/ingest.py`; `publishing/atomize.py` (clip selection + schedule); metric tables populated; `lm status --summary` shows performance overview. |
| **Dependencies** | M7 (publications exist to pull metrics for), M5 (metric tables). |
| **Acceptance criteria** | After a published video has 48h of data, `lm collect <unit>` pulls views/watch-time/CTR/subs into the metric table. Attributes + metrics joinable for IDEA-002 queries. Atomization produces ≥8 clip candidates from a flagship, scheduled across platforms. |
| **Complexity** | **Medium** (~12–16h). YouTube Analytics API is straightforward; atomization clip-selection logic (identify high-retention moments) is the interesting part — can start with manual/simple heuristics and refine. |

---

## Summary: Total Estimated Effort

| Milestone | Complexity | Est. hours | Cumulative |
|---|---|---|---|
| M0 Foundation | Medium | 12–16 | 12–16 |
| M1 Assembly | Medium | 10–14 | 22–30 |
| M2 Media chain | Large | 25–35 | 47–65 |
| M3 Gate B | Small–Med | 8–12 | 55–77 |
| M4 Research + Gate A | Large | 20–28 | 75–105 |
| M5 SQLite logging | Medium | 10–14 | 85–119 |
| M6 Local runner | Medium | 8–12 | 93–131 |
| M7 Posting | Large | 16–22 | 109–153 |
| M8 n8n orchestration | Medium | 10–14 | 119–167 |
| M9 Analytics | Medium | 12–16 | 131–183 |
| **Total** | | **131–183h** | |

At ~8h/week: **~16–23 weeks** (4–6 months), aligning with TIMEPLAN month-6 milestone (P2 complete, tool beta). Parallel work on M4 (research) while M2/M3 (media) proceeds can compress the critical path by ~3–4 weeks.

---

## Appendix: State Machine Diagram

```
DRAFT
  → RESEARCHING → RESEARCHED
    → SCRIPTING → SCRIPTED
      → AWAITING_GATE_A
        → [approve] → APPROVED_A → PRODUCING
          → ASSEMBLED
            → AWAITING_GATE_B
              → [approve] → ENDORSED → POSTING → POSTED → TRACKING
              → [edit] → SCRIPTING (with notes)
              → [reject] → REJECTED
        → [edit] → SCRIPTING (with notes)
        → [reject] → REJECTED
  (any) → FAILED (on permanent error; preserves artifacts)
```

---

*End of architecture document. Next action: begin M0 (Foundation) by scaffolding `leverage_mind/core/`, `pyproject.toml`, `db/schema.sql`, and the test harness.*
