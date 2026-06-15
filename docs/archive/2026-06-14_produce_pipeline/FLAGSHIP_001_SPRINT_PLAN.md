# Sprint Plan — Flagship_001 Remediation (Roles, Models, Feedback Loop)

**Author:** Principal AI Video Engineer (tech lead)
**Date:** 2026-06-13
**Consolidates:** `FLAGSHIP_001_REMEDIATION_PLAN.md` + `FLAGSHIP_001_FORENSIC_AUDIT.md`
**Goal:** Fix every quality-killing defect, prove on a cheap **3-min SHORT** ($25 cap), then authorize flagship spend. **Zero Higgsfield/ElevenLabs spend until all tests + gates are green.**
**Architecture invariants (non-negotiable):** standalone scripts, JSON I/O, no monolithic orchestrator, SHA-256-bound gates, no `--force-unsafe`, human-in-the-loop at storyboard + render.

---

## Roles

| Role | Mandate | Permissions | kiro-cli model |
|------|---------|-------------|----------------|
| **ENGINEER** | Implements tickets: writes production code, config, tests. | May write/modify any code + tests. May run tests. **May NOT record a gate as "verified" for its own work. May NOT render (spend).** | `claude-opus-4.8` for P0 architecture tickets (R2/R3/R-TIMING/R10); `claude-sonnet-4.6` for P1/P2 + config tickets. |
| **AUDITOR** | Independently verifies the engineer's work. **Read-only on production code.** Runs the suite, inspects diffs/artifacts, attempts adversarial inputs, writes audit reports to `docs/plans/audits/`. May write NEW test files only if a coverage gap is found (flagged to engineer). | Read production code; run pytest; create fixtures; write audit `.md`. **May NOT modify production code. May NOT render.** | `claude-sonnet-4.6` (thorough, cheaper than Opus; read-only reasoning). Escalate a contested finding to `claude-opus-4.8` only when the engineer disputes it. |
| **VALIDATOR** | Reads audit reports + artifacts; issues `APPROVE` / `REVISE(ticket, findings)` verdicts; owns the green-gate decision and the spend authorization. | Read everything; run gate-state + dry-run checks (zero spend); record the validator verdict log. **No code, no test authoring, no render.** | `claude-opus-4.8` (highest-judgment, lowest volume — only verdicts). Human co-signs the final spend authorization. |

**Model rationale:** Opus (2.20x) is reserved for the two highest-value activities — architecture implementation (where a wrong abstraction is expensive) and final validation judgment. Sonnet (1.30x) does the bulk implementation and all auditing. Nothing creative routes to Haiku/auto (creative-authority rule in `configs/llm_models.yaml`).

---

## Workflow per ticket (the feedback loop)

```
        ┌─────────────────────────────────────────────────────────┐
        ▼                                                         │
 ENGINEER implements ticket ──► commits + runs pytest ──► AUDITOR audits
 (code + tests)                                              │ (read-only, adversarial,
                                                             │  writes audit report)
                                                             ▼
                                                   VALIDATOR reads audit
                                                             │
                                          ┌──────────────────┴───────────────┐
                                       APPROVE                            REVISE(ticket, findings)
                                          │                                   │
                                          ▼                                   └──► back to ENGINEER ──┘
                                   next ticket / phase gate
```

- **Loop limit:** max **2 REVISE cycles** per ticket. A 3rd failure escalates to the human tech lead with the full trail.
- **Phase gate:** a phase does not start until every ticket in the prior phase is `APPROVE`d AND `pytest` is fully green.
- **Spend gate:** no `generate_media.py` run (even canary) until the VALIDATOR records `SPEND-AUTHORIZED` after the full test suite is green and a dry-run shows the expected cost.
- **Audit artifacts:** each ticket gets `docs/plans/audits/audit_<TICKET>.md`. Verdicts append to `docs/plans/audits/validator_log.md`.

---

## Phase A — Audio architecture (root cause of the headline failure)

> These three are coupled (forensic F1/F3/F9). They must land together; R2 cannot work without R-TIMING and R10.

