#!/usr/bin/env python3
"""Deterministic budget allocation fixtures for TKT-006.

Generates two allocation strategies for testing budget optimization:
1. Flat allocation — total / beat_count per beat.
2. Weighted allocation — distribute proportionally by beat-attention-weight,
   clamped to per-beat floor and ceiling.

Both sum exactly to the configured cap (within floating-point tolerance).
"""
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_BEAT_BUDGET_USD = 0.25
MAX_BEAT_BUDGET_USD = 8.0

# ---------------------------------------------------------------------------
# Sample storyboard
# ---------------------------------------------------------------------------

SAMPLE_BEATS = [
    {"beat_id": "B001", "narrative_function": "hook", "shot_type": "hero_lipsync", "act": 1, "est_duration_sec": 5.0},
    {"beat_id": "B002", "narrative_function": "metaphorical_b_roll", "shot_type": "broll_environment", "act": 1, "est_duration_sec": 5.0},
    {"beat_id": "B003", "narrative_function": "thesis", "shot_type": "hero_lipsync", "act": 2, "est_duration_sec": 6.0},
    {"beat_id": "B004", "narrative_function": "framework_reveal", "shot_type": "graphic_progressive", "act": 2, "est_duration_sec": 4.0},
    {"beat_id": "B005", "narrative_function": "evidence", "shot_type": "broll_archival", "act": 3, "est_duration_sec": 5.0},
    {"beat_id": "B006", "narrative_function": "thesis_close", "shot_type": "hero_lipsync", "act": 4, "est_duration_sec": 5.0},
    {"beat_id": "B007", "narrative_function": "factual_data", "shot_type": "broll_tactical", "act": 4, "est_duration_sec": 4.0},
    {"beat_id": "B008", "narrative_function": "philosophical_close", "shot_type": "hero_lipsync", "act": 6, "est_duration_sec": 5.0},
    {"beat_id": "B009", "narrative_function": "transition", "shot_type": "broll_environment", "act": 6, "est_duration_sec": 3.0},
    {"beat_id": "B010", "narrative_function": "final_motivation", "shot_type": "hero_lipsync", "act": 6, "est_duration_sec": 5.0},
]

# ---------------------------------------------------------------------------
# Allocators
# ---------------------------------------------------------------------------

def flat_allocator(beats: list[dict], total_cap_usd: float) -> list[dict]:
    """Distribute budget equally across all beats."""
    n = len(beats)
    if n == 0:
        return []
    per_beat = total_cap_usd / n
    allocations = []
    for b in beats:
        allocations.append({
            "beat_id": b["beat_id"],
            "allocation_usd": round(per_beat, 4),
            "weight": 1.0,
        })
    return allocations


def weighted_allocator(
    beats: list[dict],
    total_cap_usd: float,
    weights: dict[str, float] | None = None,
    min_budget: float = MIN_BEAT_BUDGET_USD,
    max_budget: float = MAX_BEAT_BUDGET_USD,
) -> list[dict]:
    """Distribute budget proportionally by weight, clamped to floor/ceiling."""
    if weights is None:
        weights = {}

    n = len(beats)
    if n == 0:
        return []

    # Compute raw weights
    raw_weights = []
    for b in beats:
        w = weights.get(b["beat_id"], 1.0)
        raw_weights.append(w)

    total_weight = sum(raw_weights)
    if total_weight == 0:
        total_weight = 1.0

    # Initial proportional allocation
    allocations = []
    for i, b in enumerate(beats):
        share = (raw_weights[i] / total_weight) * total_cap_usd
        clamped = max(min_budget, min(max_budget, share))
        allocations.append({
            "beat_id": b["beat_id"],
            "allocation_usd": round(clamped, 4),
            "weight": raw_weights[i],
        })

    # Adjust for any clamping drift to ensure total == cap
    current_total = sum(a["allocation_usd"] for a in allocations)
    drift = total_cap_usd - current_total
    if abs(drift) > 0.001 and n > 0:
        # Distribute drift across unclamped beats
        adjustable = [a for a in allocations if min_budget < a["allocation_usd"] < max_budget]
        if adjustable:
            per_adjust = drift / len(adjustable)
            for a in adjustable:
                a["allocation_usd"] = round(a["allocation_usd"] + per_adjust, 4)

    return allocations


# ---------------------------------------------------------------------------
# Fixture generators
# ---------------------------------------------------------------------------

