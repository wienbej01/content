# AUTOMATION_PIPELINE.md — Fully-Automated End-to-End Production: Feasibility & Solution Design

**For:** Leverage Mind (faceless AI-native education brand; persona James Harrington)
**Author:** ytbuilder (assistant)
**Date:** 2026-06-08
**Status:** Analysis / proposed architecture (not yet built)
**Relates to:** TIMEPLAN P2-03 (n8n pipeline), P2-01 (research engine), P6 (micro-tool)

> **What was verified vs. assumed.** Endpoint reachability and package versions below were
> checked directly from this server (curl HTTP probes + `npm view`). Pricing, quotas, and
> policy details are from working knowledge and labeled where uncertain — confirm current
> numbers against each vendor's pricing page before committing spend. This is engineering
> analysis, not legal advice.

---

## 0. The headline answer

**A fully *hands-off* pipeline is technically ~85% achievable today, but it should NOT be built fully hands-off.** Two of the business's non-negotiables make one human gate mandatory:

1. **Craft bar / human-in-the-loop** on script + final cut (demonetization survival).
2. **Sourcing discipline** — original framework from ≥3 primary sources, never reformulating TED (legal survival).

So the correct design is **"one-click assisted autopilot"**: the machine does *every mechanical step* and stops at exactly **two human gates** — (A) **brief/script approval**, (B) **final-cut "owner endorsement" before posting**. Everything between and around those gates is automated. This is also what protects the asset: an unattended bot that auto-posts unreviewed AI content is a demonetization/strike risk; a system that does 95% of the labor and asks for a 2-minute approval twice is both safe and a genuine moat.

**Owner interaction target:** from ~8 hrs/video today → **~5–10 minutes/video** (two approvals via Telegram), plus a one-time setup.

---

## 1. Verified toolchain status (this server, 2026-06-08)

| Tool | Status | Note |
|---|---|---|
| ffmpeg | ✅ 7.1.1 | editing/assembly engine (already used for the trailer) |
| Python | ✅ 3.13.7 | orchestration + PIL graphics |
| Node | ✅ v20.19.4 | runs n8n + @higgsfield/cli |
| Pillow (PIL) | ✅ 11.3.0 | brand graphics (wordmark/lower-third/endcard already generated) |
| `@higgsfield/cli` | ✅ npm v0.1.40 | image + lipsync via CLI (early version — pin it) |
| `n8n` | ✅ npm v2.23.4 | orchestrator, self-hostable |
| `@elevenlabs/elevenlabs-js` | ✅ npm v2.51.0 | official TTS SDK |
| faster-whisper | ⬜ installable | local auto-captioning (no API cost) |
| moviepy | ⬜ installable | optional; ffmpeg already covers most needs |
| yt-dlp | ⬜ installable | pull TED transcripts/metadata for trend scan |
| docker | ⬜ absent | optional; n8n can run via npm instead |

**Reachability probes (HTTP):** ElevenLabs, Anthropic, OpenAI, fal.ai, Replicate, Perplexity,
Tavily, Exa, Brave Search, YouTube Data API, TikTok Content Posting API, Ayrshare, Postiz,
Mixpost, Sync.so, HeyGen, D-ID, n8n, PiAPI — **all hosts resolved** (auth-required codes as
expected). None were unreachable.

---

## 2. Stage-by-stage feasibility

Legend: **Auto** = fully unattended via API/CLI/local. **Gate** = human approval point. **Cost** = approx.

### Stage 1 — TED trend scan → topic discovery  → **Auto**
- **How:** `yt-dlp` against the TED YouTube channel + TED.com listing to pull titles, view counts, dates, and transcripts (subtitles) for *signal only*. Optionally YouTube Data API for richer stats.
- **Legal guardrail (hard):** TED is CC BY-NC-ND. Transcripts/topics are used **only** to detect *what themes are resonating*. The pipeline must never pass TED text into the script generator as source content. Implement as: TED → extract topic keywords/embeddings → discard text → feed only the *topic* forward.
- **Cost:** ~free (yt-dlp local; YouTube API within free quota).

### Stage 2 — Outline + content plan → **Auto**
- **How:** Claude API (Anthropic) turns the approved topic into a structured brief: hook, 3–5 part original framework skeleton, the *questions* that must be answered by primary research.
- **Cost:** cents per call.

### Stage 3 — Web research / primary-source gathering → **Auto**
- **How:** A research API gathers ≥3 **independent primary** sources with citations. Best fits:
  - **Perplexity Sonar API** — answer + citations, simplest. (~$5/1k requests tier + token costs; confirm.)
  - **Exa API** — semantic search, returns source URLs + contents; good for primary-source discovery.
  - **Tavily API** — built for LLM research agents; generous free tier.
  - **Brave Search API** — cheap raw search; free tier ~2k queries/mo.
