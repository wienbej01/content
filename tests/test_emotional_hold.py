#!/usr/bin/env python3
"""TKT-602 tests for emotional-beat hold extension in assembler."""
from scripts.edl import EMOTIONAL_HOLD_FUNCTIONS, compute_emotional_holds


def test_emotional_hold_functions():
    """EMOTIONAL_HOLD_FUNCTIONS contains expected narrative functions."""
    assert "thesis_close" in EMOTIONAL_HOLD_FUNCTIONS
    assert "philosophical_close" in EMOTIONAL_HOLD_FUNCTIONS
    assert "final_motivation" in EMOTIONAL_HOLD_FUNCTIONS


def test_compute_holds_basic():
    """compute_emotional_holds returns holds for emotional beats."""
    storyboard = {
        "beats": [
            {"beat_id": "B001", "narrative_function": "thesis_close"},
            {"beat_id": "B002", "narrative_function": "hook"},
        ]
    }
    holds = compute_emotional_holds(storyboard, hold_sec=1.2)
    assert "B001" in holds
    assert "B002" not in holds
    assert holds["B001"] == 1.2


def test_compute_holds_custom_duration():
    """Hold duration is configurable."""
    storyboard = {
        "beats": [{"beat_id": "B003", "narrative_function": "philosophical_close"}],
    }
    holds = compute_emotional_holds(storyboard, hold_sec=0.5)
    assert holds["B003"] == 0.5
