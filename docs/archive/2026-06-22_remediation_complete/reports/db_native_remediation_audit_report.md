# Validation Report: DB-Native Media Platform Remediation

**Auditor:** Kilo (Independent Validator)
**Date:** 2026-06-22
**Branch:** forensic/use_ai_to_manage_your_time_efficiently-20260620T151859Z
**Overall Status:** FAIL

---

## 1. Test Suite Execution: FAIL

**Results:** 257 passed, 1 failed, 1 xfailed, 2 xpassed

### Critical Tests
| Test | Status |
|------|--------|
| `test_e2e_db_native_no_paid_provider.py` | PASS |
| `test_failed_production_fixture_loads.py` | PASS |
| `test_failed_production_qa_rejected.py` | PASS |

### Failing Test
| Test | Failure |
|------|---------|
| `test_repair_is_idempotent` | `RuntimeError: REPAIR BLOCKED: render_unit ... failure 'unknown_contract_failure' requires manual review` |

### Coverage Summary
- **15 unit test files** — media_contract, provider boundary, paid adapters, assembly preflight, timeline heuristics, local graphics DB, repair classifier, final QA contract, hero lipsync QA, hero temporal edit guard, compile media prompt split, smoke config
- **8 integration tests** — full lifecycle (repair loop, assembly artifact validation, e2e no-paid-provider, graphics compositing DB, provider job DB boundary, gate B review contract)
- **2 regression tests** — forensic fixture structure validation (contract-envelope checks)

---

## 2. File Size & Minimal Change Policy: PASS

| Check | Result |
|-------|--------|
| `find tests/fixtures -type f -size +150k` | **Nothing found** |
| All 4 fixture file sizes | 309–3,844 bytes ✅ |
| New untracked files | All small text/code files ✅ |
| Large media files (forensics/, brand/, assets/music/) | Pre-existing git-tracked artifacts, not added by remediation ✅ |
| Modified files | Surgical changes in 7 scripts (assemble_db, media_service, paid_adapters, produce_db, production_repo, qa_final, render_graphics) ✅ |

---

## 3. Provider Boundary Hardening: PASS

| Guard | Location | Verified |
|-------|----------|----------|
| `is_provider_forbidden_asset_type()` | media_contract.py:80 | Returns True for local_graphic, title_card, lower_third, source_card, quote_card, chart, diagram, caption, subtitle |
| `assert_provider_eligible()` | media_contract.py:135 | Raises MediaContractError for ineligible types |
| `assert_provider_prompt_text_free()` | media_contract.py:179 | Keyword-based text-risk detection (HBR, McKinsey, title card, Stanford, MIT, etc.) |
| `sanitize_provider_visual_prompt()` | media_contract.py:211 | Routes exact-text to deterministic_text_spec (returns None) |
| Provider guards invoked BEFORE job insertion | media_service.py:101–110 | `assert_provider_eligible()` + `assert_provider_prompt_text_free()` called in `submit_provider_job()` before `INSERT INTO provider_jobs` |
| Adapter-level second guard | paid_adapters.py:74–91 | HiggsfieldSeedanceAdapter re-checks asset_type, prompt text risks, deterministic_text_spec |
| Negative prompt capability gate | paid_adapters.py:146–154 | Only passes `--negative_prompt` when model has `supports_negative_prompt: True` |
| Local rendering (no AI calls) | render_graphics.py:293–372 | Uses PIL/Pillow only; registers artifact in DB with `render_method: local_graphic` |
| Test fakes (no paid APIs) | tests/helpers/fake_provider.py | FFmpeg lavfi only — testsrc2 pattern + sine audio; zero external API calls |

**All provider boundary guards are present and correctly layered:** contract → service → adapter → adapter (second guard).

---

## 4. QA & Assembly Contract Enforcement: PASS

