# TICKET-03: Unit Tests for Submit Resilience

**Priority:** HIGH
**Type:** Test coverage
**Estimated effort:** Medium (1 new test file, ~150 lines)
**Sprint:** SUBMIT-RETRY
**Dependency:** TICKET-02 must be Evaluator-APPROVED first

---

## Problem

TICKET-01 and TICKET-02 add retry logic and non-crashing failure handling to the submit path. These changes need test coverage to ensure:
1. Retry logic works correctly (retries network errors, doesn't retry permanent errors)
2. Backoff timing is correct (2s between attempts)
3. Non-crashing path is exercised
4. Existing behavior for successful submissions and permanent failures is preserved

## Objective

Write `tests/unit/test_submit_retry.py` covering:
1. `_is_submit_error_retryable` — classify connection vs application errors
2. `submit()` retry loop — 3 attempts, 2s backoff, early exit on permanent errors
3. `submit()` dry-run path — unchanged (no subprocess call)
4. Guard checks — unchanged (asset_type eligibility, prompt text risks)

## Specification

### File to create

- `tests/unit/test_submit_retry.py`

### Test classes

```python
class TestSubmitErrorClassification:
    def test_connection_error_is_retryable(self):
        assert _is_submit_error_retryable("Cannot reach") is True
        assert _is_submit_error_retryable("Connection refused") is True
        assert _is_submit_error_retryable("timeout after 30s") is True

    def test_dns_error_is_retryable(self):
        assert _is_submit_error_retryable("name resolution failed") is True

    def test_invalid_param_is_permanent(self):
        assert _is_submit_error_retryable("invalid parameter: duration") is False

    def test_unauthorized_is_permanent(self):
        assert _is_submit_error_retryable("401 Unauthorized") is False

    def test_moderation_is_permanent(self):
        assert _is_submit_error_retryable("content policy rejected") is False

    def test_unknown_is_not_retryable(self):
        assert _is_submit_error_retryable("") is False
        assert _is_submit_error_retryable("unknown error") is False


class TestSubmitRetryLoop:
    def test_retries_on_connection_error(self):
        """Transient error retries 3 times, succeeds on 3rd attempt."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = {"asset_type": "generated_video", "model": "seedance_2_0",
                   "prompt": "test prompt", "duration_sec": 5}

        with patch("subprocess.run") as mock_run:
            # Fail twice, succeed on 3rd
            mock_run.side_effect = [
                # Attempt 1: network error
                MagicMock(returncode=1, stdout="", stderr="Cannot reach endpoint"),
                # Attempt 2: same error
                MagicMock(returncode=1, stdout="", stderr="Cannot reach endpoint"),
                # Attempt 3: success
                MagicMock(returncode=0, stdout='{"id": "job_123"}', stderr=""),
            ]
            with patch("time.sleep", return_value=None):  # Don't actually sleep
                result = adapter.submit(payload, "key_123")

        assert mock_run.call_count == 3
        assert result["external_job_id"] == "job_123"
        assert result["attempts"] == 3

    def test_no_retry_on_permanent_error(self):
        """Permanent error raises immediately (1 attempt)."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = {"asset_type": "generated_video", "model": "seedance_2_0",
                   "prompt": "test prompt", "duration_sec": 5}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="invalid parameter: duration"
            )
            with pytest.raises(ProviderAdapterError, match="invalid parameter"):
                with patch("time.sleep", return_value=None):
                    adapter.submit(payload, "key_123")

        assert mock_run.call_count == 1  # No retries

    def test_success_on_first_attempt(self):
        """Successful submission returns on first attempt."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = {"asset_type": "generated_video", "model": "seedance_2_0",
                   "prompt": "test prompt", "duration_sec": 5}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"id": "job_456"}', stderr=""
            )
            result = adapter.submit(payload, "key_123")

        assert mock_run.call_count == 1
        assert result["external_job_id"] == "job_456"
        assert result["attempts"] == 1

    def test_exhausts_retries_raises(self):
        """After 3 failed retries, raises ProviderAdapterError."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = {"asset_type": "generated_video", "model": "seedance_2_0",
                   "prompt": "test prompt", "duration_sec": 5}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Cannot reach endpoint"
            )
            with patch("time.sleep", return_value=None):
                with pytest.raises(ProviderAdapterError, match="3 attempt"):
                    adapter.submit(payload, "key_123")

        assert mock_run.call_count == 3


class TestSubmitGuardChecks:
    def test_local_graphic_blocked(self):
        """Adapter still blocks forbidden asset types."""
        ...

    def test_text_risk_prompt_blocked(self):
        """Adapter still blocks text-risk prompts."""
        ...


class TestSubmitDryRun:
    def test_dry_run_no_subprocess(self):
        """Dry-run mode returns args without calling subprocess."""
        ...
```

### What NOT to test

- Do NOT test `invoke_generate_media` (that's integration-level, tested indirectly by `test_e2e_db_native_no_paid_provider.py`)
- Do NOT test Higgsfield CLI itself (external dependency)
- Do NOT test the repair loop (already covered by `test_repair_loop_db.py`)

## Acceptance Criteria

- [ ] `_is_submit_error_retryable` correctly classifies 8+ error patterns
- [ ] Retry loop: 3 attempts, 2s backoff, success on retry, raise on exhaustion
- [ ] Permanent errors: 1 attempt, immediate raise
- [ ] Guard checks unchanged (local_graphic blocked, text risk blocked)
- [ ] Dry-run path unchanged
- [ ] Full regression: 0 failures

## Loop Process

### Phase 1: Engineer
1. Read `_CONTEXT.md`, TICKET-01 + TICKET-02 (both APPROVED), and this ticket.
2. Write `test_submit_retry.py`. Run it first (fails pre-fix, passes post-fix).
3. Run `pytest tests/unit tests/integration tests/regression -v` — 0 failures.
4. Append `## Engineer Report`.

### Phase 2: Auditor
1. Read the Engineer Report. Review test file.
2. Verify: all test cases listed above are present, mocks don't call real CLI, edge cases covered.
3. Append `## Auditor Report` with verdict.

### Phase 3: Evaluator
1. Read both reports. Run full suite independently.
2. Verify: test file runs, no regressions in existing tests.
3. Append `## Evaluator Report` with verdict: APPROVED / REJECTED.

---

## Engineer Report

*(To be filled by the Engineer after implementation)*

## Auditor Report

*(To be filled by the Auditor after review)*

## Evaluator Report

*(To be filled by the Evaluator after validation)*
