"""TKT-502: Paradigm-shift music silence rule in assembler.

Beats whose narrative_function is in SILENCE_FUNCTIONS
(default: myth_bust_reveal, paradigm_shift, philosophical_close)
have music volume dropped to silence (-∞) for beat duration + 1s ramp-in after.

Configs:
  AUDIO_SILENCE_MODE = off|on (default off)
"""
from __future__ import annotations

import os

AUDIO_SILENCE_MODE_DEFAULT = "off"
SILENCE_FUNCTIONS_DEFAULT = ["myth_bust_reveal", "paradigm_shift", "philosophical_close"]
SILENCE_RAMP_IN_SEC = 1.0


def is_silence_required(beat_narrative_function: str | None,
                        silence_functions: list[str] | None = None) -> bool:
    """Return True if the beat's narrative function requires music silence."""
    if os.environ.get("AUDIO_SILENCE_MODE", AUDIO_SILENCE_MODE_DEFAULT) != "on":
        return False
    if not beat_narrative_function:
        return False
    functions = silence_functions or SILENCE_FUNCTIONS_DEFAULT
    return beat_narrative_function.strip().lower() in [f.strip().lower() for f in functions]


def compute_music_volume(beat: dict, silence_functions: list[str] | None = None) -> float:
    """Return music volume in dB for a beat. -inf means silence."""
    if is_silence_required(beat.get("narrative_function"), silence_functions):
        return float("-inf")
    return 0.0


def get_ramp_in_sec() -> float:
    """Return the silence ramp-in duration in seconds."""
    return SILENCE_RAMP_IN_SEC
