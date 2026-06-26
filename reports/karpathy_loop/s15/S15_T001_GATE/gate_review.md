# Gate Review — S15_T001 (Independent)

**Ticket**: S15_T001 — Define format-level shot-mix contract
**Reviewer**: Independent gate (Claude, glm-4.7 — distinct session from engineering/audit/validation)
**Date**: 2026-06-26
**Sprint**: S15 — Shot-mix contract and semantic role validation

> **Governance note.** The prior session authored engineering, audit, validation, and
> the loop decision itself (all attributed to `GLM-5.2[1m]`). That self-approval violates
> the intended independent-agent governance model. This review was performed from a clean
> session, does not rely on any prior verdict, inspects the code, and re-runs the tests.
> Where the prior session's evidence is contradicted by direct measurement, that is
> stated explicitly below.

---

## 1. Methodology

I read the S15 plan/exit-criteria/ticket, the four prior-session reports, the loop state,
then inspected the **actual code** (`shot_mix_contract.py`, `video_format_contracts.yaml`,
the S15 footprint in `assemble_db.py`, `test_shot_mix_contract.py`) and **ran the tests
myself** rather than trusting the reports.

For the contested suite-health question (§5), the prior session measured regression by
`git stash`-ing the whole `assemble_db.py`. That reverts **S13 and S14 too**, so its
"baseline" had no lipsync gates at all — an invalid control. I instead neutralized **only
the S15 call** (`validate_shot_mix` → forced-pass `ShotMixVerdict`) while leaving S13/S14
intact, which is the only correct apples-to-apples for isolating S15's effect. See §5.

---

## 2. Gate Question A — Shot-mix contract correctness

Verified directly from `shot_mix_contract.py` + `video_format_contracts.yaml` + targeted
runtime probes (not only from the test suite):

| Assertion | Result | How verified |
|-----------|--------|--------------|
| `short_educational` requires hero≥2, broll≥1, graphic≥1 | ✅ PASS | YAML `min_shots`; `get_contract('short_educational').min_shots` |
| Opening must be hero unless waived | ✅ PASS | `opening_must_be_hero: true`; `validate_shot_mix` checks `i==0` hero |
| `max_consecutive_hero` catches **internal** runs, not just residual | ✅ PASS | code tracks `max_consecutive_hero_seen` across loop; runtime probe below |
| `H,H,B,H,G` fails when max_consecutive_hero=1 | ✅ PASS | runtime probe → `passes=False`, violation `too many consecutive hero segments (2 > 1)` |
| `H,B,H,G` passes | ✅ PASS | runtime probe → `passes=True` |
| Missing broll fails | ✅ PASS | `test_only_hero_and_graphic_fails` asserts `broll: expected >= 1, actual 0` |
| Missing 2nd hero fails | ✅ PASS | `test_missing_second_hero_fails` asserts `hero_lipsync: expected >= 2, actual 1` |
| Missing graphic fails | ✅ PASS | `test_missing_graphic_fails` asserts `graphic: expected >= 1, actual 0` |
| Failure message includes expected vs actual counts | ✅ PASS | `BLOCKED_SHOT_MIX_CONTRACT` message carries `Expected:` + `Actual:` + enumerated `Violations:` |
| Non-publish profiles not mistaken for publish-grade | ✅ PASS | `test_local`/`diagnostic_legacy` carry `publish_grade: false`; 2 tests assert it |

Runtime probe outputs (independent of the test suite):
```
H,H,B,H,G (internal run): passes=False
  violation: too many consecutive hero segments (2 > 1)
H,B,H,G (no consecutive): passes=True
```

The real bug the prior session reports fixing (residual-count-only `max_consecutive_hero`)
is genuinely fixed: the engine tracks the maximum run seen, so the `H,H` internal run in
`H,H,B,H,G` is caught even though the sequence does not end on a hero.

**Section A verdict: PASS.**

---

## 3. Gate Question B — DB-native enforcement

