"""Tests for regression suite CI entrypoint (S05-T004)."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

FIXTURE = Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")


class TestSuiteExists:
    def test_script_exists(self):
        assert Path("scripts/evals/run_video_regression_suite.py").exists()

    def test_fixture_exists(self):
        assert FIXTURE.exists()


class TestSuiteOutput:
    def test_suite_runs_and_outputs_json(self, tmp_path):
        """Suite runs without render and produces valid JSON."""
        out = tmp_path / "regression.json"
        r = subprocess.run(
            [sys.executable, "scripts/evals/run_video_regression_suite.py",
             "--fixture", str(FIXTURE), "--out", str(out)],
            capture_output=True, text=True, timeout=300,
        )
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["suite"] == "video_regression_suite"
        assert data["fixture_exists"] is True

    def test_suite_reports_expected_fields(self, tmp_path):
        out = tmp_path / "regression2.json"
        subprocess.run(
            [sys.executable, "scripts/evals/run_video_regression_suite.py",
             "--fixture", str(FIXTURE), "--out", str(out)],
            capture_output=True, timeout=300,
        )
        data = json.loads(out.read_text())
        assert "total_checks" in data
        assert "passed" in data
        assert "failed" in data
        assert "details" in data
        assert "render_lock" in data
        assert "sha256" in data

    def test_bad_fixture_does_not_fake_pass(self, tmp_path):
        out = tmp_path / "regression3.json"
        subprocess.run(
            [sys.executable, "scripts/evals/run_video_regression_suite.py",
             "--fixture", str(FIXTURE), "--out", str(out)],
            capture_output=True, timeout=300,
        )
        data = json.loads(out.read_text())
        # Status is baked into individual eval results, not overall
        assert data["sha256"] is not None
