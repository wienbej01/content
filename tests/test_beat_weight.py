#!/usr/bin/env python3
"""TKT-801 tests for beat attention-weight classifier."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from beat_weight import (
    classify_beat,
    classify_beats,
    total_weight,
    NARRATIVE_FUNCTION_WEIGHTS,
    SHOT_TYPE_MODIFIERS,
    ACT_MODIFIERS,
    MIN_WEIGHT,
    MAX_WEIGHT,
)


def test_classify_beat_thesis_close_hero_act1():
    """thesis_close + hero_lipsync + Act 1 → weight = 5.85."""
    beat = {"narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 1}
    weight = classify_beat(beat)
    assert weight == 3.0 * 1.5 * 1.3  # 5.85


def test_classify_beat_transition():
    """transition beat → low weight."""
    beat = {"narrative_function": "transition", "shot_type": "still_kenburns", "act": 3}
    weight = classify_beat(beat)
    assert weight == 0.5 * 0.5 * 1.1  # 0.275


def test_classify_beat_unknown_narrative_function():
    """Unknown narrative_function defaults to base weight 1.0."""
    beat = {"narrative_function": "unknown_fn", "shot_type": "broll_archival", "act": 3}
    weight = classify_beat(beat)
    assert weight == 1.0 * 1.0 * 1.1  # 1.1 (act mod)


def test_classify_beats_list():
    """classify_beats returns a list of weights."""
    beats = [
        {"narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 1},
        {"narrative_function": "transition", "shot_type": "still_kenburns", "act": 4},
    ]
    weights = classify_beats(beats)
    assert len(weights) == 2
    assert abs(weights[0] - 5.85) < 0.01
    assert abs(weights[1] - 0.25) < 0.01


def test_total_weight():
    """total_weight sums all beat weights."""
    beats = [
        {"narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 1},
        {"narrative_function": "transition", "shot_type": "still_kenburns", "act": 4},
    ]
    tw = total_weight(beats)
    assert abs(tw - 6.1) < 0.01


def test_determinism():
    """Same beat always produces the same weight."""
    beat = {"narrative_function": "hook", "shot_type": "hero_lipsync", "act": 6}
    weights = [classify_beat(beat) for _ in range(100)]
    assert all(w == weights[0] for w in weights)


def test_all_acts_covered():
    """ACT_MODIFIERS covers acts 1-6."""
    for act in range(1, 7):
        assert act in ACT_MODIFIERS


def test_empty_beats():
    """Empty beats list returns 0.0 total."""
    assert total_weight([]) == 0.0
    assert classify_beats([]) == []
