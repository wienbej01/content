# Controlled Canary Render Plan (Revised — S06_FIX_T003)

## Purpose
One hero-lipsync canary render unit only. Must produce a GENUINELY NEW artifact after unlock — idempotent reuse does not satisfy the gate.

## Target
- **Production**: prod_2f9bb58c0508465fb51ac6b4578bba92
- **Canary unit**: S000 (render_f91a245c14b341b6a7975e2a8d5716fc) — first hero lipsync segment at 0-4572ms
- **Source slice SHA256**: 8e72630b726ab148586eb8445052be7c272efbee75e42f5c852a4a5bb6e8416b

## Freshness requirements
To pass the actual canary render gate, ALL of the following must be true:

```
1. Unlock file at ops/ACTUAL_RENDER_UNLOCK.json includes a unique canary_attempt_id
2. The idempotency key submitted to the provider includes this canary_attempt_id
3. A NEW provider_job row is created (not a reuse of an old one)
4. provider_job.submitted_at >= unlock_created_at
5. provider_job.completed_at >= unlock_created_at (if completed)
6. A NEW generated_media artifact is registered after unlock
7. artifact.created_at >= unlock_created_at
8. artifact.provider_job_id equals the new provider_job.id
9. Diagnostic provider audio is extracted from the new video
10. source_slice_sha256 is compared against the provider request audio hash
11. Post-render evals (lipsync, comparison) run against the new artifact
```

## Freshness gate eval
```bash
python3 scripts/evals/eval_canary_freshness.py --render-unit-id <ru_id> --out <json>
```

## If idempotent reuse is detected
```
IDEMPOTENCY_REUSE_CHECK_PASS
ACTUAL_CANARY_RENDER_NOT_EXECUTED
decision = BLOCKED_NEEDS_FRESH_CANARY_RENDER
```

## Pre-render checklist (S06_T002 — dry-run audit)
1. Verify source_slice_sha256 is populated for S000
2. Add canary_attempt_id to unlock file
3. Audit provider request payload (hash match, audio_path correct)
4. Ensure idempotency key includes canary_attempt_id
5. Confirm HIGGSFIELD_DRY_RUN=0 only after all checks pass

## Render steps (corrected)
1. Update `ops/ACTUAL_RENDER_UNLOCK.json` with canary_attempt_id
2. Submit one S000 canary render via `submit_provider_job` with dry-run=0
3. Wait for job completion (provider polling)
4. Run freshness eval: `python3 scripts/evals/eval_canary_freshness.py`
5. If freshness fails → BLOCKED_NEEDS_FRESH_CANARY_RENDER

## Pass/fail criteria
| Metric | Pass | Fail |
|--------|------|------|
| Fresh provider_job row | new row created | reused old row |
| submitted_at >= unlock_ts | >= | < |
| completed_at >= unlock_ts | >= | < |
| New generated_media artifact | created after unlock | pre-unlock or missing |
| Diagnostic audio extracted | exists | missing |
| Source slice SHA comparison | match | mismatch |
| Canary attempt ID in idempotency key | present | absent |

## Rollback plan
If canary fails any freshness or quality criterion:
1. Do NOT proceed to full production rerender
2. Analyze failure, update evals, request human review
