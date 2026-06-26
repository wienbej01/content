# Gate Decision — S15_T001

**Ticket**: S15_T001 — Define format-level shot-mix contract
**Reviewer**: Independent gate (Claude, glm-4.7)
**Date**: 2026-06-26

## Verdict: **CONDITIONAL_PASS**

S15_T001 is **accepted**, with one **explicit non-blocking follow-up**.

---

## Rationale

**The S15_T001 implementation is correct and complete** — independently verified:

- Contract correctness (A): `short_educational` requires hero≥2/broll≥1/graphic≥1,
  opening-must-be-hero, `max_consecutive_hero` catches internal runs. The residual-count
  bug is genuinely fixed (`H,H,B,H,G` fails; `H,B,H,G` passes).
- DB-native enforcement (B): wired into `validate_assembly_inputs` after S13/S14, raises
  `BLOCKED_SHOT_MIX_CONTRACT`, reads the same active units, fail-closed on bad config.
- No false counting (C): hero audio excluded from broll via `exclude_hero_policies`,
  labels are not consulted, broll/graphics not forced to carry hero metadata.
- Own suite: 12/12 pass. S13/S14 gate-ordering regression tests pass. Supporting modules
  (lipsync_policy, hero_framing) green; S13 audio-continuity green (18/18).

**The evidence that accompanied the ticket was not correct**, and the gate must not inherit
the prior session's "zero regressions" claim:

- The prior session's regression method (`git stash` the whole `assemble_db.py`) reverted
  S13 and S14 too, measuring "no gates" vs "all gates".
- Correct measurement (neutralize **only** S15, keep S13/S14): **baseline 12 pass / 16 fail
  → S15 7 pass / 21 fail = 5 newly-broken tests, 0 newly fixed.**
- All 5 are `BLOCKED_SHOT_MIX_CONTRACT` failures in `test_s14_t004_syncnet_confidence.py`
  positive-path tests (`test_hero_unit_with_good_syncnet_passes`,
  `test_medium_framing_uses_medium_policy`, `test_wide_framing_uses_medium_policy`,
  `test_missing_framing_defaults_to_close`, `test_broll_flex_bypasses_confidence_check`).
  They fail **at** the S15 gate, not before it as previously claimed. They are stale
  single-unit fixtures that predate the contract — not production defects.

### Why CONDITIONAL_PASS and not PASS

A plain PASS would inherit and implicitly endorse the prior session's materially-wrong
"zero regressions" evidence and leave S14's positive-path coverage silently degraded. The
governance model (independent validation) requires the corrected record plus an explicit,
tracked remediation.

### Why CONDITIONAL_PASS and not RETRY/BLOCKED

- The S15 implementation itself is sound — reverting or blocking it would be disproportionate
  and would discard correct, needed contract enforcement.
- The 5 failures are stale fixtures, not broken S15 logic or weakened S13/S14 negative-path
  guarantees (those still pass).
- S15's own 12-test suite plus dedicated S13/S14 gate-ordering regression tests provide
  meaningful independent validation of the contract.
- The suite is noisy but not untrustworthy for S15 (the noise is pre-existing fixture gaps).

---

## Non-blocking follow-up created

**S15_SUITE_HEALTH_FIX001** — Restore S14 positive-path coverage.

Update the 5 stale fixtures in `tests/test_s14_t004_syncnet_confidence.py` to satisfy the
`short_educational` contract (each positive-path case should build ≥2 hero + ≥1 broll +
≥1 graphic, with the hero-under-test carrying the relevant SyncNet evidence), so the
"good-syncnet-passes" assertions are reachable again. The S15 contract class (`_make_units_batch`
in `test_shot_mix_contract.py`) is a reusable template. No production code change expected;
the fix is to test fixtures only. **Non-blocking for S15_T002** but should be scheduled
before S15 sprint close so S14's positive-path guarantees stay covered.

(Optionally, the same fixture-refresh pattern applies to the 11 pre-existing
`SYNCNET_PER_SEGMENT_MISSING` and 5 `has no passing QA` failures in the S13/S14 files, but
those predate S15 and are lower priority.)

---

## Corrected regression record (supersedes prior reports)

```
Baseline (S13/S14 intact, S15 disabled): 12 passed / 16 failed
S15 enabled (current):                    7  passed / 21 failed
Net S15 effect:                           5 newly broken, 0 newly fixed
  - all 5: BLOCKED_SHOT_MIX_CONTRACT, stale S14 positive-path fixtures
  - 0 production regressions
```

The prior engineering/audit/validation/loop_decision figure of "22→21 fail, +1 pass, zero
regressions" is **superseded**; it used a control that reverted S13/S14.

---

## Status of prior-session artifacts

The four prior reports (engineering/audit/validation/loop_decision) remain on record but
their **regression section is inaccurate**. They are not to be cited as evidence of "zero
regressions." This gate decision + `gate_review.md` §5 are the authoritative regression
record.

---

## Effect on state

- `LOOP_STATE.md`: S15_T001 → **CONDITIONALLY APPROVED** (gate review); S15_T002 remains
  gated on **explicit user approval** per the session instruction — the gate decision does
  not auto-start T002.
- `TICKET_STATUS.json`: S15_T001 condition flag + S15_SUITE_HEALTH_FIX001 recorded.
- S15_T002: **BLOCKED on user approval. Do not start.**

*End of Gate Decision*
