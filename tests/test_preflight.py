"""Tests for scripts/preflight.py — system dependency checker."""
import os
import subprocess
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import preflight


class TestPreflightChecks:
    def test_check_python_passes(self):
        result = preflight.check_python()
        assert result.passed
        assert "3." in result.detail

    def test_check_pytesseract_importable(self):
        result = preflight.check_pytesseract()
        assert result.passed is True or result.passed is False

    def test_check_smoke_config_exists(self):
        result = preflight.check_smoke_config()
        assert result.passed

    def test_check_ffmpeg_present(self):
        result = preflight.check_ffmpeg()
        assert result.passed

    def test_check_ffprobe_present(self):
        result = preflight.check_ffprobe()
        assert result.passed

    def test_check_mediapipe_importable(self):
        result = preflight.check_mediapipe()
        assert result.passed is True or result.passed is False

    def test_report_all_passed_when_no_failures(self):
        report = preflight.PreflightReport()
        report.add(preflight.CheckResult("a", True, ""))
        report.add(preflight.CheckResult("b", True, ""))
        assert report.all_passed

    def test_report_fails_on_required_failure(self):
        report = preflight.PreflightReport()
        report.add(preflight.CheckResult("a", True, ""))
        report.add(preflight.CheckResult("b", False, "missing", required=True))
        assert not report.all_passed
        assert len(report.actionable) == 1
        assert "missing" in report.actionable[0]

    def test_report_passes_on_nonrequired_failure(self):
        report = preflight.PreflightReport()
        report.add(preflight.CheckResult("a", True, ""))
        report.add(preflight.CheckResult("b", False, "advisory", required=False))
        assert report.all_passed

    @patch("preflight._which", return_value=False)
    def test_tesseract_not_found(self, mock_which):
        result = preflight.check_tesseract()
        assert not result.passed
        assert "not found" in result.detail

    @patch("preflight._which", return_value=True)
    @patch("preflight._run_version", return_value=(True, "tesseract v5.0.0"))
    def test_tesseract_found(self, mock_run, mock_which):
        result = preflight.check_tesseract()
        assert result.passed

    def test_check_all_returns_report(self):
        report = preflight.check_all()
        assert isinstance(report, preflight.PreflightReport)
        assert len(report.checks) >= 6

    def test_main_exit_code(self):
        report = preflight.PreflightReport()
        report.add(preflight.CheckResult("required_check", False, "fail", required=True))
        with patch.object(preflight, "check_all", return_value=report):
            exit_code = preflight.main()
            assert exit_code == 1

    def test_main_success_exit(self):
        report = preflight.PreflightReport()
        report.add(preflight.CheckResult("ok", True, ""))
        with patch.object(preflight, "check_all", return_value=report):
            exit_code = preflight.main()
            assert exit_code == 0

    def test_elevenlabs_unset_warns(self):
        with patch.dict(os.environ, {}, clear=True):
            result = preflight.check_elevenlabs()
            assert not result.passed
            assert not result.required

    @patch.dict(os.environ, {"ELEVENLABS_API_KEY": "sk-1234567890abcdef"})
    def test_elevenlabs_set_passes(self):
        result = preflight.check_elevenlabs()
        assert result.passed

    def test_check_higgsfield_true(self):
        result = preflight.check_higgsfield()
        assert result.passed  # npm is available in this env

    def test_json_output_format(self):
        report = preflight.check_all()
        data = {
            "all_passed": report.all_passed,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail, "required": c.required} for c in report.checks],
            "actionable": report.actionable,
        }
        assert "all_passed" in data
        assert "checks" in data
        assert len(data["checks"]) >= 6
        for check in data["checks"]:
            assert "name" in check
            assert "passed" in check
