# PLAN — S9-C: Complete the production system before any further paid call

**Sprint ID:** S9-C (complete-system). **Program:** Recovery, branch `fix/flagship-001-end-to-end-recovery`.
**Written:** 2026-06-18. **Baseline HEAD:** `3f1c9fa`. **Baseline tests:** 1051 collected (S8 exit-gate was 1047 at `4152574`; +4 from the recent routing/authoring fixes).
**Supersedes / scopes:** `reports/recovery/S9/CONTINUE.md` §3 (items 3.1–3.7). The earlier `S9-T01`/`S9-T02` were the *paid-test plan phases*; this sprint is the **engineering required before that paid test is allowed to resume**.

> This is a **planning artifact only**. No production code is changed by this file. Each ticket is implemented one-per-session by a coding agent using the loop at the bottom of each ticket.

---

## 1. Objective and outcome contract

The DB-native pipeline (S0–S8) passes its full suite **only against test-provider behavior** (`FakeProvider`, short fixtures). Driving a real production (`db/s9_real.db`, slug `ai_notes_teaser`) exposed that several material process steps were never planned as named tickets and were hidden by those fixtures. This sprint closes those gaps at the **root cause in pipeline code** (no-hacks rule) so that the next real, paid generation run is well-formed, compliant, and auditable — **before** any further paid provider call.

### Required new behavior (must become true)

1. **Duration compliance (R1).** A script whose estimated narration duration exceeds the format's target range is **rejected by a deterministic programmatic gate**, not merely requested via prompt text. The teaser word budget is recalibrated to the actual James voice pace (~60–74 wpm) so the budget and the 75 s target agree (~75–95 words, not 140–230).
2. **Storyboard shot-mix compliance (R2).** A storyboard produced by the DB path assigns shot types in the **canonical vocabulary** (`hero_lipsync` / `broll_*` / `graphic_*`) in a distribution that satisfies the `review_storyboard.py` bands — never a uniform `talking_head_standard` fallback.
3. **Render-unit supersession (R3 / D-015).** Re-running `compile_media` after invalidation **supersedes** the prior render units; `generate_media`, `qa_media`, and `assemble` see exactly one active set (no 2× timeline).
4. **Multi-clip slotting (R4).** Long beats are broken into ≤max-clip-length slots (and hero slots carry their master-narration audio slice) so coverage has no gaps.
5. **Real generation request (R5 / Q-001).** A Higgsfield generation request carries a real **per-clip prompt**, the hero **reference image** (`--image`), and the hero **master-narration slice** (`--audio`, seedance_2_0 only) — so hero clips are lipsynced and b-roll is on-brief.
6. **Assembly richness (R6).** The assembled output includes **graphics** and a **music bed** in addition to the clip bed + master narration.
7. **Paid-call cost tracking (R7).** Every paid call (TTS + generation) writes a `cost_events` row so spend is auditable against the $5 cap.

### Behavior that must remain unchanged (invariants I1–I5)

- **I1** `invoke_tts` refuses paid calls when `YT_TEST_MODE=1` (D-013 guard, commit `f69d601`).
- **I2** No-hacks rule: root cause fixed in pipeline code; never edit intermediate JSON/state/DB/outputs.
- **I3** Gate binding (SHA-256), no `--force-unsafe`, two human gates (`gate_a_content`-style + `gate_a_spend` + `gate_b_review`).
- **I4** Lipsync non-negotiable: a hero beat MUST produce a lipsync clip or hard-fail; baked lipsync audio preserved verbatim at assembly (`-map 0:a`).
- **I5** Deterministic, AI-free assembly (same manifest + same clips = same output).

### Failures that must become impossible

Accepting a 2.6× over-duration script · a uniformly talking-head storyboard passing as compliant · duplicated render units doubling the timeline · a paid generation request with `prompt="educational video"` and no `--audio`/`--image` · a paid call with no `cost_events` row.

---

## 2. Evidence-based current-state summary (observed, not assumed)

