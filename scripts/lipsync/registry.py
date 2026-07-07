"""Lipsync provider registry and failover selector.

Maintains the ordered list of registered LipsyncProvider instances and
exposes get_active_provider() for failover selection.

Config flags:
  LIPSYNC_PROVIDER_MODE = single|failover  (default single)
"""
from __future__ import annotations

import os
from typing import List, Optional

from lipsync import LipsyncProvider, NoHealthyLipsyncProviderError
from lipsync.health import ProviderHealthMonitor


# Module-level registry
_providers: List[LipsyncProvider] = []
_monitor: Optional[ProviderHealthMonitor] = None


def register_provider(provider: LipsyncProvider) -> None:
    """Register a lipsync provider. Order matters: first registered = highest priority."""
    _providers.append(provider)
    if _monitor:
        _monitor.register(provider)


def get_active_provider() -> LipsyncProvider:
    """Return the first healthy provider by priority.

    In 'single' mode, returns the first registered provider (Seedance 2.0).
    In 'failover' mode, returns the first healthy provider; raises
    NoHealthyLipsyncProviderError if none are healthy.
    """
    if not _providers:
        raise NoHealthyLipsyncProviderError("No lipsync providers registered")
    mode = os.environ.get("LIPSYNC_PROVIDER_MODE", "single")
    if mode == "single":
        return _providers[0]
    # failover mode
    if _monitor is None:
        raise NoHealthyLipsyncProviderError(
            "LIPSYNC_PROVIDER_MODE=failover but no health monitor configured")
    healthy = _monitor.healthy_providers()
    if not healthy:
        raise NoHealthyLipsyncProviderError(
            f"No healthy providers available. Registered: "
            f"{[p.name() for p in _providers]}; "
            f"healthy: []")
    return healthy[0]


def get_prioritized_providers() -> List[LipsyncProvider]:
    """Return all registered providers in priority order."""
    return list(_providers)


def configure_health_monitor(monitor: ProviderHealthMonitor) -> None:
    """Attach a health monitor and register all existing providers."""
    global _monitor
    _monitor = monitor
    for p in _providers:
        _monitor.register(p)


def reset_registry() -> None:
    """Clear the registry (used by tests)."""
    global _providers, _monitor
    _providers = []
    _monitor = None
