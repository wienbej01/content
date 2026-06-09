# ARCHITECTURE REVIEW — CTO Tear-Down

**Reviewer:** Principal Architect (adversarial review)
**Document:** strategy/ARCHITECTURE.md
**Date:** 2026-06-08
**Verdict:** The architecture is over-engineered for the constraints. It will delay content shipment by months, create maintenance debt that compounds, and solve problems you don't have yet while ignoring problems you will have tomorrow. Major revision required.

---

## Critical Flaw #1: The Architecture Inverts the Plan's Own Sequencing

**Severity:** Critical
**Evidence:** TIMEPLAN says first 4 flagships ship by week 4 (P3-01/02). This architecture's M0+M1 alone = 22–30h = 3–4 weeks at 8h/wk. M2 (media chain) adds another 4+ weeks. That's 7–8 weeks of infrastructure before a SINGLE video ships through the "proper" system. Meanwhile, `build_trailer.py` already produces a video in minutes. You built 6 trailer versions today with ad-hoc scripts.
**Recommended change:** Invert the approach. Ship videos NOW with the current tools. Extract and generalize incrementally as patterns stabilize (week 6–8+). The pipeline should crystallize FROM production experience, not precede it.
**Impact:** Eliminates 2–3 months of zero-output infrastructure theater. Content ships week 1.

---

## Critical Flaw #2: 131–183h of Infrastructure for 1 Video/Week

