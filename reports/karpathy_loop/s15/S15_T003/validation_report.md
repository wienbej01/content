# Validation Report — S15_T003 (Post-render semantic role QA)

**Ticket**: S15_T003 — Post-render semantic role QA
**Sprint**: S15
**Validator**: Software Validator (Claude Code, independent of engineer/auditor)
**Date**: 2026-06-27

---

## Required ticket tests — run, with exact counts

All eight required commands run via
`python3 -m pytest <args> -p no:cacheprovider`. Raw output captured to
`reports/karpathy_loop/s15/S15_T003/test_results.txt`.

| # | Command | Result |
|---|---------|--------|
| 1 | `tests/test_semantic_role_qa.py -v` | **16 passed** |
| 2 | `tests/test_visual_role_contract.py -v` | **12 passed** |
| 3 | `tests/test_shot_mix_contract.py -v` | **12 passed** |
| 4 | `tests/test_s14_t004_syncnet_confidence.py -v` | **9 passed** |
| 5 | `tests/test_s14_t003_per_segment_syncnet.py -v` | **6 passed** |
| 6 | `tests/test_lipsync_policy.py tests/test_hero_framing.py -v` | **73 passed** |
| 7 | `tests/test_s13_t005_integration_regression.py -v` | **14 passed, 1 skipped** |
| 8 | `tests/test_audio_continuity.py -v` | **18 passed** |
| | **Required-set total** | **160 passed, 1 skipped** |

The 1 skip is pre-existing: `test_s13_t005::test_assembly_produces_segment_timeline`
wraps a hardcoded production-id manifest build in `try/except → pytest.skip`; it
skips because that production does not exist in the per-test isolated DB. Not
caused by S15_T003.

Required-set growth vs the S15_T002-accepted baseline (144 passed / 1 skipped):
**+16 passed**, which is exactly the new `test_semantic_role_qa.py` suite. No
existing required test regressed.

## Full-suite attribution check (optional, run)

```
python3 -m pytest -q 2>&1 | tee /tmp/s15_t003_fullsuite.txt
grep -E "SEMANTIC_ROLE|VISUAL_ROLE|SHOT_MIX|SYNCNET|COMPENSATED" /tmp/s15_t003_fullsuite.txt
```

**Full suite: 90 failed, 1799 passed, 10 skipped, 2 xfailed, 1 xpassed.**

- **`BLOCKED_SEMANTIC_ROLE` failure count across the entire suite: 0.** The gate
  fires only inside `test_semantic_role_qa.py`'s controlled negative tests
  (which pass). No other test reaches or fails at the semantic-role gate.
- **Failure count unchanged vs the S15_T002-accepted baseline** (90 failed /
  1783 passed / 10 skipped → now 90 failed / 1799 passed / 10 skipped). The +16
  passes are exactly the new tests. **Net new failures introduced by S15_T003:
  zero.**

## Remaining full-suite failures — classification

All 90 failures are **REAL but PRE-EXISTING and OUT OF SCOPE** → **NO MATERIAL
IMPACT** on S15_T003. They fail at earlier gates or are unrelated subsystems:

| Bucket | Examples | Classification |
|--------|----------|----------------|
| S14 SyncNet earlier-gate debt | `test_syncnet_gate`, `test_s13_t002_compensated_hero_requirement`, `test_compensated_hero_assembly` (`BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING` / `BLOCKED_HERO_COMPENSATED_*`) | Pre-existing; fails before semantic gate |
| S15_T001 shot-mix fixture debt | `tests/unit/test_assembly_preflight`, `test_assembly_timeline_heuristics`, `test_sprint7_assemble_db`, `test_s9_c07_assembly` (`BLOCKED_SHOT_MIX_CONTRACT` on non-compliant fixtures) | Pre-existing; fails before semantic gate |
| Unrelated subsystems | `test_audio_slicing`, `test_audio_timing`, `test_canary_freshness`, `test_db_render_state_machine`, `test_lb301_slicing`, `test_qa_final`, `tests/e2e/*`, `test_sprint6_media_service` | Pre-existing; not assembly-gate / not S15_T003 |

**Definitive attribution**: S15_T003's only failure mode is
`BLOCKED_SEMANTIC_ROLE_*`, and that mode appears **zero** times across the full
suite outside the new file's intentional (passing) negative tests.

## Inspection of reports / evidence

- `reports/karpathy_loop/s15/S15_T003/engineering_report.md` — design, files, signatures.
- `reports/karpathy_loop/s15/S15_T003/audit_report.md` — checklist PASS, no BLOCKER/MAJOR.
- `reports/karpathy_loop/s15/S15_T003/test_results.txt` — raw required-test output.

## Unintended-broad-change check

- Production diff is two files: `scripts/semantic_role_qa.py` (new) and
  `scripts/assemble_db.py` (constant import + one gate function + one call site).
- Test diff: one new file + `seed_semantic_role_qa` helper + one-line seeding
  calls in four shared batch builders. No production gate logic was weakened.
- No S15_T004 work started (no frame-sampling utility implemented).

## Loop-state accuracy check

`management/LOOP_STATE.md` and `management/TICKET_STATUS.json` updated to record
S15_T003 as ENGINEERING PASS (engineering + audit + validation complete), state
INDEPENDENT_ACCEPTANCE_REVIEW_PENDING, S15_T004 not started.

## Validation verdict

**PASS.** Required ticket tests fully green (160 passed / 1 pre-existing skip).
No regression vs baseline (90 failures unchanged; zero `BLOCKED_SEMANTIC_ROLE`
failures anywhere). No gate weakening, no fake-green, no paid renders, no broad
suite cleanup, no S15_T004 implementation.
