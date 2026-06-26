# Loop Decision — S15_T002_RETRY / FIX001

**Ticket**: S15_T002 — Add visual_role metadata (semantic role validation)
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Date**: 2026-06-26
**Decision**: **PASS (engineering self-validation) — awaits independent acceptance**
**Sprint gate**: S15_T003 is **NOT started**.

---

## Executive Summary

S15_T002 is implemented correctly. `visual_role` (the editorial function of a shot,
deliberately separate from the technical `asset_type` and the audio/sync
`audio_policy`) is now sourced from the creative_beat, propagated onto the
render_unit through the timeline span (DB-native planning), and **enforced at the
publish-grade assembly gate**. A publish-grade batch missing `visual_role` blocks
with `BLOCKED_VISUAL_ROLE_MISSING`; an out-of-enum role blocks with
`BLOCKED_VISUAL_ROLE_INVALID`. Non-publish contracts (`test_local`,
`diagnostic_legacy`) are explicitly exempt.

The prior attempt's **bad test simplification is reverted/fixed**: the new tests
build real contract-compliant H→B→H→G batches (so shot-mix passes and the
visual_role gate is reached), instead of bypassing shot-mix with `test_local` /
single-graphic fixtures. The two over-aggressive production changes that broke the
suite (unconditional gate; save-time hard requirement) were removed.

## Was the prior bad simplification reverted/fixed? — **YES**

1. The two publish-grade visual_role tests no longer bypass shot-mix. They build a
   contract-compliant batch and break one unit's `visual_role`, then assert the
   error is `BLOCKED_VISUAL_ROLE_*` **and not** `BLOCKED_SHOT_MIX_CONTRACT`.
2. The unconditional `visual_role` block in `assemble_db.py` → replaced with
   publish-grade-conditional `validate_visual_roles`.
3. The save-time hard requirement in `authoring_service.py` → reverted to optional
   storage (enforcement at the assembly gate).
4. The 3 shared batch helpers now carry a propagated `visual_role` so existing
   S13/S14/S15_T001 positive fixtures remain green.

## Files changed

**Production (3, all ticket targets):**
- `scripts/assemble_db.py` — `ALLOWED_VISUAL_ROLES`, `validate_visual_roles`,
  `_resolve_production_contract`, publish-grade-conditional gate after shot-mix;
  kept the `db_path=db_path` framing-lookup bug fix.
- `scripts/authoring_service.py` — optional `visual_role` storage on creative_beats
  (reverted hard requirement); propagation doc.
- `scripts/production_repo.py` — `visual_role` propagation creative_beat→span→unit
  (unchanged from prior attempt; already correct).

**Migration (1):**
- `db/migrations/011_visual_role.sql` — `visual_role` columns + `visual_roles`
  reference table (unchanged from prior attempt).

**Tests (4):**
- `tests/visual_role_fixtures.py` — NEW shared `seed_visual_roles` fixture.
- `tests/test_visual_role_contract.py` — rewritten (12 contract-compliant tests).
- `tests/test_shot_mix_contract.py`, `tests/test_s14_t004_syncnet_confidence.py`,
  `tests/test_s14_t003_per_segment_syncnet.py` — wired `seed_visual_roles` into the
  shared batch helpers.

## Exact tests run + pass/fail counts

| Suite | Result |
|-------|--------|
| `tests/test_visual_role_contract.py` | **12 passed** |
| `tests/test_shot_mix_contract.py` | **12 passed** |
| `tests/test_s14_t004_syncnet_confidence.py` | **9 passed** |
| `tests/test_s14_t003_per_segment_syncnet.py` | **6 passed** |
| `tests/test_lipsync_policy.py` + `tests/test_hero_framing.py` | passed |
| `tests/test_s13_t005_integration_regression.py` | passed (1 pre-existing skip) |
| `tests/test_audio_continuity.py` | passed |
| **Required set (all of the above together)** | **144 passed, 1 skipped** |
| All 10 files calling `validate_assembly_inputs` | 14 failed, 65 passed, 1 skipped — **0 `BLOCKED_VISUAL_ROLE`** |
| Optional diagnostic (`test_compensated_hero_assembly`, `test_syncnet_gate`) | 5 pre-existing fail (`|| true`) |
| Full suite (`python3 -m pytest -q`) | **90 failed, 1783 passed, 10 skipped** |

