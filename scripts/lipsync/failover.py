"""Provider failover for lipsync generation.

Wraps LipsyncProvider.submit() and .poll() with failover semantics.

  LIPSYNC_PROVIDER_MODE == 'failover' → iterate over prioritized healthy
  providers; try next if current fails submit or poll.

Failover is logged and recorded as evidence per attempt.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import List, Optional

from lipsync import LipsyncProvider, LipsyncResult, LipsyncProviderError, NoHealthyLipsyncProviderError
from lipsync.registry import get_prioritized_providers


logger = logging.getLogger(__name__)


class FailoverResult:
    """Result of lipsync submission with failover attempt history."""

    def __init__(self, clip_path: Optional[Path] = None,
                 cost_usd: float = 0.0,
                 attempts: Optional[List[dict]] = None,
                 provider_name: str = ""):
        self.clip_path = clip_path
        self.cost_usd = cost_usd
        self.attempts = attempts or []
        self.provider_name = provider_name

    def __repr__(self) -> str:
        return (f"FailoverResult(provider={self.provider_name!r}, "
                f"clip={self.clip_path}, cost={self.cost_usd:.4f}, "
                f"attempts={len(self.attempts)})")


def _is_failover_enabled() -> bool:
    return os.environ.get("LIPSYNC_PROVIDER_MODE") == "failover"


def _try_submit(provider: LipsyncProvider, reference_image: Path,
                audio_slice: Path) -> tuple[str, float]:
    """Submit via provider. Returns (job_id, estimated_cost)."""
    job_id = provider.submit(reference_image, audio_slice)
    estimate = provider.cost_estimate_sec(audio_slice.stat().st_size / 44100 / 2 if audio_slice.exists() else 5.0)
    return job_id, estimate


def _try_poll(provider: LipsyncProvider, job_id: str) -> LipsyncResult:
    """Poll provider for result."""
    return provider.poll(job_id)


def lipsync_with_failover(
    reference_image: Path,
    audio_slice: Path,
) -> FailoverResult:
    """Submit a lipsync job with automatic failover across providers.

    In single mode, only the first registered provider is used.
    In failover mode, iterate over providers until one succeeds.
    Raises NoHealthyLipsyncProviderError if all providers fail.
    """
    providers = get_prioritized_providers()
    if not providers:
        raise NoHealthyLipsyncProviderError("No lipsync providers registered")

    attempts: List[dict] = []

    if not _is_failover_enabled():
        # Single-provider mode
        provider = providers[0]
        try:
            job_id, estimate = _try_submit(provider, reference_image, audio_slice)
            result = _try_poll(provider, job_id)
            attempts.append({
                "provider": provider.name(),
                "job_id": job_id,
                "status": result.status,
                "cost_usd": result.cost_usd,
            })
            if result.status == "completed":
                return FailoverResult(
                    clip_path=result.clip_path,
                    cost_usd=result.cost_usd,
                    attempts=attempts,
                    provider_name=provider.name(),
                )
            raise LipsyncProviderError(f"Single-provider failed: {result.error}")
        except Exception as e:
            attempts.append({
                "provider": provider.name(),
                "status": "error",
                "error": str(e),
            })
            raise

    # Failover mode: iterate over providers
    last_error = None
    for provider in providers:
        try:
            job_id, estimate = _try_submit(provider, reference_image, audio_slice)
            result = _try_poll(provider, job_id)
            attempts.append({
                "provider": provider.name(),
                "job_id": job_id,
                "status": result.status,
                "cost_usd": result.cost_usd,
            })
            if result.status == "completed":
                logger.info("lipsync_with_failover: completed by %s (%.4f USD)",
                            provider.name(), result.cost_usd)
                return FailoverResult(
                    clip_path=result.clip_path,
                    cost_usd=result.cost_usd,
                    attempts=attempts,
                    provider_name=provider.name(),
                )
            last_error = result.error or f"{provider.name()} returned {result.status}"
            logger.warning("lipsync_with_failover: %s returned %s; trying next provider",
                           provider.name(), result.status)
        except Exception as e:
            last_error = str(e)
            attempts.append({
                "provider": provider.name(),
                "status": "error",
                "error": last_error,
            })
            logger.warning("lipsync_with_failover: %s failed: %s",
                           provider.name(), last_error)

    raise NoHealthyLipsyncProviderError(
        f"All providers failed. Last error: {last_error}. "
        f"Attempts: {len(attempts)}")
