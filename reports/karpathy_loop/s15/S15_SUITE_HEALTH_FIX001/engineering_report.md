# Engineering Report — S15_SUITE_HEALTH_FIX001

**Ticket**: S15_SUITE_HEALTH_FIX001 (non-blocking follow-up to S15_T001 CONDITIONAL_PASS)
**Author**: Claude (glm-5.2), session independent of S15_T001 engineering/audit/validation
**Date**: 2026-06-26
**Scope**: Restore meaningful S13/S14 targeted test coverage degraded by S15_T001 shot-mix enforcement.

---

## 1. Problem statement

S15_T001 made the `short_educational` shot-mix contract mandatory at assembly preflight
(`assemble_db.validate_assembly_inputs`, ~line 351). The contract requires
`hero_lipsync >= 2, broll >= 1, graphic >= 1`, opening hero, and `max_consecutive_hero == 1`.

The independent gate review (`S15_T001_GATE/gate_review.md` §5.3) measured the real effect:
**baseline 12 pass / 16 fail → S15 enabled 7 pass / 21 fail = 5 newly-broken tests, 0 fixed.**
All 5 newly-broken tests were stale single-unit positive-path fixtures in
`tests/test_s14_t004_syncnet_confidence.py` that failed at `BLOCKED_SHOT_MIX_CONTRACT` — not
production defects. This fix restores that coverage.