| Item | Evidence (file:line) | Classification |
|---|---|---|
| Teaser budget miscalibrated | `scripts/episode_format.py:34-41` `word_range=[140,230]`, `target_sec=75`. At ~60–74 wpm → 113–230 s (1.5–3× over). | CONFIRMED |
| Budget injected into prompts only (soft) | `episode_format.py:49-60` `format_block`; used by `write_script.py:52,68`, `review.py:75-76` | CONFIRMED |
| No deterministic length enforcement | `produce_db.py:77-106` `invoke_write_script` saves writer output verbatim; `produce_db.py:109-155` `invoke_review_script` runs LLM `review_loop` then saves — no programmatic word/duration check | CONFIRMED |
| Role discarded on save | `authoring_service.py:117` `seg_id = _db._id("seg")` (random id); `:123` stores `seg.get("label","S{i:03d}")`; `get_script_segments` (`:151-161`) returns id/label/text/word_count only — no role/shot_type | CONFIRMED |
| Shot-type derivation wrong vocab + uniform fallback | `produce_db.py:363-381` `_derive_shot_type` returns `talking_head_*`; falls to `talking_head_standard` when no role keyword. Canonical vocab differs: `review_storyboard.py:28-34` | CONFIRMED |
| Bands enforced downstream | `review_storyboard.py:88-108` `_bands_check` (hero 25–40%, broll≥25%, graphics≥10% for explainer; relaxed for short). `direct_storyboard.py:105-151` is the real canonical generator | CONFIRMED |
| Invalidation skips render units (D-015) | `production_db.py:353-368` `invalidate_stages` marks `stage_runs` stale only. `production_repo.py:439-442` `plan_render_units` does `MAX(ordinal)+1` (appends, never supersedes) | CONFIRMED |
| `render_units` has lifecycle columns already | `db/migrations/001_production_ledger.sql:206-232`: `status`, `parent_render_unit_id`, `slot_index`, `slot_total`, `UNIQUE(production_id,ordinal)` | CONFIRMED |
| One slot per beat (slotting gap) | `produce_db.py:463-479` span spec has no `slots` key; `production_repo.py:423-430` defaults to one slot = whole span | CONFIRMED |
| Generation payload minimal (Q-001) | `produce_db.py:662-667` request = `{asset_type,model,duration_ms,audio_policy}`; no prompt/image/audio | CONFIRMED |
| Real Seedance adapter exists but incomplete | `paid_adapters.py:32-63` `HiggsfieldSeedanceAdapter.submit` builds `--prompt/--duration/--aspect_ratio/--resolution/--mode`; `prompt` defaults `"educational video"`; **no `--audio`/`--image`**. Registered `:136` | CONFIRMED |
| Reference frames present | `assets/reference/james/canonical/JAMES_*.png` (25 files, e.g. `JAMES_MEDIUM_FRONT_NAVY_SWEATER_SPEAKING_002.png`) | CONFIRMED |
| Assembly has clips+narration only | `assemble_db.py:120-183` `build_assembly_manifest` (no graphics/music layer). `assemble.py:52` already imports `generate_music`; overlay support at `:253-260`,`:378` | CONFIRMED |
| TTS cost not recorded | `produce_db.py:190-251` `invoke_tts` calls `ElevenLabsAdapter.submit` (`:226`) then `record_tts_artifact` — no `cost_events`. `provider_adapter.py:100-128` `record_actual_cost` reads a `provider_jobs` row (TTS path has none). `tts_service.py:387,408` has unused cost helpers | CONFIRMED |

**Program state:** S0–S8 COMPLETE (S8 exit-gate PASS @ `4152574`). S9 paid test IN PROGRESS, **~$0.90 of $5.00 spent** (3 real ElevenLabs calls). Real run **paused at `gate_a_spend`**. No further paid call permitted until this sprint + user re-approval.

---

## 3. Architectural decisions

