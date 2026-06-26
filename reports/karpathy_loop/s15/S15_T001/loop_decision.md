# Loop Decision — S15_T001

**Ticket**: Define format-level shot-mix contract
**Date**: 2026-06-26
**Decision**: APPROVED
**Sprint**: S15 — Shot-mix contract and semantic role validation

---

## Executive Summary

S15_T001 is **APPROVED**. A format-level shot-mix contract now blocks assembly of
editorially-broken storyboards. A `short_educational` episode must contain ≥2 hero
lip-sync beats, ≥1 b-roll, ≥1 graphic, must open on a hero, and must not exceed 1
consecutive hero segment without a break. The contract is config-driven
(`configs/video_format_contracts.yaml`) and enforced in the DB-native assembly
preflight after the S13/S14 lipsync gates. The ticket's four explicit pass criteria
are all traced to passing tests; 12/12 tests pass; zero regressions vs. baseline.

## Decision Basis

### 1. Engineering Report ✅
Complete. New contract engine + config + assembly integration + 12-test suite.
Honest scope: only the import + ~32-line validation block in `assemble_db.py`
belong to this ticket. Fail-closed, config-driven, classification-correct.

### 2. Audit Report ✅
PASS. 0 BLOCKER, 0 MAJOR, 1 MINOR (pre-existing S13/S14 fixture failures — not a
regression). No fake green, no silent fallback, no parallel infrastructure, no
provider renders, explicit `BLOCKED_`-prefixed messages, gate priority preserved.

### 3. Validation Report ✅
PASS. Independent run: 12/12 tests pass. All four explicit pass criteria traced.
Apples-to-apples regression check: baseline 22 fail/6 pass → S15 21 fail/7 pass on
the same S13/S14 files (one additional pass, none newly broken). No unintended
broad changes.

## Requirement Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| short_educational: min hero/broll/graphic counts | ✅ | `hero_lipsync>=2, broll>=1, graphic>=1` |
| Duration/editorial policy (opening hero, max-consecutive-hero) | ✅ | rules in YAML + tested |
| 2 hero + 1 broll + 1 graphic passes | ✅ | `test_2_hero_1_broll_1_graphic_passes` |
| Missing broll/hero fails with expected vs actual | ✅ | `test_only_hero_and_graphic_fails`, `test_missing_second_hero_fails` |
| Non-publish profiles marked | ✅ | `test_local`/`diagnostic_legacy` publish_grade=false |
| Tests meaningful, not file-existence-only | ✅ | exact expected-vs-actual substrings asserted |
| Existing relevant tests still pass | ✅ | zero regression (verified) |

## Test Results

```
$ python3 -m pytest tests/test_shot_mix_contract.py -q
12 passed in 1.49s
```

## Risk Assessment: LOW

- Focused change: one import + one validation block in the preflight, two new files.
- Fail-closed on missing/invalid contract config.
- Gate priority preserved (S13 → S14 → S15 → artifact hash), proven by regression tests.
- Zero regressions vs. baseline on the S13/S14 test files.

## Residual Risk / Out-of-Scope

- 21 pre-existing S13/S14 QA-fixture failures remain (not introduced by S15).
  Recommended for a separate suite-health ticket.
- Semantic-role classification refinement is deferred to S15_T002+; this ticket
  deliberately classifies on audio_policy/asset_type only.

## Blockers / Issues

- BLOCKER: None.
- MAJOR: None.
- MINOR-1: pre-existing S13/S14 fixture failures (accepted; not a regression).

## Decision

**APPROVED ✅** for integration.

### Actions
1. Update `LOOP_STATE.md`: add S15 (IN PROGRESS), mark S15_T001 implemented.
2. Update `TICKET_STATUS.json`: record S15_T001 = DONE/APPROVED.
3. Archive engineering/audit/validation reports under
   `reports/karpathy_loop/s15/S15_T001/` (done).
4. Stop. Do not begin S15_T002 in this session (one-ticket-per-session rule).

## Sign-Off

**Ticket**: S15_T001 — Define format-level shot-mix contract
**Status**: DONE
**Decision**: APPROVED
**Date**: 2026-06-26
**Approver**: GLM-5.2[1m] (Loop Decision)

*End of Loop Decision*
