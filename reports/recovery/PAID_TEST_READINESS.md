# Sprint 9 — Controlled Paid 45-Second Provider Test (S9-T01 PLAN)

**Status:** DRAFT — awaiting Sprint 8 exit-gate PASS and explicit human approval of
this plan + hard cap. **No paid call will be made until both are received.**

**Date drafted:** 2026-06-18. **Branch:** `fix/flagship-001-end-to-end-recovery`.

## 1. Objective

Execute exactly ONE controlled 45-second paid production through the DB-native
pipeline using REAL providers, to prove the paid path works end-to-end (real TTS,
real media generation, real QA/assembly) under the same invariants proven locally
in Sprint 8.

## 2. Inputs (frozen + hashed at S9-T02)

- **Script:** the deterministic 5-segment "compound interest" script used in the S8
  fixture (~67 words, ~45s narration). Frozen as a `script` document revision.
- **Storyboard:** 5 beats — B1 hero, B2 b-roll(environment), B3 hero, B4 b-roll(human),
  B5 local graphic — with full R7 B-roll semantic contracts and hero→B-roll→hero
  continuity. Frozen as a `storyboard` revision.
- **Master narration:** ONE ElevenLabs TTS call (the single continuous-voiceover
  master). Bound to the script revision SHA.
- **Render plan:** 5 render units (see §3). Bound to the script+storyboard+timing SHAs.
- Spend approval (`gate_a_spend`) binds to the exact render-plan SHA.

## 3. Provider requests, models, durations, estimated cost

| Beat | Asset | Model | Duration | Est. cost |
|---|---|---|---|---|
| TTS (master) | narration_master | eleven_v3 | ~45s | ~$0.30 |
| B1 | lipsync_video | **seedance_2_0_fast** (unlimited) | ~8s | $0.00 |
| B2 | generated_video | kling3_0 | ~5s | $0.49 |
| B3 | lipsync_video | **seedance_2_0_fast** (unlimited) | ~7s | $0.00 |
| B4 | generated_video | kling3_0 | ~6s | $0.49 |
| B5 | local_graphic | local (deterministic) | ~6s | $0.00 |

**Estimated total: ~$1.28** (ElevenLabs TTS ~$0.30 + 2× kling3_0 b-roll $0.98;
hero/lipsync is $0 under the temporary unlimited seedance_2_0_fast authorization).
Costs are estimates; actuals are recorded per provider response in `cost_events`.

## 4. Hard cap

**$5.00 USD** (~4× the estimate, conservative headroom for any per-clip variance).
Execution aborts if estimated or actual spend would exceed the cap.

## 5. Retry policy & stop conditions (non-negotiable)

- **No automatic paid retry.** A failed paid request halts the run.
- **Stop on:** any provider error; any media-QA or final-QA failure; any artifact
  SHA/validation mismatch; spend reaching the cap; lipsync/safe-boundary returning
  BLOCKED.
- If repair would require another paid request, STOP and request explicit approval.
- Every external job ID and raw provider response is recorded; every downloaded
  artifact is ffprobe+SHA validated before acceptance.

## 6. Approvals required (human-in-the-loop)

1. **gate_a_spend** — render-plan SHA approval (before any generation).
2. **gate_b_review** — final-deliverable SHA approval (before publish).

Both require your explicit decision. In S9 they are NOT auto-approved (no
`YT_TEST_MODE`).

## 7. Acceptance criteria (S9-T05 final validation)

Actual 45s output; correct James presentation; acceptable lipsync; no neighbouring
speech; no provider narration in the final mix; relevant B-roll; no repetitive
laptop/notebook filler; exact deterministic graphic text; no frozen/blank media;
music+graphics present; captions aligned; final technical QA passes; actual spend
within cap; all evidence current. Decision: GO / CONDITIONAL GO / NO-GO / BLOCKED.

## 8. What this plan is NOT

- Not a content/quality benchmark — it's a controlled paid-path smoke test on
  deterministic content.
- Not authorized to run until you approve §4 (hard cap) and the plan overall.

---

**APPROVAL REQUIRED:** confirm the $5.00 hard cap and authorize S9-T02 (one paid
production) before any provider call is made.