- **AD-1 (enforcement is programmatic, not prompt-only).** LLM reviewers demonstrably passed a 2.6× over-length script. Budget/duration compliance must be a deterministic gate in pipeline code that raises/revokes on violation, with the prompt block retained as guidance.
- **AD-2 (canonical shot-type vocabulary everywhere).** The DB storyboard must emit the `review_storyboard.py`/`direct_storyboard.py` vocabulary (`hero_lipsync`/`broll_*`/`graphic_*`). `talking_head_*` is retired from the DB path. See S9-C04 for the route-through-`direct_storyboard.py` vs deterministic-assignment decision.
- **AD-3 (supersession, not deletion).** Render units are immutable history. Re-compile marks the prior plan's units `superseded` (status column already exists) and threads `parent_render_unit_id`; consumers filter to the active plan revision. No destructive updates.
- **AD-4 (audio slicing belongs to slotting).** Each slot already has a time range; the hero audio slice = `master[start:end]`. Slice files are materialized in S9-C05 and consumed as `--audio` in S9-C06. Lipsync baked audio remains verbatim at assembly (I4).
- **AD-5 (no paid call in tests).** Every ticket proves behavior with `--dry-run`, mocks, `FakeProvider`, or deterministic fixtures. `YT_TEST_MODE=1` throughout. The single real paid run resumes only after Wave 3 + user `gate_a_spend` re-approval.
- **AD-6 (one ticket per session).** Per global CLAUDE.md. Tickets are ordered by dependency; do not start a blocked ticket.

---

## 4. Waves and dependency graph

```
Wave 1 (independent foundations)     Wave 2 (structure)        Wave 3 (paid-path capstone)
  S9-C01 duration  ────────────────► S9-C04 storyboard mix ──► S9-C06 generation adapter
  S9-C02 D-015 supersede ──────────► S9-C05 slotting+slices ──►
  S9-C03 tts cost                                            S9-C07 assembly richness ◄─ S9-C04
  S9-C08 test isolation (no deps; test reliability)
  S9-C09 hermetic research/LLM tests (unblocks the suite-wide validation gate)
```

- **Wave 1:** S9-C01, S9-C02, S9-C03, S9-C08, S9-C09 (mutually independent; **do C08/C09 early** — they make the suite trustworthy so every other ticket can be validated).
- **Wave 2:** S9-C04 (blockedBy C01), S9-C05 (blockedBy C02).
- **Wave 3:** S9-C06 (blockedBy C04, C05), S9-C07 (blockedBy C04; may overlap C06).

---

## 5. Ticket index

| Ticket | Title | Wave | Req/Defect | Exec class | Blocks |
|---|---|---|---|---|---|
| S9-C01 | Deterministic script-duration compliance + teaser budget recalibration | 1 | R1 / D-DUR | COMPLEX | C04 |
| S9-C02 | Supersede render units on re-compile (D-015) | 1 | R3 / D-015 | COMPLEX | C05 |
| S9-C03 | Record TTS paid-call cost in `cost_events` | 1 | R7 / D-COST | ROUTINE | — |
| S9-C08 | Eliminate module-level `PRODUCTION_DB_PATH` override (test isolation) | 1 | R8 / D-017 | COMPLEX | — |
| S9-C09 | Hermeticize research/LLM tests (unmocked kiro-cli stalls suite) | 1 | R9 / D-018 | COMPLEX | unblocks validation gate |
| S9-C04 | Canonical, band-compliant storyboard shot mix | 2 | R2 / D-016 | REASONING_CRITICAL | C06,C07 |
| S9-C05 | Multi-clip slotting + per-slot hero audio slices | 2 | R4 / D-SLOT | COMPLEX | C06 |
| S9-C06 | Real generation request: prompt + hero `--image` + hero `--audio` | 3 | R5 / Q-001 | REASONING_CRITICAL | — |
| S9-C07 | Assembly richness: graphics overlay + music bed | 3 | R6 / D-ASM | COMPLEX | — |

---

## 6. Traceability matrix

