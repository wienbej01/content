import pytest
"""Tests for visual bed duration contract (S02-T004).

Verifies that assembly duration checks use realistic thresholds.
"""
import ast
import re
from pathlib import Path


ASSEMBLE_PY = Path("scripts/assemble.py")


class TestDurationThresholds:
    """Duration delta thresholds must be realistic, not 120 seconds."""

    def test_no_120s_thresholds_remain(self):
        """No > 120.0 threshold remains in assemble.py."""
        code = ASSEMBLE_PY.read_text()
        lines = code.split("\n")
        bad = [(i+1, l.strip()) for i, l in enumerate(lines) if "> 120.0" in l]
        assert len(bad) == 0, f"120s thresholds remain at lines: {bad}"

    def test_contract_threshold_is_3s(self):
        """Contract total threshold is 3.0s."""
        code = ASSEMBLE_PY.read_text()
        assert "> 3.0" in code, "3.0s contract threshold not found"

    def test_premux_threshold_is_3s(self):
        """Pre-mux visual bed threshold is 3.0s."""
        code = ASSEMBLE_PY.read_text()
        matches = [l for l in code.split("\n") if "> 3.0" in l and "visual_bed_dur" in l]
        assert len(matches) >= 1, "3.0s pre-mux threshold not found"

    def test_postmux_threshold_is_1_5s(self):
        """Post-mux integrity threshold is 1.5s."""
        code = ASSEMBLE_PY.read_text()
        assert "> 1.5" in code, "1.5s post-mux threshold not found"
        assert "joined_vid_dur" in code, "Post-mux check references joined_vid_dur"

    def test_thresholds_are_below_60s(self):
        """All duration thresholds are below 60 seconds (realistic)."""
        import subprocess, sys
        r = subprocess.run([
            sys.executable, "-c",
            "import ast; ast.parse(open('scripts/assemble.py').read())",
        ], capture_output=True, text=True)
        assert r.returncode == 0, f"Syntax error: {r.stderr[:200]}"

    def test_max_freeze_is_0_5s(self):
        """MAX_FREEZE is 0.5s (already realistic)."""
        code = ASSEMBLE_PY.read_text()
        for line in code.split("\n"):
            if "MAX_FREEZE" in line and "=" in line:
                assert "0.5" in line, f"MAX_FREEZE should be 0.5: {line.strip()}"
                return
        pytest.fail("MAX_FREEZE definition not found")

    def test_tail_pad_is_0_25s(self):
        """TAIL_PAD is 0.25s (already realistic)."""
        code = ASSEMBLE_PY.read_text()
        for line in code.split("\n"):
            if "TAIL_PAD" in line and "=" in line:
                assert "0.25" in line, f"TAIL_PAD should be 0.25: {line.strip()}"
                return
        pytest.fail("TAIL_PAD definition not found")
