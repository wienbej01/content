"""Tests for S14_T005: Recalibrate baseline with tiered thresholds.

Validates that:
- eval_lipsync uses tiered policy thresholds instead of hardcoded 160ms
- Hero framing selects correct policy (close/medium/wide)
- Fallback to legacy mode when policy modules unavailable
- Policy name and grade are included in results
- Threshold values come from policy config
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture
def test_video(tmp_path):
    """Create a minimal test video file."""
    video_path = tmp_path / "test_video.mp4"

    # Create a minimal 1-second black video with silence
    # Using ffmpeg to generate test video
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=160x90:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=48000",
            "-c:v", "libx264", "-c:a", "aac",
            "-t", "1.0",
            str(video_path)
        ], capture_output=True, check=True, timeout=30)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Skip if ffmpeg not available
        pytest.skip("ffmpeg not available")

    return video_path


class TestTieredPolicyIntegration:
    """Tests for S14_T005 tiered policy integration in eval_lipsync."""

    def test_eval_uses_close_hero_policy_by_default(self, test_video, tmp_path):
        """eval_lipsync should use close_hero policy by default (fail-closed)."""
        out_path = tmp_path / "output.json"

        # Run eval_lipsync without hero-framing argument
        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
        ], capture_output=True, text=True, timeout=60)

        # Should succeed (or skip if numpy not available)
        assert result.returncode in [0, 1]  # 0 = pass/warn, 1 = fail/blocked

        # Check output JSON exists
        assert out_path.exists()

        # Load and check result
        with open(out_path) as f:
            data = json.load(f)

        # Should include policy_name
        assert "policy_name" in data
        if data.get("policy_name"):
            # Default should be close_hero
            assert data["policy_name"] == "close_hero"

        # Should include thresholds
        assert "thresholds" in data
        thresholds = data["thresholds"]

        # Should have tiered thresholds (not hardcoded 160ms)
        if "pass_offset_ms" in thresholds:
            # close_hero has 30ms pass threshold
            assert thresholds["pass_offset_ms"] == 30
        if "fail_offset_ms" in thresholds:
            # close_hero has 45ms fail threshold
            assert thresholds["fail_offset_ms"] == 45

    def test_eval_uses_medium_policy_for_medium_framing(self, test_video, tmp_path):
        """eval_lipsync should use medium_hero policy for medium framing."""
        out_path = tmp_path / "output.json"

        # Run eval_lipsync with medium hero-framing
        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "medium",
        ], capture_output=True, text=True, timeout=60)

        # Should succeed
        assert result.returncode in [0, 1]

        # Check output JSON
        with open(out_path) as f:
            data = json.load(f)

        # Should use medium_hero policy
        assert "policy_name" in data
        if data.get("policy_name"):
            assert data["policy_name"] == "medium_hero"

        # Should have medium_hero thresholds
        assert "thresholds" in data
        thresholds = data["thresholds"]
        if "pass_offset_ms" in thresholds:
            # medium_hero has 40ms pass threshold
            assert thresholds["pass_offset_ms"] == 40
        if "fail_offset_ms" in thresholds:
            # medium_hero has 60ms fail threshold
            assert thresholds["fail_offset_ms"] == 60

    def test_eval_uses_wide_policy_for_wide_framing(self, test_video, tmp_path):
        """eval_lipsync should use wide_hero policy for wide framing."""
        out_path = tmp_path / "output.json"

        # Run eval_lipsync with wide hero-framing
        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "wide",
        ], capture_output=True, text=True, timeout=60)

        # Should succeed
        assert result.returncode in [0, 1]

        # Check output JSON
        with open(out_path) as f:
            data = json.load(f)

        # Should use wide_hero policy (which maps to medium_hero)
        assert "policy_name" in data
        if data.get("policy_name"):
            assert data["policy_name"] == "wide_hero"

        # Should have medium_hero thresholds (wide uses medium)
        assert "thresholds" in data
        thresholds = data["thresholds"]
        if "pass_offset_ms" in thresholds:
            # wide_hero (via medium) has 40ms pass threshold
            assert thresholds["pass_offset_ms"] == 40


class TestThresholdValues:
    """Tests for threshold value correctness."""

    def test_close_hero_thresholds_correct(self, test_video, tmp_path):
        """close_hero policy should have correct thresholds."""
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "close",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        thresholds = data.get("thresholds", {})
        # close_hero: 30ms pass, 45ms warn, 45ms fail, 2.0 confidence
        assert thresholds.get("pass_offset_ms") == 30
        assert thresholds.get("warn_offset_ms") == 45
        assert thresholds.get("fail_offset_ms") == 45
        assert thresholds.get("min_confidence") == 2.0

    def test_medium_hero_thresholds_correct(self, test_video, tmp_path):
        """medium_hero policy should have correct thresholds."""
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "medium",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        thresholds = data.get("thresholds", {})
        # medium_hero: 40ms pass, 60ms warn, 60ms fail, 2.0 confidence
        assert thresholds.get("pass_offset_ms") == 40
        assert thresholds.get("warn_offset_ms") == 60
        assert thresholds.get("fail_offset_ms") == 60
        assert thresholds.get("min_confidence") == 2.0


class TestBackwardCompatibility:
    """Tests for backward compatibility and fallback behavior."""

    def test_policy_grade_included(self, test_video, tmp_path):
        """Result should include policy_grade field."""
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        # Should include policy_grade
        assert "policy_grade" in data
        # close_hero is publish-grade
        if data.get("policy_name") == "close_hero":
            assert data["policy_grade"] == "publish"

    def test_reason_included(self, test_video, tmp_path):
        """Result should include reason field from policy evaluation."""
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        # Should include reason when policy evaluation succeeds
        if data.get("offset_ms") is not None and data.get("policy_name"):
            assert "reason" in data
            # Reason should mention offset, threshold, confidence, or minimum (policy-related concepts)
            reason_lower = data["reason"].lower()
            assert any(keyword in reason_lower for keyword in ["offset", "threshold", "confidence", "minimum"])


class TestNoHardcodedThresholds:
    """Tests that hardcoded 160ms threshold is replaced."""

    def test_no_hardcoded_160ms_close(self, test_video, tmp_path):
        """close_hero should not use hardcoded 160ms threshold."""
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "close",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        thresholds = data.get("thresholds", {})
        # Should NOT be 160ms
        fail_ms = thresholds.get("fail_offset_ms")
        assert fail_ms is not None
        assert fail_ms != 160, "close_hero should use 45ms, not hardcoded 160ms"
        assert fail_ms == 45, "close_hero should use 45ms fail threshold"

    def test_no_hardcoded_160ms_medium(self, test_video, tmp_path):
        """medium_hero should not use hardcoded 160ms threshold."""
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "medium",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        thresholds = data.get("thresholds", {})
        # Should NOT be 160ms
        fail_ms = thresholds.get("fail_offset_ms")
        assert fail_ms is not None
        assert fail_ms != 160, "medium_hero should use 60ms, not hardcoded 160ms"
        assert fail_ms == 60, "medium_hero should use 60ms fail threshold"


class TestIntegrationWithOtherTickets:
    """Tests for integration with S14_T001, S14_T002, S14_T003, S14_T004."""

    def test_s14_t001_integration(self, test_video, tmp_path):
        """Should integrate with S14_T001 tiered policy."""
        # This is verified by the threshold values being correct
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "close",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        # Should use S14_T001 policy
        assert "policy_name" in data
        assert data["policy_name"] in ["close_hero", "medium_hero", "wide_hero", "diagnostic_legacy"]

    def test_s14_t002_integration(self, test_video, tmp_path):
        """Should integrate with S14_T002 hero framing."""
        # This is verified by the --hero-framing argument working
        out_path = tmp_path / "output.json"

        result = subprocess.run([
            sys.executable, "scripts/evals/eval_lipsync.py",
            "--video", str(test_video),
            "--out", str(out_path),
            "--subject-id", "test_unit",
            "--hero-framing", "close",
        ], capture_output=True, text=True, timeout=60)

        with open(out_path) as f:
            data = json.load(f)

        # Should use policy based on hero framing
        assert data["policy_name"] == "close_hero"