- **Output:** a **source log** (URL, date, snippet, how-used) written to disk — satisfies the defensibility requirement automatically.
- **Cost:** ~$0.01–0.10 per video depending on provider.

### Stage 4 — "Typical audience profile" feedback loop → **Auto**
- **How:** An LLM "critic" pass simulating personas B (mid-career) and E (technical adopter) from the business plan. It scores the brief/script against: clarity, ROI-to-viewer, hook strength, on-brand voice, and "is there an original framework + original data point?" (the craft bar, checked programmatically). Low score → auto-revise loop (max N iterations) before reaching the human gate.
- **Cost:** cents.

### Stage 5 — Script finalization → **GATE A (human)** then **Auto**
- **How:** Claude writes the full script in the locked James Harrington voice (RP, measured, dry wit, no hype) using the prompt library (TIMEPLAN P2-02). The **source log + originality check** is attached.
- **Human gate A:** Owner gets the script + source log + craft-bar checklist on **Telegram**, replies **approve / edit / reject**. This is the *sourcing-discipline + craft* checkpoint. ~2–3 min.

### Stage 6 — Audio generation → **Auto**
- **How:** ElevenLabs API with the locked voice + settings (speed 1.05 / stability 50% / similarity 75% / style 12%). Official `@elevenlabs/elevenlabs-js` SDK (v2.51.0 verified) or REST. Splits script into scene-level chunks; returns mp3/wav.
- **Cost:** Creator/Pro tier; roughly a few $ per long-form video of narration. Unattended: ✅.

### Stage 7 — Still image generation (consistent persona) → **Auto**
- **Challenge:** character consistency across videos. Options:
  - **Higgsfield Soul ID** via `@higgsfield/cli` — purpose-built identity consistency; we already have the Harrington reference set. **Recommended primary.**
  - **fal.ai / Replicate (Flux + reference/LoRA)** — strong fallback; can train a small LoRA on the Harrington images for near-perfect consistency, then generate scenes/B-roll via API.
- **Cost:** cents–low-$ per image (fal.ai/Replicate); Higgsfield per its credit model.

### Stage 8 — Video + lipsync generation → **Auto** (with cost/queue caveats)
- **How:** image + ElevenLabs audio → lipsynced talking head. Verified working manually via Higgsfield (Kling 2.6 Lipsync). Programmatic routes:
  - **`@higgsfield/cli`** (upload image + audio → lipsync job → poll → download). v0.1.x = young; **pin the version**, wrap with retries.
  - **Alternatives with documented APIs:** Sync.so, HeyGen API, D-ID API; Kling via aggregators (fal.ai / Replicate / PiAPI).
- **Caveat:** this is the **slowest + most expensive** stage and the one most likely to need polling/retry logic. Design for async jobs.
- **Cost:** the dominant per-video cost. Budget carefully; consider B-roll (cheaper image-to-video) for non-talking segments.

### Stage 9 — Editing / assembly → **Auto (local, free)**
- **How:** the existing `build_trailer.py` pattern, generalized: normalize/crop (16:9 + 9:16), warm grade, crossfades, **silent-tail padding to fix VO overlap** (the bug we logged), lower-thirds, end card, loudness-normalize. All **local ffmpeg + PIL** — no SaaS, no GUI.
- **Cost:** $0 (CPU time).

### Stage 10 — Captions / graphics → **Auto (local, free)**
- **How:** **faster-whisper** locally for word-level subtitles (burned-in, brand font/colors) — no per-minute API fee. PIL/ffmpeg for kinetic text, framework diagrams, lower-thirds.
- **Cost:** $0 (local GPU/CPU).

### Stage 11 — Music → **Auto** (licensing-dependent)
- **Options, safest first:**
  - **Royalty-free library APIs** (Pixabay Music API = free + commercial-safe; Uppbeat; Epidemic Sound if subscribed) — **lowest legal risk.** Recommended.
  - **AI music generation** (Suno via PiAPI, Udio, or **MusicGen locally/Replicate**). ⚠️ Commercial-use rights for AI-generated music vary by provider/plan — verify the license grants commercial use and ownership before relying on it.
- **Cost:** free (Pixabay/local MusicGen) to subscription (Epidemic/Suno).

### Stage 12 — Owner endorsement → **GATE B (human)**
- **How:** finished 16:9 + 9:16 cuts auto-uploaded to **Telegram** (we already built `send_telegram_video`). Owner replies **approve / changes**. This is the final craft + brand + legal check. ~2–3 min.

