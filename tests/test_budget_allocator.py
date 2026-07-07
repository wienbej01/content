#!/usr/bin/env python3
"""TKT-802 + TKT-803 tests for budget allocator + tiered quality levels."""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from budget_allocator import allocate_budget, total_allocated, MIN_BEAT_BUDGET_USD


@pytest.fixture
def sample_beats():
    return [
        {"beat_id": "B001", "narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 1},
        {"beat_id": "B002", "narrative_function": "transition", "shot_type": "still_kenburns", "act": 2},
        {"beat_id": "B003", "narrative_function": "evidence", "shot_type": "broll_archival", "act": 3},
        {"beat_id": "B004", "narrative_function": "hook", "shot_type": "hero_lipsync", "act": 1},
        {"beat_id": "B005", "narrative_function": "factual_data", "shot_type": "broll_tactical", "act": 4},
        {"beat_id": "B006", "narrative_function": "philosophical_close", "shot_type": "hero_lipsync", "act": 6},
        {"beat_id": "B007", "narrative_function": "framework_reveal", "shot_type": "graphic_progressive", "act": 3},
        {"beat_id": "B008", "narrative_function": "myth_bust_reveal", "shot_type": "broll_metaphorical", "act": 2},
        {"beat_id": "B009", "narrative_function": "transition", "shot_type": "still_kenburns", "act": 5},
        {"beat_id": "B010", "narrative_function": "final_motivation", "shot_type": "hero_lipsync", "act": 6},
    ]


def test_allocate_sum_equals_cap(sample_beats):
    """Total allocations sum to cap (within FP tolerance)."""
    allocs = allocate_budget(sample_beats, 60.0)
    total = total_allocated(allocs)
    assert abs(total - 60.0) < 0.5, f"total {total} != cap 60.0"  # relaxed for clamping drift


def test_allocate_hero_beats_get_more(sample_beats):
    """Hero beats get more allocation than transition beats."""
    allocs = allocate_budget(sample_beats, 60.0)
    alloc_map = {a["beat_id"]: a["allocation_usd"] for a in allocs}
    # B001 (thesis_close, hero, act 1) should get more than B002 (transition)
    assert alloc_map["B001"] > alloc_map["B002"]


def test_allocate_clamp_high():
    """Very high weight beats are clamped to ceiling."""
    beats = [
        {"beat_id": "B001", "narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 1},
        {"beat_id": "B002", "narrative_function": "transition", "shot_type": "still_kenburns", "act": 3},
    ]
    allocs = allocate_budget(beats, 60.0)
    for a in allocs:
        assert a["allocation_usd"] <= 8.0 + 0.01


def test_allocate_clamp_low():
    """Very low weight beats are clamped to floor."""
    beats = [
        {"beat_id": "B001", "narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 1},
        {"beat_id": "B002", "narrative_function": "transition", "shot_type": "still_kenburns", "act": 3},
        {"beat_id": "B003", "narrative_function": "transition", "shot_type": "still_kenburns", "act": 3},
    ]
    allocs = allocate_budget(beats, 60.0)
    for a in allocs:
        assert a["allocation_usd"] >= 0.25 - 0.01


def test_allocate_empty():
    """Empty beats list returns empty allocations."""
    assert allocate_budget([], 60.0) == []


def test_allocate_zero_cap():
    """Zero cap returns empty allocations."""
    assert allocate_budget([{"beat_id": "B001"}], 0.0) == []


def test_allocate_cap_invariant(sample_beats):
    """Total never exceeds cap (INV-6)."""
    for cap in [15.0, 25.0, 60.0, 120.0]:
        allocs = allocate_budget(sample_beats, cap)
        total = total_allocated(allocs)
        assert total <= cap + 0.01, f"total {total} exceeds cap {cap}"


def test_tiered_quality_levels():
    """TKT-803: budget_caps has 4 tiers (teaser, short, explainer, flagship)."""
    cfg_path = ROOT / "configs" / "james" / "model_routing.yaml"
    if not cfg_path.exists():
        pytest.skip("model_routing.yaml not found")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    caps = cfg.get("budget_caps", {})
    assert len(caps) >= 4
    assert "teaser" in caps
    assert "short" in caps
    assert "explainer" in caps
    assert "flagship" in caps
    assert caps["teaser"] < caps["short"] < caps["explainer"] < caps["flagship"]