Per the task instruction ("fix any REAL failures regardless of whether they are new or old; ignore
failures with no material impact"), the remaining targeted S13/S14 failures named in the gate report
(`SYNCNET_PER_SEGMENT_MISSING` and `has no passing QA`) were also inspected and fixed where they were
deterministic fixture-health problems in the same suite area.

## 2. Root causes (all fixture-side; **no production bug**)

### 2.1 `test_s14_t004_syncnet_confidence.py` — 5 stale single-unit fixtures
Each positive-path / non-hero test built **one** render unit (a lone hero, or a lone b-roll) and
asserted `validate_assembly_inputs` passes. Post-S15 that single unit can never satisfy
`short_educational` (needs ≥2 hero + ≥1 broll + ≥1 graphic), so every such assertion failed at
`BLOCKED_SHOT_MIX_CONTRACT` before reaching the SyncNet-confidence logic the test exists to exercise.

### 2.2 `test_s14_t003_per_segment_syncnet.py` — two distinct fixture bugs (4 failures)
1. **Deferred-transaction bug in `_make_hero_render_unit`.** The helper used a raw
   `conn = _db.connect(db)` + inserts + `conn.close()` with **no `commit()`**. `_db.connect()`
   returns a deferred-transaction connection (no autocommit), so the `provider_jobs`,
   compensated-artifact path, and SyncNet/audio_offset validations were rolled back on close and
   invisible to the separate connection `validate_assembly_inputs` opens. Result: the positive-path
   hero tests (`test_hero_unit_with_syncnet_passes`, `test_hero_unit_with_both_passes`) failed at
   `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING`. (The negative-path tests passed because they assert
   the *absence* of SyncNet — which holds whether or not the uncommitted insert persists.)
2. **Incomplete QA checklists for non-hero units.** `test_broll_flex_does_not_require_syncnet`
   omitted `audio_policy_ok` and `test_silent_graphic_does_not_require_syncnet` omitted
   `dimensions_ok`/`audio_policy_ok` from `run_render_unit_qa`, which records a pass **only if all
   four required checks** (`file_exists`, `dimensions_ok`, `duration_ok`, `audio_policy_ok`) are
   truthy. The incomplete checklists recorded a **fail** `qa_media` validation, so preflight raised
   `BLOCKED: ... has no passing QA`.

These four `test_s14_t003` failures pre-date S15 (they are part of the gate review's "16 baseline
failures") but are real, deterministic, in-area fixture-health failures, so they were fixed.

## 3. Fix

**Test-fixture changes only. No production code modified.** Verified: `git diff --name-only` lists
only the two test files.

### 3.1 `test_s14_t004_syncnet_confidence.py`
- Added `_make_contract_compliant_batch(...)` helper (adapted from the proven `_make_units_batch` in
  `test_shot_mix_contract.py`). It builds a publish-grade production in one transaction:
  `H001 (hero, opening) → B001 (broll) → H002 (hero under test) → G001 (graphic)` — satisfies
  ≥2 hero, ≥1 broll, ≥1 graphic, opening hero, no consecutive heroes. All inserts use
  `_db.transaction()` (commits), every unit gets an artifact + passing QA, and heroes get a
  compensated artifact + per-segment SyncNet validation.
- Rewrote the 5 failing tests to seed the hero-under-test parameters (framing, offset, confidence)
  into the batch instead of a single unit, preserving each test's original assertion and the
  specific SyncNet evidence/framing it is meant to exercise:
  - `test_hero_unit_with_good_syncnet_passes`
  - `test_medium_framing_uses_medium_policy`
  - `test_wide_framing_uses_medium_policy`
  - `test_missing_framing_defaults_to_close` (clears `hero_framing` on the hero-under-test after
    seeding, to exercise the close-hero default)
  - `test_broll_flex_bypasses_confidence_check` (the batch's B001 carries no SyncNet yet the batch
    passes — proving b-roll bypasses the confidence check inside a valid publish-grade shot mix)

### 3.2 `test_s14_t003_per_segment_syncnet.py`
- Added `_make_syncnet_contract_batch(...)` helper mirroring `_make_units_batch` with **committed**
  transactions, full QA for every unit, compensated artifacts + SyncNet-on-render_unit for heroes.
- Rewrote the 4 failing tests to embed the unit-under-test in a contract-compliant batch:
  - `test_hero_unit_with_syncnet_passes`, `test_hero_unit_with_both_passes` (also attaches an
    `audio_offset` validation to H002 — SyncNet remains the satisfying evidence).
  - `test_broll_flex_does_not_require_syncnet`, `test_silent_graphic_does_not_require_syncnet` —
    each now asserts the non-hero unit genuinely has **no** SyncNet row, yet the batch passes,
    proving the exemption inside a valid publish-grade shot mix.
- The 2 passing negative-path tests (`test_hero_unit_without_syncnet_fails`,
  `test_hero_unit_with_only_audio_offset_fails`) and the old `_make_hero_render_unit` helper were
  left **untouched**. They still pass for the right reason — verified by runtime probe that the
  raised error is `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` (the SyncNet gate, line 254), reached
  *after* the QA gate, not short-circuited by an earlier gate.

## 4. Production-code change justification

**None.** The production gates (S14 per-segment SyncNet, S14 confidence thresholds, QA-passing
requirement, S15 shot-mix contract) are behaving exactly as specified — they correctly reject
under-populated / un-evidenced storyboards. Every failure was a stale or buggy *fixture*. Per the
`.kiro/rules/no-hacks.md` hard rule, fixtures were refreshed at their source rather than worked
around.

## 5. No weakening of gates

- No gate, schema, threshold, or assertion was relaxed.
- The refreshed fixtures build **publish-grade** productions (full shot-mix + QA + SyncNet), so the
  gates they pass are genuinely satisfied.
- Non-hero exemption tests now *additionally* assert the non-hero unit has no SyncNet row, making
  the exemption proof stronger, not weaker.

## 6. Evidence

See `test_results.txt`. Summary:

| Suite | Before | After |
|-------|--------|-------|
| `test_s14_t004_syncnet_confidence.py` | 4 pass / 5 fail | **9 pass / 0 fail** |
| `test_s14_t003_per_segment_syncnet.py` | 2 pass / 4 fail | **6 pass / 0 fail** |
| `test_shot_mix_contract.py` | 12 pass | **12 pass** (unchanged) |
| `test_lipsync_policy.py` + `test_hero_framing.py` | 73 pass | **73 pass** (unchanged) |
| `test_s13_t005_integration_regression.py` + `test_audio_continuity.py` | 32 pass / 1 skip | **32 pass / 1 skip** (unchanged) |
| Broad S13/S14 DB-gate regression (8 files) | — | **143 pass / 1 skip** |

## 7. Residual / not-fixed failures (classified)

| Failure | Class | Reason not fixed |
|---------|-------|------------------|
| `test_compensated_hero_assembly.py::test_syncnet_on_c1_remux_verification` | **NO MATERIAL IMPACT / ENVIRONMENTAL** | Requires the SyncNet Python pipeline (`syncnet_python/run_syncnet.py`), whose model/binary fails to load in this env. Pre-existing, S15-independent (gate review §5.4). Outside the targeted suite area. No provider render involved; cannot be made deterministic without the binary. |
| `test_syncnet_gate.py` (4 tests) | **NO MATERIAL IMPACT / TEST-INFRA** | FK-constraint errors in test *setup* (the tests set `PRAGMA foreign_keys=OFF` then insert render_units referencing absent spans). Pre-existing, S15-independent (gate review §5.4). Outside the targeted suite area; not a fixture-health problem in the S14 SyncNet area. |

These are explicitly carved out by the task ("Do not chase unrelated legacy/environmental failures
such as missing external remux artifacts unless the test can be made deterministic/local without
provider renders").

## 8. Residual observation (not a failure)

The legacy `_make_hero_render_unit` helper in `test_s14_t003` retains its deferred-transaction
(uncached-commit) behavior. It is now used only by the two **passing** negative-path tests, where
the uncommitted inserts are harmless (the asserted error is raised at the SyncNet gate before any
gate that depends on those rows). It was left untouched to avoid destabilizing passing tests and to
keep the diff focused; future positive-path consumers of that helper should use
`_make_syncnet_contract_batch` instead.

## 9. Effect on state

- S14 positive-path and non-hero-exemption coverage for both the per-segment SyncNet gate (S14_T003)
  and the confidence/offset gate (S14_T004) is **restored**.
- No production regressions; S13/S14/S15 gates unchanged.
- S15_T002 remains **BLOCKED on explicit user approval** — not started.

*End of Engineering Report*