**Severity:** Critical
**Evidence:** The system produces ~52 flagships/year. The architecture estimates 131–183h to build. That's **2.5–3.5 hours of infrastructure per video** the system will ever produce in year 1. The marginal time saved per video (from "8h manual" to "10 min approvals") doesn't pay back until month 8–10 at best — and that assumes the infrastructure works first try (it won't).
**Recommended change:** Cut scope to ~40–60h total. Kill M0 as a standalone milestone (fold essential bits into M1). Merge M3 into M2. Kill M5 as standalone (a few INSERT statements, not a milestone). Kill M9 until there's enough data to analyze (month 6+).
**Impact:** Ship the pipeline in 6–8 weeks instead of 16–23.

---

## Critical Flaw #3: The Provider Abstraction Layer is Premature

**Severity:** High
**Evidence:** You have ONE TTS provider. ONE lipsync provider (a v0.1.x beta). You have never used Sync.so, HeyGen, or fal.ai in production. You don't have accounts or API keys for most "fallback" providers. The architecture specifies 7 port interfaces, contract tests with recorded fixtures, and automatic fallback chains for providers you've never tested.
**The actual scenario:** Higgsfield breaks (it will, it's v0.1). You spend an afternoon writing a Sync.so adapter. That's it. You don't need an interface hierarchy pre-built.
**Recommended change:** Hardcode the ONE provider per capability as a plain function. When (not if) you actually switch, write the new function and swap the import. If you end up with 3+ adapters for the same capability (unlikely in year 1), THEN extract a common interface. This is the "Rule of Three" — don't abstract until you have three concrete implementations.
**Impact:** Eliminates ~30% of M2 complexity (contract tests, fixtures, fallback routing), and 100% of "interface before implementation" waste.

---

## Critical Flaw #4: The State Machine is a Maintenance Trap

**Severity:** High
**Evidence:** 12+ states. Transition rules enforced in code. "A unit in ASSEMBLED state cannot re-enter PRODUCING without explicit reset." In practice: you WILL want to re-edit videos constantly (new music, fix a glitch, try a different thumbnail). The state machine makes the most common operation (re-run a stage) require a ceremony.
**The reality:** You are ONE person running this. The "state" is "what files exist on disk for this unit." If `final/16x9.mp4` exists, it's assembled. If `script.json` has an `approved_at` field, Gate A passed. You don't need a separate enforcement layer.
**Recommended change:** Replace the 12-state machine with a 4-value status column (draft, in_progress, ready, posted) plus per-stage "done" markers (presence of output artifacts). Allow ANY stage to re-run by deleting its output and re-running. Idempotency comes from "check if output exists; skip if yes" — not from state transition policing.
**Impact:** Eliminates `pipeline/state.py`, simplifies the runner to a loop, makes re-edits trivial.

---

## Critical Flaw #5: Database Schema is 4x Too Complex

**Severity:** High
**Evidence:** 12 tables for a system operated by 1 person producing 1 video/week. `config_snapshot` (you have git), `segment` (intermediate computation — compute and discard), `cost_event` (a column on stage_execution suffices), separate `script` and `source_log` tables (JSON files in the unit workspace serve the same purpose and are more inspectable).
**The math:** 12 tables × schema changes × migration scripts × repository classes × query methods = ongoing maintenance load that scales with schema complexity, not with business value.
**Recommended change:** Three tables:
1. `content_unit` — core entity, status, key timestamps, a `metadata` JSON column for flexible attributes.
2. `run_log` — append-only journal (unit_id, stage, status, cost_usd, error, timestamp). Replaces stage_execution + cost_event.
3. `metric` — publication_id, name, value, captured_at (IDEA-002).

Everything else (source_log, script, gate approvals, segments) lives as **files in the unit workspace** (JSON). They're inspectable, diffable, git-trackable, and don't require migrations when the schema evolves.
**Impact:** ~70% less DB maintenance. No migrations for the first year. Data still captured; just stored in the right medium (files for documents, DB for queryable state).

---

## Issue #6: n8n Adds Complexity Without Proportional Value

**Severity:** Medium-High
**Evidence:** For 1 video/week: n8n adds a running Node.js process, a web UI to secure, webhook routing to debug, workflow JSON to version-control, and a dependency on n8n's stability. The architecture's own M6 (local runner) does everything n8n does — it sequences stages, honors gates, retries. If M6 works, n8n provides only: a cron trigger (cron does this) and a webhook listener for Telegram (a 20-line Flask/FastAPI app does this).
**Recommended change:** Defer n8n to month 6+ (after the pipeline is proven in production for 3+ months via the local runner). Run the pipeline weekly via cron + `lm_run.py`. Handle Telegram gate responses by polling `getUpdates` (already proven in the existing code) rather than requiring webhook infrastructure. If/when you hire a non-technical VA who needs a visual interface, THEN add n8n.
**Impact:** Removes a running service, a Node.js dependency, and M8 entirely from the critical path.

---

## Issue #7: Testing Strategy Has False-Confidence Risks

**Severity:** Medium
**Evidence:**
- "Golden-file tests for assembly (assert duration, streams, loudness)" — ffmpeg lossy encoding is non-deterministic across versions. These tests WILL flake on upgrades.
- "Contract tests with recorded fixtures" — provider APIs change. Fixtures rot silently. Tests pass while production fails. Rotten fixtures are worse than no tests: they give confidence without safety.
- No mention of the ACTUAL highest-value test: "detect obviously broken output" (black frames, dead silence during narration, wildly wrong duration, lipsync obviously desynced). These are cheap, robust, and catch real failures.

**Recommended change:**
- Kill golden-file exact-match tests. Replace with **property tests**: duration within ±0.5s of expected, audio mean volume in [-22, -14] dB, no silence > 1s during narration regions, video resolution correct, both output formats present.
- Kill fixture-based contract tests. Replace with **smoke tests against real providers** (tiny inputs, cost-capped) run before each production batch. If the provider works today, ship today.
- ADD "obviously broken" detector: run after assembly, check for black frames (`blackdetect`), dead silence during expected narration (`silencedetect`), duration sanity. This catches more real bugs than any fixture test.

**Impact:** Tests catch real failures instead of asserting implementation details. No flaky suite to maintain.

---

## Issue #8: Observability is Over-Specified for the Scale

**Severity:** Medium
**Evidence:** 4 CLI tools (`lm doctor`, `lm cost`, `lm status`, `lm log`), P50/P95 metrics, circuit-breaker alerts, gate-turnaround tracking — for a pipeline that runs once a week, operated by one person, who will SEE the Telegram messages and know the state. You don't need percentiles for N=52/year.
**Recommended change:** One command: `lm status [unit]`. Shows: unit state, last stage, cost, any error. That's it. Telegram notifications (already built!) handle alerting. If you need cost totals, run a SQLite query ad-hoc. Build the other tools if you ever FEEL the pain of not having them (you probably won't for 12+ months).
**Impact:** Eliminates 4–6h of CLI tool development. Zero operational degradation.

---

## Issue #9: Milestone M0 (Foundation) is a Trap

**Severity:** High
**Evidence:** "M0 blocks everything. 12–16h of scaffolding before any useful work." This is the classic enterprise mistake: build the platform, THEN build features on it. For a solo founder at 8h/wk, two weeks of pure scaffolding (config loaders, migration runners, error taxonomies, structured logging, Makefiles) before shipping ANY value is demoralizing and wasteful.
**The truth:** You need `pip install pyyaml` and a `config = yaml.safe_load(open('config.yaml'))`. You need `import sqlite3; conn = sqlite3.connect('db.sqlite')`. You need `import logging`. These are 5-line patterns, not milestones.
**Recommended change:** Kill M0 as a milestone. Start M1 (assembly) immediately. Add infrastructure AS NEEDED when a stage hits a genuine pain (e.g., "I keep writing retry logic" → extract retry.py; "I lost state after a crash" → add the DB table). Emergent architecture beats speculative architecture for a solo operator.
**Impact:** First useful milestone (working assembly) starts day 1, not week 3.

---

## Issue #10: Missing Critical Concerns

**Severity:** Medium-High
**Evidence:** The architecture is silent on:

| Missing concern | Why it matters |
|---|---|
| **Content buffer/queue** (IDEA-001) | The plan calls for 10 ready-to-publish items in stock. No concept of a scheduling queue. |
| **Backup/disaster recovery** | Single SQLite file + local disk artifacts. Laptop dies → everything gone. |
| **Re-upload/versioning** | Re-edited video: new upload? Replace? Same platform_id? Undefined. |
| **Copyright takedown response** | If a claim hits, how is it detected and handled? Manual? |
| **A/B thumbnail testing** | Business plan mentions it. Architecture has no hook for it. |
| **Scheduling logic** | WHEN does a video post? Timezone? Day of week? The "cadence" is mentioned but no mechanism exists. |
| **Graceful degradation** | If lipsync provider is down for a week, can you ship with static images + voice? The architecture assumes all stages succeed or the unit fails. There's no "good enough" path. |

**Recommended change:** Add a `schedule` table (or a publish_at field on content_unit) for the buffer queue. Add a nightly backup (SQLite `.backup` to a second disk/cloud). Define the "degraded output" path (static image + VO as fallback for lipsync failure). The rest can wait.
**Impact:** Addresses the single realistic operational risk (data loss) and the single realistic workflow gap (scheduling).

---

## Issue #11: Vendor Lock-In is Understated

**Severity:** Medium
**Evidence:**
- **ElevenLabs voice:** If they deprecate the model or change the voice subtly, the brand identity breaks. No mention of archiving the voice model ID or having reference recordings to verify consistency.
- **Higgsfield Soul ID:** v0.1.x. If they pivot, shutdown, or break backward compat, the entire lipsync pipeline stops. The "fallback" to Sync.so/HeyGen is untested and the persona consistency guarantee vanishes (different providers render faces differently).
- **Claude (Anthropic):** Every LLM call goes through one provider. Model deprecation (they deprecated Claude 2 with 90 days notice) or price changes affect the entire pipeline.
- **Telegram:** If Telegram blocks bot API access in your region, both gates break.

**Recommended change:**
- Archive the ElevenLabs voice ID + sample recordings; add a "voice consistency check" (compare new VO to reference via spectral similarity — simple, cheap).
- Accept that persona consistency across lipsync providers is UNSOLVED. Plan for it: if Higgsfield dies, you re-generate the reference images for the new provider. Don't pretend fallback is seamless.
- For LLM: the prompt library is the valuable IP. Prompts are portable across providers (Claude → GPT → local). Document the prompts well; switching the API call is trivial.
- For gates: Telegram polling (getUpdates) is resilient. Webhooks add fragility. Stick with polling.

**Impact:** Honest risk acknowledgment + concrete mitigations (voice archive, prompt portability) instead of a false sense of security from provider "abstraction."

---

## Issue #12: The Manifest Schema is Premature

**Severity:** Medium
**Evidence:** "Manifest JSON schema" as an M1 deliverable. You've built exactly ONE type of video (a 3-clip trailer). You don't yet know what a flagship explainer, a screen-demo, or a data-viz video needs. Designing a schema from one data point guarantees it will be wrong and require migration.
**Recommended change:** Use a plain Python dict (or YAML file) as the manifest for the next 10 videos. Let the shape emerge from actual production. Formalize the schema after you've shipped 10+ videos of 3+ different types and the common structure is clear.
**Impact:** No premature schema to maintain/migrate. The schema you eventually write will be correct because it's derived from reality.

---

## Issue #13: The "No Implementation Code" Mandate Created the Wrong Document

**Severity:** Meta/strategic
**Evidence:** An architecture doc without code is a plan without a prototype. You can't validate the module boundaries, the state flow, or the config loading without running something. The document FEELS comprehensive but is untested. Every "acceptance criterion" is aspirational until code proves it.
**Recommended change:** The next step should NOT be "implement M0 scaffolding per the architecture." It should be: take the EXISTING `build_trailer.py` pipeline, add ONE new stage (e.g., TTS from a script.json), run it end-to-end, and LET THE ARCHITECTURE EMERGE from that integration. Then write the architecture doc as a description of what exists + what's planned, not as a speculative design.
**Impact:** Architecture becomes a living document that describes reality, not a fiction that must be implemented.

---

## Summary: Recommended Revised Approach

| Instead of | Do this |
|---|---|
| M0 Foundation (12-16h scaffold) | Start building. Add infra when pain is real. |
| 7 provider port interfaces | Hardcode the one provider per stage. |
| 12-state machine | 4-status column + "output exists" checks. |
| 12 DB tables | 3 tables + JSON files in workspace. |
| n8n (M8) | cron + local runner. Add n8n at month 6 if needed. |
| Contract tests with fixtures | Smoke tests against real providers. |
| 131–183h total | Target 40–60h to a working, shipping pipeline. |
| Ship content after infra | Ship content NOW, extract infra from production. |

### Revised Milestone Sequence (40–60h)

1. **M1: Assemble engine** (8h) — generalize build_trailer, manifest as dict, property tests.
2. **M2: Media chain + Gate B** (20h) — TTS + images + lipsync → assemble → Telegram. Hardcoded providers.
3. **M3: Research + script + Gate A** (16h) — TED scan + research + script + Telegram approval.
4. **M4: Runner + posting + DB** (12h) — local runner, YouTube post, 3-table DB, cron.
5. **M5: Polish** (4h) — `lm status`, backup script, voice consistency check.

Total: ~60h = 7–8 weeks at 8h/wk. First video through the system by end of M2 (~week 4).

---

**Final note:** This architecture was written by an architect who wants to build a PLATFORM. But you're building a PIPELINE for one brand, one voice, one cadence. A pipeline can be 5 scripts and a cron job. A platform needs interfaces, state machines, and migration frameworks. Build the pipeline. If it ever needs to become a platform (the micro-tool, P6), you'll know exactly what to abstract because you'll have run the pipeline for 6 months.
