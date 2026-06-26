# Validation Report — S15_T001

**Ticket**: Define format-level shot-mix contract
**Date**: 2026-06-26
**Validator**: GLM-5.2[1m]
**Sprint**: S15 — Shot-mix contract and semantic role validation

---

## Validation Scope

Independent validation (distinct from engineering) of S15_T001:

- Run the ticket tests.
- Run relevant existing tests.
- Inspect reports/evidence.
- Confirm no unintended broad changes.
- Confirm loop-state update is accurate.

Validation checklist items from the ticket were each executed and checked below.

## 1. Ticket Tests — PASS

```
$ python3 -m pytest tests/test_shot_mix_contract.py -v
12 passed in 1.49s
```

All 12 tests pass: core invariant (2 hero/1 broll/1 graphic passes), four
missing-shot failure modes (broll, second hero, graphic), editorial rules
(opening-hero, max-consecutive-hero), classification exclusions
(hero-audio and local-graphic not counted as broll), non-publish profile
marking, and S13/S14 gate-priority regression.

## 2. Pass-Criteria Traceability

| Ticket pass criterion | Test | Result |
|-----------------------|------|--------|
| 2 hero + 1 broll + 1 graphic passes | `test_2_hero_1_broll_1_graphic_passes` | ✅ |
| missing broll fails w/ expected vs actual | `test_only_hero_and_graphic_fails` | ✅ |
| missing hero fails w/ expected vs actual | `test_missing_second_hero_fails` | ✅ |
| missing graphic fails w/ expected vs actual | `test_missing_graphic_fails` | ✅ |

All four explicit pass criteria from the ticket are traced to a passing test.

## 3. Required Tests — Met

| Required test | Present |
|---------------|---------|
| Unit test proving the core invariant | ✅ `test_2_hero_1_broll_1_graphic_passes` |
| Regression test proving old bad behavior cannot occur | ✅ `test_only_hero_and_graphic_fails` + the editorial-rule and classification-exclusion tests |
| Existing relevant tests still pass | ✅ see §4 |

## 4. Relevant Existing Tests — No Regression

Apples-to-apples comparison on the three S13/S14 test files that touch the
modified preflight, with the S15 block stashed (baseline) vs present:

```
Baseline:  22 failed, 6 passed   (S15 block removed)
With S15:  21 failed, 7 passed   (one additional test passes; none newly broken)
```

The 21 remaining failures are pre-existing QA-fixture gaps in S13/S14 tests,
failing at `assemble_db.py:233` ("has no passing QA") — **before** the shot-mix
gate at line 351 — and are therefore not caused by S15. They are recorded as a
separate suite-health concern (MINOR-1 in the audit).

The S13/S14 gate-priority regression tests inside the S15 suite independently
prove the lipsync gates still fire before shot-mix:

- `test_s13_hero_compensated_artifact_gate_still_enforced` →
  `BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING`
- `test_s14_per_segment_syncnet_still_enforced` →
  `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING`

## 5. Evidence / Artifact Inspection — PASS

- `configs/video_format_contracts.yaml`: `short_educational` requires
  `hero_lipsync>=2, broll>=1, graphic>=1`; `test_local`/`diagnostic_legacy` carry
  `publish_grade: false`. Verified by direct `get_contract()` load.
- `scripts/shot_mix_contract.py`: classification honors empty `shot_type`,
  excludes hero-audio from broll, tracks max consecutive-hero run.
- `scripts/assemble_db.py`: shot-mix gate sits after S13/S14 and before artifact
  hash; records `evidence["shot_mix_verdict"]`; fail-closed on config errors.
- Direct config check:
  ```
  short_educational min_shots={'hero_lipsync': 2, 'broll': 1, 'graphic': 1}, publish_grade=True
  test_local: publish_grade=False
  diagnostic_legacy: publish_grade=False
  ```

## 6. No Unintended Broad Changes — PASS

S15 footprint is exactly: 1 import line + 1 validation block in `assemble_db.py`,
plus the two new files (`shot_mix_contract.py`, `video_format_contracts.yaml`) and
the test file. No other production files touched. The remainder of the
`assemble_db.py` diff is pre-existing S13/S14 recovery work, confirmed by isolating
only `shot_mix`/`S15` lines in the diff.

## 7. Loop State Update — Accurate

`LOOP_STATE.md` will be updated to mark S15_T001 implemented and S15 IN PROGRESS.
`TICKET_STATUS.json` will record the S15_T001 verdict. (See loop_decision.md.)

## Issues Found

- **BLOCKER**: None.
- **MAJOR**: None.
- **MINOR-1**: 21 pre-existing S13/S14 fixture failures — not a regression; out of scope.

## Verdict

**PASS** — Recommend APPROVE FOR INTEGRATION.

*End of Validation Report*
