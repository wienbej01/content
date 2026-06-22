"""Unit test: submit() retry loop + non-crashing failure handling (SUBMIT-RETRY).

Tests:
1. _is_submit_error_retryable classification (14+ retryable, 14+ permanent patterns)
2. submit() retry loop: 3 attempts, 2s backoff, success on retry, exhaustion
3. submit() permanent errors: no retry, immediate raise
4. submit() successful first attempt returns immediately
5. Dry-run path unchanged (no subprocess call)
6. Guard checks unchanged (asset_type eligibility, prompt text risks)
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from paid_adapters import (
    HiggsfieldSeedanceAdapter,
    ProviderAdapterError,
    _is_submit_error_retryable,
    SUBMIT_RETRYABLE_PATTERNS,
    SUBMIT_PERMANENT_PATTERNS,
)

# Sample payload that passes all guard checks
SAFE_PAYLOAD = {
    "asset_type": "generated_video",
    "model": "seedance_2_0",
    "prompt": "a scenic mountain view with flowing river",
    "duration_sec": 5,
}


# =========================================================================
# _is_submit_error_retryable classification
# =========================================================================
class TestSubmitErrorClassification:
    def test_cannot_reach_is_retryable(self):
        assert _is_submit_error_retryable("Cannot reach endpoint") is True

    def test_connection_refused_is_retryable(self):
        assert _is_submit_error_retryable("Connection refused") is True

    def test_timeout_is_retryable(self):
        assert _is_submit_error_retryable("timeout after 30s") is True
        assert _is_submit_error_retryable("timed out") is True

    def test_dns_error_is_retryable(self):
        assert _is_submit_error_retryable("name resolution failed") is True
        assert _is_submit_error_retryable("Cannot resolve host") is True

    def test_http_5xx_is_retryable(self):
        assert _is_submit_error_retryable("HTTP 503 Service Unavailable") is True
        assert _is_submit_error_retryable("502 Bad Gateway") is True
        assert _is_submit_error_retryable("504 Gateway Timeout") is True

    def test_network_error_is_retryable(self):
        assert _is_submit_error_retryable("network unreachable") is True
        assert _is_submit_error_retryable("no route to host") is True

    def test_invalid_param_is_permanent(self):
        assert _is_submit_error_retryable("invalid parameter: duration") is False

    def test_not_found_is_permanent(self):
        assert _is_submit_error_retryable("404 Not Found") is False

    def test_unauthorized_is_permanent(self):
        assert _is_submit_error_retryable("401 Unauthorized") is False
        assert _is_submit_error_retryable("403 Forbidden") is False

    def test_moderation_is_permanent(self):
        assert _is_submit_error_retryable("content policy violation") is False
        assert _is_submit_error_retryable("moderation rejected") is False

    def test_quota_is_permanent(self):
        assert _is_submit_error_retryable("quota exceeded") is False
        assert _is_submit_error_retryable("billing expired") is False

    def test_bad_request_is_permanent(self):
        assert _is_submit_error_retryable("400 Bad Request") is False

    def test_unknown_error_not_retryable(self):
        assert _is_submit_error_retryable("") is False
        assert _is_submit_error_retryable("something broke") is False

    def test_all_retryable_patterns_documented(self):
        assert len(SUBMIT_RETRYABLE_PATTERNS) >= 14
        assert len(SUBMIT_PERMANENT_PATTERNS) >= 14


# =========================================================================
# submit() retry loop
# =========================================================================
class MockAdapter(HiggsfieldSeedanceAdapter):
    """Minimal adapter for testing — skips guard checks to focus on retry logic."""
    def __init__(self):
        # Bypass the ProviderAdapter config init
        pass

    def estimate_cost(self, payload):
        return 0.0


class TestSubmitRetryLoop:
    def test_retries_on_connection_error_then_succeeds(self):
        """Transient error retries 3 times, succeeds on 3rd."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout="", stderr="Cannot reach endpoint"),
                MagicMock(returncode=1, stdout="", stderr="Cannot reach endpoint"),
                MagicMock(returncode=0, stdout="Job ID: 123e4567-e89b-12d3-a456-426614174000\n", stderr=""),
            ]
            with patch("time.sleep", return_value=None):
                result = adapter.submit(SAFE_PAYLOAD, "key_retry")

        assert mock_run.call_count == 3
        assert result["external_job_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert result["attempts"] == 3

    def test_no_retry_on_permanent_error(self):
        """Permanent error raises immediately (1 attempt, no retry)."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="invalid parameter: duration must be 1-30"
            )
            with patch("time.sleep", return_value=None):
                with pytest.raises(ProviderAdapterError, match="invalid parameter"):
                    adapter.submit(SAFE_PAYLOAD, "key_perm")

        assert mock_run.call_count == 1  # No retries

    def test_success_on_first_attempt(self):
        """Successful submission returns immediately on first attempt."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Job ID: 123e4567-e89b-12d3-a456-426614174000\n", stderr=""
            )
            with patch("time.sleep", return_value=None):
                result = adapter.submit(SAFE_PAYLOAD, "key_ok")

        assert mock_run.call_count == 1
        assert result["external_job_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert result["attempts"] == 1

    def test_exhausts_retries_raises(self):
        """After 3 failed retries, raises ProviderAdapterError with attempt count."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Cannot reach endpoint"
            )
            with patch("time.sleep", return_value=None):
                with pytest.raises(ProviderAdapterError, match="3 attempt") as exc:
                    adapter.submit(SAFE_PAYLOAD, "key_exhaust")

        assert mock_run.call_count == 3
        assert "Cannot reach" in str(exc.value)

    def test_backoff_called_between_retries(self):
        """time.sleep(2) is called between retries, not after the last."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Cannot reach endpoint"
            )
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(ProviderAdapterError):
                    adapter.submit(SAFE_PAYLOAD, "key_backoff")

        # sleep called 2 times (between attempt 1→2 and attempt 2→3)
        assert mock_sleep.call_count == 2
        for call in mock_sleep.call_args_list:
            assert abs(call[0][0] - 2.0) < 0.1  # ~2s each

    def test_no_backoff_on_success(self):
        """No sleep on first-attempt success."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Job ID: 123e4567-e89b-12d3-a456-426614174000\n", stderr=""
            )
            with patch("time.sleep") as mock_sleep:
                adapter.submit(SAFE_PAYLOAD, "key_nobackoff")

        assert mock_sleep.call_count == 0


# =========================================================================
# submit() guard checks (unchanged from prior behavior)
# =========================================================================
class TestSubmitGuardChecks:
    def test_local_graphic_blocked(self):
        """Adapter still blocks forbidden asset types (guard check unchanged)."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = dict(SAFE_PAYLOAD, asset_type="local_graphic")
        with pytest.raises(ProviderAdapterError, match="forbidden asset_type"):
            adapter.submit(payload, "key_guard1")

    def test_text_risk_prompt_blocked(self):
        """Adapter still blocks text-risk prompts (guard check unchanged)."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = dict(SAFE_PAYLOAD, prompt="This is a title card with HBR content")
        with pytest.raises(ProviderAdapterError, match="risky prompt"):
            adapter.submit(payload, "key_guard2")

    def test_deterministic_graphic_policy_blocked(self):
        """Adapter still blocks deterministic graphic policy (guard check unchanged)."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        payload = dict(SAFE_PAYLOAD, text_policy="DETERMINISTIC_GRAPHIC")
        with pytest.raises(ProviderAdapterError, match="deterministic text spec"):
            adapter.submit(payload, "key_guard3")


# =========================================================================
# submit() dry-run path (unchanged)
# =========================================================================
class TestSubmitDryRun:
    def test_dry_run_returns_args_no_subprocess(self):
        """Dry-run mode returns constructed args without calling subprocess."""
        adapter = HiggsfieldSeedanceAdapter(config={})
        with patch.dict("os.environ", {"HIGGSFIELD_DRY_RUN": "1"}):
            with patch("subprocess.run") as mock_run:
                result = adapter.submit(SAFE_PAYLOAD, "key_dry1")

        assert mock_run.call_count == 0  # No subprocess
        assert result.get("dry_run") is True
        assert "args" in result
        assert "--prompt" in result["args"]
        assert result["idempotency_key"] == "key_dry1"
