# BSS-03 — Engineer Report: Remove Unsafe Generation Bypass and Wire Real Gates

**Date:** 2026-06-14  
**Status:** ✅ Complete

## Problem

`step_generate_media()` in `scripts/produce.py` called `run_from_media_plan(..., force_unsafe=True)`, which bypassed ALL spend gates (`storyboard_review`, `media_plan_review`, `budget`, `render_approval`). This meant any orchestrated production run could trigger paid Higgsfield/ElevenLabs generation without verifying that prerequisite reviews and human approvals had occurred.

Additionally, `step_gate_a_budget()` only prompted the human but never wrote gate-ledger entries, and neither `step_storyboard_review_loop` nor `step_compile_media_plan` recorded their gate-ledger entries after completing successfully.

## Changes Made

### `scripts/produce.py`

1. **`step_storyboard_review_loop()`** — after the review loop passes, records `storyboard_review` gate bound to the SHA-256 of `storyboard.json`.

2. **`step_compile_media_plan()`** — after successful compilation, records `media_plan_review` gate bound to the SHA-256 of `media_plan.json`.

3. **`step_gate_a_budget()`** — after human approves, records both:
   - `budget` gate (bound to `media_plan.json` hash, with `approved_cost` in extra)
   - `render_approval` gate (human_interactive approval)

4. **`step_generate_media()`** — replaced `force_unsafe=True` with `force_unsafe=False` and added an explicit `require_gates()` call before `run_from_media_plan`. This provides defense-in-depth: even if `generate_media.py` changes internally, `produce.py` independently enforces the gate check.

### `tests/test_spend_gates.py` (new file, 5 tests)

| Test | Verifies |
|------|----------|
| `test_generate_requires_all_gates` | step_generate_media exits before calling run_from_media_plan when gates are missing |
| `test_generate_proceeds_with_fresh_gates` | Proceeds normally when all 4 gates are recorded with fresh hashes |
| `test_stale_gate_blocks_generation` | Modifying storyboard.json after gate was recorded → blocks generation |
| `test_no_force_unsafe_in_produce` | Source code of step_generate_media contains no `force_unsafe=True` |
| `test_budget_gate_recorded_on_approval` | Human "go" → both budget and render_approval gates written to ledger |

## Verification

```
$ rg "force_unsafe=True" scripts/produce.py
(no output — confirmed removed)

$ python3 -m pytest tests/test_spend_gates.py -v
5 passed in 0.82s

$ python3 -m pytest -q
367 passed in 98.94s
```

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `rg "force_unsafe=True" scripts/produce.py` returns nothing for step_generate_media | ✅ |
| 2 | `step_generate_media()` fails if any required gate is missing/stale/failed | ✅ |
| 3 | Budget approval records gates.json entry with artifact hash | ✅ |
| 4 | All 5 tests pass | ✅ |
