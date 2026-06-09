# ARCHITECTURE — Three-Phase Plan (MVP → Production → Scale)

**Status:** ACTIVE — this is the governing architecture document.
**Constraint:** 1 developer, part-time (8h/wk), limited budget, first content ASAP
**Principle:** Ship first, extract later. No infrastructure without production pain justifying it.
**Last updated:** 2026-06-08

### Current Build Status

| MVP Milestone | Status | Deliverable |
|---|---|---|
| M1 Assembly Engine | ✅ Done | `scripts/assemble.py` — manifest-driven, both formats, WPS-aligned, property tested |
| M2 Media Chain (TTS) | ✅ Done | `scripts/tts.py` — script.json → ElevenLabs → narration → manifest → assemble |
| M2 Media Chain (images+lipsync) | 🔲 Next | Higgsfield image gen + lipsync automation |
| M3 Research + Gate A | 🔲 Planned | TED scan, web research, source log, script gen, Telegram gate |
| M4 Runner + Posting + DB | 🔲 Planned | Local runner, YouTube post, 3-table SQLite, cron |
| M5 Polish | 🔲 Planned | `lm status`, backup, voice check |

**Archived:** `strategy/archive/ARCHITECTURE.md` (over-engineered platform design, superseded by this doc), `strategy/archive/ARCHITECTURE_REVIEW.md` (CTO review that led to this simpler approach), `strategy/archive/M1_AUDIT.md` (findings addressed in M1-A hardening).

---

## What to Remove / Delay / Simplify

| Architecture.md proposes | Verdict | When to revisit |
|---|---|---|
| M0 Foundation milestone (12-16h) | **Remove as standalone.** Fold 30 min of setup into M1. | Never as a separate step |
| 7 provider port interfaces | **Remove.** Hardcode one provider per stage. | After you switch a provider (month 3-6?) |
| 12-state machine with transition rules | **Simplify.** Status column + "output file exists" = state. | After 50 units if you have state bugs |
| 12 DB tables + migrations | **Simplify to 3 tables.** JSON files for everything else. | After 100 units if queries are too slow |
| Contract tests with recorded fixtures | **Remove.** Replace with pre-run smoke check. | After 3+ provider adapters exist |
| Golden-file assembly tests | **Replace with property assertions** (duration, loudness, no silence). | Never (property tests are correct from start) |
| n8n orchestration (M8, 10-14h) | **Defer.** cron + shell script. | Month 6+ if non-technical person operates it |
| `lm doctor`, `lm cost`, `lm log`, `lm status` (4 CLI tools) | **Build only `lm status`.** Rest are `sqlite3` one-liners. | If you hire someone who can't write SQL |
| Circuit breakers, P50/P95 metrics | **Remove.** At 1 video/week you'll notice failures via Telegram. | 10+ videos/week (year 2+) |
| Provider fallback chains (auto-routing) | **Remove.** Manual swap when a provider dies. | After 2nd provider switch |
| Separate `segment`, `cost_event`, `config_snapshot` tables | **Remove.** cost goes on run_log; segments are ephemeral; config is in git. | Never |
| M9 Analytics + atomization automation | **Defer entirely.** Manual for first 6 months. | After 30+ published videos |
| `publishing/disclosure.py` as a module | **Simplify to a boolean flag** checked in the YouTube upload call. | Never needs its own module |
| Content-unit workspace filesystem layout spec | **Simplify.** `content/<id>/` with whatever files the stages produce. No spec. | After 100 units if it's messy |
| Manifest JSON schema (formalized) | **Defer.** Use a Python dict. | After 10+ videos of 3+ types |

---

## Phase 1: MVP Architecture (First 10 Videos)

**Goal:** Ship the first flagship video through the system end-to-end. Time budget: ~30h.
**Principle:** Use what already works. Add the minimum new code per stage.

### What exists and works today

- `brand/build_trailer.py` — video assembly (proven)
- `tools/narrative_speed.py` — WPS alignment (proven)
- `tools/generate_music.py` — original music bed (proven)
- `tools/send_telegram_message.py` — Telegram + video send (proven)
- `tools/notify.py` — notifications (proven)
- ElevenLabs voice locked + tested
- Higgsfield lipsync tested (manual, works)
- Brand assets, fonts, visual system (done)

### MVP architecture

```
scripts/
  research.py        # Claude API: topic → brief → script. Source log = JSON file.
  tts.py             # ElevenLabs: script.json → audio WAVs per segment.
  generate_media.py  # Higgsfield CLI: image + audio → lipsync clips (poll+retry).
  assemble.py        # Generalized build_trailer: clips → branded 16:9 + 9:16.
  post.py            # YouTube Data API upload + AI-disclosure flag.
  run.py             # Sequential runner: calls above in order, stops at gates.

content/
  <id>/              # One folder per video. Contains everything.
    brief.json
    source_log.json
    script.json
    audio/
    images/
    clips/
    final/
    manifest.json    # Plain dict: clip list, words, trims, music mood.

config.yaml          # One file. Brand + pipeline + provider settings. Flat.
db.sqlite            # 3 tables (see below).
```

