"""Shared test constants — read from the single source of truth (constraints.json)."""
import json
from pathlib import Path

_CONSTRAINTS_PATH = Path(__file__).resolve().parent.parent / "docs" / "channel_universe" / "constraints.json"
_c = json.loads(_CONSTRAINTS_PATH.read_text())
_rules = _c.get("lipsync_render_rules", {})

MODEL_MAX_CLIP_SEC = float(_rules.get("max_clip_duration_sec", 15))
MODEL_MIN_CLIP_SEC = float(_rules.get("min_clip_duration_sec", 4))
MIN_BEAT_SEC = float(_rules.get("min_beat_duration_sec", 0.1))

# Standard test constraints dict matching what reconcile/reroute/slice expect
TEST_CONSTRAINTS = {
    "max_clip_sec": MODEL_MAX_CLIP_SEC,
    "min_clip_sec": MODEL_MIN_CLIP_SEC,
    "min_beat_sec": MIN_BEAT_SEC,
    "reroute_target": "hero_cutaway",
    "broll_slot_max": 6.0,
}

# A duration guaranteed to exceed the model limit (for split/reroute testing)
OVER_LIMIT_DURATION = MODEL_MAX_CLIP_SEC + 3.0  # e.g., 18.0 if max is 15
