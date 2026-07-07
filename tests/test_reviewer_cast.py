#!/usr/bin/env python3
"""TKT-701 tests for reviewer_cast config + multi-model routing."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from review import _load_reviewer_cast, _get_persona_model_profile, REVIEWER_CAST


def test_load_reviewer_cast():
    """reviewer_cast config loads from llm_models.yaml."""
    cast = _load_reviewer_cast()
    assert isinstance(cast, dict)
    assert "audience" in cast


def test_persona_mapping():
    """Each persona maps to a valid model profile."""
    profiles = set()
    for name in ["audience", "filmmaker", "visual_director", "brand_voice", "technical"]:
        profile = _get_persona_model_profile(name)
        assert isinstance(profile, str)
        assert len(profile) > 0
        profiles.add(profile)
    # At least 2 distinct profiles (creative + utility)
    assert len(profiles) >= 2


def test_audience_uses_creative_profile():
    """Audience persona routes through sonnet_creative (highest weight, veto)."""
    profile = _get_persona_model_profile("audience")
    assert profile == "sonnet_creative"


def test_default_fallback():
    """Unknown persona falls back to auto_utility."""
    profile = _get_persona_model_profile("unknown_persona")
    assert profile == "auto_utility"


def test_weight_preserved():
    """Aggregation weights from SCRIPT_CAST and STORYBOARD_CAST are unchanged."""
    from review import SCRIPT_CAST, STORYBOARD_CAST
    assert SCRIPT_CAST["audience"] == 2.0
    assert SCRIPT_CAST["brand_voice"] == 1.2
    assert STORYBOARD_CAST["audience"] == 2.0
    assert STORYBOARD_CAST["filmmaker"] == 1.5
    assert STORYBOARD_CAST["visual_director"] == 1.5
    assert STORYBOARD_CAST["technical"] == 0.8
