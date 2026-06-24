# S06_T002 Dry-Run Provider Request Audit

## Purpose

Audit exactly what provider request would be sent, without sending it.

## Required behavior

```text
- HIGGSFIELD_DRY_RUN=1
- build request payload
- verify audio_path points to source slice
- verify audio hash matches ledger
- verify image/reference path exists
- verify model supports audio
- verify idempotency key stable
- verify prompt is text-risk clean
```

## Required output

```json
{
  "dry_run": true,
  "would_submit_provider_job": false,
  "payload_hash": "",
  "audio_sha256_verified": true,
  "prompt_policy_ok": true,
  "issues": []
}
```

## Pass gates

PASS only if dry-run payload is clean and no external job submitted.
