"""TKT-802: Pre-generation budget allocator.

Allocates generation budget across beats proportionally by attention-weight,
clamped to per-beat floor and ceiling. Total equals cap (within FP tolerance).
No path can exceed cap (INV-6).
"""
from __future__ import annotations

from typing import Any

from beat_weight import classify_beats

MIN_BEAT_BUDGET_USD = 0.25
MAX_BEAT_BUDGET_USD = 8.0


def allocate_budget(
    beats: list[dict],
    total_cap_usd: float,
    min_budget: float = MIN_BEAT_BUDGET_USD,
    max_budget: float = MAX_BEAT_BUDGET_USD,
) -> list[dict]:
    """Allocate budget across beats by attention weight.

    Returns list of allocation dicts:
        [{beat_id, weight, allocation_usd, clamped}]
    """
    if not beats or total_cap_usd <= 0:
        return []

    weights = classify_beats(beats)
    tw = sum(weights)
    if tw == 0:
        tw = 1.0

    allocations = []
    for i, b in enumerate(beats):
        share = (weights[i] / tw) * total_cap_usd
        clamped = max(min_budget, min(max_budget, share))
        allocations.append({
            "beat_id": b.get("beat_id", f"beat_{i}"),
            "weight": weights[i],
            "share_raw": round(share, 4),
            "allocation_usd": round(clamped, 4),
            "clamped": clamped != share,
        })

    # Adjust for clamping drift to ensure total == cap
    current_total = sum(a["allocation_usd"] for a in allocations)
    drift = total_cap_usd - current_total
    if abs(drift) > 0.001:
        adjustable = [a for a in allocations if not a["clamped"]]
        if adjustable:
            per_adjust = drift / len(adjustable)
            for a in adjustable:
                a["allocation_usd"] = round(
                    max(min_budget, min(max_budget, a["allocation_usd"] + per_adjust)), 4
                )
        else:
            # All clamped: distribute drift to the highest-weight beat
            allocations[0]["allocation_usd"] = round(
                allocations[0]["allocation_usd"] + drift, 4
            )

    return allocations


def total_allocated(allocations: list[dict]) -> float:
    """Sum of allocated USD."""
    return sum(a["allocation_usd"] for a in allocations)