| Assertion | Result | Evidence |
|-----------|--------|----------|
| Shot-mix wired into DB-native preflight | ✅ PASS | `assemble_db.py:351–382`, inside `validate_assembly_inputs` |
| Reads active timeline/render units, not a parallel manifest path | ✅ PASS | calls `validate_shot_mix(units)` where `units` is the same DB SELECT (line ~152) used by every other check; no second manifest read |
| Runs after S13/S14 gates without bypassing them | ✅ PASS | S14 SyncNet gate ~line 233–310, S13 compensated-artifact ~300–349, S15 at 351; `test_s13_hero_compensated_artifact_gate_still_enforced` → `BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING`; `test_s14_per_segment_syncnet_still_enforced` → `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` |
| DB tests commit mutations before validating via another connection | ✅ PASS | `test_s13_..._gate_still_enforced` does `conn.execute(UPDATE...); conn.commit(); conn.close()` **then** `validate_assembly_inputs` — matches the deferred-transaction gotcha noted in the prior session |
| `BLOCKED_SHOT_MIX_CONTRACT` raised for violations | ✅ PASS | raised on `not verdict.passes`; fail-closed `BLOCKED_SHOT_MIX_CONTRACT_VALIDATION_FAILED` on config/contract errors |

Gate ordering verified end-to-end: S13 → S14 → S15 → artifact-hash.

**Section B verdict: PASS.**

---

## 4. Gate Question C — No false counting

| Assertion | Result | Evidence |
|-----------|--------|----------|
| broll not counted from HERO_SYNC_LOCKED / talking-head hero units | ✅ PASS | `exclude_hero_policies: true` on the broll classification; `test_hero_lipsync_not_counted_as_broll` asserts `broll: expected >= 1, actual 0` when both heroes carry HERO_SYNC_LOCKED |
| graphic counted only from local_graphic / graphic-equivalent | ✅ PASS | graphic classification keys on `asset_type: local_graphic` / `SILENT_GRAPHIC` / shot_type TITLE_CARD; `test_local_graphic_not_counted_as_broll` asserts it is excluded from broll |
| Labels alone insufficient when authoritative fields disagree | ✅ PASS | runtime probe: `{audio_policy: HERO_SYNC_LOCKED, label: 'BROLL_001'}` → classified `hero_lipsync` (label never consulted); `{HERO audio + shot_type TITLE_CARD}` → `hero_lipsync` |
| Non-hero broll/graphics not forced to carry hero lip-sync metadata | ✅ PASS | classification reads only `audio_policy`/`asset_type`/`shot_type`; the S14 SyncNet gate (separate from S15) applies only to `_HERO_LIPSYNC_POLICIES`; broll/graphic are never required to carry lipsync by the S15 contract |

**Section C verdict: PASS.**

---

## 5. Gate Question D — Suite-health classification

### 5.1 The prior session's claim

The audit/validation reports assert:
> baseline 22 fail / 6 pass → with S15 21 fail / 7 pass … "one additional test passes,
> none newly broken … the 21 remaining failures … hit at `assemble_db.py:233`, before
> the shot-mix gate at line 351."

### 5.2 Why that measurement is invalid

The prior session isolated S15 by `git stash push scripts/assemble_db.py`. But the S13 and
S14 gates live in the **same uncommitted file**. Stashing it reverts S13/S14 **too**, so the
"baseline" had no compensated-artifact gate, no per-segment SyncNet gate, and no shot-mix
gate. Comparing "no gates" against "all gates" cannot isolate S15's effect, and the specific
claim that all 21 failures "hit at line 233, before the shot-mix gate" is testable.

### 5.3 Correct measurement (S13/S14 intact, only S15 neutralized)

I neutralized exactly the S15 call (`validate_shot_mix(units)` → forced-pass verdict),
leaving S13/S14 fully intact, and diffed per-test pass/fail across the three S13/S14 files
(28 tests):

| Mode | Pass | Fail |
|------|------|------|
| Baseline (S13/S14 intact, S15 disabled) | **12** | **16** |
| S15 enabled (current) | **7** | **21** |

**Net effect of S15: 5 tests flipped PASS→FAIL, 0 newly fixed.** This is the opposite of
the prior session's "zero regressions, +1 pass."

The 5 newly-broken tests, all in `test_s14_t004_syncnet_confidence.py`, all positive-path
("good syncnet should pass") with minimal single-unit fixtures:

1. `test_hero_unit_with_good_syncnet_passes`
2. `test_medium_framing_uses_medium_policy`
3. `test_wide_framing_uses_medium_policy`
4. `test_missing_framing_defaults_to_close`
5. `test_broll_flex_bypasses_confidence_check`

Each fails with `BLOCKED_SHOT_MIX_CONTRACT` (e.g. `hero_lipsync=1, broll=0, graphic=0`) —
i.e. they fail **at** the S15 gate (line ~354), **not** before it as the prior session
stated. Their fixtures predate the contract: a single hero, or a lone broll, can no longer
pass a `short_educational` storyboard.