def generate_flat_allocation(tmp_path: Path, total_cap_usd: float = 60.0) -> dict[str, Any]:
    """Generate a flat allocation fixture."""
    tmp_path.mkdir(exist_ok=True, parents=True)
    allocations = flat_allocator(SAMPLE_BEATS, total_cap_usd)
    result = {
        "fixture_type": "flat_allocation",
        "strategy": "flat",
        "total_cap_usd": total_cap_usd,
        "beat_count": len(SAMPLE_BEATS),
        "allocations": allocations,
    }
    out = tmp_path / "budget_flat.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True))
    return {
        "path": str(out),
        "result": result,
        "total_cap_usd": total_cap_usd,
        "fixture_type": "flat_allocation",
    }


def generate_weighted_allocation(tmp_path: Path, total_cap_usd: float = 60.0) -> dict[str, Any]:
    """Generate a weighted allocation fixture with hero beats at 3x weight."""
    tmp_path.mkdir(exist_ok=True, parents=True)
    # Mark hero thesis_close beats as 3x weight, transitions as 0.5x
    weights = {}
    for b in SAMPLE_BEATS:
        if b["narrative_function"] in ("thesis_close", "hook", "final_motivation"):
            weights[b["beat_id"]] = 3.0
        elif b["narrative_function"] == "transition":
            weights[b["beat_id"]] = 0.5
        else:
            weights[b["beat_id"]] = 1.0

    allocations = weighted_allocator(SAMPLE_BEATS, total_cap_usd, weights)
    result = {
        "fixture_type": "weighted_allocation",
        "strategy": "weighted",
        "total_cap_usd": total_cap_usd,
        "beat_count": len(SAMPLE_BEATS),
        "weights": weights,
        "allocations": allocations,
    }
    out = tmp_path / "budget_weighted.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True))
    return {
        "path": str(out),
        "result": result,
        "total_cap_usd": total_cap_usd,
        "fixture_type": "weighted_allocation",
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flat_allocation(tmp_path):
    yield generate_flat_allocation(tmp_path)


@pytest.fixture
def weighted_allocation(tmp_path):
    yield generate_weighted_allocation(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_flat_allocation(flat_allocation):
    """Flat allocation: each beat gets equal share, sum equals cap."""
    result = flat_allocation["result"]
    cap = flat_allocation["total_cap_usd"]
    allocs = result["allocations"]
    assert len(allocs) == 10
    # All beats get same allocation
    amounts = [a["allocation_usd"] for a in allocs]
    assert all(abs(a - amounts[0]) < 0.01 for a in amounts), "flat allocation not equal"
    # Sum equals cap
    total = sum(amounts)
    assert abs(total - cap) < 0.01, f"flat total {total} != cap {cap}"


def test_weighted_allocation(weighted_allocation):
    """Weighted allocation: hero beats get more, sum equals cap."""
    result = weighted_allocation["result"]
    cap = weighted_allocation["total_cap_usd"]
    allocs = result["allocations"]
    assert len(allocs) == 10

    # Hero beats (thesis_close, hook, final_motivation) should get more than transitions
    hero_beats = {"B001", "B006", "B010"}  # hook, thesis_close, final_motivation
    transition_beats = {"B009"}

    hero_amounts = [a["allocation_usd"] for a in allocs if a["beat_id"] in hero_beats]
    transition_amounts = [a["allocation_usd"] for a in allocs if a["beat_id"] in transition_beats]

    assert hero_amounts, "no hero beats found"
    assert transition_amounts, "no transition beats found"
    assert min(hero_amounts) > max(transition_amounts), \
        f"hero min {min(hero_amounts)} should be > transition max {max(transition_amounts)}"

    # Sum equals cap
    total = sum(a["allocation_usd"] for a in allocs)
    assert abs(total - cap) < 0.01, f"weighted total {total} != cap {cap}"


def test_cap_invariant(flat_allocation, weighted_allocation):
    """Neither allocator exceeds the cap."""
    for fix in [flat_allocation, weighted_allocation]:
        cap = fix["total_cap_usd"]
        total = sum(a["allocation_usd"] for a in fix["result"]["allocations"])
        assert total <= cap + 0.01, f"total {total} exceeds cap {cap}"


def test_fixture_determinism(tmp_path):
    """Same inputs produce same output."""
    m1 = generate_flat_allocation(tmp_path / "run1")
    m2 = generate_flat_allocation(tmp_path / "run2")
    assert Path(m1["path"]).read_bytes() == Path(m2["path"]).read_bytes(), \
        "flat allocation generation is not deterministic"


def test_budget_json_schema(flat_allocation):
    """Budget JSON has expected schema."""
    result = flat_allocation["result"]
    assert "fixture_type" in result
    assert "strategy" in result
    assert "total_cap_usd" in result
    assert "beat_count" in result
    assert "allocations" in result
    for a in result["allocations"]:
        assert "beat_id" in a
        assert "allocation_usd" in a
        assert "weight" in a