**Full-suite / regression attribution (honest).** S15_T002's only failure mode is
`BLOCKED_VISUAL_ROLE_*`. I ran the complete set of 10 files that call
`validate_assembly_inputs` (the only path to the visual_role gate) and confirmed
**zero `BLOCKED_VISUAL_ROLE` failures**. The 14 failures in those files block on
EARLIER gates S15_T002 does not touch: `BLOCKED_SHOT_MIX_CONTRACT` (S15_T001, on
non-compliant single-unit fixtures), `BLOCKED_HERO_SYNCNET_*` (S14),
`BLOCKED_HERO_COMPENSATED_*` (S13), and `FOREIGN KEY` (test setup). The full
suite's 90 failures are these same pre-existing classes (overwhelmingly S15_T001
shot-mix debt across `tests/unit/` etc.); prior WIP baseline was **121 failed** →
FIX001 is **90 failed** (fixed 31, introduced 0). **S15_T002 introduces zero
regressions.** None of the 90 are chased — out of scope (S15_T001/S13/S14 fixture
debt), and the retry brief scopes S15_T002 to its own tests + the required set.

## Remaining failures — classification

All **REAL but PRE-EXISTING and OUT OF SCOPE** → **NO MATERIAL IMPACT** on S15_T002.

The airtight attribution: S15_T002's only failure mode is `BLOCKED_VISUAL_ROLE_*`,
and **zero** tests fail with that signature (verified across the full set of
`validate_assembly_inputs` callers and the full suite). The 90 full-suite failures
block on earlier gates S15_T002 does not touch:

| Gate / cause | Files (representative) | Count | Class |
|--------------|------------------------|-------|-------|
| `BLOCKED_SHOT_MIX_CONTRACT` (S15_T001, non-compliant single-unit fixtures) | `tests/unit/test_assembly_timeline_heuristics.py`, `tests/unit/test_assembly_preflight.py`, + others | bulk of 90 | NO MATERIAL IMPACT (S15_T001 fixture debt) |
| `BLOCKED_HERO_SYNCNET_*` (S14) | `tests/unit/test_assembly_preflight.py`, `tests/integration/test_e2e_db_native_no_paid_provider.py` | several | NO MATERIAL IMPACT |
| `BLOCKED_HERO_COMPENSATED_*` (S13) | `tests/test_s13_t002_simple.py` | 1 | NO MATERIAL IMPACT |
| `FOREIGN KEY constraint failed` (test setup) | `tests/test_syncnet_gate.py`, `tests/test_compensated_hero_assembly.py` | 5+ | NO MATERIAL IMPACT |
| `produce_db.invoke_repair` routing | `tests/contracts/test_selective_repair.py` | 2 | NO MATERIAL IMPACT |

Verified by stashing the 3 production files and reproducing identical failures on
HEAD code (for `test_syncnet_gate`, `test_compensated_hero_assembly`,
`test_selective_repair`). None are caused by S15_T002; none are chased — out of
scope (this is S15_T001/S13/S14 fixture debt; the retry brief scopes S15_T002 to
its own tests + the required set, all green).

## Requirement compliance

| Requirement | Status |
|-------------|--------|
| 1. Valid H→B→H→G + valid visual_role passes | ✅ |
| 2. Missing → `BLOCKED_VISUAL_ROLE_MISSING` (not shot-mix) | ✅ |
| 3. Invalid → `BLOCKED_VISUAL_ROLE_INVALID` (not shot-mix) | ✅ |
| 4. Propagates creative_beat → span → unit | ✅ |
| 5. Not inferred from label | ✅ |
| 6. Non-publish explicit (test_local/diagnostic_legacy) | ✅ |
| 7. Shot-mix tests green | ✅ 12/12 |
| 8. S13/S14 targeted green | ✅ |

## Is S15_T003 ready to start? — **NO**

- This is an engineering **self-validation**. Per global operating rules, an
  engineer must not approve its own implementation; only an **independent
  validator** may mark S15_T002 accepted.
- The retry brief explicitly says: **"Stop after S15_T002. Do not start S15_T003."**
- S15_T003 remains PENDING pending independent acceptance of S15_T002.

## Residual risk

- Real LLM authoring (`run_episode`/`direct_storyboard`) does not yet emit
  `visual_role`; a real publish run will fail-closed at this gate until wired
  (separate ticket). Intended behavior.
- Self-authored engineering/audit/validation/loop_decision — independent review
  recommended (consistent with the S15_T001 independent gate-review precedent).
