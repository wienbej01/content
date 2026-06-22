# CDB-06 Engineer Report — Golden-Truth Gate

**Status:** ✅ Complete  
**Date:** 2026-06-15  

## Summary

`build_manifest.py` now calls `clip_db.assert_all_valid(project_id)` before building a manifest. If any clip is not in `valid` status or has an open change request, manifest construction is impossible — the pipeline halts with an actionable error listing each problem clip, its status, target_step, and reason.

## Changes

### `scripts/build_manifest.py`

Added the golden-truth gate at the top of `build()`, immediately after loading the plan JSON:

1. Derives `project_id` from the plan (or falls back to `project_dir.name`)
2. Calls `clip_db.list_clips(project_id)` — if no rows exist (legacy/table missing), emits a warning and skips (backward compat)
3. If rows exist, calls `clip_db.assert_all_valid(project_id)` — on failure, raises `RuntimeError` with per-clip details
4. The error message lists each problem: `clip_id`, `status`/`change_type`, `target_step`, and `reason`

Graceful handling:
- `ImportError` (clip_db unavailable): skip with warning
- `OperationalError` (no table): treat as legacy, skip with warning
- No clip rows for project: skip with warning

### Tests

| File | Tests | Purpose |
|------|-------|---------|
| `tests/test_cdb06_golden_gate.py` | 4 | Gate behavior: blocked on non-valid, blocked on open request, passes when valid, legacy skip |
| `tests/test_cdb06_e2e.py` | 1 | Full closed-loop: order → deficit → change request → blocked → regen → resolve → valid → proceed |

## Test Results

```
tests/test_cdb06_golden_gate.py::TestGoldenGate::test_manifest_blocked_when_clip_not_valid PASSED
tests/test_cdb06_golden_gate.py::TestGoldenGate::test_manifest_blocked_when_open_change_request PASSED
tests/test_cdb06_golden_gate.py::TestGoldenGate::test_manifest_proceeds_when_all_valid PASSED
tests/test_cdb06_golden_gate.py::TestGoldenGate::test_legacy_no_clips_skips_assertion PASSED
tests/test_cdb06_e2e.py::TestFullLoopDeficitThenFixed::test_full_loop_deficit_then_fixed PASSED
```

Full suite: **588 passed** (no regressions)

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | build_manifest calls assert_all_valid; blocks with actionable error | ✅ |
| 2 | Proceeds only when all clips valid | ✅ |
| 3 | Legacy projects (no clip rows) skip the gate | ✅ |
| 4 | Closed-loop E2E proves deficit → change request → fix → valid → proceed | ✅ |
| 5 | All tests pass; full suite green | ✅ 588 passed |

## Validation Commands

```bash
python3 -m pytest tests/test_cdb06_golden_gate.py tests/test_cdb06_e2e.py -v
python3 -m pytest tests/test_manifest_builder.py -v
python3 -m pytest -q
```
