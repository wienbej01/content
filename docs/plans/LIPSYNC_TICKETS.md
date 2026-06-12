# LIPSYNC IMPLEMENTATION — TICKET BOARD

**Date:** 2026-06-12
**Parent spec:** `docs/plans/PRODUCTION_V2_BLUEPRINT.md` (§3.8, §3.13, §5, §6, §10 rules 4/10)
**Goal:** Production-grade talking-head lipsync for `hero_lipsync` beats. Talking heads are the core product. No silent degradation, ever.
**Spend rules:** Zero Higgsfield spend through T1–T8. T9 spends exactly one canary clip (~$1.10) after human approval. T10 spends the remainder only after canary pass. Total project ≤ $60 cap.

## Roles

| Role | Model | Permissions |
|---|---|---|
| **ENGINEER** | Opus (Sonnet where marked) | Writes code/config/tests. May not record gates for its own work as "verified". May not render. |
| **AUDITOR** | Sonnet | **Read-only on production code.** Runs tests, inspects diffs/artifacts, attempts adversarial inputs, writes audit reports to `docs/plans/audits/`. May write test files ONLY if a coverage gap is found (flagged to ENGINEER). May not fix production code. |
| **VALIDATOR** | Fable-lite (or human) | Reads audit reports + artifacts. Issues `APPROVE` / `REVISE(ticket-id, findings)` verdicts. REVISE loops back to ENGINEER, then re-audit, then re-validate. Max 2 loops per ticket before human escalation. |

**Workflow per ticket:** ENGINEER implements → AUDITOR audits (report committed) → VALIDATOR verdict → next ticket. Tickets within a phase may not start until the previous phase is validated.

---

## Phase A — Stop the bleeding

### T1 — Kill silent lipsync degradation [ENGINEER / Opus]
- **Objective:** A `hero_lipsync` beat with no `audio_slice` must hard-fail at compile, not degrade to a non-lipsynced hero shot. Remove the graceful-degradation path entirely ("Fix 2").
- **Files:** `scripts/compile_media_prompts.py`, `scripts/generate_media.py`
- **Implementation:**
  - Compile: missing/invalid `audio_slice` on any `hero_lipsync` beat → exit 1, message names every offending beat id.
  - Generate: defense-in-depth — refuse to render a `hero_lipsync` beat without a slice even if a stale media plan slips through.
- **Tests:** `tests/test_compile_media_prompts.py::test_lipsync_beat_without_slice_fails`, `::test_error_names_all_offending_beats`; `tests/test_generate_media.py::test_generate_refuses_sliceless_lipsync_beat`
- **Acceptance gate:** Compiling the current (slice-less) `media_plan` source storyboard FAILS loudly listing all hero beats. No code path converts `hero_lipsync` → non-lipsync.
- **Block condition:** Any reachable degradation path remaining = REVISE.

### T2 — QA hard checks for lipsync clips [ENGINEER / Sonnet]
- **Objective:** `qa_media.py` validates lipsync clips structurally.
- **Files:** `scripts/qa_media.py`
- **Checks (all fatal):** `hero_lipsync` clip has an audio stream; audio duration matches beat's true speech length ±0.1s; clip video duration ≥ slice duration; provenance fields present in the beat record.
- **Tests:** `tests/test_qa_media.py::test_lipsync_clip_missing_audio_fatal`, `::test_audio_duration_mismatch_fatal`, `::test_voiceover_clip_with_audio_still_fatal` (existing rule must not regress)
- **Acceptance gate:** Fixture clips (one valid, one silent, one wrong-duration) produce pass/fail/fail.
- **Block condition:** Any lipsync check downgradeable to a warning = REVISE.

---

## Phase B — Real audio slices

### T3 — Silence-snapped beat→audio mapping [ENGINEER / Opus]
- **Objective:** Wire `audio_timing.py` into `compile_media_prompts.py` so every `hero_lipsync` beat carries a real, validated `audio_slice`.
- **Files:** `scripts/compile_media_prompts.py`, `scripts/audio_timing.py`
- **Implementation:**
  - Map each beat's `narration_word_span` to timestamps in `narration/{segment_id}.mp3`, **snapped to nearest detected silence** (beats are sentence-aligned; never interpolate mid-word).
  - Validate slice duration vs `est_duration_sec` within ±20%; unresolvable → compile failure with beat id + silence-map context.
  - Extract `narration/slices/{beat_id}.mp3` via ffmpeg: 200ms leading silence (closed mouth at start), tail padded with room tone to next **integer** second (seedance `duration` is an integer). Store true unpadded speech length.
  - Beat fields written: `audio_slice {file, start_sec, end_sec, speech_len_sec, padded_len_sec, slice_sha256, parent_mp3_sha256}`.
