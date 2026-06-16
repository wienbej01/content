"""Sprint 2: Canonical timeline timebase utilities (Ticket LB-201).

Provides integer-based audio sample calculations to eliminate floating-point
drift and independent rounding decisions across the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

# Standard master sample rate for all internal calculations (48kHz is standard for video)
MASTER_SAMPLE_RATE = 48000


@dataclass(frozen=True)
class TimeInterval:
    """Immutable time interval represented in integer samples."""
    start_samples: int
    end_samples: int

    def __post_init__(self):
        if self.start_samples < 0:
            raise ValueError(f"Interval start cannot be negative: {self.start_samples}")
        if self.end_samples < self.start_samples:
            raise ValueError(f"Interval end ({self.end_samples}) cannot be before start ({self.start_samples})")

    @property
    def duration_samples(self) -> int:
        return self.end_samples - self.start_samples

    @property
    def duration_ms(self) -> int:
        return samples_to_ms(self.duration_samples)


def ms_to_samples(ms: int) -> int:
    """Convert integer milliseconds to integer audio samples."""
    if ms < 0:
        raise ValueError(f"Milliseconds cannot be negative: {ms}")
    # Round to nearest sample to avoid cumulative drift
    return round((ms * MASTER_SAMPLE_RATE) / 1000)


def samples_to_ms(samples: int) -> int:
    """Convert integer audio samples to integer milliseconds."""
    if samples < 0:
        raise ValueError(f"Samples cannot be negative: {samples}")
    # Round to nearest millisecond
    return round((samples * 1000) / MASTER_SAMPLE_RATE)


def validate_interval(interval: TimeInterval, master_duration_samples: int) -> None:
    """Validate that an interval is within master bounds and logically sound."""
    if interval.start_samples < 0:
        raise ValueError(f"Interval start cannot be negative: {interval.start_samples}")
    if interval.end_samples > master_duration_samples:
        raise ValueError(
            f"Interval end ({interval.end_samples}) exceeds master duration ({master_duration_samples})"
        )
    if interval.duration_samples <= 0:
        raise ValueError(f"Interval duration must be positive: {interval.duration_samples}")


def interval_duration_samples(start_samples: int, end_samples: int) -> int:
    """Calculate duration in samples between two points."""
    if end_samples < start_samples:
        raise ValueError(f"End ({end_samples}) cannot be before start ({start_samples})")
    return end_samples - start_samples


def detect_overlap_samples(interval1: TimeInterval, interval2: TimeInterval) -> bool:
    """Detect if two intervals overlap in samples."""
    return not (interval1.end_samples <= interval2.start_samples or 
                interval2.end_samples <= interval1.start_samples)


def detect_gap_samples(interval1: TimeInterval, interval2: TimeInterval) -> int:
    """
    Detect gap between two intervals in samples.
    Returns positive gap size if interval2 starts after interval1 ends.
    Returns 0 if they touch or overlap.
    """
    gap = interval2.start_samples - interval1.end_samples
    return max(0, gap)


def clamp_to_master_bounds(start_samples: int, end_samples: int, master_duration_samples: int) -> TimeInterval:
    """Clamp an interval to the valid bounds of the master audio."""
    clamped_start = max(0, start_samples)
    clamped_end = min(master_duration_samples, end_samples)
    
    # If clamping results in an invalid interval, return a zero-duration interval at the start
    if clamped_end <= clamped_start:
        return TimeInterval(start_samples=0, end_samples=0)
        
    return TimeInterval(start_samples=clamped_start, end_samples=clamped_end)


def provider_duration_from_samples(samples: int, provider_min_ms: int = 4000) -> int:
    """
    Calculate the duration to request from a provider in milliseconds.
    Ensures the requested duration meets the provider's minimum requirement.
    This is the ONLY place where provider-specific rounding/padding logic should occur.
    """
    duration_ms = samples_to_ms(samples)
    return max(duration_ms, provider_min_ms)
