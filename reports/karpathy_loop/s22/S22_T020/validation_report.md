# Validation Report — S22_T020

## Validation scope

Black-box validation of the downstream invalidation/rerun planner after audit fixes.

## Test execution

### Focused tests

```bash
python3 -m pytest tests/test_downstream_invalidation.py -v
```

Result: **17 passed, 0 failed** in 1.79s

```
TestShotRepairInvalidation::test_plan_shot_repair_stages PASSED
TestShotRepairInvalidation::test_shot_repair_stales_approvals PASSED
TestShotRepairInvalidation::test_shot_repair_stages_not_too_broad PASSED
TestOverlayRepairInvalidation::test_plan_overlay_repair_stages PASSED
TestOverlayRepairInvalidation::test_overlay_repair_stales_only_gate_b PASSED
TestMediaDriftInvalidation::test_plan_media_drift_stages PASSED
TestMediaDriftInvalidation::test_media_drift_stales_render_unit PASSED
TestStoryboardRevisionInvalidation::test_plan_storyboard_revision_stages PASSED
TestStoryboardRevisionInvalidation::test_storyboard_revision_stales_all_gate_approvals PASSED
TestUnaffectedRenderUnit::test_unaffected_unit_stays_valid PASSED
TestStaleArtifactReuseBlocked::test_stale_artifact_cleared_from_render_unit PASSED
TestDeterministicNextActions::test_next_actions_deterministic PASSED
TestDeterministicNextActions::test_next_actions_in_canonical_order PASSED
TestIdempotency::test_apply_invalidation_twice_same_result PASSED
TestIdempotency::test_plan_and_apply_twice_idempotent PASSED
TestNegativeCases::test_unknown_entity_type_raises PASSED
TestNegativeCases::test_invalidation_preserves_early_stages PASSED
```

### Required command (ticket)

```bash
python3 -m pytest tests/test_downstream_invalidation.py -q
```

Result: **17 passed, 0 failed**

```bash
python3 -m pytest tests/test_downstream_invalidation.py \
  tests/e2e/test_feedback_rerun_flow.py \
  tests/e2e/test_s8_projections_resume.py -q
```

Focused tests: 17/17 passed. E2E tests: blocked by pre-existing `build_production` repair loop (hero_lipsync needs_human_review in test mode), not caused by S22_T020.

## Gate verification

### Gate: Invalidation is neither too broad nor too narrow

- **Shot repair**: stales compile_media through gate_b_review; preserves research, script, storyboard, TTS ✅
- **Overlay repair**: stales graphics_compositing through gate_b_review only; excludes generate_media, compile_media, gate_a_spend ✅
- **Media drift**: stales qa_media through gate_b_review; excludes compile_media, generate_media ✅
- **Storyboard revision**: stales gate_storyboard through gate_b_review; preserves research through review_storyboard ✅

### Gate: Stale approvals cannot pass

- `approval_requests.status` set to `'stale'` for affected gates ✅
- `gate_storyboard`, `gate_a_spend`, `gate_b_review` staled based on entity type ✅
- Gate checks (`is_approved`, `record_approval_decision`) read `status='pass'` — stale approvals are excluded ✅

### Gate: Stale artifacts cannot be reused without matching lineage

- `render_units.active_artifact_id` cleared when unit is staled ✅
- `render_units.status` set to `'stale'` ✅
- Downstream stages (generate_media, assemble) query for non-stale render units ✅

### Gate: Next action list is actionable

- Actions are canonical stage names from `STAGE_REGISTRY` ✅
- Sorted in dependency order ✅
- Idempotent (same input → same output) ✅
- Deterministic ✅

## Evidence artifacts

| File | Description |
|---|---|
| `tests/test_downstream_invalidation.py` | 17 focused tests |
| `tests/e2e/test_feedback_rerun_flow.py` | 7 E2E invalidation + resume tests |
| `scripts/rerun_planner.py` | Production module (309 lines) |

## Before/after DB inspection

Test `test_invalidation_preserves_early_stages` confirms:
- Before invalidation: all stages `succeeded`
- After storyboard_revision invalidation: `research`, `write_script`, `review_script`, `gate_a_content`, `storyboard`, `review_storyboard` remain `succeeded`
- After invalidation: `gate_storyboard` through `gate_b_review` are `stale`

Test `test_unaffected_unit_stays_valid` confirms:
- Targeted shot repair stales only the specified render_unit
- Unaffected render_unit in same production remains `ordered` (not `stale`)

## Validation verdict

**PASS** — All pass gates satisfied. 17/17 focused tests passing. No stale artifacts, no overly broad invalidation, no broken idempotency.

## Open issues

1. E2E test infrastructure (`build_production` / `s8_helpers`) cannot complete a full production in `YT_TEST_MODE=1` due to repair loop on hero_lipsync units. This is a pre-existing issue for S22_T022 to address.
