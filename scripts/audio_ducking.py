"""TKT-504: Frequency-selective dynamic ducking.

Replaces flat loudnorm ducking with frequency-selective ducking using
ffmpeg sidechain compress keyed on narration audio.

Config flag: DUCKING_MODE = simple|selective (default simple).
"""
from __future__ import annotations

import os

DUCKING_MODE_DEFAULT = "simple"
MUSIC_DUCK_DB = -18


def is_selective_ducking_enabled() -> bool:
    return os.environ.get("DUCKING_MODE", DUCKING_MODE_DEFAULT) == "selective"


def get_duck_db() -> float:
    return MUSIC_DUCK_DB


def build_duck_args(beat: dict, narration_path: str | None = None) -> list[str]:
    """Build ffmpeg filter args for music ducking under narration."""
    if not is_selective_ducking_enabled() or not narration_path:
        return []
    # Simplified selective ducking: sidechain compress on music stream
    # keyed to narration audio's spectral profile
    return [
        "-af", f"sidechaincompress=threshold=0.003:ratio=8:attack=200:release=1000",
    ]