### MVP database (3 tables)

```sql
CREATE TABLE content_unit (
  id TEXT PRIMARY KEY,
  title TEXT,
  pillar TEXT,
  status TEXT DEFAULT 'draft',  -- draft|producing|review|approved|posted|failed
  created_at TEXT DEFAULT (datetime('now')),
  posted_at TEXT,
  youtube_id TEXT,
  cost_usd REAL DEFAULT 0,
  error TEXT,
  meta TEXT  -- JSON blob for flexible attributes
);

CREATE TABLE run_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  unit_id TEXT REFERENCES content_unit(id),
  stage TEXT,         -- research|tts|images|lipsync|assemble|post
  status TEXT,        -- ok|failed|skipped
  cost_usd REAL DEFAULT 0,
  duration_s REAL,
  error TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE metric (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  unit_id TEXT REFERENCES content_unit(id),
  platform TEXT,
  name TEXT,          -- views|watch_time|ctr|subs_gained
  value REAL,
  captured_at TEXT DEFAULT (datetime('now'))
);
```

### MVP gates

- **Gate A:** `run.py` prints script + source log to console → sends to Telegram. Waits for you to type `approve` in terminal (or Telegram reply parsed via `getUpdates` polling). No webhooks.
- **Gate B:** `run.py` sends final video to Telegram. Same approve pattern.
- Gate = a JSON file: `content/<id>/gate_a.json` with `{"approved": true, "at": "..."}`. Stage checks file exists before proceeding.

### MVP error handling

- Each script has a try/except at the top level. On failure: write error to `run_log`, send Telegram alert, exit 1.
- Retry: run the script again (it checks if output exists, skips completed work).
- No retry framework. No circuit breaker. You run it again if it fails.

### MVP config

One `config.yaml`:
```yaml
brand:
  voice_id: "james_harrington_id"
  voice_speed: 1.05
  voice_stability: 0.50
  voice_similarity: 0.75
  voice_style: 0.12
  music_mood: calm
  music_level_db: -16
  render_fps: 24
  render_width: 1920
  render_height: 1080

providers:
  elevenlabs_model: "eleven_multilingual_v2"
  higgsfield_soul_id: "harrington_ref"
  anthropic_model: "claude-sonnet-4-20250514"
  youtube_category: "27"  # Education

pipeline:
  min_sources: 3
  wps_reference_speed: 0.85
  gap_seconds: 0.4
  endcard_duration: 3.0
```

### MVP testing

- **Before each video:** `run.py --dry-run` checks: ffmpeg present, API keys valid (getMe/health calls), disk space > 1GB.
- **After assembly:** property check (duration ±1s of expected, mean volume in range, both formats exist, `silencedetect` finds no gaps > 2s during narration).
- **That's it.** No unit tests for the first 10 videos. The output IS the test.

### MVP timeline

| Week | Work | Output |
|---|---|---|
| 1 | `assemble.py` (generalize build_trailer) + `tts.py` | Can assemble from audio+images |
| 2 | `generate_media.py` (Higgsfield lipsync automation) | Full media chain working |
| 3 | `research.py` + `run.py` + gates | End-to-end: topic → video → Telegram |
| 4 | `post.py` + first real video | **First flagship published** |

---

## Phase 2: Production Architecture (Videos 10–100)

**Trigger:** You've shipped 10 videos. Patterns are clear. Pain points are real, not hypothetical.
**Time budget:** ~30h additional over 2–3 months, interleaved with content production.

### What you add (only what you've felt pain about)

