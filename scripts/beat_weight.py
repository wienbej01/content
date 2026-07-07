"""TKT-801: Beat attention-weight classifier.

Maps each beat to a viewer_attention_weight ∈ [0.5, 3.0] based on:
- narrative_function lookup (thesis_close=3.0, hook=2.8, factual_data=1.0, transition=0.5)
- shot_type modifier (hero_lipsync ×1.5, graphic ×0.8)
- act modifier (Act 1+6 ×1.3)

Configurable via configs/beat_weights.yaml. Deterministic.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Weight tables
# ---------------------------------------------------------------------------

NARRATIVE_FUNCTION_WEIGHTS = {
    "thesis_close": 3.0,
    "final_motivation": 2.8,
    "hook": 2.8,
    "myth_bust_reveal": 2.5,
    "framework_reveal": 2.0,
    "evidence": 1.8,
    "philosophical_close": 1.5,
    "factual_data": 1.0,
    "transition": 0.5,
}

SHOT_TYPE_MODIFIERS = {
    "hero_lipsync": 1.5,
    "hero_cutaway": 1.3,
    "broll_archival": 1.0,
    "broll_environment": 0.8,
    "broll_metaphorical": 0.8,
    "broll_tactical": 0.9,
    "graphic_progressive": 0.8,
    "graphic_title_card": 0.7,
    "kinetic_text": 0.6,
    "ui_insert": 0.7,
    "still_kenburns": 0.5,
}

ACT_MODIFIERS = {
    1: 1.3,
    2: 1.0,
    3: 1.1,
    4: 1.0,
    5: 1.0,
    6: 1.3,
}

MIN_WEIGHT = 0.5
MAX_WEIGHT = 3.0


def classify_beat(beat: dict) -> float:
    """Compute viewer_attention_weight for a single beat.

    Returns the raw weight (unclamped) for proportional allocation.
    Clamping to [MIN_WEIGHT, MAX_WEIGHT] happens at allocation time,
    not here, so the allocator can distinguish high-value beats.
    """
    nf = (beat.get("narrative_function") or "").strip().lower()
    st = (beat.get("shot_type") or "").strip().lower()
    act = beat.get("act", 3)

    base = NARRATIVE_FUNCTION_WEIGHTS.get(nf, 1.0)
    shot_mod = SHOT_TYPE_MODIFIERS.get(st, 1.0)
    act_mod = ACT_MODIFIERS.get(act, 1.0)

    return base * shot_mod * act_mod


def classify_beats(beats: list[dict]) -> list[float]:
    """Map each beat to its attention weight."""
    return [classify_beat(b) for b in beats]


def total_weight(beats: list[dict]) -> float:
    """Sum of all beat weights."""
    return sum(classify_beats(beats))
