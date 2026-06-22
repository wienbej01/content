# Sprint 9 — Controlled Paid 45-Second Provider Test (in progress)

**Agent:** GLM-5.2 (Claude Code harness)
**Date:** 2026-06-18
**Hard cap:** $5.00 (approved). **No automatic paid retry.**

## S9-T01 — Plan

Approved plan in `reports/recovery/PAID_TEST_READINESS.md`. User authorized one paid
production ($5 cap) with seedance_2_0 + fast mode (hero), kling3_0 (b-roll), ElevenLabs
(TTS). Both human gates (gate_a_spend, gate_b_review) require sign-off.

## S9-prep — Real-adapter + credential verification

- **ElevenLabs:** `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` present in runtime.env.
- **Higgsfield:** CLI authenticated (`jacobw@gmail.com`, max plan, ~2878 credits).
- **Models verified** (`higgsfield model list --video`): real models are `seedance_2_0`,
  `kling3_0`, etc. There is **no `seedance_2_0_fast` model** — corrected routing to
  `seedance_2_0` (+ `--mode fast`); commit `706d1d1`. Added logical→real model
  resolution in `invoke_compile_media` (was storing `lipsync_primary`).
- **Reference frames present:** `assets/reference/james/canonical/JAMES_*_NAVY_SWEATER_*.png`.

## S9-T02 (partial) — TTS PAID CALL ✓

**One real ElevenLabs TTS call made and succeeded (2026-06-18).**
- Production `prod_24a2b93ad2b143a5a302c3069c603edf` (slug `s9_paid`).
- Master narration: `Videos/Projects/s9_paid/narration/continuous.mp3`, **30.35s**,
  SHA256 `952ff5f48cea…`, registered as `tts_master` artifact.
- **Cost: ~$0.30** (ElevenLabs multilingual_v2, ~360 chars). Within cap.
- **Finding:** `invoke_tts` does not record a `cost_events` row (ElevenLabsAdapter
  returns audio inline; `record_actual_cost` not wired). Tracking gap to fix.

## S9-T02 (remaining) — Generation: BLOCKED on adapter build-out (Q-001)

The real generation path is not yet wired (handover Q-001, now concrete):
`invoke_generate_media` builds a request payload of only `{asset_type, model,
duration_ms, audio_policy}` — but a meaningful Higgsfield request needs:
- **prompt** (from prompt_template / B-roll semantic) — currently defaults to
  `"educational video"` for every clip.
- **hero lipsync:** `--audio` (the master-narration slice for the beat) +
  `--image` (the James reference frame) — `seedance_2_0` is the only model that
  accepts `--audio`; without it there is no lip sync.
- **b-roll:** prompt only (kling3_0).

Reference frames exist; the master narration exists (post-TTS). Building this out is
the remaining S9 engineering: enrich `compile_media` (attach prompt + reference +
slice) → `generate_media` (pass `--prompt/--image/--audio`) → adapter. Then run
generation, QA, assembly, Gate B.

## Spend so far

| Provider | Estimated | Actual recorded |
|---|---|---|
| ElevenLabs (TTS) | ~$0.30 | ~$0.30 (not in cost_events — gap) |
| Higgsfield | $0 (pending generation) | $0 |
| **Total** | **~$0.30 of $5.00 cap** | |

## Recommendation

Proceed to build the generation request enrichment (prompt + hero `--audio`/`--image`),
then run the real generation. This is the Q-001 work that makes the paid test
meaningful; without it generation would produce generic, non-lipsynced clips.
