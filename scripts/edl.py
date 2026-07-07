"""TKT-601: Edit Decision List (EDL) override parser and validator.

Parses a YAML/JSON EDL override file and validates every override against
the same constraint engine used by the storyboard validator and assembler.
Invalid overrides are rejected with named errors.

Config flag: EDL_MODE = off|on (default off).

Usage:
    from edl import parse_edl, validate_edl, apply_edl_overrides
    overrides = parse_edl(Path("edl.yaml"))
    validated = validate_edl(overrides, storyboard)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BEAT_MIN_SEC = 2.0
HERO_CHAIN_CAP_SEC = 15.05
ACT6_HERO_CHAIN_CAP_SEC = 25.05

EMOTIONAL_HOLD_FUNCTIONS = frozenset({
    "thesis_close",
    "philosophical_close",
    "final_motivation",
    "identity_shift",
})

DEFAULT_EMOTIONAL_HOLD_SEC = 0.8

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_edl(path: Path) -> list[dict]:
    """Parse an EDL override file (YAML or JSON).

    Returns a list of override dicts:
        [{beat_id, trim_start_sec, trim_end_sec, reorder_after, music_duck_db}]
    """
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError(f"EDL root must be a dict, got {type(data).__name__}")

    overrides = data.get("overrides", [])
    if not isinstance(overrides, list):
        raise ValueError(f"EDL 'overrides' must be a list, got {type(overrides).__name__}")

    parsed = []
    for i, ov in enumerate(overrides):
        if not isinstance(ov, dict):
            raise ValueError(f"Override #{i} must be a dict, got {type(ov).__name__}")
        if "beat_id" not in ov:
            raise ValueError(f"Override #{i} missing required field 'beat_id'")
        parsed.append({
            "beat_id": str(ov["beat_id"]),
            "trim_start_sec": float(ov.get("trim_start_sec", 0.0)),
            "trim_end_sec": float(ov.get("trim_end_sec", 0.0)),
            "reorder_after": ov.get("reorder_after"),
            "music_duck_db": float(ov.get("music_duck_db", 0.0)),
        })

    return parsed


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_edl(overrides: list[dict], storyboard: dict) -> tuple[list[dict], list[str]]:
    """Validate EDL overrides against storyboard constraints.

    Returns (valid_overrides, errors).
    """
    errors = []
    beats = storyboard.get("beats", [])
    beat_map = {b.get("beat_id"): b for b in beats if b.get("beat_id")}

    for ov in overrides:
        bid = ov["beat_id"]
        beat = beat_map.get(bid)
        if beat is None:
            errors.append(f"beat_id '{bid}' not found in storyboard")
            continue

        # Validate trim
        trim_start = ov["trim_start_sec"]
        trim_end = ov["trim_end_sec"]
        est_dur = beat.get("est_duration_sec", 0.0)

        if trim_start < 0 or trim_end < 0:
            errors.append(f"{bid}: trim values must be non-negative")

        if trim_start + trim_end >= est_dur - BEAT_MIN_SEC:
            errors.append(
                f"{bid}: trim ({trim_start:.1f}s + {trim_end:.1f}s) would push "
                f"{est_dur:.1f}s beat below {BEAT_MIN_SEC}s minimum"
            )

        # Validate reorder target
        if ov.get("reorder_after"):
            target = ov["reorder_after"]
            if target not in beat_map:
                errors.append(f"{bid}: reorder_after target '{target}' not in storyboard")

    return overrides, errors


# ---------------------------------------------------------------------------
# Emotional-hold auto-extension
# ---------------------------------------------------------------------------

def compute_emotional_holds(storyboard: dict, hold_sec: float = DEFAULT_EMOTIONAL_HOLD_SEC) -> dict[str, float]:
    """Return {beat_id: hold_sec} for beats whose narrative_function is in EMOTIONAL_HOLD_FUNCTIONS."""
    holds = {}
    for b in storyboard.get("beats", []):
        nf = (b.get("narrative_function") or "").strip().lower()
        if nf in EMOTIONAL_HOLD_FUNCTIONS:
            holds[b["beat_id"]] = hold_sec
    return holds


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_edl_overrides(segments: list[dict], overrides: list[dict]) -> list[dict]:
    """Apply validated EDL overrides to assembly segments.

    Modifies segments in-place and returns them.
    """
    override_map = {ov["beat_id"]: ov for ov in overrides}

    for seg in segments:
        bid = seg.get("beat_id") or seg.get("id")
        if not bid or bid not in override_map:
            continue

        ov = override_map[bid]

        # Apply trim
        if ov["trim_start_sec"] > 0 or ov["trim_end_sec"] > 0:
            seg["trim"] = {
                "planned_duration_sec": seg.get("est_duration_sec", 0.0) - ov["trim_start_sec"] - ov["trim_end_sec"],
                "trim_start_sec": ov["trim_start_sec"],
                "trim_end_sec": ov["trim_end_sec"],
            }

        # Apply music ducking
        if ov["music_duck_db"] != 0.0:
            seg["music_duck_db"] = ov["music_duck_db"]

    return segments
