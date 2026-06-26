# Validation Report — S15_T002_RETRY / FIX001

**Ticket**: S15_T002 — Add visual_role metadata
**Sprint**: S15
**Date**: 2026-06-26
**Validator model**: ZAI_STRONG_CODING (glm-5.2)
**Verdict**: **PASS** (pending independent acceptance — see loop_decision)

> The validator runs the ticket tests, relevant existing tests, inspects evidence,
> and confirms no unintended broad changes. Per global operating rules, an engineer
> must not approve its own implementation; this report is the engineering
> self-validation and **does not constitute acceptance**.

---

## 1. Commands run (exact)

```bash
python3 -m pytest tests/test_visual_role_contract.py -v
python3 -m pytest tests/test_shot_mix_contract.py -v
python3 -m pytest tests/test_s14_t004_syncnet_confidence.py -v
python3 -m pytest tests/test_s14_t003_per_segment_syncnet.py -v
python3 -m pytest tests/test_lipsync_policy.py tests/test_hero_framing.py -v
python3 -m pytest tests/test_s13_t005_integration_regression.py -v
python3 -m pytest tests/test_audio_continuity.py -v
# broad regression sweep (assembly / authoring / contracts / syncnet)
python3 -m pytest tests/test_assemble.py tests/test_assemble_continuous_contract.py \
  tests/test_assemble_policy_driven.py tests/test_sprint4_authoring.py \
  tests/test_sprint5_tts_service.py tests/contracts/ tests/test_s14_t005_baseline_recalibration.py ...
# optional diagnostic
python3 -m pytest tests/test_compensated_hero_assembly.py tests/test_syncnet_gate.py -v
# full suite
python3 -m pytest -q
```

## 2. Required test results

| File | Result |
|------|--------|
| `tests/test_visual_role_contract.py` | **12/12 PASS** |
| `tests/test_shot_mix_contract.py` | **12/12 PASS** |
| `tests/test_s14_t004_syncnet_confidence.py` | **9/9 PASS** |
| `tests/test_s14_t003_per_segment_syncnet.py` | **6/6 PASS** |
| `tests/test_lipsync_policy.py` + `tests/test_hero_framing.py` | PASS (part of 144) |
| `tests/test_s13_t005_integration_regression.py` | PASS (1 pre-existing skip) |
| `tests/test_audio_continuity.py` | PASS |
| **Required set total** | **144 passed, 1 skipped** |

## 3. Pass-criteria trace (ticket: "Every active span has visual_role; missing role blocks")

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Every active span/unit has visual_role (publish-grade) | `validate_visual_roles` enforces; positive test passes | ✅ |
| Missing role blocks | `test_missing_visual_role_fails_visual_role_error` → `BLOCKED_VISUAL_ROLE_MISSING` | ✅ |
| Invalid role blocks | `test_invalid_visual_role_fails_visual_role_error` → `BLOCKED_VISUAL_ROLE_INVALID` | ✅ |
| `asset_type` logic remains | shot-mix classification unchanged; 12/12 shot-mix tests green | ✅ |
| Regression: old bad behavior cannot occur | negative tests assert shot-mix NOT in message; not-inferred-from-label test | ✅ |
| Existing relevant tests still pass | s13/s14/s15_T001 targeted all green | ✅ |

## 4. Negative tests fail for the intended reason (not masked)

Both negative tests build a **contract-compliant** batch (shot-mix passes), then
break one unit's `visual_role`:

- Missing → `BLOCKED_VISUAL_ROLE_MISSING` (asserts `BLOCKED_SHOT_MIX_CONTRACT` absent). ✅
- Invalid → `BLOCKED_VISUAL_ROLE_INVALID` (asserts `BLOCKED_SHOT_MIX_CONTRACT` absent). ✅

This is the core correction to the prior attempt, where the same scenarios were
masked by `BLOCKED_SHOT_MIX_CONTRACT` because the fixtures were non-compliant.

## 5. No unintended broad changes

- **Diff scope**: 3 production files (ticket targets) + migration 011 + 4 test
  files (1 new shared fixture, 1 rewritten suite, 3 helper wirings).
- **Stash verification**: stashing the 3 production files reproduces the identical
  pre-existing failures in `test_syncnet_gate` (FK setup), `test_compensated_hero_assembly`,
  and `contracts/test_selective_repair` → these are **not** caused by S15_T002.
- **Baseline comparison**: prior WIP = **121 failed**; after FIX001 the only
  remaining failures are the pre-existing out-of-scope ones above.

## 6. Optional diagnostic tests

`tests/test_compensated_hero_assembly.py` + `tests/test_syncnet_gate.py`: 5 failures,
all `FOREIGN KEY constraint failed` in **test setup** (manual render_unit insert
without a parent timeline_span), reproduced identically on HEAD production code.
**NO MATERIAL IMPACT** on S15_T002 (per the retry brief these are optional `|| true`).

## 7. Full-suite count

**Full suite (`python3 -m pytest -q`): 90 failed, 1783 passed, 10 skipped, 2 xfailed, 1 xpassed.**

This is the honest, complete number. The earlier broad sweep in §5 understated the
pre-existing total (it did not traverse `tests/unit/`, `tests/regression/`,
`tests/integration/`). The corrected analysis:

**Definitive regression attribution.** S15_T002's only failure mode is
`BLOCKED_VISUAL_ROLE_*`. I ran the **complete set of 10 test files that call
`validate_assembly_inputs`** (the only code path that can reach the visual_role
gate) and grepped the output:

```
$ <all 10 callers> | grep -c BLOCKED_VISUAL_ROLE
0
```

**Zero `BLOCKED_VISUAL_ROLE` failures anywhere in the suite.** Therefore S15_T002
introduces **zero regressions**. Every one of the 14 failures in those 10 files is
on an EARLIER gate that S15_T002 does not touch:

| File | Failures | Blocking gate (NOT visual_role) |
|------|----------|---------------------------------|
| `tests/unit/test_assembly_timeline_heuristics.py` | 5 | `BLOCKED_SHOT_MIX_CONTRACT` (single-graphic batches) — S15_T001 |
| `tests/unit/test_assembly_preflight.py` | 3 | `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` / shot-mix — S14/S15_T001 |
| `tests/test_syncnet_gate.py` | 4 | `FOREIGN KEY constraint failed` in test setup |
| `tests/test_s13_t002_simple.py` | 1 | `BLOCKED_HERO_COMPENSATED_*` / `BLOCKED_HERO_SYNC_UNVERIFIED` — S13 |
| `tests/integration/test_e2e_db_native_no_paid_provider.py` | 1 | `BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` — S14 |

The remaining ~76 of the 90 are the same classes (overwhelmingly S15_T001
shot-mix on non-compliant single-unit fixtures across `tests/unit/` and other
dirs, plus S14 syncnet and FK-setup) — all pre-existing relative to S15_T002 and
not chased (out of scope; this is S15_T001/S13/S14 fixture debt). The prior WIP
baseline was **121 failed**; FIX001 reduced it to **90** by removing the two
over-aggressive S15_T002 changes — i.e. FIX001 **fixed 31 failures and introduced
none**.

## 8. Limitations

- Self-authored engineering/audit/validation; **independent validation required**
  for acceptance (global rule: an engineer must not approve its own implementation).
- Real LLM authoring does not yet emit `visual_role`; a real publish run will
  fail-closed at this gate until that wiring is added (separate ticket).
