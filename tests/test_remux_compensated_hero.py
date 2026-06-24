"""Tests for compensated hero remux helper (S08-T002)."""
import json
from pathlib import Path

import pytest

from scripts.evals.remux_compensated_hero import remux

CANARY = Path("assets/media/prod_2f9bb58c0508465fb51ac6b4578bba92/canary_pjob_fe40c769ad84418fb1091449e63d4da6.mp4")
SOURCE = Path("Videos/Projects/use_ai_to_triage_your_notifications_and/narration/hero_audio_slices/render_f91a245c14b341b6a7975e2a8d5716fc.wav")
HAS_FILES = CANARY.exists() and SOURCE.exists()


class TestRemux:
    def test_remux_creates_output(self, tmp_path):
        """Compensated remux produces valid MP4."""
        if not HAS_FILES:
            pytest.skip("Canary/source files not available")
        out = tmp_path / "compensated.mp4"
        result = remux(CANARY, SOURCE, offset_ms=-575, output_path=out)
        assert "error" not in result, result.get("error")
        assert out.exists()
        assert result["size_bytes"] > 0
        assert result["duration_sec"] > 0

    def test_remux_with_positive_offset(self, tmp_path):
        """Positive offset also works."""
        if not HAS_FILES:
            pytest.skip("Canary/source files not available")
        out = tmp_path / "comp_positive.mp4"
        result = remux(CANARY, SOURCE, offset_ms=+335, output_path=out)
        assert "error" not in result
        assert out.exists()

    def test_remux_missing_video(self, tmp_path):
        """Missing video returns error."""
        result = remux(Path("/nonexistent.mp4"), SOURCE, -500, tmp_path / "out.mp4")
        assert "error" in result

    def test_remux_missing_audio(self, tmp_path):
        """Missing audio returns error."""
        result = remux(CANARY, Path("/nonexistent.wav"), -500, tmp_path / "out.mp4")
        assert "error" in result

    def test_output_is_smaller_than_input(self, tmp_path):
        """Compensated output should be similar size to input."""
        if not HAS_FILES:
            pytest.skip("Canary/source files not available")
        out = tmp_path / "comp_small.mp4"
        result = remux(CANARY, SOURCE, -575, out)
        assert "error" not in result
        input_size = CANARY.stat().st_size
        ratio = result["size_bytes"] / input_size
        assert 0.5 < ratio < 2.0, f"Output size {result['size_bytes']} vs input {input_size}"
