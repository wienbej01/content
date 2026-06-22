# TICKET-01: Adapter Submit Retry with Backoff + Error Classification

**Priority:** CRITICAL
**Type:** Resilience fix
**Estimated effort:** Medium (1 file, ~40 lines)
**Sprint:** SUBMIT-RETRY
**Dependency:** None (start immediately)

---

## Problem

The `HiggsfieldSeedanceAdapter.submit()` method calls `subprocess.run(["higgsfield", "generate", "create", ...])`. When the CLI returns a non-zero exit code (e.g., "Cannot reach" endpoint), the method raises `ProviderAdapterError` immediately. There is no retry for transient network failures, and no classification of the error type.

## Objective

1. Add a **retry loop** inside `submit()`: up to 3 attempts with 2-second backoff between tries
2. Only retry on **connection-level errors** (Cannot reach, timeout, refused, resolve, 5xx)
3. Do NOT retry on **permanent errors** (invalid params, auth, content policy, not found)
4. Expose the **retryability classification** on the result so the caller can decide

## Specification

### File to modify

- `scripts/paid_adapters.py` — `HiggsfieldSeedanceAdapter.submit()` (line ~169-219)

### Change

Replace the single `subprocess.run` + error handling with a retry loop:

```python
def submit(self, payload: dict, idempotency_key: str) -> dict:
    # ... EXISTING guard checks (unchanged) ...
    # ... EXISTING args construction (unchanged) ...

    if os.environ.get("HIGGSFIELD_DRY_RUN") == "1":
        # ... EXISTING dry-run path (unchanged) ...

    last_error = None
    for attempt in range(1, 4):  # 3 attempts
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode == 0:
            # Success — extract external_job_id from output
            ext_id = _extract_external_job_id(r.stdout)
            return {
                "external_job_id": ext_id,
                "status": "submitted",
                "raw_output": r.stdout.strip(),
                "attempts": attempt,
            }
        # Classify the error
        err_text = (r.stderr or "").strip()
        retryable = _is_submit_error_retryable(err_text)
        last_error = err_text
        if not retryable:
            break  # Don't retry permanent errors
        if attempt < 3:
            import time
            time.sleep(2)  # 2s backoff

    raise ProviderAdapterError(
        f"Higgsfield submit failed after {attempt} attempt(s): {last_error[:500]}"
    )
```

### New helper: `_is_submit_error_retryable`

```python
SUBMIT_RETRYABLE_PATTERNS = [
    "cannot reach", "cannot connect", "connection refused",
    "connection reset", "timeout", "timed out",
    "temporarily unavailable", "service unavailable",
    "503", "502", "504", "429",
    "dns", "resolve", "name resolution",
    "network", "no route to host",
    "broken pipe", "connection closed",
]
SUBMIT_PERMANENT_PATTERNS = [
    "invalid", "not found", "unauthorized", "forbidden",
    "401", "403", "404",
    "content policy", "moderation", "rejected",
    "insufficient", "quota", "billing",
    "not supported", "bad request",
]


def _is_submit_error_retryable(error_text: str) -> bool:
    """Classify submit errors: retryable (network) vs permanent (application)."""
    text = error_text.lower()
    for pattern in SUBMIT_PERMANENT_PATTERNS:
        if pattern in text:
            return False
    for pattern in SUBMIT_RETRYABLE_PATTERNS:
        if pattern in text:
            return True
    return False  # Unknown errors → don't retry (safe default)
```

### New helper: `_extract_external_job_id`

```python
def _extract_external_job_id(output: str) -> Optional[str]:
    """Try to extract external_job_id from CLI stdout (JSON or table)."""
    try:
        data = json.loads(output.strip())
        return data.get("id") or data.get("job_id") or data.get("external_job_id")
    except (json.JSONDecodeError, TypeError):
        pass
    # Table format fallback: first column is typically the ID
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    if len(lines) >= 2:
        cols = re.split(r" {2,}", lines[1])
        if cols:
            return cols[0]
    return None
```

### What NOT to change

- Do NOT change the guard checks (lines 74-91) — asset_type eligibility, prompt text risks
- Do NOT change the args construction (lines 93-167) — models, modes, audio, negative_prompt
- Do NOT change the dry-run path (lines 157-168)
- Do NOT change `_classify_retryable` (used by poll) — keep separate from submit classifier

## Acceptance Criteria

- [ ] Transient error ("Cannot reach") retries 3 times with 2s backoff, succeeds on retry
- [ ] Permanent error ("invalid parameter") raises immediately (1 attempt)
- [ ] `attempts` field returned on success (counts attempts taken)
- [ ] `_is_submit_error_retryable` classifies network errors as True, app errors as False
- [ ] Existing submit behavior unchanged for successful submissions
- [ ] Dry-run path unchanged
- [ ] `test_submit_retry.py` tests pass (written in TICKET-03)

## Loop Process

### Phase 1: Engineer
1. Read `_CONTEXT.md` and this ticket.
2. Implement `submit()` retry loop + `_is_submit_error_retryable` + `_extract_external_job_id`.
3. Run `pytest tests/unit tests/integration tests/regression -v` — 0 failures.
4. Append `## Engineer Report`.

### Phase 2: Auditor
1. Read the Engineer Report. `git diff`.
2. Verify: only `paid_adapters.py` changed, guard checks unchanged, dry-run unchanged, retry count=3, backoff=2s, permanent errors not retried.
3. Append `## Auditor Report` with verdict.

### Phase 3: Evaluator
1. Read both reports. Run full suite independently.
2. Verify: transient error path retries, permanent error path doesn't.
3. Append `## Evaluator Report` with verdict: APPROVED / REJECTED.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*

## Auditor Report

*(To be filled by the Auditor after review)*

## Evaluator Report

*(To be filled by the Evaluator after validation)*
