#!/usr/bin/env python3
"""audio_alignment.py — Measured silence-based split point detection.

Provides find_legal_split_points() which returns MEASURED audio boundaries
(silence midpoints) within a beat interval. These replace word-proportional
estimation for split timing decisions.

Requires: ffmpeg (silencedetect filter). No paid API calls.
"""
import hashlib
from pathlib import Path

from audio_timing import detect_silences


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def find_legal_split_points(audio_path, beat_start, beat_end,
                            min_silence_dur=0.20, noise_db=-35):
    """Return measured silence-based split points within [beat_start, beat_end].

    Each point is the MIDPOINT of a detected silence interval that falls
    inside the beat boundaries.

    Returns dict with:
        split_points: list of absolute-sec midpoints
        method: 'silence_detection'
        confidence: 'high' if >=1 clear silence, 'low' if none
        audio_sha256: hash of audio file
        silences: raw (start, end) intervals within beat
    """
    all_silences = detect_silences(audio_path, noise_db=noise_db, min_dur=min_silence_dur)

    # Filter to silences whose midpoint falls within (beat_start, beat_end)
    in_range = []
    for s, e in all_silences:
        mid = (s + e) / 2
        if beat_start < mid < beat_end:
            in_range.append((round(s, 3), round(e, 3)))

    split_points = [round((s + e) / 2, 3) for s, e in in_range]
    confidence = "high" if split_points else "low"

    return {
        "split_points": split_points,
        "method": "silence_detection",
        "confidence": confidence,
        "audio_sha256": _sha256(audio_path),
        "silences": in_range,
    }
