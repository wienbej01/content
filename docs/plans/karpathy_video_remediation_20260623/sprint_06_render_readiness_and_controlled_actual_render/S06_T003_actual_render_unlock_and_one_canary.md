# S06_T003 Actual Render Unlock and One Canary

## Purpose

Allow exactly one controlled actual render canary after explicit human unlock.

## Preconditions

All must be true:

```text
- S06_T001 recommends allow_one_canary
- S06_T002 dry-run audit passed
- ops/ACTUAL_RENDER_UNLOCK.json exists
- unlock file allows max_provider_jobs=1
- production_id matches target
```

## Required behavior

If unlock is missing, stop with:

```text
BLOCKED_RENDER_LOCK: ops/ACTUAL_RENDER_UNLOCK.json missing
```

If unlock exists, allow exactly one provider render for the selected canary render_unit_id.

## Required canary selection

Choose one hero-lipsync unit only. Prefer the shortest hero unit that currently has full source-slice ledger evidence.

## Required post-submit evidence

```text
provider_job_id
external_job_id
request_json
request_payload_hash
source_slice_sha256
idempotency_key
estimated_cost
```

## Pass gates

PASS if exactly one canary job is submitted and all evidence is recorded. FAIL if more than one job is submitted.
