"""Lipsync provider package.

Defines the LipsyncProvider ABC, SeedanceLipsyncProvider wrapper,
ProviderHealthMonitor, and get_active_provider() failover selector.

Config flags:
  LIPSYNC_PROVIDER_MODE = single|failover  (default single)
  LIPSYNC_PROVIDER_HEALTH_CHECK_INTERVAL_SEC = 60

See: docs/plans/WORLD_CLASS_REMEDIATION_20260707/tickets/WAVE_1.md (TKT-102).
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


class LipsyncProviderError(RuntimeError):
    """Raised when a lipsync provider fails in a non-retryable way."""


class NoHealthyLipsyncProviderError(LipsyncProviderError):
    """Raised when no healthy lipsync provider is available for failover."""


class LipsyncResult:
    """Result of a lipsync poll."""

    def __init__(self, status: str, clip_path: Optional[Path] = None,
                 cost_usd: float = 0.0, error: Optional[str] = None):
        self.status = status
        self.clip_path = clip_path
        self.cost_usd = cost_usd
        self.error = error

    def __repr__(self) -> str:
        return (f"LipsyncResult(status={self.status!r}, clip_path={self.clip_path}, "
                f"cost_usd={self.cost_usd:.4f}, error={self.error!r})")


class LipsyncProvider(ABC):
    """Abstract lipsync provider interface.

    Implementations must support:
      submit(reference_image, audio_slice) -> job_id
      poll(job_id) -> LipsyncResult
      cost_estimate_sec(duration_sec) -> float (USD)
      health_check() -> bool
      name() -> str
    """

    @abstractmethod
    def submit(self, reference_image: Path, audio_slice: Path) -> str:
        """Submit a lipsync job. Returns a job_id string."""
        ...

    @abstractmethod
    def poll(self, job_id: str) -> LipsyncResult:
        """Poll job status. Returns a LipsyncResult."""
        ...

    @abstractmethod
    def cost_estimate_sec(self, duration_sec: float) -> float:
        """Estimate cost in USD for a clip of the given duration."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is healthy and available."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Return the provider's logical name."""
        ...
