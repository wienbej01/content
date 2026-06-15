"""Calibrated pre-TTS duration estimates using measured voice pacing data.

These estimates are NON-AUTHORITATIVE planning aids only.
Actual audio_duration_sec must always come from real TTS measurement.
"""

from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "voice_pacing.yaml"
_config = None


def _load_config():
    global _config
    if _config is None:
        with open(_CONFIG_PATH) as f:
            _config = yaml.safe_load(f)
    return _config


def estimate_duration_sec(text: str, treatment: str = "broll") -> dict:
    """Return a non-authoritative duration estimate for planning purposes.

    Returns {'estimate_sec': float, 'confidence': str, 'wpm': float,
             'uncertainty_pct': int, 'authoritative': False}
    """
    cfg = _load_config()
    wps = cfg["calibrated_wps"]
    factor = cfg.get("treatment_factors", {}).get(treatment, 1.0)
    uncertainty = cfg["estimate_uncertainty_pct"]

    words = len(text.split())
    adjusted_wps = wps * factor
    estimate = round(words / adjusted_wps, 2) if words else 0.0

    return {
        "estimate_sec": estimate,
        "confidence": "low" if len(cfg.get("measured_wpm", [])) < 3 else "medium",
        "wpm": cfg["calibrated_wpm"],
        "uncertainty_pct": uncertainty,
        "authoritative": False,
    }
