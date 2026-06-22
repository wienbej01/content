"""Unit test: Higgsfield poll failure classification (S10-C08).

Verifies the poll adapter classifies failures as retryable vs permanent
and extracts structured error information from both JSON and table formats.
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from paid_adapters import (
    _classify_retryable, _extract_table_error,
    RETRYABLE_PATTERNS, PERMANENT_PATTERNS,
)


class TestClassifyRetryable:
    def test_connection_timeout_is_retryable(self):
        assert _classify_retryable("connection timeout") is True
        assert _classify_retryable("timed out after 30s") is True

    def test_http_429_is_retryable(self):
        assert _classify_retryable("HTTP 429 Too Many Requests") is True
        assert _classify_retryable("rate limit exceeded") is True

    def test_server_errors_are_retryable(self):
        assert _classify_retryable("500 internal server error") is True
        assert _classify_retryable("502 Bad Gateway") is True
        assert _classify_retryable("503 Service Unavailable") is True

    def test_capacity_is_retryable(self):
        assert _classify_retryable("no capacity available") is True

    def test_moderation_is_permanent(self):
        assert _classify_retryable("content moderation flagged") is False
        assert _classify_retryable("rejected by safety filter") is False
        assert _classify_retryable("inappropriate content") is False

    def test_invalid_parameter_is_permanent(self):
        assert _classify_retryable("invalid parameter: duration") is False
        assert _classify_retryable("unsupported resolution") is False

    def test_quota_is_permanent(self):
        assert _classify_retryable("quota exceeded") is False
        assert _classify_retryable("billing disabled") is False

    def test_unknown_error_is_not_retryable(self):
        assert _classify_retryable("") is False
        assert _classify_retryable("something went wrong") is False

    def test_all_retryable_patterns_documented(self):
        assert len(RETRYABLE_PATTERNS) >= 8, "Expected at least 8 retryable patterns"
        assert len(PERMANENT_PATTERNS) >= 8, "Expected at least 8 permanent patterns"


class TestExtractTableError:
    def test_extracts_extra_columns(self):
        table = (
            "ID                                    DATE              MODEL         STATUS  URL  ERROR\n"
            "1e90a9a6-c30f-4d5a-b649-7a71a397d5ce  2026-06-22 13:16  Seedance 2.0  failed  —  content_moderation_rejected"
        )
        result = _extract_table_error(table)
        assert result == "content_moderation_rejected"

    def test_no_extra_columns_returns_empty(self):
        table = (
            "ID  DATE  MODEL  STATUS  URL\n"
            "abc  2026-06-22  seedance  failed  —"
        )
        result = _extract_table_error(table)
        assert result == ""

    def test_empty_table_returns_empty(self):
        assert _extract_table_error("") == ""
        assert _extract_table_error("ID\n") == ""


class TestPollJSONFailure:
    def test_extracts_error_from_json(self):
        """Poll extracts structured error info from JSON failed response."""
        from paid_adapters import HiggsfieldSeedanceAdapter

        adapter = HiggsfieldSeedanceAdapter(config={})
        json_resp = json.dumps({
            "state": "failed",
            "error": "content moderation rejected",
            "error_code": "MOD_001",
            "reason": "unsafe_content",
        })

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json_resp, stderr=""
            )
            result = adapter.poll("job_123")

        assert result["status"] == "failed"
        assert "MOD_001" in result["error"]
        assert "content moderation rejected" in result["error"]
        assert result["failure_reason"] == "unsafe_content"
        assert result["retryable"] is False  # moderation is permanent

    def test_transient_json_failure_is_retryable(self):
        """Poll classifies timeout from JSON as retryable."""
        from paid_adapters import HiggsfieldSeedanceAdapter

        adapter = HiggsfieldSeedanceAdapter(config={})
        json_resp = json.dumps({
            "state": "failed",
            "error": "connection timeout after 30s",
        })

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json_resp, stderr=""
            )
            result = adapter.poll("job_123")

        assert result["status"] == "failed"
        assert result["retryable"] is True

    def test_completed_json_still_works(self):
        """Poll still returns completed for JSON completed responses."""
        from paid_adapters import HiggsfieldSeedanceAdapter

        adapter = HiggsfieldSeedanceAdapter(config={})
        json_resp = json.dumps({"state": "completed"})

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json_resp, stderr=""
            )
            result = adapter.poll("job_123")

        assert result["status"] == "completed"
        assert "retryable" not in result  # Only on failed results


class TestPollTableFailure:
    def test_table_failed_with_error_column(self):
        """Poll extracts error column from table output."""
        from paid_adapters import HiggsfieldSeedanceAdapter

        adapter = HiggsfieldSeedanceAdapter(config={})
        table = (
            "ID                                    DATE              MODEL         STATUS  URL  ERROR\n"
            "1e90a9a6-c30f-4d5a-b649-7a71a397d5ce  2026-06-22 13:16  Seedance 2.0  failed  —  content_moderation"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=table, stderr=""
            )
            result = adapter.poll("job_123")

        assert result["status"] == "failed"
        assert result["failure_reason"] == "content_moderation"
        assert result["retryable"] is False

    def test_table_running_still_works(self):
        """Poll still returns running for table running responses."""
        from paid_adapters import HiggsfieldSeedanceAdapter

        adapter = HiggsfieldSeedanceAdapter(config={})
        table = (
            "ID  DATE  MODEL  STATUS  URL\n"
            "abc  2026-06-22  seedance  running  —"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=table, stderr=""
            )
            result = adapter.poll("job_123")

        assert result["status"] == "running"
        assert "retryable" not in result