### Stage 13 — Posting → **Auto (after gate B)**
- **How:** publish to YouTube + atomize to Shorts/TikTok/Reels/X. See §4 for per-platform reality and the **mandatory AI-disclosure** flags.

---

## 3. Orchestration: what runs the machine

| Option | Self-host | Fit | Verdict |
|---|---|---|---|
| **n8n** (v2.23.4 verified) | ✅ | visual workflow, HTTP nodes, schedule/webhook triggers, run shell/Python, wait-for-webhook (human gates), built-in retries | **Recommended.** Matches the plan (P2-03), great for the Telegram approve/reject gates via webhook. |
| Plain Python + queue + cron | ✅ | full control, fewer moving parts | Good if you prefer code over GUI; more to build yourself. |
| Windmill / Prefect / Temporal | ✅ | heavier, durable execution | Overkill now; revisit at scale. |
| "OpenClaw"/agentic CLI orchestrators | varies | agent-driven runs | Unverified maturity for unattended media; **not recommended as the backbone** — fine as a helper. |

**Recommended backbone: self-hosted n8n** as the conductor, calling:
- local **Python "worker" scripts** for ffmpeg/PIL/whisper (the free local stages),
- **vendor APIs** for TTS / image / video / research,
- **Telegram** for the two human gates (n8n "Wait" node resumes on your reply),
- a small **SQLite job table** (also seeds IDEA-002, the performance DB / future micro-tool).

How human gates work in n8n: workflow hits a **Wait-for-webhook** node, Telegram message includes approve/reject links (or the bot relays your reply), node resumes on click. Long video jobs use **poll loops** (check job status every N sec until done), with retry/backoff.

---

## 4. Posting reality check (the biggest automation friction)

| Platform | Unattended post? | Friction | Disclosure |
|---|---|---|---|
| **YouTube Data API v3** | ✅ after one-time OAuth | **upload ≈ 1,600 quota units; default 10,000/day ≈ ~6 uploads/day** (request increase for more). Sets title/desc/tags/thumbnail. | Must set **"altered or synthetic content"** disclosure flag. |
| **TikTok Content Posting API** | ⚠️ partial | Requires **approved developer app + audit**; unaudited apps are limited (often private-only posts). | TikTok **AI-generated content label** required. |
| **Instagram Reels (Meta Graph API)** | ⚠️ partial | Needs **Business/Creator account + app review**; publishing rate limits. | Meta **AI-content labeling**. |
| **X API v2** | ✅ | **Paid tiers** (Free is near-unusable for posting media at volume; Basic/Pro cost). | Label per platform norms. |
| **Multi-platform: Ayrshare** | ✅ | paid SaaS, one API → many platforms; fastest path | handles much of the plumbing |
| **Postiz** (open-source, self-host) | ✅ | self-host, no per-post SaaS fee | you run it |
| **Mixpost** (self-host) | ✅ | self-host scheduler | you run it |

**Mandatory:** because the presenter is AI-generated/synthetic, the auto-post step **must** set each platform's AI/synthetic-content disclosure. Build it into the posting node as a non-optional field. (Failure = strike/demonetization risk = violates the platform-survival non-negotiable.)

