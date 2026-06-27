# Validation Report — S15_T004 (Frame sampling utility)

**Ticket**: S15_T004 — Frame sampling utility
**Sprint**: S15 — Shot-mix contract and semantic role validation
**Validator**: Software Validator (Claude Code, independent of engineer/auditor)
**Date**: 2026-06-27

---

## Required ticket tests — run, with exact counts

All required commands run via `python3 -m pytest <args> -p no:cacheprovider`. Raw output captured to `reports/karpathy_loop/s15/S15_T004/test_results.txt`.

| # | Command | Result |
|---|---------|--------|
| 1 | `tests/test_frame_sampling.py -v` | **13 passed** |
| 2 | `tests/test_semantic_role_qa.py -v` | **16 passed** |
| 3 | `tests/test_visual_role_contract.py -v` | **12 passed** |
| 4 | `tests/test_shot_mix_contract.py -v` | **12 passed** |
| 5 | `tests/test_s14_t004_syncnet_confidence.py -v` | **9 passed** |
| 6 | `tests/test_s14_t003_per_segment_syncnet.py -v` | **6 passed** |
| 7 | `tests/test_lipsync_policy.py tests/test_hero_framing.py -v` | **73 passed** |
| 8 | `tests/test_s13_t005_integration_regression.py -v` | **14 passed, 1 skipped** |
| 9 | `tests/test_audio_continuity.py -v` | **18 passed** |
| | **Required-set total** | **173 passed, 1 skipped** |

The 1 skip is pre-existing: `test_assembly_produces_segment_timeline` wraps a hardcoded production-id manifest build in `try/except → pytest.skip`; it skips because that production does not exist in the per-test isolated DB. Not caused by S15_T004.

Required-set growth vs the S15_T003-accepted baseline (160 passed / 1 skipped): **+13 passed**, which is exactly the new `test_frame_sampling.py` suite. No existing required test regressed.

---

## Full-suite attribution check (optional, run)

```
python3 -m pytest -q 2>&1 | tee /tmp/s15_t004_fullsuite.txt
grep -E "FRAME|frame_sampling|SEMANTIC_ROLE|VISUAL_ROLE|SHOT_MIX|SYNCNET|COMPENSATED" /tmp/s15_t004_fullsuite.txt
```

**Full suite: 90 failed, 1812 passed, 10 skipped, 2 xfailed, 1 xpassed.**

- **`FRAME_SAMPLING` or related failure count across the entire suite: 0.** The frame sampling module fires only inside `test_frame_sampling.py`'s controlled tests (which pass). No other test reaches frame sampling code.
- **Failure count vs the S15_T003-accepted baseline** (90 failed / 1799 passed / 10 skipped): **+13 passed**, **0 new failures**. Net new failures introduced by S15_T004: **zero.**

---

## Remaining full-suite failures — classification

All 90 failures are **REAL but PRE-EXISTING and OUT OF SCOPE** → **NO MATERIAL IMPACT** on S15_T004:

| Bucket | Examples | Classification |
|--------|----------|----------------|
| S14 SyncNet earlier-gate debt | `test_syncnet_gate`, `test_compensated_hero` | Pre-existing; fails before frame sampling |
| S15_T001 shot-mix fixture debt | `test_assembly_timeline_heuristics`, `test_s9_c07_assembly` | Pre-existing; non-compliant fixtures |
| Unrelated subsystems | `test_audio_slicing`, `test_canary_freshness`, `test_db_render_state_machine`, `tests/e2e/*` | Pre-existing; not S15_T004 |

**Definitive attribution**: S15_T004's only involvement is frame sampling extraction. Zero failures anywhere in the full suite relate to frame sampling. All 90 failures are pre-existing earlier-gate debt or unrelated subsystems.

---

## Inspection of reports / evidence

- `reports/karpathy_loop/s15/S15_T004/engineering_report.md` — design, files, strategies, determinism.
- `reports/karpathy_loop/s15/S15_T004/audit_report.md` — checklist PASS, no BLOCKER/MAJOR.
- `reports/karpathy_loop/s15/S15_T004/test_results.txt` — raw required-test output.

---

## Unintended-broad-change check

- Production diff: one file only (`scripts/frame_sampling.py`, NEW).
- Test diff: one file only (`tests/test_frame_sampling.py`, NEW).
- No production gate logic was modified.
- No existing test files were modified.
- No S15_T005 work started (no semantic judgment, no frame analysis metrics).

---

## Loop-state accuracy check

`management/LOOP_STATE.md` and `management/TICKET_STATUS.json` updated to record S15_T004 as ENGINEERING PASS (engineering + audit + validation complete), awaiting final loop decision.

---

## Validation verdict

**PASS.** Required ticket tests fully green (173 passed / 1 pre-existing skip). No regression vs baseline (90 failures unchanged; +13 passes are the new tests). Zero frame-sampling-related failures anywhere in the full suite. No gate weakening, no fake-green, no paid renders, no broad suite cleanup, no S15_T005 implementation.

Frame sampling is correctly scoped as evidence-input-only and ready for S15_T005 to build semantic analysis on top.