- **Tests:** `tests/test_audio_slicing.py` (new): `::test_slice_snaps_to_silence_not_midword` (synthetic mp3 with known silences), `::test_slice_duration_within_tolerance`, `::test_unresolvable_beat_fails_compile`, `::test_padding_to_integer_seconds`, `::test_lead_in_200ms`, `::test_slice_hashes_recorded`
- **Acceptance gate:** Compiling flagship 001 yields a slice for every `hero_lipsync` beat; spot-check 3 slices by ear/waveform = clean sentence boundaries.
- **Block condition:** Any proportional/word-position interpolation fallback = REVISE (that was rejected option A).

### T4 — Merge consecutive lipsync chains [ENGINEER / Opus]
- **Objective:** Consecutive `hero_lipsync` beats with combined duration ≤15s render as ONE clip with one combined slice (B086+B087 = 12.1s is the live case). Prevents same-setup jump cuts.
- **Files:** `scripts/compile_media_prompts.py` (merge at plan level: `render_group` field), `scripts/generate_media.py` (render per group), `scripts/assemble.py` (map group clip back to beat spans)
- **Tests:** `tests/test_audio_slicing.py::test_chain_under_15s_merges`, `::test_chain_over_15s_not_merged`, `::test_merged_slice_is_contiguous_audio`, `tests/test_assemble.py::test_group_clip_spans_constituent_beats`
- **Acceptance gate:** Flagship plan shows B086+B087 as one render group, one slice, one cost line; storyboard beat structure unchanged.
- **Block condition:** Merge that crosses a non-hero beat or exceeds 15s = REVISE.

---

## Phase C — Generation quality

### T5 — Seedance lipsync render path [ENGINEER / Opus]
- **Objective:** `hero_lipsync` render groups generate via `seedance_2_0` with `--image <angle-correct canonical reference> --audio <slice> --duration <int> --mode std --aspect_ratio 16:9`, full provenance logging (job id, params, slice + reference hashes).
- **Files:** `scripts/generate_media.py`, `scripts/shot_router.py`, `configs/james/model_routing.yaml`
- **Rules:** `mode=std` always (fast variants banned); reference image must match the beat's approved studio angle; consecutive non-merged hero beats may not reuse the identical reference frame; fallback ladder per T7 — never to non-lipsynced hero.
- **Tests:** `tests/test_generate_media.py::test_lipsync_invocation_args` (mocked CLI), `::test_mode_std_enforced`, `::test_reference_angle_mismatch_blocks`, `::test_banned_model_never_invoked`
- **Acceptance gate:** `--dry-run` shows correct full command line per render group, zero API calls.
- **Block condition:** Any render invocation constructed from script-JSON `visual_brief` = REVISE (blueprint §10 rule 2).

### T6 — 720p vs 1080p decision (zero-cost exploration) [ENGINEER / Sonnet]
- **Objective:** Run `higgsfield generate cost` for an identical seedance lipsync job at 720p and 1080p. If 1080p keeps total project spend ≤ $60, set `resolution: 1080p` for all `hero_lipsync` beats (faces suffer most from upscaling); else stay 720p. Document evidence in `docs/plans/audits/resolution_decision.md` and encode in `model_routing.yaml`.
- **Tests:** `tests/test_shot_router.py::test_lipsync_resolution_from_config`
- **Acceptance gate:** Decision file exists with both cost quotes; budget recomputed; cap respected.
- **Block condition:** Resolution hardcoded outside config = REVISE.

### T7 — Fallback ladder + Soul ID evaluation (zero-cost) [ENGINEER / Sonnet]
- **Objective:**
  1. Probe `higgsfield model get cinematic_studio_3_0` (does it accept `--audio`? max duration? `generate cost` for 10s) — it is the approved `experimental_lipsync` fallback.
  2. Probe `higgsfield soul-id` / `soul_cast`: cost to train a Soul ID on James reference frames + per-generation cost. **Report only — do not train.**
  3. Encode fallback ladder in media plan `fallback` fields: seedance retry with adjusted reference (1 retry) → `cinematic_studio_3_0` (if `--audio` supported and budget allows) → **BLOCK and report**. Never veo3/minimax/wan. Never non-lipsynced hero.
- **Output:** `docs/plans/audits/lipsync_fallback_and_soulid.md`
- **Tests:** `tests/test_generate_media.py::test_fallback_ladder_order`, `::test_fallback_never_degrades_to_nonlipsync`
- **Acceptance gate:** Report exists with real CLI output; ladder encoded and tested.
- **Block condition:** Any Soul ID training or paid probe = REVISE.

---

## Phase D — Assembly correctness

