"""Tests for the lipsync provider package."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure scripts is on path so `lipsync` is importable
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lipsync import LipsyncProvider, LipsyncResult, NoHealthyLipsyncProviderError
from lipsync.health import ProviderHealthMonitor
from lipsync.registry import (
    register_provider, get_active_provider, get_prioritized_providers,
    configure_health_monitor, reset_registry
)
from lipsync.seedance import SeedanceLipsyncProvider


class MockProvider:
    """Mock provider for testing."""

    def __init__(self, name: str, healthy: bool = True, cost: float = 1.0):
        self._name = name
        self._healthy = healthy
        self._cost = cost
        self.submit_count = 0
        self.poll_count = 0

    def name(self) -> str:
        return self._name

    def submit(self, reference_image: Path, audio_slice: Path) -> str:
        self.submit_count += 1
        return f"mock_{self._name}_job"

    def poll(self, job_id: str) -> LipsyncResult:
        self.poll_count += 1
        return LipsyncResult(status="completed", clip_path=Path("/tmp/fake.mp4"),
                            cost_usd=self._cost)

    def cost_estimate_sec(self, duration_sec: float) -> float:
        return self._cost

    def health_check(self) -> bool:
        return self._healthy


@pytest.fixture(autouse=True)
def _clear_registry():
    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def _seedance_always_healthy(monkeypatch):
    monkeypatch.setenv("YT_TEST_MODE", "1")


class TestSeedanceLipsyncProvider:
    def test_name(self, _seedance_always_healthy):
        p = SeedanceLipsyncProvider()
        assert p.name() == "seedance_2_0"

    def test_cost_estimate(self, _seedance_always_healthy):
        p = SeedanceLipsyncProvider()
        cost = p.cost_estimate_sec(5.0)
        assert cost > 0

    def test_health_check_in_test_mode(self, _seedance_always_healthy):
        p = SeedanceLipsyncProvider()
        assert p.health_check() is True

    def test_submit_test_mode(self, _seedance_always_healthy, tmp_path: Path):
        p = SeedanceLipsyncProvider()
        ref = tmp_path / "ref.png"
        audio = tmp_path / "audio.wav"
        ref.write_bytes(b"fake")
        audio.write_bytes(b"fake")
        job_id = p.submit(ref, audio)
        assert job_id.startswith("seedance_test_")

    def test_poll_test_mode(self, _seedance_always_healthy):
        p = SeedanceLipsyncProvider()
        result = p.poll("seedance_test_123")
        assert result.status == "completed"
        assert result.cost_usd > 0


class TestProviderHealthMonitor:
    def test_register_and_check(self, tmp_path: Path):
        state_path = tmp_path / "health.json"
        mon = ProviderHealthMonitor(state_path=state_path, interval_sec=1)
        p1 = MockProvider("p1", healthy=True)
        mon.register(p1)
        mon.tick()
        assert mon.is_healthy("p1") is True

    def test_unhealthy_provider(self, tmp_path: Path):
        state_path = tmp_path / "health.json"
        mon = ProviderHealthMonitor(state_path=state_path, interval_sec=1)
        p1 = MockProvider("p1", healthy=False)
        mon.register(p1)
        mon.tick()
        assert mon.is_healthy("p1") is False

    def test_persist(self, tmp_path: Path):
        state_path = tmp_path / "health.json"
        mon = ProviderHealthMonitor(state_path=state_path, interval_sec=1)
        p1 = MockProvider("p1", healthy=True)
        mon.register(p1)
        mon.tick()
        assert state_path.exists()


class TestRegistry:
    def test_register_and_get_single_mode(self, _seedance_always_healthy):
        p1 = SeedanceLipsyncProvider()
        register_provider(p1)
        active = get_active_provider()
        assert active.name() == "seedance_2_0"

    def test_failover_mode(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        state_path = tmp_path / "health.json"
        mon = ProviderHealthMonitor(state_path=state_path, interval_sec=1)
        p1 = MockProvider("p1", healthy=False)
        p2 = MockProvider("p2", healthy=True)
        register_provider(p1)
        register_provider(p2)
        configure_health_monitor(mon)
        mon.tick()
        active = get_active_provider()
        assert active.name() == "p2"

    def test_failover_all_unhealthy(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        state_path = tmp_path / "health.json"
        mon = ProviderHealthMonitor(state_path=state_path, interval_sec=1)
        p1 = MockProvider("p1", healthy=False)
        register_provider(p1)
        configure_health_monitor(mon)
        mon.tick()
        with pytest.raises(NoHealthyLipsyncProviderError):
            get_active_provider()

    def test_no_providers(self):
        with pytest.raises(NoHealthyLipsyncProviderError):
            get_active_provider()

    def test_get_prioritized(self, _seedance_always_healthy):
        p1 = SeedanceLipsyncProvider()
        p2 = MockProvider("other")
        register_provider(p1)
        register_provider(p2)
        providers = get_prioritized_providers()
        assert len(providers) == 2
        assert providers[0].name() == "seedance_2_0"
        assert providers[1].name() == "other"

    def test_single_mode_returns_first(self, monkeypatch):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "single")
        p1 = MockProvider("primary", healthy=False)
        register_provider(p1)
        active = get_active_provider()
        assert active.name() == "primary"