### A1 — R-TIMING — Emit silence-snapped continuous timing map [ENGINEER · opus-4.8]
- **Problem (F3):** `narration/timing_map.json` is absent; continuous-master assembly is impossible without beat→[start,end] timestamps.
- **Do:** `tts.py` continuous mode produces `timing_map.json` mapping each beat_id to [start,end] in the master MP3, silence-snapped (reuse `audio_timing.py`). No interpolation mid-word.
- **Files:** `scripts/tts.py`, `scripts/audio_timing.py`.
- **Tests:** `test_timing_map_emitted`, `test_timing_snaps_to_silence`, `test_timing_covers_all_beats`.
- **Acceptance:** a fixture script → a valid timing map covering every beat; ZERO TTS spend (local wav fixture).

### A2 — R10 — Manifest as a gated, compiler-emitted artifact [ENGINEER · opus-4.8]
- **Problem (F9):** the manifest is hand-built, ungated, missing `narration_mode` → proximate cause of the double-audio bug.
- **Do:** the compiler (or a new `build_manifest.py`) emits the assembly manifest from `media_plan.json` with `narration_mode: continuous_voiceover`, `continuous_audio`, `timing_map`, and per-clip `[start,end]`. Bind it to a gate hash.
- **Files:** `scripts/compile_media_prompts.py` (or `scripts/build_manifest.py`), `scripts/gates.py`.
- **Tests:** `test_manifest_emitted_from_plan`, `test_manifest_declares_continuous`, `test_manifest_gate_binds_hash`.
- **Acceptance:** manifest is reproducible from the plan; carries continuous mode + timing refs.

### A3 — R2 — Continuous master-audio assembly [ENGINEER · opus-4.8]
- **Problem (F1):** double-audio stutter — lipsync baked audio + segment narration both play. **This is the "garbage script" symptom.**
- **Do:** `assemble.py` finals use continuous master: mute ALL clips (`-an`), lay the single ElevenLabs master, snap muted clips to `timing_map` windows, mix music under, loudnorm once. Retain baked-audio path only behind `--debug-segment-audio`.
- **Files:** `scripts/assemble.py`.
- **Tests:** `test_continuous_master_single_audio_track`, `test_no_audio_eq_shift` (tone-marked), `test_clip_snapped_to_timing_map`, `test_finals_ignore_baked_audio`, `test_no_double_audio_on_lipsync_span`.
- **Acceptance:** assembled fixture has exactly ONE audio stream == master; no double-audio at any lipsync span; boundaries inaudible.
- **Depends on:** A1, A2.

---

## Phase B — Desync + prompt-quality root causes

### B1 — R3 — Split long lipsync beats at compile (never clamp) [ENGINEER · opus-4.8]
- **Problem (F4):** B047/B086/B090 (>10s speech) clamped at render → mouth drift.
- **Do:** `storyboard.py` splits hero beats > `max_clip_duration_sec` (10s, config) into ≤10s sub-beats at sentence boundaries; `compile_media_prompts.py` asserts no hero beat exceeds the max (compile FAIL naming offenders, no clamp). Sub-beats get distinct reference angles + contiguous slices.
- **Files:** `scripts/storyboard.py`, `scripts/compile_media_prompts.py`.
- **Tests:** `test_hero_beat_over_max_is_split`, `test_compile_rejects_overlong_lipsync`, `test_split_beats_get_distinct_angles`.

### B2 — R11 — Dedupe `[beat focus]` prompt tag [ENGINEER · sonnet-4.6]
- **Problem (F2):** the beat-focus tag is emitted TWICE on 81/96 beats — a doubled noisy fragment degrading every generated clip.
- **Do:** `_compose_positive()` emits each `[beat focus: …]` once; collapse whitespace.
- **Files:** `scripts/compile_media_prompts.py`.
- **Tests:** `test_beat_focus_not_duplicated` (assert ≤1 focus tag per prompt across a compiled plan).

