"""Tests: PST-06 — Downstream production storyboard adoption."""
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from produce import STEPS, step_compile_media_plan


# ─── Fixtures ──────────────────────────────────────────────────────────────

def _minimal_storyboard(production=False):
    sb = {
        "schema_version": "2.0",
        "project_id": "test_proj",
        "video_type": "flagship",
        "beats": [
            {
                "beat_id": "s1_b1",
                "segment_id": "s1",
                "shot_type": "b_roll_specific",
                "duration_sec": 5,
                "prompt": "cityscape",
                "narration": "Hello world",
                "source_beat_id": "s1_b1_orig",
            }
        ],
    }
    if production:
        sb["reconciled_from"] = "storyboard.json"
    return sb


@pytest.fixture
def project_with_both(tmp_path):
    """Project dir with both creative and production storyboard."""
    creative = _minimal_storyboard(production=False)
    creative["beats"][0]["beat_id"] = "creative_b1"
    (tmp_path / "storyboard.json").write_text(json.dumps(creative))

    prod = _minimal_storyboard(production=True)
    prod["beats"][0]["beat_id"] = "prod_b1"
    (tmp_path / "production_storyboard.json").write_text(json.dumps(prod))

    # Continuous narration for slice logic
    (tmp_path / "narration").mkdir()
    (tmp_path / "narration" / "continuous.mp3").write_bytes(b"\x00" * 100)
    return tmp_path


@pytest.fixture
def project_creative_only(tmp_path):
    """Project dir with only creative storyboard."""
    creative = _minimal_storyboard(production=False)
    creative["beats"][0]["beat_id"] = "creative_b1"
    (tmp_path / "storyboard.json").write_text(json.dumps(creative))
    (tmp_path / "narration").mkdir()
    (tmp_path / "narration" / "continuous.mp3").write_bytes(b"\x00" * 100)
    return tmp_path


# ─── Tests ─────────────────────────────────────────────────────────────────

def test_compile_uses_production_storyboard_when_present(project_with_both):
    """When production_storyboard.json exists, compile uses it instead of creative."""
    with patch("compile_media_prompts.compile_plan") as mock_compile, \
         patch("compile_media_prompts.load_constraints", return_value={}), \
         patch("compile_media_prompts.load_routing", return_value={}), \
         patch("gates.record_gate"):
        mock_compile.return_value = (
            {"beats": [], "totals": {"est_usd": 0, "est_tokens": 0}}, []
        )
        step_compile_media_plan(project_with_both, {})
        called_sb = mock_compile.call_args[0][0]
        assert called_sb["beats"][0]["beat_id"] == "prod_b1"


def test_compile_requires_production_storyboard_strict(project_creative_only):
    """When only storyboard.json is present, compile raises RuntimeError (no fallback)."""
    import pytest
    with pytest.raises(RuntimeError, match="production_storyboard.json"):
        step_compile_media_plan(project_creative_only, {})


def test_production_storyboard_step_in_steps_list():
    """production_storyboard appears between build_timing_map and compliance_check."""
    assert "production_storyboard" in STEPS
    idx = STEPS.index("production_storyboard")
    assert STEPS[idx - 1] == "build_timing_map"
    assert STEPS[idx + 1] == "compliance_check"


def test_production_storyboard_before_compile():
    """Verify ordering: tts < build_timing_map < production_storyboard < compliance_check < compile_media_plan."""
    order = ["tts", "build_timing_map", "production_storyboard", "compliance_check", "compile_media_plan"]
    indices = [STEPS.index(s) for s in order]
    assert indices == sorted(indices), f"Steps out of order: {list(zip(order, indices))}"