### T8 — Baked-audio assembly for lipsync spans [ENGINEER / Opus]
- **Objective:** `assemble.py` uses the lipsync clip's own baked audio for hero spans — never overlays master narration on a lipsync clip (echo) and never strips it (silent mouth). Trim each clip to true speech length (T3 field). Music bed continues per `constraints.json` levels. `validate_lipsync_provenance()` runs at assembly and fails on hash mismatch.
- **Files:** `scripts/assemble.py`, `scripts/tts.py` (manifest fields)
- **Tests:** `tests/test_assemble.py::test_lipsync_span_uses_baked_audio`, `::test_no_narration_overlay_on_lipsync_span`, `::test_trim_to_speech_length`, `::test_provenance_mismatch_fails_assembly`, `::test_segment_timing_within_quarter_second`
- **Acceptance gate:** Fixture assembly: lipsync↔voiceover boundary has no double audio, no silence gap, timing ±0.25s; provenance check demonstrably fires on a tampered fixture.
- **Block condition:** Audible seam or double-audio in fixture output = REVISE.

---

## Phase E — Audit, canary, full render

### T9a — Full audit pass [AUDITOR / Sonnet — read-only]
- **Objective:** Independent verification of Phases A–D before any spend.
- **Actions:** Run full `pytest` (must be green). Re-run the pipeline chain: compile → `review_media_plan.py` → `budget.py` → `generate_media.py --dry-run`. Adversarial checks: delete one slice file and confirm compile/generate fail; tamper a slice hash and confirm provenance failure; craft a 16s hero chain and confirm no merge; grep for any remaining degradation path. Verify gates.json entries are fresh (hashes match artifacts).
- **Output:** `docs/plans/audits/lipsync_audit_T9a.md` — findings table, PASS/FAIL per ticket.
- **Acceptance gate:** All adversarial probes blocked; pytest green; zero Higgsfield calls during audit (verify via `higgsfield generate list`).
- **Block condition:** Any finding rated FAIL → VALIDATOR routes REVISE to the owning ticket.

### T9b — Canary render (single clip, ~$1.10) [ENGINEER executes; HUMAN approves]
- **Objective:** Render exactly ONE hero_lipsync render group (the shortest) after human runs `approve.py --gate render --scope canary`. Extract review frames + the clip.
- **Human checklist:** mouth sync accurate across the whole clip; mouth closed at start/end (200ms lead-in working); identity matches reference; no rubber mouth / warped teeth / waxy skin; studio angle correct.
- **Acceptance gate:** Human records pass in `gates.json` (`canary` gate entry).
- **Block condition:** Canary fail → fallback ladder (T7) on that beat, re-canary; 2 consecutive canary fails → STOP, escalate to VALIDATOR with frames.

### T10 — Full hero render + final QA [ENGINEER executes; gates enforce]
- **Objective:** Render remaining hero render groups; then full `qa_media.py` (G6); then assembly; then human final video QA (G7) per `QA_RUBRIC.md`.
- **Preconditions (all enforced by `gates.py`):** script_review, storyboard_review, media_plan_review, budget, canary, render_approval all `pass` with fresh hashes; pytest green.
- **Acceptance gate:** §7 blueprint acceptance criteria on the assembled video; every automatic_fail_condition in `constraints.json` clear.
- **Block condition:** Any gate stale/missing → `generate_media.py` exits 1. No `--force-unsafe` permitted in this run.

### T11 — Validator feedback loop [VALIDATOR / Fable-lite or human]
- **Objective:** After T9a (pre-spend) and after T10 (post-assembly): read audit report + artifacts, issue `APPROVE` or `REVISE(ticket, findings)`.
- **Loop rule:** REVISE → ENGINEER fixes → AUDITOR re-audits (delta report) → VALIDATOR re-verdicts. Max 2 loops per ticket; third failure escalates to human with the full trail.
- **Output:** verdict appended to `docs/plans/audits/validator_log.md`.

---

## Global acceptance criteria (VALIDATOR checks at T9a and T10)

1. Zero `hero_lipsync` beats without a validated, silence-snapped `audio_slice`; compile dies loudly otherwise.
2. All slices ±20% of beat duration, 200ms closed-mouth lead-in, integer-second padding with true speech length recorded.
3. Consecutive lipsync chains ≤15s rendered as merged single clips; no same-setup jump cuts.
4. Resolution decision documented with cost evidence; total projected spend ≤ $60.
5. Assembly uses baked lipsync audio verbatim; no overlay/strip on hero spans; timing ±0.25s; provenance wired and firing.
6. Fallback ladder never produces a non-lipsynced hero; banned models unreachable.
7. Full pytest green; auditor's adversarial probes all blocked.
8. Spend order strictly: gates → canary ($1.10) → human pass → remainder. Nothing renders outside that order.