| Requirement / risk | Ticket(s) | Executable proof | Acceptance gate |
|---|---|---|---|
| R1 duration compliance | S9-C01 | unit test: over-budget script rejected; teaser word_range recalibrated | W1-gate |
| R3 D-015 no duplication | S9-C02 | integration test: re-compile → exactly one active unit set | W1-gate |
| R7 TTS cost recorded | S9-C03 | unit test: `cost_events` row after mocked TTS | W1-gate |
| R8 test isolation / order-independence | S9-C08 | orchestrator→e2e batch passes; meta-guard on module-scope env | W1-gate |
| R9 test hermeticity (no unmocked external LLM/web) | S9-C09 | full suite green with kiro-cli unavailable | W1-gate (unblocks all validation) |
| R2 storyboard mix | S9-C04 | `review_storyboard` passes on DB-produced storyboard | W2-gate |
| R4 slotting | S9-C05 | unit test: 30 s beat → N slots ≤ max clip len; slices materialized | W2-gate |
| R5 real generation request | S9-C06 | contract test: hero payload has prompt+image+audio (mock, no paid call) | W3-gate |
| R6 assembly richness | S9-C07 | contract test: manifest has graphic+music layer; assembled output has music track | W3-gate |
| I1–I5 invariants | all | regression: existing YT_TEST_MODE/gate/lipsync/assembly tests still green | every wave gate |
| RK1 paid-path correctness | S9-C06 | dry-run payload diff + `--dry-run` adapter verification before any paid call | W3-gate |
| I6 financial rule | all | no paid call in any ticket; spend unchanged at ~$0.90 | final gate |

---

## 7. Wave gates

- **W1-gate (after C01,C02,C03):** full suite green; the over-budget script is rejected deterministically; re-compile yields one active unit set; a mocked TTS writes a cost row. **Zero paid calls.**
- **W2-gate (after C04,C05):** a compliant ~75 s script + a `review_storyboard`-passing storyboard + a slotted render plan with hero audio slices are all producible in test/dry-run mode. Full suite green. **Zero paid calls.**
- **W3-gate (after C06,C07):** dry-run generation payload for a hero unit carries prompt + image + audio slice; `HiggsfieldSeedanceAdapter` builds `--audio`/`--image` under `--dry-run`; assembly manifest has a graphic + music layer. Full suite green. **Zero paid calls.** Then STOP and request user `gate_a_spend` re-approval before any real generation.

---

## 8. Final acceptance gates (sprint)

1. Requested behavior works through a real observable path (the paused `db/s9_real.db` run, once re-approved, advances past `gate_a_spend` into a well-formed generation).
2. Each confirmed defect (D-DUR, D-015, D-016, D-SLOT, Q-001, D-ASM, D-COST) has a regression test.
3. Invalid states fail loudly (over-budget script, non-compliant storyboard, duplicated units, payload missing prompt/image/audio).
4. No dummy output / silent fallback introduced.
5. Source-of-truth + architecture invariants (I1–I5) consistent.
6. No unrelated regression (full suite green at HEAD).
7. Unit/contract/integration/E2E checks pass; runtime proof where mocks could hide breakage.
8. No material perf/resource regression.
9. Docs/commands match behavior.
10. Restart/recovery works (idempotent re-run; supersession correct on resume).
11. Independent audit + validator evidence recorded.
12. Repo buildable, testable, reviewable.

---

## 9. Major risks and blockers

- **RK1 (highest) — S9-C06 generation adapter:** the only ticket on the paid, partly-irreversible path. Must be verified with `--dry-run`/mocks **before** any paid call. Reference image selection and audio-slice provenance must match the lipsync invariants (I4) or final QA will block.
- **RK2 — S9-C04 vocabulary reconciliation:** genuine design choice (route DB storyboarding through `direct_storyboard.py` vs deterministic band-compliant assignment in `_derive_shot_type`). Marked REASONING_CRITICAL; reproduce non-compliance, then decide. Visual-intent richness couples into S9-C06's prompt source.
- **RK3 — S9-C05 slotting/slicing:** coverage math (no gaps/overruns) and audio-sync (slice ↔ slot ↔ final assembly) must stay consistent with the lipsync provenance hash checked at assembly.
- **BLOCKER (human):** no real generation may run until Wave 3 is complete AND the user re-approves `gate_a_spend`. Hard cap $5.00; ~$0.90 spent. No automatic paid retry; stop on first failed paid request.

---

## 10. Execution model

- One ticket per coding session (global CLAUDE.md). Load `STATE.json` + the active ticket before editing.
- Ticket loop: `LOAD → BASELINE → REPRODUCE → IMPLEMENT → FOCUSED TEST → AUDIT → REPAIR → VALIDATE → RECORD`. Max 3 engineer–audit–repair cycles.
- An **auditor reviews but does not repair**; only an **independent validator** marks a ticket accepted.
- Append every action to `EXECUTION_LOG.jsonl` (append-only).