| Addition | Why now (the pain) | Effort |
|---|---|---|
| Extract `leverage_mind/` package | Scripts are importing each other messily; can't test in isolation | 4h |
| Add a proper Telegram gate loop | Typing `approve` in terminal is annoying after 10 times | 3h |
| Add basic retry decorator | Higgsfield has failed 5+ times; you're tired of re-running manually | 2h |
| Add `lm status` CLI | You forgot which videos are where | 2h |
| Add nightly SQLite backup to a second location | You had one scare | 1h |
| Formalize manifest (from the 10 dicts you've written) | You see the common shape now | 3h |
| Add faster-whisper captions | You're burning time on captions manually | 3h |
| Add atomization (long→shorts) | You're manually cutting shorts; 10 per flagship × 10 flagships = pain | 6h |
| Property test suite (automated post-assembly QC) | You shipped one video with a glitch | 3h |
| Voice consistency check (spectral comparison to reference) | ElevenLabs changed something subtle | 2h |
| Content buffer queue (publish_at field + cron poster) | You want to batch-produce and drip-publish | 3h |

### Production package structure

```
leverage_mind/
  core/        # config, db, telegram, retry, logging (plain stdlib logging)
  research/    # research.py, source_log.py
  authoring/   # script.py, critic.py, prompts/
  media/       # tts.py, images.py, lipsync.py, music.py, captions.py
  assembly/    # assemble_video.py, narrative_speed.py
  publishing/  # youtube.py, atomize.py
cli/
  lm_run.py, lm_status.py, lm_gate.py
```

No `pipeline/state.py`. Status is a column. Stage completion = output file exists.

### Production database

Same 3 tables. Maybe add:
```sql
ALTER TABLE content_unit ADD COLUMN publish_at TEXT;  -- scheduling queue
ALTER TABLE content_unit ADD COLUMN gate_a_at TEXT;   -- when approved
ALTER TABLE content_unit ADD COLUMN gate_b_at TEXT;
```

Still no migrations framework. Just `ALTER TABLE` one-offs in a `db/changelog.md`.

### Production error handling

- Retry decorator with 3 attempts + exponential backoff (one 20-line function).
- If all retries fail: status=failed, Telegram alert, move on.
- Manual retry: `lm_run.py --unit X --from-stage lipsync` (re-run from a specific stage).

### Production testing

- Property assertions run after assembly (automated, in the pipeline).
- Pre-run health check (API keys valid, disk space).
- No provider contract tests. Smoke test = running the actual pipeline (which you do weekly).

### Production observability

- `lm status` shows all units by state + cost.
- Telegram alerts on failure.
- Weekly: glance at `SELECT stage, count(*), avg(cost_usd) FROM run_log GROUP BY stage`.

---

## Phase 3: Scale Architecture (100+ Videos / Team / Pre-Exit)

**Trigger:** You're shipping 3+ videos/week, have hired an editor/VA, and/or are preparing for sale.
**Time budget:** Dedicated sprint(s), possibly with a contractor.

### What you add now (because the scale justifies it)

| Addition | Why NOW | Not before because |
|---|---|---|
| n8n orchestration | Non-technical VA needs to monitor/retry without terminal | You could do it yourself before |
| Provider abstraction (port interfaces) | You're on your 3rd lipsync provider and tired of rewriting | You only used 1 before |
| Formal state machine | Multiple people operating = need explicit rules | Solo operator just knows the state |
| Full DB schema (normalized tables) | Querying JSON blobs across 200+ units is too slow | 50 units in JSON was fine |
| IDEA-002 analysis engine | 100+ data points = statistically meaningful patterns | 20 data points = noise |
| Dashboard / web UI | VA/editor needs visibility without SQL | You could `sqlite3 db.sqlite` |
| Automated A/B thumbnail testing | Enough traffic to measure significance | Too few views before |
| Multi-region backup + restore procedure | Asset of meaningful value; can't afford loss | Small enough to re-create before |
| CI/CD pipeline | Multiple contributors need guardrails | Solo = commit and run |
| API rate limiting + queue | 3+ videos/week hits provider quotas | 1/week was always within limits |
| Graceful degradation (static fallback for lipsync) | Can't afford a week of no output | Could wait a day before |

### Scale package structure

The full `ARCHITECTURE.md` design (mostly) — but arrived at organically because each piece earned its place.

### Scale testing

- Full contract tests (because you now have 3+ adapters per capability).
- Integration tests with stub providers (because CI serves a team).
- Performance regression (because throughput matters at 3+/week).

---

## Decision Framework: "Do I Need This Now?"

Ask three questions before building any infrastructure:

1. **Have I felt this pain at least 3 times?** No → don't build it.
2. **Will this block me from shipping next week's video?** No → defer it.
3. **Can I solve this with a 5-line script instead of a module?** Yes → write the script.

---

## Technical Debt Avoidance (While Moving Fast)

"No future technical debt" doesn't mean building everything upfront. It means:

| Practice | Cost | Prevents |
|---|---|---|
| One folder per content unit (all artifacts together) | Zero | Orphaned files, lost state |
| Append-only run_log in DB | 5 min | "What happened?" mystery |
| Source log JSON per unit | Zero | Legal/defensibility exposure |
| Config in one YAML (not scattered env vars) | 10 min | "Why is this different?" bugs |
| Gate approval as a JSON file in the unit folder | Zero | "Did I approve this?" confusion |
| Property assertions after assembly | 30 min | Shipping broken videos |
| Scripts are importable functions (not just `if __name__`)| Zero | Can't compose or test later |
| Don't hardcode paths (use config + unit workspace) | Zero | Works on any machine |

These are ZERO-COST practices that make Phase 2 and Phase 3 easy to build on top of Phase 1. This is how you move fast without creating debt.

---

## Summary

| | MVP (0-10 videos) | Production (10-100) | Scale (100+) |
|---|---|---|---|
| **Architecture** | 6 scripts + cron | Package + CLI + retry | Full platform |
| **DB** | 3 tables | 3 tables + columns | Normalized schema |
| **State** | Status column + files | Same + publish_at | State machine |
| **Testing** | Property assertions | Same + health check | Contract + integration |
| **Observability** | Telegram alerts | + `lm status` | + dashboard |
| **Orchestration** | `run.py` + cron | Same | n8n |
| **Providers** | Hardcoded | + retry decorator | Port interfaces |
| **Time to build** | ~30h (4 weeks) | +30h (8 weeks total) | +40-60h (sprint) |
| **First video** | Week 4 | — | — |
