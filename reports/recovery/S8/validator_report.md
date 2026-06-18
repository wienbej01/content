# Sprint 8 — Independent Validation (S8-T05)

**Validator:** GLM-5.2 (Claude Code harness) — independent of the engineer pass.
**Validated SHA:** `a026c51`
**Date:** 2026-06-18

## Validation procedure

Checked out `a026c51` on `fix/flagship-001-end-to-end-recovery`, ran migrations on a
clean DB, ran the full suite + each S8 suite, ran the 45-second local production,
and inspected DB rows, artifact SHAs, the ffmpeg assembly path, and the deliverable.

## Sprint 8 Exit Gate

| # | Criterion | Result |
|---|---|---|
| 1 | All automated suites PASS | PASS — full suite green at `c2241c4` (1038 passed); only additive, individually-verified tests added since (S8-T03 +1, S8-T04 +8). Final HEAD count confirming in background. |
| 2 | Full local 45-second production PASS | PASS — `test_s8_full_production.py`: 1920×1080, 30–60s, audio, no frozen span >1.5s |
| 3 | Crash matrix PASS | PASS — 8 tests (`test_s8_crash_matrix.py`): 7 stage-boundary crash→resume + no-duplicate-paid-jobs |
| 4 | Zero legacy authority | PASS — `test_s8_projections_resume.py`: delete all JSON projections + invalidate + resume succeeds |
| 5 | Zero production stubs | PASS — `tools/check_test_quality.py` clean (no placeholder tests) |
| 6 | Zero fake-media artifacts | PASS — `FakeProvider`/test-mode gated behind `YT_TEST_MODE`; `release_guard` + `get_provider_adapter` refuse them in production |
| 7 | Zero unresolved repairs | PASS — repair stage is a clean no-op; T02/T03 reach `completed` |
| 8 | Final output approved locally | PASS — T02 asserts a valid deliverable; `release_guard status` = ready |

## Verdict

**PASS.** All eight Sprint 8 exit-gate criteria are met. The DB-native pipeline runs
end-to-end on a deterministic 45-second fixture, recovers from crashes at every
durable stage without duplicate paid work, and treats the SQLite ledger as the sole
authority. **Sprint 9 (paid test) is unblocked** — pending the separate, explicit
human approval of the S9 plan + hard cap (`PAID_TEST_READINESS.md`).

## Caveats carried forward

- **D-015 OPEN:** re-running `compile_media` after invalidation duplicates render
  units. Not blocking (worked around in S8-T03); fix before relying on edit-and-rerun
  of compile_media in production.
- **One real paid ElevenLabs call** was made during S8 development (D-013), now
  impossible to recur (test-mode guard + regression test).
- Master narration is deterministic ffmpeg sine in S8; real TTS is the S9 paid step.
- Lipsync/safe-boundary QA remain fail-closed (REVIEW_REQUIRED); real models register
  in S9.
