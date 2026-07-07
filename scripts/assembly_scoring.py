"""TKT-604: Multi-variant assembly scoring.

Scores different assembly variants using a deterministic function:
    score = w1 * pacing_match + w2 * variety_match + w3 * constraint_margin

Returns the highest-scoring variant. No paid calls.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Weights (configurable)
# ---------------------------------------------------------------------------

W_PACING = 0.4
W_VARIETY = 0.35
W_CONSTRAINT = 0.25

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_pacing(variant: dict) -> float:
    """Pacing score: how well the variant's total duration matches target.

    Returns 0.0 (way off) to 1.0 (exact match).
    """
    target = variant.get("target_duration_sec", 0.0)
    actual = variant.get("total_duration_sec", 0.0)
    if target <= 0:
        return 0.0
    ratio = actual / target
    if ratio > 1.0:
        ratio = 1.0 / ratio  # Penalize both over and under
    return max(0.0, min(1.0, ratio))


def score_variety(variant: dict) -> float:
    """Variety score: fraction of distinct shot types across all beats.

    Returns 0.0 (all same) to 1.0 (all distinct).
    """
    beats = variant.get("beats", [])
    if not beats:
        return 0.0
    shot_types = set()
    for b in beats:
        st = b.get("shot_type", "")
        if st:
            shot_types.add(st)
    # Normalize: 6+ distinct types = perfect score
    return min(1.0, len(shot_types) / 6.0)


def score_constraint_margin(variant: dict) -> float:
    """Constraint margin score: fraction of beats within safe bounds.

    Returns 0.0 (all violating) to 1.0 (all within bounds).
    """
    beats = variant.get("beats", [])
    if not beats:
        return 0.0
    safe = 0
    for b in beats:
        dur = b.get("est_duration_sec", 0.0)
        st = b.get("shot_type", "")
        if st == "hero_lipsync":
            if dur <= 15.0:
                safe += 1
        else:
            if dur >= 1.0:
                safe += 1
    return safe / len(beats)


def score_variant(variant: dict) -> float:
    """Compute total score for a variant. Higher is better."""
    p = score_pacing(variant)
    v = score_variety(variant)
    c = score_constraint_margin(variant)
    return W_PACING * p + W_VARIETY * v + W_CONSTRAINT * c


def select_best_variant(variants: list[dict]) -> tuple[dict | None, list[tuple[dict, float]]]:
    """Select the highest-scoring variant from a list.

    Returns (best_variant, [(variant, score), ...]).
    """
    if not variants:
        return None, []

    scored = [(v, score_variant(v)) for v in variants]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0], scored
