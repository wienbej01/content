# Corrective Report: S06_FIX_T003 Canary Must Generate New Artifact

## Problem
S06_T003 submitted a canary render but the idempotency key matched an existing job. The provider returned the old job without generating a new render. The gate accepted it as a pass because no freshness check existed.

## Corrective actions taken
1. **S06_T003 loop decision** → marked `INVALID_FOR_ACTUAL_CANARY`
2. **Freshness eval** → created `scripts/evals/eval_canary_freshness.py` with 10 checks
3. **Tests** → created `tests/test_canary_freshness.py` (6 tests)
4. **Canary plan** → updated with freshness requirements and canary_attempt_id
5. **Corrective ticket** → `S06_FIX_T003_CANARY_MUST_GENERATE_NEW_ARTIFACT.md`

## Freshness gate result (against invalid S06_T003)
```
Overall:          BLOCKED_NEEDS_FRESH_CANARY_RENDER
Fresh:            False
unlock_has_canary_attempt_id      ✗
artifact_created_after_unlock     ✗ (pre-unlock: 2026-06-23)
completed_at_after_unlock         ✗ (pre-unlock: 2026-06-23)
idempotency_key_includes_attempt  ✗ (no attempt_id)
```

## What must happen before actual render
1. Add `canary_attempt_id` to `ops/ACTUAL_RENDER_UNLOCK.json`
2. Re-submit with idempotency key that includes this attempt_id
3. Verify NEW provider_job row (not the old one)
4. Verify NEW generated_media artifact
5. Run freshness eval → must return `PASS_FRESH_CANARY`
6. Then proceed to post-render comparison (S06_T004)

## No actual render was executed during this fix
HIGGSFIELD_DRY_RUN=1 throughout. No provider calls.