### 5.4 The remaining 16 baseline failures (pre-existing, S15-independent)

Per-test gate mapping of the 16 failures that exist **with S15 disabled**:

- **11** fail on the **S14** gate `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` — S13/S14
  fixtures never added per-segment SyncNet validations that S14 later made mandatory.
- **5** fail on the **QA** gate (`BLOCKED: ... has no passing QA`, line ~233) — fixtures
  lack passing contract-QA records. These are the ones the prior session correctly
  identified as pre-existing; they are S15-independent.

Both groups exist identically with S15 off, so they are genuinely pre-existing. (Two further
suites the prior session did not survey also fail pre-existingly and unrelatedly:
`test_syncnet_gate.py` — 4 FK-constraint errors in test setup; `test_compensated_hero_assembly.py`
— 1 SyncNet-binary-not-available error. None reach or relate to S15.)

### 5.5 Classification

| Failure | Caused by S15? | Nature | Class |
|---------|----------------|--------|-------|
| 11 × `SYNCNET_PER_SEGMENT_MISSING` | No | stale S13/S14 fixtures (predate S14 gate) | ACCEPTABLE / PRE-EXISTING |
| 5 × `has no passing QA` (line 233) | No | stale fixtures (no QA records) | ACCEPTABLE / PRE-EXISTING |
| **5 × `BLOCKED_SHOT_MIX_CONTRACT`** | **Yes** | stale S14 fixtures (predate S15 contract) | **NEW, but stale-fixture not production-bug** |
| 4 × FK errors / 1 × SyncNet binary | No | test infra / env | ACCEPTABLE / PRE-EXISTING |

**Conclusion on D:** S15 is **not** free of new test failures — it newly breaks 5 S14
positive-path tests. However, these are **stale fixtures**, not broken production behavior:
the contract is working exactly as specified (it correctly rejects an under-populated
storyboard), and the failures degrade S14's positive-path coverage rather than any S15/S13/S14
guarantee. The prior session's regression evidence was materially wrong and must be
superseded by §5.3.

This does **not** rise to MAJOR per the gate's MAJOR rubric: S15 does not cause/worsen a
production defect, does not hide a broken S13/S14 **negative-path** guarantee (those still
pass), does not prevent meaningful validation of S15 (the 12-test suite + dedicated
regression tests validate it cleanly), and the suite is noisy but not untrustworthy for S15.
It is a real, non-blocking coverage gap that should be fixed in a follow-up so S14's
"good-syncnet-passes" assertions are reachable again.

---

## 6. Gate Question E — Governance independence

- Reviewer is a separate session; no reliance on the prior PASS/APPROVED verdicts.
- Code inspected directly; classifications and the `max_consecutive_hero` fix reproduced
  with runtime probes independent of the test suite.
- Tests re-run; regression re-measured with a corrected methodology that contradicts the
  prior session's headline number.
- The decision below is this reviewer's own.

---

## 7. No-fake-green / no-silent-fallback spot checks

- Fail-closed on missing/invalid contract config (`BLOCKED_SHOT_MIX_CONTRACT_CONFIG_MISSING`
  / `_INVALID` / `_UNKNOWN` / `_VALIDATION_FAILED`) — verified in code, no silent pass.
- `classify_render_unit` returns `None`→`other` for unmatched units; "other" cannot satisfy
  any hero/broll/graphic minimum, so an unclassifiable unit is not a back door.
- No `--force-unsafe`, no provider calls, no test-specific production branches observed in
  the S15 footprint.
- The S15 footprint in `assemble_db.py` is exactly 1 import (line 24) + 1 validation block
  (351–382). The larger working-tree diff is pre-existing S13/S14 work, consistent with the
  engineering report's scope note.

---

## 8. Summary

| Section | Verdict |
|---------|---------|
| A — Contract correctness | PASS |
| B — DB-native enforcement | PASS |
| C — No false counting | PASS |
| D — Suite health | **5 NEW S15-caused failures (stale fixtures), prior regression evidence WRONG** |
| E — Governance independence | Satisfied |

The S15_T001 **implementation is correct and complete**. The **evidence accompanying it was
not**: the headline "zero regressions, +1 pass" is wrong (true figure: 5 new failures, 0
fixed), and the "all failures hit before the shot-mix gate" claim is wrong (5 hit the
shot-mix gate itself). The 5 real failures are stale S14 positive-path fixtures, not
production defects.

*End of Gate Review*
