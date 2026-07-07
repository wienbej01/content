"""TKT-503: Chapter marker audio cue library + manifest schema.

Defines audio cue types for act boundaries and a manifest schema extension.
Config flag: CHAPTER_MARKERS_MODE = off|on (default off).
"""
from __future__ import annotations

import os

CHAPTER_MARKERS_MODE_DEFAULT = "off"

CUE_TYPES = {
    "act_open": {"description": "Soft UI tink at act start", "duration_sec": 0.5},
    "act_close": {"description": "Low swoosh at act end", "duration_sec": 0.8},
    "chapter_reveal": {"description": "Chime for chapter title card", "duration_sec": 1.0},
    "transition_whoosh": {"description": "Whoosh for scene transitions", "duration_sec": 0.6},
}


def is_chapter_marker_enabled() -> bool:
    return os.environ.get("CHAPTER_MARKERS_MODE", CHAPTER_MARKERS_MODE_DEFAULT) == "on"


def get_cue_for_act_boundary(act_index: int, is_open: bool) -> dict:
    """Return cue configuration for an act boundary."""
    cue_type = "act_open" if is_open else "act_close"
    return {"type": cue_type, "act": act_index, **CUE_TYPES[cue_type]}


def get_cue_library() -> dict:
    """Return the full cue library."""
    return dict(CUE_TYPES)