### B3 — R12 — Forbid same narration span on title-card + following hero [ENGINEER · sonnet-4.6]
- **Problem (F6):** B025 title card and B026 hero narrate the same sentence → redundant pacing.
- **Do:** storyboard segmentation must not assign overlapping narration spans to a title_card and the immediately-following hero; reassign or merge.
- **Files:** `scripts/storyboard.py`, `scripts/review_storyboard.py` (backstop check).
- **Tests:** `test_no_overlapping_titlecard_hero_narration`.

---

## Phase C — QA safety net (the missing guard)

### C1 — R1 — Perceptual QA: blank-screen + frozen-video detection [ENGINEER · opus-4.8]
- **Problem (F5):** 2.5 min of blank screens + frozen lipsyncs passed Gate 8. QA never checked content.
- **Do:** `qa_media.py` adds (scope=source, generated_video only): blank/solid-color via `signalstats`/`blackdetect` (luma stddev floor) → FATAL `BLANK_SCREEN`; frozen via `freezedetect` + first/last-frame SSIM > 0.985 → FATAL `FROZEN_VIDEO`. Thresholds in `constraints.json → qa_thresholds`. Scope graphics OUT (intentionally static).
- **Files:** `scripts/qa_media.py`, `docs/channel_universe/constraints.json`.
- **Tests:** `test_blank_screen_fatal`, `test_frozen_video_fatal`, `test_moving_video_passes`, `test_graphics_not_falsely_frozen`, `test_blank_threshold_configurable`.

---

## Phase D — Content + brand gates

### D1 — R4 — Deterministic stutter pre-filter [ENGINEER · sonnet-4.6]
- **Problem (§2A guard):** future LLM repetition loops. (Note: NOT the cause of the current stutter — F1 is.)
- **Do:** `review_script.py` runs `detect_repetition()` (3/5-gram ratio + adjacent near-duplicate) BEFORE LLM personas; on trip → hard block, skip LLM (no spend), trigger re-roll.
- **Files:** `scripts/review_script.py`, `constraints.json → qa_thresholds.max_ngram_repetition`.
- **Tests:** `test_repetition_detected_skips_llm` (stub llm_call, assert 0 calls), `test_clean_script_passes_prefilter`.

### D2 — R5 + R13 — Text/gibberish negatives + hard reject [ENGINEER · sonnet-4.6]
- **Problem (F7):** b-roll renders gibberish writing/reading.
- **Do:** add text/writing/reading negatives to `constraints.json`; `generate_media.py` HARD-rejects (not flags) a b-roll prompt with writing/reading verbs in source scope; `b_roll_rules.content_must_be` enforced at compile.
- **Files:** `docs/channel_universe/constraints.json`, `scripts/generate_media.py`, `scripts/compile_media_prompts.py`.
- **Tests:** `test_broll_with_writing_rejected`, `test_negatives_include_text_terms`.

### D3 — R6 — Anti-loop LLM params + reroll cap [ENGINEER · sonnet-4.6]
- **Do:** `configs/llm_models.yaml` adds an anti-repetition directive to `sonnet_creative` + `max_reroll_attempts: 2` then escalate (Telegram). `llm_call.py` injects the directive.
- **Files:** `configs/llm_models.yaml`, `scripts/llm_call.py`.
- **Tests:** `test_creative_profile_has_antiloop_directive`, `test_reroll_cap_enforced`.

### D4 — R7 — Shot-mix structural failsafe [ENGINEER · sonnet-4.6]
- **Problem (F-monotony):** 0% graphics, no hook.
- **Do:** `storyboard.py` after routing: if `graphics_ui_pct<10` inject graphic beats; if `kinetic_text_pct<2` inject kinetic on stats; if Act-1 has no hook → FAIL parse. Recompute bands AFTER R3 split + R7 inject.
- **Files:** `scripts/storyboard.py`.
- **Tests:** `test_storyboard_injects_graphics`, `test_missing_hook_fails`, `test_bands_recomputed_after_inject`.

