# Audit Report — S15_T001

**Ticket**: Define format-level shot-mix contract
**Date**: 2026-06-26
**Auditor**: GLM-5.2[1m]
**Sprint**: S15 — Shot-mix contract and semantic role validation

---

## Audit Scope

Independent audit of the S15_T001 implementation against the ticket:

- Every explicit pass criterion is met.
- Tests are meaningful (not file-existence-only).
- No fake green, no silent fallback, no parallel infrastructure.
- No provider render triggered.
- Failure messages are explicit and `BLOCKED_`-prefixed.
- No unintended broad changes.
- No regression to S13/S14 gates.

## Audit Findings

### ✅ Pass Criteria

| Criterion | Verdict | Evidence |
|-----------|---------|----------|
| 2 hero + 1 broll + 1 graphic passes | PASS | `test_2_hero_1_broll_1_graphic_passes` — `validation_passed is True` |
| Missing broll fails with expected vs actual | PASS | `test_only_hero_and_graphic_fails` asserts `broll: expected >= 1, actual 0` in message |
| Missing hero fails with expected vs actual | PASS | `test_missing_second_hero_fails` asserts `hero_lipsync: expected >= 2, actual 1` |
| Missing graphic fails with expected vs actual | PASS | `test_missing_graphic_fails` asserts `graphic: expected >= 1, actual 0` |
| Opening must be hero | PASS | `test_opening_must_be_hero` asserts `opening segment must be hero` |
| No >1 consecutive hero | PASS | `test_consecutive_hero_segments_fails` asserts `consecutive hero` |
| HERO_SYNC_LOCKED excluded from broll count | PASS | `test_hero_lipsync_not_counted_as_broll` |
| local_graphic excluded from broll count | PASS | `test_local_graphic_not_counted_as_broll` |
| Non-publish profiles marked | PASS | `TestNonPublishGradeProfiles` (publish_grade is False) |

### ✅ Failure Messages Explicit and BLOCKED_-prefixed

The assembly failure path raises:
```
BLOCKED_SHOT_MIX_CONTRACT: render units violate shot-mix contract 'short_educational'.
Expected: hero_lipsync>=2, broll>=1, graphic>=1. Actual: hero_lipsync=0, broll=0, graphic=1.
Violations: hero_lipsync: expected >= 2, actual 0; ...
```
Carries contract name, expected-vs-actual, and enumerated violations. Config-level
failures raise `BLOCKED_SHOT_MIX_CONTRACT_CONFIG_MISSING` / `_CONFIG_INVALID` /
`_UNKNOWN` / `_VALIDATION_FAILED`. Compliant with the `BLOCKED_` convention.

### ✅ Tests Are Meaningful

- Tests exercise the **real** assembly preflight (`validate_assembly_inputs`) against
  a migrated production DB, not a stub of `validate_shot_mix`.
- Assertions check the exact expected-vs-actual substrings the ticket requires, not
  mere exception presence.
- The classification tests prove *exclusion* behavior (hero-audio / local-graphic not
  counted as broll), which is the subtle requirement.

### ✅ No Fake Green

- 12/12 pass legitimately; 0 skips, 0 xfail.
- During development, 6 then 3 tests failed and were root-caused (stale-unit marking
  from repeated `plan_render_units`; span overlaps; missing SyncNet/compensated
  artifacts; a `max_consecutive_hero` bug that only checked the residual count).
  None were weakened to force a pass — the contract engine was fixed instead.

### ✅ No Silent Fallback

- Missing/invalid contract config raises (fail-closed), never passes.
- Classification returns `other` for unmatched units, which still counts against the
  contract (it cannot satisfy a hero/broll/graphic minimum).

### ✅ No Parallel Infrastructure

- Uses the existing DB-native preflight path in `assemble_db.py`. No second
  validator, no shadow contract store. Contract config is a single YAML consumed by
  one loader.

### ✅ No Provider Render

- Tests build synthetic artifact files (`b"fake video "`) and fake compensated
  artifacts. No Higgsfield/ElevenLabs calls, no `--force-unsafe`, dry-run-safe.

### ✅ No Unintended Broad Changes

- S15 footprint in `assemble_db.py` = 1 import line + 1 validation block (~32 lines).
  The larger `git diff` (191/18) is pre-existing S13/S14 recovery work already in the
  working tree — verified by isolating only the `shot_mix`/`S15` lines. No unrelated
  files edited.

### ✅ S13/S14 Gate Priority Preserved

- `test_s13_hero_compensated_artifact_gate_still_enforced`: with valid shot-mix but a
  non-existent compensated artifact path, assembly fails with
  `BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING` (S13), not shot-mix.
- `test_s14_per_segment_syncnet_still_enforced`: heroes without SyncNet fail with
  `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` (S14), not shot-mix.
- Confirms ordering: S13 → S14 → S15 → artifact hash.

## Issues Found

### BLOCKER
None.

### MAJOR
None.

### MINOR
1. **MINOR-1**: 21 pre-existing failures in S13/S14 test files (`test_s13_t002_*`,
   `test_s14_t003_*`, `test_s14_t004_*`) — QA-fixture gaps at `assemble_db.py:233`
   ("no passing QA"), reached before the shot-mix gate.
   - **Impact**: Non-blocking for S15; not a regression (verified apples-to-apples:
     baseline 22 fail/6 pass → S15 21 fail/7 pass on the same files).
   - **Action**: Separate suite-health ticket; out of S15_T001 scope.

### ENVIRONMENTAL
None.

## Compliance Checklist

| Requirement | Status |
|------------|--------|
| Implement only this ticket | ✅ |
| Extend existing infrastructure | ✅ |
| No duplicate architecture | ✅ |
| Tests meaningful, not file-existence-only | ✅ |
| No fake green | ✅ |
| No silent fallback | ✅ |
| No provider render | ✅ |
| Failure messages explicit + `BLOCKED_` | ✅ |
| No unintended broad changes | ✅ |

## Overall Verdict

**PASS** — Recommend ACCEPT and proceed to validation.

*End of Audit Report*