**Recommendation:** Start with **YouTube API direct** (the hub) + a **self-hosted Postiz/Mixpost** (or Ayrshare if you'd rather pay to skip ops) for atomized Shorts/TikTok/Reels/X. Expect TikTok/IG to need one-time app-review paperwork — that's a setup cost, not a per-video cost.

---

## 5. Proposed architecture (one diagram)

```
                         ┌──────────────── n8n (self-hosted) ────────────────┐
                         │            orchestrator + scheduler                │
TED scan (yt-dlp) ──topic→│ 1.scan  2.outline(Claude)  3.research(Exa/Perplx) │
                         │ 4.audience-critic(LLM)  →  source log (SQLite/MD)  │
                         └───────────────┬──────────────────────────────────┘
                                         │  brief + source log
                                  ┌──────▼───────┐
                                  │  GATE A       │  Telegram: approve/edit script
                                  └──────┬───────┘
                                         │ approved script
        ┌───────────────┬───────────────┼───────────────┬──────────────┐
        ▼               ▼               ▼               ▼              ▼
  6.TTS(ElevenLabs) 7.image(Higgsfield 8.video/lipsync 11.music     10.captions
                       Soul ID/Flux)     (Higgsfield/Sync) (Pixabay/   (faster-whisper
                                                          MusicGen)    local)
        └───────────────┴───────────────┴───────────────┴──────────────┘
                                         │ assets
                                  ┌──────▼───────┐
                                  │ 9.EDIT (local │  ffmpeg+PIL: normalize, grade,
                                  │   ffmpeg/PIL) │  crossfade+silent-gap, lower-third,
                                  └──────┬───────┘  endcard, loudnorm → 16:9 + 9:16
                                  ┌──────▼───────┐
                                  │  GATE B       │  Telegram: send_telegram_video → approve
                                  └──────┬───────┘
                                         │ endorsed
                                  ┌──────▼───────────────────────────┐
                                  │ 13.POST (+AI disclosure)          │
                                  │ YouTube API → Postiz/Ayrshare →   │
                                  │ Shorts/TikTok/Reels/X             │
                                  └──────┬───────────────────────────┘
                                         ▼
                                 analytics → SQLite (feeds IDEA-002 + idea engine)
```

---

## 6. Cost envelope (assumption-based, per long-form video + atomized set)

| Item | Low | Typical | Notes |
|---|---|---|---|
| Research APIs | $0.01 | $0.10 | Tavily/Brave cheap; Perplexity mid |
| LLM (outline+script+critic) | $0.05 | $0.50 | Claude/OpenAI tokens |
| TTS (ElevenLabs) | $1 | $4 | per narration length |
| Images | $0.20 | $2 | fal.ai/Replicate/Higgsfield |
| **Video lipsync** | **$3** | **$15+** | **dominant cost; per provider/length** |
| Music | $0 | $0 | Pixabay/MusicGen local |
| Captions/edit | $0 | $0 | local whisper + ffmpeg |
| Posting | $0 | $0–low | YouTube free; Postiz self-host free; Ayrshare paid |
| **Per video** | **~$4** | **~$20–25** | excludes monthly tool subscriptions |
| Monthly tools | — | ~$50–150 | ElevenLabs + research API + (opt) Ayrshare |

Local-first design keeps marginal cost low; the lipsync model is the lever to watch.

---

## 7. Risks & honest limits

1. **Full unattended posting is a strategic mistake**, not just a technical one — it removes the craft/legal gate that protects the channel. Keep gate B. (This is the one place I'd push back on "fully automatic.")
2. **`@higgsfield/cli` is v0.1.x** — expect breaking changes; pin version, add retries, keep a fallback provider (Sync.so/HeyGen) behind the same interface.
3. **TikTok/IG app review** is a one-time bureaucratic blocker to true auto-posting; plan for it.
4. **AI-music commercial licensing** is provider-specific — default to Pixabay/royalty-free or local MusicGen until a license is confirmed in writing.
5. **AI-disclosure compliance** is mandatory and easy to forget — must be a required field in the post step.
6. **Quota limits** (YouTube ~6 uploads/day default) are fine for this cadence; request increase only if scaling.

---

## 8. Recommended build sequence (maps to TIMEPLAN P2-03 / P2-01)

1. ✅ **Generalize the editor** — `scripts/assemble.py` (manifest-driven, both 16:9+9:16, WPS-aligned, gap-concat, generated music, property tested). DONE 2026-06-08.
2. ✅ (partial) **Wire the local-only chain**: `scripts/tts.py` → ElevenLabs → narration → manifest → assemble. TTS DONE 2026-06-08. Images + lipsync automation NEXT.
3. **Add the research front-end**: TED scan + Exa/Perplexity + source log + gate A.
4. **Add n8n** as the conductor once the scripts work standalone (defer to month 6+; cron+runner suffices).
5. **Add posting** last: YouTube API + AI-disclosure, then Postiz/Ayrshare for atomization.
6. **Log to SQLite** throughout → becomes the performance DB (IDEA-002) and seed of the micro-tool (P6).

**Guiding principle:** build each stage as a standalone, testable CLI script first; n8n only *orchestrates* proven scripts. That keeps it debuggable and keeps the valuable IP in your own code (the moat), not locked in a SaaS workflow.

**Active architecture:** `strategy/ARCHITECTURE_MVP.md` (simplified three-phase plan, supersedes the original over-engineered design).

---

## 9. Verdict

- **Fully hands-off:** technically ~85% feasible; **not advisable** (kills the craft/legal moat).
- **One-click assisted autopilot (2 human gates):** **feasible now**, mostly with local/free tooling + a handful of APIs, orchestrated by self-hosted n8n. Cuts owner time per video from hours to **~5–10 minutes** while *strengthening* (not weakening) the platform-survival and sourcing non-negotiables.
- **Biggest watch items:** lipsync cost/maturity, TikTok/IG app-review, AI-disclosure compliance, AI-music licensing.

This is also the natural on-ramp to the sellable micro-tool: the orchestrator + performance DB + the persona/identity assets are exactly the kind of transferable IP the business plan targets for a high-multiple exit.
