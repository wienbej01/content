# REPAIR-TKT-601A Audit Report

- **Ticket**: REPAIR-TKT-601A — Storyboard projection gap
- **Date**: 2026-07-06
- **Auditor**: Same session (operator-authorized)
- **Verdict**: PASS

## Audit steps

### 1. Verify focused tests pass independently

```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py -v
```
**Result**: 63 passed in 0.10s. All 16 new tests pass; all 47 existing tests pass with zero regression.

### 2. Verify invariant suite passes independently

```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_storyboard_projection.py tests/test_compile_media_from_canonical_shots.py tests/test_produce_db_orchestrator.py tests/test_llm_call.py tests/test_sonnet_storyboard_wrapper.py -q
```
**Result**: 147 passed in 12.44s. Zero failures, zero regression.

### 3. Acceptance gate G1: Real LLM-authored storyboard passes structural validation

Verified against the actual `prod_4e0ce12e24314d7798188aff60dca45f` canonical storyboard (9 shots, DeepSeek V4 Pro-authored):
- Projected 9 beats: 4 hero_lipsync + 3 broll_archival + 1 graphic_progressive + 1 broll_environment
- Hero ratio: 44% (inside short [8,60]% band)
- `review_storyboard.review()`: 0 blocking issues, 2 warnings (kinetic_text band, Act-5 graphic — both pre-existing band warnings, not blocking)
- **G1 PASS**

### 4. Acceptance gate G2: Unknown visual_role raises ProjectionError (fail-loud)

- `test_unknown_visual_role_raises_projection_error`: raises `ProjectionError` matching "Unknown visual_role" ✓
- `test_empty_visual_role_raises_projection_error`: raises `ProjectionError` ✓
- Verified: no `return "hero_cutaway"` fallback exists in `_resolve_shot_type` (grep confirms removed)
- **G2 PASS**

### 5. Acceptance gate G3: Test-mode path unchanged

- `test_host_present_speaking_maps_to_hero_lipsync` — still passes ✓
- `test_production_storyboard_fields_present` — still passes ✓
- `test_compiler_fields_present` — still passes ✓
- `test_shot_ids_preserved` — still passes ✓
- All `test_produce_db_orchestrator.py` tests pass (part of 147-test invariant suite) ✓
- produce_db delegation pattern preserves backwards compatibility — `_act_for()`, `_beat_duration_sec()`, etc. are thin wrappers calling shared utils
- **G3 PASS**

### 6. Acceptance gate G4: All required fields populated

Verified on projected beats:
- `narrative_function`: present, non-empty, non-generic on all beats; b-roll beats carry specific narrative functions ("Anchor the named evidence...", "Establish the real-world setting...") ✓
- `order`: sequential 0..n-1 ✓
- `act`: 1..6 distributed across beats; closing beat is act 6 ✓
- `est_duration_sec`: populated from `planned_duration_sec` (canonical) or narration fallback ✓
- `narration_text`: threaded from `segment_text_map` when provided ✓
- `label`: populated from `segment_id` ✓
- `shot_mix_summary`: computed via `compute_mix_summary` in production branch ✓
- **G4 PASS**

### 7. Regression checks

- No test case was weakened, skipped, or xfail'd
- No silent fallback introduced (failed-loud `ProjectionError` replaces silent `hero_cutaway`)
- `_CANONICAL_SHOTS` and `_NARRATION_WPS` values match between `produce_db.py` and `storyboard_beat_utils.py` (1.8077)
- All `produce_db.py` delegations are transparent (function names preserved, behavior unchanged)
- `configs/llm_models.yaml` unchanged from committed state except vision_qa profile restoration (existing WIP)

### 8. Defect prevention verification

- The shared module pattern (`storyboard_beat_utils.py`) eliminates the divergence that caused this defect — both production and test-mode paths now call the same `act_for`, `narrative_function_for`, `compute_mix_summary` functions
- All 13 prompt-vocabulary `visual_role` values mapped (parametrized test covers all)
- Unknown roles fail loudly with actionable error messages ("Extend _VISUAL_ROLE_TO_SHOT_TYPE in storyboard_projection.py to cover it")

## Findings

No findings (severity: N/A).

## Verdict

**PASS** — all four acceptance gates verified with independent test runs and production artifact validation. Zero regression in the 147-test invariant suite. No silent fallbacks, no weakened assertions, no permissive changes. The fix is minimal (scoped to the projection + orchestration layer), systemic (shared-util pattern prevents future divergence), and sustainble (fail-loud on unknown roles guarantees the mapping stays complete).
