# REPAIR-TKT-601A Validation Report

- **Ticket**: REPAIR-TKT-601A — Storyboard projection gap
- **Date**: 2026-07-06
- **Validator**: Same session (operator-authorized)
- **Verdict**: PASS

## Validation steps

### 1. Focused tests pass independently
```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py -q
```
63 passed in 0.10s. ✓

### 2. Sprint invariant 5-file suite passes
```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q
```
147 passed in 12.61s. ✓

### 3. Original defect irrereproducible
Verified against the real `prod_4e0ce12e` canonical storyboard (DeepSeek V4 Pro-authored, 9 shots with the prompt vocabulary roles):
- Pre-fix: all 9 beats projected as hero (all-hero failure, `review_storyboard.review()` → 7 blocking issues)
- Post-fix: 4 hero_lipsync + 3 broll_archival + 1 graphic_progressive + 1 broll_environment → `review_storyboard.review()` → **0 blocking issues**
- Defect is irrereproducible ✓

### 4. No silent fallbacks introduced
- `_resolve_shot_type` no longer contains `return "hero_cutaway"` (grep verified)
- Unknown `visual_role` raises `ProjectionError` with actionable message
- Empty `visual_role` raises `ProjectionError` (not silently mapped)
- All produce_db.py delegation wrappers are transparent (function signatures unchanged)

### 5. No unintended file changes
Git diff confirms only intended files changed:
- `scripts/storyboard_beat_utils.py` (new — shared helpers)
- `scripts/storyboard_projection.py` (extended mapping + enriched beats + fail-loud)
- `scripts/produce_db.py` (delegation pattern + segment_text_map + shot_mix_summary)
- `tests/test_storyboard_projection.py` (16 new test methods)
- `configs/llm_models.yaml` (vision_qa profile restoration only; no model change)

Pre-existing test modifications (`test_brand_render.py`, etc.) are from prior Wave 4/5 tickets, not introduced by this fix.

### 6. Audit findings resolved
Auditor reported PASS with zero findings. No corrective action required.

### 7. No test-mode evasion or weakened assertions
- No `YT_TEST_MODE` checks added to new code
- No xfail/skip markers on new tests
- No `simulated: true` or dummy outputs introduced
- Projection failure is loud (`ProjectionError`), not logged-and-swallowed

### 8. Security and hygiene
- No secrets, tokens, or environment variables committed
- No new dependencies introduced (`storyboard_beat_utils.py` is pure Python, no imports beyond stdlib)
- No network/file I/O in the shared util module

## Verdict

**PASS** — all validation steps satisfied. The fix is minimal, systemic, and sustainable. Original defect is irrereproducible. No regressions. Ready for commit.
