# S06_FIX_T003 Canary Must Generate New Artifact

## Purpose
Correct S06_T003 so that the actual canary render gate requires an unequivocally *new* provider job and generated media artifact, not an idempotent reuse.

## Why the prior attempt failed
- Idempotency key matched an existing provider job
- No new provider_job row was created
- No new generated_media artifact was registered
- Post-render evals ran against the old (pre-unlock) artifact
- The gate did not verify `provider_job.submitted_at >= unlock_created_at`

## Required changes

### 1. Unlock file must include `canary_attempt_id`
The unlock file at `ops/ACTUAL_RENDER_UNLOCK.json` must include a unique `canary_attempt_id` (e.g., UUID) that has never been used before. This attempt_id is incorporated into the idempotency key to guarantee a fresh submission.

### 2. Freshness gate (S06_T003 only passes when all true)
```text
- a new provider_job row is created after the unlock file timestamp
- provider_job.submitted_at >= unlock_created_at (or submitted_at)
- provider_job.completed_at >= unlock_created_at, if completed
- a new generated_media artifact is registered after unlock
- artifact.created_at >= unlock_created_at
- artifact.provider_job_id equals the new provider_job.id
- the provider job idempotency key includes the canary_attempt_id
- the canary_attempt_id has not been used before
- diagnostic provider audio is extracted, or the report explicitly fails if missing
- source_slice_sha256 is compared against the provider request audio hash
- post-render evals run against the new artifact
```

### 3. Idempotency classification
If the provider job already existed before the unlock:
```text
IDEMPOTENCY_REUSE_CHECK_PASS
ACTUAL_CANARY_RENDER_NOT_EXECUTED
decision = BLOCKED_NEEDS_FRESH_CANARY_RENDER
```

### 4. Do not proceed to S06_T004
No post-render comparison until there is a fresh candidate artifact generated after unlock.

### 5. Scope limit
- one render unit only (S000)
- max_provider_jobs=1
- no full production rerender
- no bulk regeneration

### 6. Render lock during fix
HIGGSFIELD_DRY_RUN=1 while fixing the gate logic. No actual render calls.
