# Sprint 8 — Full Local 45-Second E2E

**Agent:** GLM-5.2 (Claude Code harness)
**Base SHA:** `68f3ee5` (program base)
**Result SHA:** `a026c51` (HEAD of `fix/flagship-001-end-to-end-recovery`)
**Date:** 2026-06-18

## Objective

Exercise the entire DB-native stage graph end-to-end on a deterministic 45-second
fixture, prove crash/resume idempotency and zero-legacy-authority, and validate a
real deliverable — the gate before any paid (Sprint 9) work.

## Tickets

| Ticket | Objective | Status |
|---|---|---|
| S8-T01 | Define the deterministic 45-second fixture | PASS — `tests/e2e/s8_helpers.py::build_production` (2 hero lipsync, 2 B-roll with distinct semantic functions, 1 deterministic graphic, hero→B-roll→hero continuity, captions/graphics, music bed path, 16:9) |
| S8-T02 | Execute local E2E with test providers | PASS — `test_s8_full_production.py`: full graph via `run_production()` in `YT_TEST_MODE`; asserts 1920×1080 deliverable, 30–60s, audio, no frozen span >1.5s |
| S8-T03 | Delete projections and resume | PASS — `test_s8_projections_resume.py`: deleting all legacy JSON projections + invalidating + resuming succeeds (DB is sole authority) |
| S8-T04 | Crash matrix | PASS — `test_s8_crash_matrix.py`: 7 stage-boundary crash→fail→resume→complete + no-duplicate-paid-jobs at generate_media |
| S8-T05 | Independent validation | See `validator_report.md` |

## Defects found and fixed during S8 (root-cause fixes, no artifact patching)

The orchestrator tests mocked every stage, so none of these were caught before a
real run. All recorded in `reports/recovery/DEFECT_LEDGER.md`.

- **D-013 (BLOCKER, FIXED f69d601):** `invoke_tts` instantiated `ElevenLabsAdapter`
  directly, bypassing `YT_TEST_MODE` — a missing master narration triggered a REAL
  paid ElevenLabs call (~32s). One real paid call was made during development before
  the fix. Now fail-loud in test mode; pinned by `test_s8_tts_paid_guard.py`.
- **D-014 (BLOCKER, FIXED b77c2c6 + a5ded58):** the DB-native orchestrator could not
  run end-to-end — `audio_timing` key mismatch (zero-duration spans), `compile_media`
  never populated the R7 B-roll semantic contract, `generate_media` marked itself
  succeeded after only submitting (jobs never completed), `qa_media`/`publish`/
  deliverable lookups queried non-existent columns, and `build_assembly_inputs`
  returned a DTO incompatible with `assemble.py` (added `build_assembly_manifest`
  bridge). Plus `FakeProvider` now emits moving `testsrc2` media.
- **D-015 (MEDIUM, OPEN):** re-running `compile_media` after invalidation duplicates
  render units (`plan_render_units` doesn't supersede prior units). Worked around in
  S8-T03 by invalidating from `assemble`; recorded for a focused fix.

## Commands

```bash
python3 -m pytest tests/e2e/test_s8_full_production.py -q        # ~23s, full E2E
python3 -m pytest tests/e2e/test_s8_projections_resume.py -q     # ~37s
python3 -m pytest tests/e2e/test_s8_crash_matrix.py -q           # ~3 min (8 tests)
python3 -m pytest tests/test_s8_tts_paid_guard.py -q             # <1s
python3 -m pytest -q                                              # full suite
```

## Database / artifact effects

- Test productions run in conftest-isolated tmp DBs; deliverables land in
  `Videos/Projects/<slug>/` and provider media in `assets/media/<prod>/` (both
  gitignored). Cleaned per-test by unique slugs.
- No paid provider call is possible in `YT_TEST_MODE` after D-013.

## Known limitations

1. D-015 open (compile_media invalidation duplicates units) — does not block S8.
2. Master narration is a deterministic ffmpeg sine (real TTS is paid → S9).
3. Lipsync/safe-boundary QA stays fail-closed (REVIEW_REQUIRED) — no real model is
   registered in S8; real models are an S9 integration concern.

## Rollback

All S8 changes are additive fixes + new tests on `fix/flagship-001-end-to-end-recovery`.
`git revert` the S8 commits (c2241c4, b4791f1, a026c51, and the D-013/D-014 fix
commits) to restore pre-S8 behavior (which could not run end-to-end).
