"""Provider health monitor for lipsync providers.

Tracks provider health status in a local JSON file (synced to the
validations table in productions via the gateway operator).

The HealthMonitor runs health_check() on each registered provider every
HEALTH_CHECK_INTERVAL_SEC and records the result. A provider failing
its check is removed from rotation until healed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional


HEALTH_CHECK_INTERVAL_SEC_DEFAULT = 60
HEALTH_HISTORY_LIMIT = 50


class ProviderHealthMonitor:
    """Track health status of providers and dismiss ones that fail."""

    def __init__(self, state_path: Optional[Path] = None,
                 interval_sec: int = HEALTH_CHECK_INTERVAL_SEC_DEFAULT):
        self.state_path = state_path
        self.interval_sec = interval_sec
        self._providers: list = []
        self._state: Dict[str, dict] = {}
        if self.state_path and self.state_path.exists():
            self._state = json.loads(self.state_path.read_text())

    def register(self, provider) -> None:
        self._providers.append(provider)
        name = provider.name()
        if name not in self._state:
            self._state[name] = {
                "healthy": True,
                "last_check": None,
                "last_result": None,
                "history": [],
            }

    def record(self, provider_name: str, healthy: bool, detail: Optional[str] = None) -> None:
        entry = self._state.setdefault(provider_name, {
            "healthy": True, "last_check": None, "last_result": None, "history": []
        })
        entry["healthy"] = healthy
        entry["last_check"] = time.time()
        entry["last_result"] = detail
        history = entry.get("history", [])
        history.append({"t": time.time(), "ok": healthy, "detail": detail})
        entry["history"] = history[-HEALTH_HISTORY_LIMIT:]
        self._persist()

    def is_healthy(self, provider_name: str) -> bool:
        return self._state.get(provider_name, {}).get("healthy", False)

    def healthy_providers(self) -> list:
        return [p for p in self._providers if self.is_healthy(p.name())]

    def tick(self) -> None:
        """Run health checks on all registered providers."""
        for provider in self._providers:
            try:
                ok = provider.health_check()
                self.record(provider.name(), ok, "health_check_passed" if ok else "health_check_failed")
            except Exception as e:
                self.record(provider.name(), False, str(e))

    def _persist(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2, default=str))
