# Audit Report — S15_T002_RETRY / FIX001

**Ticket**: S15_T002 — Add visual_role metadata
**Sprint**: S15
**Date**: 2026-06-26
**Auditor model**: ZAI_BEST_REASONING (glm-5.2)
**Verdict**: **PASS** — 0 BLOCKER, 0 MAJOR, 0 in-scope MINOR.

> The auditor reviews but does not repair. Findings below are observations against
> the S15_T002 ticket pass criteria and the retry brief's constraints.

---

## Audit checklist (per ticket)

| Check | Result | Evidence |
|-------|--------|----------|
| Every active span has visual_role; missing role blocks | ✅ | `validate_visual_roles` raises `BLOCKED_VISUAL_ROLE_MISSING` for publish-grade; `test_missing_visual_role_fails_visual_role_error` |
| `asset_type` logic remains | ✅ | `asset_type` untouched; classification still drives shot-mix |
| Tests meaningful, not file-existence-only | ✅ | negative tests assert exact `BLOCKED_VISUAL_ROLE_*` substrings AND assert `BLOCKED_SHOT_MIX_CONTRACT` is **absent** |
| No fake green | ✅ | see §2 |
| No silent fallback | ✅ | non-publish exemption is explicit + logged in evidence, not a swallowed error |
| No parallel infrastructure | ✅ | extends `assemble_db.py` + reuses `shot_mix_contract.get_contract`; one shared `visual_role_fixtures.py` |
| No provider render unless explicitly allowed | ✅ | no paid calls; all fixtures/dry-run |
| Failure messages explicit, `BLOCKED_`-prefixed | ✅ | `BLOCKED_VISUAL_ROLE_MISSING`, `BLOCKED_VISUAL_ROLE_INVALID` |

## 1. Was the prior bad test simplification reverted/fixed? — YES

The prior attempt's two publish-grade tests used `test_local` / single-graphic
fixtures to bypass the shot-mix contract. The retry brief rejects this. Verified
in the rewritten `tests/test_visual_role_contract.py`:

- The positive test (`test_publish_grade_batch_with_visual_roles_passes`) builds a
  full **H001→B001→H002→G001** publish-grade batch (2 hero w/ SyncNet +
  compensated, 1 b-roll, 1 graphic, opening hero, no consecutive heroes) and asserts
  `validation_passed is True`.
- The missing-role test NULLs `visual_role` on **one unit of an otherwise
  contract-compliant batch** and asserts the error is `BLOCKED_VISUAL_ROLE_MISSING`
  **and not** `BLOCKED_SHOT_MIX_CONTRACT` — i.e. shot-mix passed and the visual_role
  gate was reached. Same for invalid-role → `BLOCKED_VISUAL_ROLE_INVALID`.

No test bypasses shot-mix to reach visual_role.

## 2. No fake green

- The over-aggressive production changes that produced the prior 121-failure suite
  were **removed**, not papered over:
  - The unconditional `visual_role` block in `assemble_db.py` was replaced with a
    publish-grade-conditional `validate_visual_roles` call.
  - The save-time hard requirement in `authoring_service.py` was reverted to
    optional storage.
- Every previously-failing-because-of-visual_role test now passes for the **right
  reason**: the shared batch helpers carry a propagated `visual_role`, so shot-mix
  and visual_role both genuinely pass.
- Negative tests assert both the presence of the intended error and the **absence**
  of the masking shot-mix error.

## 3. Gate ordering / no weakening

- Shot-mix is **untouched** (`validate_shot_mix(units)` still always applies
  `short_educational`). No contract threshold, rule, or classification changed.
- The visual_role gate runs **after** shot-mix — the prior order is preserved; it
  was not reordered to make tests pass.
- `_resolve_production_contract` defaults unknown/NULL `video_type` to
  `short_educational` (publish-grade) — real productions cannot accidentally opt out.
  Only an explicit `test_local` / `diagnostic_legacy` opts out, and that exemption is
  logged in evidence.

## 4. Scope hygiene

- Production files touched: only the three in the ticket's targets
  (`assemble_db.py`, `authoring_service.py`, `production_repo.py`) + migration 011.
- The incidental `db_path=db`→`db_path=db_path` fix is a real latent bug (undefined
  `db` → swallowed `NameError` → silent `close_hero` fallback for every hero); kept.
- No unrelated production files modified.

## 5. Residual failures — classification

Full suite: **90 failed, 1783 passed, 10 skipped.** The airtight attribution:
S15_T002's only failure mode is `BLOCKED_VISUAL_ROLE_*`, and **zero** tests fail
with that signature (verified across the full set of 10 `validate_assembly_inputs`
callers and corroborated by the full suite). Therefore S15_T002 causes **zero**
failures.

The 90 are pre-existing, blocking on earlier gates S15_T002 does not touch:

| Cause | Representative files | Class |
|------|----------------------|-------|
| `BLOCKED_SHOT_MIX_CONTRACT` (S15_T001 — non-compliant single-unit fixtures) | `tests/unit/test_assembly_timeline_heuristics.py`, `tests/unit/test_assembly_preflight.py`, + others | NO MATERIAL IMPACT (S15_T001 fixture debt) |
| `BLOCKED_HERO_SYNCNET_*` (S14) | `tests/unit/test_assembly_preflight.py`, `tests/integration/test_e2e_db_native_no_paid_provider.py` | NO MATERIAL IMPACT |
| `BLOCKED_HERO_COMPENSATED_*` (S13) | `tests/test_s13_t002_simple.py` | NO MATERIAL IMPACT |
| `FOREIGN KEY constraint failed` (test setup) | `tests/test_syncnet_gate.py`, `tests/test_compensated_hero_assembly.py` | NO MATERIAL IMPACT |
| `produce_db.invoke_repair` routing | `tests/contracts/test_selective_repair.py` | NO MATERIAL IMPACT |

Verified by stashing the three production files and reproducing identical
failures on HEAD code (FK/repair cases). Prior WIP baseline = 121 failed → FIX001
= 90 failed (fixed 31, introduced 0). Out of S15_T002 scope; not chased.

## 6. MINOR observations (non-blocking)

- M-1: `validate_visual_roles` validates against `ALLOWED_VISUAL_ROLES` (frozenset)
  while the `visual_roles` table is seeded separately by migration 011. They are
  consistent today; a future change to one should update the other. Acceptable:
  decoupling the gate from table state is intentional and the enum is small/stable.
- M-2: Real LLM authoring does not yet emit `visual_role` (out of scope). A real
  publish run will fail-closed at this gate until wired. Intended behavior.
