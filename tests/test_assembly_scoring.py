#!/usr/bin/env python3
"""TKT-604 tests for multi-variant assembly scoring."""
from scripts.assembly_scoring import (
    score_pacing,
    score_variety,
    score_constraint_margin,
    score_variant,
    select_best_variant,
)


def test_score_pacing_exact_match():
    """Exact duration match scores 1.0."""
    v = {"target_duration_sec": 100.0, "total_duration_sec": 100.0}
    assert score_pacing(v) == 1.0


def test_score_pacing_over():
    """Over-target scores lower than 1.0."""
    v = {"target_duration_sec": 100.0, "total_duration_sec": 150.0}
    assert 0.0 < score_pacing(v) < 1.0


def test_score_variety_all_distinct():
    """6+ distinct shot types scores 1.0."""
    v = {"beats": [{"shot_type": f"t{i}"} for i in range(6)]}
    assert score_variety(v) == 1.0


def test_score_variety_all_same():
    """Single shot type scores ~0.167."""
    v = {"beats": [{"shot_type": "a"}] * 5}
    assert score_variety(v) < 0.2


def test_score_constraint_margin_all_safe():
    """All beats within bounds scores 1.0."""
    v = {"beats": [
        {"shot_type": "hero_lipsync", "est_duration_sec": 10.0},
        {"shot_type": "broll_archival", "est_duration_sec": 3.0},
    ]}
    assert score_constraint_margin(v) == 1.0


def test_score_variant():
    """Total score is weighted sum of subscores."""
    v = {
        "target_duration_sec": 100.0,
        "total_duration_sec": 100.0,
        "beats": [{"shot_type": f"t{i}", "est_duration_sec": 3.0} for i in range(3)],
    }
    score = score_variant(v)
    assert 0.0 <= score <= 1.0


def test_select_best_variant_empty():
    """Empty variants list returns None."""
    best, scored = select_best_variant([])
    assert best is None
    assert scored == []


def test_select_best_variant_deterministic():
    """Same variants always return same best variant."""
    variants = [
        {"target_duration_sec": 100, "total_duration_sec": 90, "beats": [{"shot_type": "a", "est_duration_sec": 3}]},
        {"target_duration_sec": 100, "total_duration_sec": 100, "beats": [{"shot_type": "b", "est_duration_sec": 3}]},
        {"target_duration_sec": 100, "total_duration_sec": 110, "beats": [{"shot_type": "c", "est_duration_sec": 3}]},
    ]
    best1, _ = select_best_variant(variants)
    best2, _ = select_best_variant(variants)
    assert best1 is best2
