"""TKT-505: Animated element integration for emotional beats.

Graphics >2s whose narrative_function is in EMOTIONAL_FUNCTIONS
get alpha-based animation metadata attached (fade in, slow scale, element reveal).

Config flag: EMOTIONAL_ANIMATION_MODE = off|on (default off).
"""
from __future__ import annotations

import os

EMOTIONAL_ANIMATION_MODE_DEFAULT = "off"
EMOTIONAL_FUNCTIONS_DEFAULT = [
    "thesis_close",
    "philosophical_statement",
    "identity_shift",
    "final_motivation",
]


def is_emotional_animation_enabled() -> bool:
    return os.environ.get("EMOTIONAL_ANIMATION_MODE", EMOTIONAL_ANIMATION_MODE_DEFAULT) == "on"


def should_animate_graphic(beat: dict) -> bool:
    """Return True if a graphic beat should have animation metadata."""
    if not is_emotional_animation_enabled():
        return False
    if beat.get("shot_type") not in ("graphic_progressive", "graphic_title_card", "kinetic_text"):
        return False
    dur = beat.get("est_duration_sec", 0)
    if dur <= 2.0:
        return False
    nf = (beat.get("narrative_function") or "").strip().lower()
    return nf in [f.strip().lower() for f in EMOTIONAL_FUNCTIONS_DEFAULT]


def get_animation_metadata(beat: dict) -> dict | None:
    """Return animation metadata for qualifying emotional beats, else None."""
    if not should_animate_graphic(beat):
        return None
    return {
        "animation": {
            "type": "alpha_reveal",
            "fade_in_sec": 0.5,
            "scale": {"from": 0.95, "to": 1.0, "duration_sec": 1.0},
            "element_reveal": True,
        }
    }