### D5 — R8 — Reference-frame lock enforcement [ENGINEER · sonnet-4.6]
- **Problem (F8):** wardrobe/host drift.
- **Do:** compile asserts hero `reference_images[0]` ∈ active set; QA flags any hero clip whose generation-log reference is off-set. Wardrobe-from-pixels stays a human canary check.
- **Files:** `scripts/compile_media_prompts.py`, `scripts/qa_media.py`.
- **Tests:** `test_hero_reference_in_active_set`, `test_offset_reference_flagged`.

---

## Phase E — Cheap validation vehicle

### E1 — R9 — `short` video-type mode (3-min) [ENGINEER · sonnet-4.6]
- **Do:** `storyboard.py` `short` profile: ~180s, 6–8 beats, MITmonk-shaped (hook→1 framework→CTA), hero ≤25%, ≥1 graphic. **Must include one >10s speech beat so R3/B1 is exercised.** Budget cap `short`=$25 (exists).
- **Files:** `scripts/storyboard.py`.
- **Tests:** `test_short_profile_shape`, `test_short_includes_long_beat_for_r3`.

---

## Phase F — Audit, validate, spend

### F1 — Full audit pass [AUDITOR · sonnet-4.6, read-only]
- Run full `pytest` (must be green). Re-run the chain on the SHORT: compile → review_script (R4) → review_storyboard → review_media_plan → budget → `generate_media.py --dry-run`. Adversarial: tamper a slice hash; feed a silent/blank/frozen fixture; craft a 16s hero chain (must split, not clamp); confirm continuous-master single audio track; grep for any remaining degradation path. Verify gates fresh + SHA-bound; `higgsfield generate list` unchanged (zero spend).
- **Output:** `docs/plans/audits/audit_phaseF.md` — findings table, PASS/FAIL per ticket.

### F2 — Validator verdict + spend authorization [VALIDATOR · opus-4.8 + human co-sign]
- Read F1 audit + artifacts. Issue `APPROVE` or `REVISE`. On full APPROVE + green suite + clean dry-run (≤$5 for the short): record `SPEND-AUTHORIZED` in `validator_log.md`.
- **Then the gated rollout (human executes):** approve render → **canary 1 hero clip (~$1.10)** → human verifies motion+sync+wardrobe → full short render (~$3–5) → `qa_media --scope source` (R1 must pass) → continuous assembly (R2) → human final review.
- **Flagship spend is authorized ONLY after a clean short.**

---

## Sequencing & dependencies

```
Phase A (A1→A2→A3)  ──┐  audio root cause
Phase B (B1,B2,B3)  ──┤  desync + prompt quality
Phase C (C1)        ──┼──► Phase D (D1..D5) ──► Phase E (E1) ──► Phase F (audit→validate→SHORT spend)
                      │
  A1,A2 BEFORE A3.  B1+D4 both change beat count → recompute bands after both.
  C1 will retroactively fail the existing flagship render (expected; prove on SHORT first).
```

## Definition of done (sprint exit)
- `pytest` fully green (≈265+ tests incl. all new perceptual/continuous-audio/split/stutter/short tests).
- All tickets `APPROVE`d by the validator; ≤2 revise cycles each.
- A 3-min SHORT renders end-to-end: no blank/frozen clips (C1), one continuous audio track / no stutter (A3), no >10s lipsync beats (B1), no doubled prompt tags (B2), no text-surface b-roll (D2), MITmonk-shaped with ≥10% graphics (D4), no script stutter (D1).
- Validator records `SPEND-AUTHORIZED`; human canary + final review pass on the short.
- Validation short spend ≤ $25 (realistically ~$3–5).
- **Flagship render authorized only after the short is clean.**

## Model cost summary
| Role | Model | Multiplier | Volume |
|------|-------|-----------|--------|
| Engineer (P0 architecture: A1,A2,A3,B1,C1) | claude-opus-4.8 | 2.20x | High-value, low count |
| Engineer (P1/P2 + config: B2,B3,D1–D5,E1) | claude-sonnet-4.6 | 1.30x | Bulk |
| Auditor (all phases) | claude-sonnet-4.6 | 1.30x | Per-ticket, read-only |
| Validator (verdicts only) | claude-opus-4.8 | 2.20x | Low volume |