| Contract Check | Module | Verified |
|----------------|--------|----------|
| Media QA dispatches by render method | media_service.py:946–1011 | `run_contract_media_qa()` classifies via `classify_render_method()` and dispatches to `_qa_local_graphic`, `_qa_hero_lipsync`, `_qa_provider_video`, `_qa_still` |
| Local graphic QA: provenance, text hash, no provider jobs | media_service.py:596–695 | Checks render_method==local_graphic, renderer==render_graphics.py, zero provider_jobs, text_spec_sha match |
| Final QA DB-contract checks | qa_final.py:222–404 | `run_db_contract_checks()`: passing QA per RU, local provenance, no provider-for-local, deliverable artifact + SHA, assembly preflight |
| Assembly preflight: active artifacts, passing QA, no stale | assemble_db.py:44–192 | `validate_assembly_inputs()`: active spans, no gaps/overlaps, per-span render mapping, active artifacts, passing QA, no provider-for-local-graphic, file existence, artifact set hash |
| Timeline heuristics | assemble_db.py:195–236 | Rejects: consecutive identical local_graphic labels, micro-cuts (<1s), long holds (>15s without 'hold' marker) |
| Gate B requires DB-contract evidence | assemble_db.py:558–582 | `request_gate_b()` requires deliverable + qa_validation_id before creating approval request |

**QA checks are contract-based** (render method, provenance, text spec, provider job linkage) — not merely mechanical file properties. Assembly blocks unvalidated artifacts.

---

## BLOCKER ISSUES

### B1. `test_repair_is_idempotent` fails — repair lifecycle not idempotent

- **File:** `scripts/media_service.py` lines 1194–1277 (`run_repair_lifecycle`)
- **Root cause:** The function loads the latest validation for the render unit (line 1221–1226) and passes its evidence to `classify_validation_failure()` (line 1233) without first checking whether the validation has `status == 'pass'`. When called a second time on an already-repaired unit:
  1. The latest validation is the **pass** from the first repair.
  2. `classify_validation_failure()` iterates through all failure conditions — all false because the unit is healthy.
  3. Falls through to `return "unknown_contract_failure"` (line 1166).
  4. `choose_repair_action` maps this to `"block_for_manual_review"` (line 1179).
  5. `RuntimeError` is raised (line 1272–1275).
- **Violation:** Repair must preserve history *and* be safe to re-run (invariant #5). The current implementation is not idempotent.
- **Fix:** Add an early-return guard — if `failure["status"] == "pass"`, return success immediately.

---

## MAJOR ISSUES

### M1. `classify_validation_failure` has no passing-case exit

- **File:** `scripts/media_service.py` lines 1129–1166
- **Defect:** The classifier assumes it will always receive failure evidence. Passing evidence (all checks true) falls through every branch to `unknown_contract_failure`. Either:
  - The caller (`run_repair_lifecycle`) should check validation status before calling the classifier, or
  - The classifier should accept an optional "skip if passing" parameter, or
  - `classify_validation_failure` should return None (or a sentinel) when no failure is detected.

### M2. `test_no_duplicate_active_artifacts` silently tolerates repair double-call

- **File:** `tests/integration/test_repair_loop_db.py` line 231
- **Observation:** This test also calls `run_repair_lifecycle()` twice (like `test_repair_is_idempotent`) but does not assert the second outcome or wrap it in `pytest.raises`. Its current PASS status is fragile — fixing the idempotency gap will change its behavior.

---

## Verification Log

All commands executed during audit:

```bash
# Test suite
python3 -m pytest tests/unit tests/integration tests/regression -v

# File size check
find tests/fixtures -type f -size +150k

# Large committed media files
git ls-files -- '*.mp4' '*.mp3' '*.png' '*.jpg' '*.wav' '*.m4a'

# Git status
git status
```

---

## Residual Risks

- The forensics directory contains ~100 tracked media files (pre-existing) that are not subject to the 100KB invariant. These were not added by the remediation.
- The `db/` directory contains several `.bak` and `.db` files >100KB. These are runtime artifacts, not test fixtures.
- The large `.ttf` font files in `brand/fonts/` are pre-existing.

---

## Recommendation

**Do not approve.** The build has one BLOCKER issue (B1). Fix the idempotency gap in `run_repair_lifecycle` by adding a status check before classification, then re-run the full test suite to confirm all tests pass. The remaining architecture (8/9 invariants) is sound and correctly implemented.
