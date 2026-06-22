# Sprint Context: Provider Submit Resilience — Retry + Backoff

**Created:** 2026-06-22
**Sprint ID:** SUBMIT-RETRY
**Trigger:** `generate_media` submission failure on `prod_59b622f838254187924b2fc58a0905ac`
**Status:** PLANNED (not yet started)
**Dependency:** S10-C08 (poll failure classification), S10-C09 (repair loop provider job recovery)

---

## Incident Summary

```
✗ Stage 'generate_media' failed:
  Provider job pjob_e6c5e46f submit failed:
  Higgsfield submit failed: Error: Cannot reach
  https://fnf.higgsfield.ai/agents/uploads?type=audio.
```

The Higgsfield CLI couldn't reach its audio upload endpoint during job submission. The `submit` method treated this as a fatal error, crashing the stage. The repair loop (S10-C09) can resubmit failed provider jobs, but it never runs because `generate_media` crashes first.

## Forensic Root Cause (4-Why)

### Why 1: Why did `generate_media` fail?
`adapter.submit()` called `subprocess.run(["higgsfield", "generate", "create", ...])`. The CLI returned non-zero exit code with "Cannot reach https://fnf.higgsfield.ai/agents/uploads?type=audio". `submit()` raised `ProviderAdapterError`.

### Why 2: Why couldn't the CLI reach the endpoint?
The Higgsfield CLI needs to upload audio files (`--audio` paths) before creating a generation job. The connection to `fnf.higgsfield.ai:443` failed — either transient network blip, DNS failure, service degradation, or firewall/proxy issue. The error is a connection-level failure (not application rejection).

### Why 3: Why does a single submission failure crash the entire stage?
The error handler at `produce_db.py:1445-1447` treats ALL provider errors as terminal — `fail_provider_job` + `raise RuntimeError`. Unlike the poll path (S10-C08), the submit path has no retryability classification. The next `resume` hits the same failure. The repair stage (after `qa_media`) never gets to run.

### Why 4 (bedrock): Why is the submission layer atomic?
`generate_media` was designed as a single-invocation stage (submit all, poll all, exit). The wave-size/concurrency changes moved it to multi-invocation, but the error handling was never retrofitted. The assumption was "if CLI fails, crash and let human fix it" — wrong for distributed systems with intermittent provider APIs.

**Three architectural gaps:**

| Gap | Impact |
|-----|--------|
| No submit retry | 10s network blip kills the stage |
| No retryability classification at submit | Same error class as poll, but no `_classify_retryable` path |
| Submit failure crashes all waves | If job 1 of 3 fails, jobs 2 and 3 never get submitted |

---

## Sprint Goal

Make the `generate_media` stage resilient to transient provider submission failures: retry with backoff, classify failures, skip retryable failures without crashing, and let the repair loop resubmit later.

## Architecture

```
invoke_generate_media
│
├─ for each ordered unit:
│   ├─ adapter.submit_with_retry(request_payload, max_retries=3, backoff=2s)
│   │   └─ tries submit, catches connection errors → retry
│   │   └─ permanent errors → raises immediately
│   │
│   ├─ if submit failed (exhausted retries):
│   │   ├─ _classify_retryable(error) → True → fail_provider_job, continue loop
│   │   └─ _classify_retryable(error) → False → raise RuntimeError (permanent)
│   │
│   └─ if submit succeeded → normal flow
│
└─ after loop: if ALL submissions were retryable failures → raise "ALL_SUBMISSIONS_FAILED_RETRYABLE"
```

## Ticket Structure

| Ticket | Title | Priority | Scope |
|--------|-------|----------|-------|
| `TICKET-01` | Adapter submit retry with backoff + error classification | CRITICAL | `paid_adapters.py` |
| `TICKET-02` | Non-crashing retryable failures in generate_media | CRITICAL | `produce_db.py` |
| `TICKET-03` | Unit tests for submit resilience | HIGH | New test file |

**Dependency order:** TICKET-01 → TICKET-02 → TICKET-03

---

## Loop Process (Engineer → Auditor → Evaluator)

Each ticket is executed through a strict 3-role loop:

| Role | Responsibility | Cannot Do |
|------|----------------|-----------|
| **Engineer** | Implement per ticket spec. Write/update tests. Run suite. Report. | Approve own work. Weaken assertions. |
| **Auditor** | Review diff against spec + root cause. Check minimal-change, invariants. Verdict: PASS / PASS_WITH_FINDINGS / FAIL. | Modify code. Approve. |
| **Evaluator** | Re-run full suite independently. Verify root cause addressed. Verdict: APPROVED / REJECTED. | Modify code. Skip full suite. |

### Rules
1. One ticket per session. TICKET-01 must be APPROVED before TICKET-02 starts.
2. Reproduce before fixing. Write test that FAILS before fix, PASSES after.
3. Full regression: `pytest tests/unit tests/integration tests/regression -v` — 0 failures.
4. Minimal-change policy: only files listed in ticket spec are modified.
5. Each role appends report to ticket file in `## <Role> Report` section.

---

## Files in This Sprint

```
docs/plans/submit_retry_sprint/
├── _CONTEXT.md                 ← this file
├── TICKET-01-submit-retry.md   ← adapter retry + backoff
├── TICKET-02-submit-noncrash.md ← non-crashing retryable failures
└── TICKET-03-submit-tests.md   ← unit tests
```

## Key Source Files

| File | Relevance |
|------|-----------|
| `scripts/paid_adapters.py` (lines 169-171, 217-219) | `submit()` — CLI calls, error handling |
| `scripts/produce_db.py` (lines 1419-1447) | `invoke_generate_media` — submit loop + error handler |
| `scripts/media_service.py` (lines 426-447) | `fail_provider_job` — marks job/unit failed |
| `scripts/paid_adapters.py` (lines 1-33) | `_classify_retryable()` — existing retryability classifier |

## Acceptance Criteria (Sprint-Level)

- [ ] Transient network error (Cannot reach, timeout) → 3 retries with 2s backoff → success or skip
- [ ] Permanent error (invalid params, auth) → raise immediately (no retry)
- [ ] Retryable submit failure → fail_provider_job, continue submit loop
- [ ] Permanent submit failure → raise RuntimeError as before
- [ ] Full regression: 0 failures
- [ ] Only `paid_adapters.py`, `produce_db.py`, + test file modified
