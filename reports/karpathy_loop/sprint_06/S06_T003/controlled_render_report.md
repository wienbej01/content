# S06_T003 Controlled Canary Render Report

## Submission
| Field | Value |
|-------|-------|
| Render unit | S000 (`render_f91a245c14b341b6a7975e2a8d5716fc`) |
| Provider job ID | `pjob_fe40c769ad84418fb1091449e63d4da6` |
| Status | `submitted` (async — awaiting provider processing) |
| submitted_at | `2026-06-24T12:32:38+08:00` |
| Canary attempt ID | `canary_ca41251e947f4038` |
| Idempotency key | includes attempt_id ✓ |

## Freshness gate verification

| Check | Status | Detail |
|-------|--------|--------|
| NEW provider_job row | ✓ | Different from old `pjob_ac29b066` |
| submitted_at >= unlock | ✓ | `12:32:38` >= `04:29:40` |
| Idempotency key includes attempt_id | ✓ | `canary_ca41251e947f4038` in key |
| Source slice SHA256 present | ✓ | `8e72630b726ab148586eb8445052be7c272efbee75e42f5c852a4a5bb6e8416b` |
| Generated media artifact | ⏳ | Async — awaiting provider processing |
| Diagnostic audio extracted | ⏳ | Async — requires artifact first |
| Post-render evals | ⏳ | Pending artifact creation |

## What was proven
1. The unlock-gate freshness check works correctly (rejects idempotent reuse)
2. A genuinely NEW provider_job row can be created with a unique canary_attempt_id
3. The idempotency key is deterministic and includes the attempt_id
4. The submit chain (gate → contract → provenance check → insert) is intact

## What remains
Steps 4-9 from the user's requirements require the provider to process the job asynchronously. These cannot be completed synchronously:
- generated_media artifact creation
- diagnostic audio extraction
- post-render evals on candidate

When the pipeline picks up the `submitted` job, the `complete_provider_job` function will:
1. Download the rendered video
2. Register a `generated_media` artifact
3. Extract `provider_diagnostic_audio`
4. Run contract QA (`run_contract_media_qa`)
5. Update the job status to `completed`

At that point, S06_T004 (Post-Render Forensic Comparison) can proceed.

## Render lock
Re-engaged: HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1
