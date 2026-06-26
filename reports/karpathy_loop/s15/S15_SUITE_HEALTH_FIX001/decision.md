# Decision — S15_SUITE_HEALTH_FIX001

**Ticket**: S15_SUITE_HEALTH_FIX001 (non-blocking follow-up to S15_T001)
**Decider**: Claude (glm-5.2)
**Date**: 2026-06-26

## Verdict: **COMPLETE**

The S15_T001 non-blocking follow-up is resolved. S14 positive-path and non-hero-exemption coverage
degraded by S15 shot-mix enforcement is restored. No production code changed; no gate was weakened.

---

## What was done

- **Primary fix (test_s14_t004_syncnet_confidence.py):** 5 stale single-unit positive-path fixtures
  refreshed via a new `_make_contract_compliant_batch` helper that builds a publish-grade shot mix
  (≥2 hero + ≥1 broll + ≥1 graphic, opening hero, no consecutive heroes) while preserving the exact
  SyncNet evidence / hero framing each test exercises. 5 fail → 0 fail.
- **In-area fix (test_s14_t003_per_segment_syncnet.py):** 4 deterministic fixture-health failures
  fixed via a new `_make_syncnet_contract_batch` helper (committed transactions + full QA +
  SyncNet-on-hero). Root causes were a deferred-transaction (no-commit) bug in the old helper and
  incomplete QA checklists for non-hero units — both fixture-side, no production bug. 4 fail → 0 fail.
- **Negative-path tests untouched** and verified to still pass for the right reason (raised error is
  `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` at the SyncNet gate, reached after the QA gate).

## Pass criteria — all met

| Criterion | Result |
|-----------|--------|
| `test_s14_t004_syncnet_confidence.py` green (or remaining classified) | ✅ **9/9 green** |
| `test_shot_mix_contract.py` remains 12/12 | ✅ 12/12 |
| `lipsync_policy` + `hero_framing` green | ✅ 73/73 |
| S13 integration + audio-continuity green | ✅ 32 pass / 1 skip |
| No production code changes without a demonstrated bug | ✅ **0 production files changed** |
| No paid renders | ✅ none (all `--dry-run`/fixture/deterministic) |
| No weakening of S13/S14/S15 gates | ✅ gates unchanged; fixtures build publish-grade productions |

## Remaining failures — classified (not fixed, by design)

- `test_compensated_hero_assembly.py::test_syncnet_on_c1_remux_verification` — **NO MATERIAL IMPACT
  / ENVIRONMENTAL** (SyncNet binary/pipeline unavailable). Pre-existing, S15-independent, out of area.
- `test_syncnet_gate.py` (4) — **NO MATERIAL IMPACT / TEST-INFRA** (FK-constraint errors in test
  setup). Pre-existing, S15-independent, out of area.

Both are explicitly carved out by the task instruction (do not chase unrelated legacy/environmental
failures such as missing external remux artifacts).

## Scope discipline

- Diff is confined to two **test** files (`git diff --name-only`).
- No endless review loop; no expansion into passing-test semantic refactors.
- S15_T002 is **not** started.

## Effect on state

- `LOOP_STATE.md`: S15_SUITE_HEALTH_FIX001 → **COMPLETE**; S15_T001 CONDITIONAL_PASS follow-up
  cleared. S15_T002 still **BLOCKED on explicit user approval**.
- `TICKET_STATUS.json`: S15_SUITE_HEALTH_FIX001 → **DONE**.
- **S15_T002 is NOT unblocked by this fix.** It remains gated on explicit user approval per the
  session instruction. This ticket only cleared the S15_T001 non-blocking follow-up; it did not
  receive approval to begin T002.

*End of Decision*
