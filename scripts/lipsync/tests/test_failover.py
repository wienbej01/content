"""Tests for lipsync failover."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lipsync import LipsyncProvider, LipsyncResult, NoHealthyLipsyncProviderError
from lipsync.registry import (
    register_provider, get_prioritized_providers, configure_health_monitor, reset_registry
)
from lipsync.health import ProviderHealthMonitor
from lipsync.failover import lipsync_with_failover, FailoverResult


class MockLipsyncProvider:
    def __init__(self, name: str, *, healthy: bool = True,
                 submit_ok: bool = True, poll_ok: bool = True,
                 cost: float = 1.0):
        self._name = name
        self._healthy = healthy
        self._submit_ok = submit_ok
        self._poll_ok = poll_ok
        self._cost = cost
        self.submitted: list[tuple[Path, Path]] = []

    def name(self) -> str:
        return self._name

    def submit(self, reference_image: Path, audio_slice: Path) -> str:
        self.submitted.append((reference_image, audio_slice))
        if not self._submit_ok:
            raise RuntimeError(f"{self._name} submit failed")
        return f"{self._name}_job_123"

    def poll(self, job_id: str) -> LipsyncResult:
        if not self._poll_ok:
            return LipsyncResult(status="failed", error=f"{self._name} poll failed")
        return LipsyncResult(status="completed", clip_path=Path("/tmp/fake.mp4"),
                            cost_usd=self._cost)

    def cost_estimate_sec(self, duration_sec: float) -> float:
        return self._cost

    def health_check(self) -> bool:
        return self._healthy


@pytest.fixture(autouse=True)
def _clear_state():
    reset_registry()
    yield
    reset_registry()


def _make_tmp_audio(tmp_path: Path) -> Path:
    p = tmp_path / "audio.wav"
    p.write_bytes(b"\x00" * 100)
    return p


def _make_tmp_ref(tmp_path: Path) -> Path:
    p = tmp_path / "ref.png"
    p.write_bytes(b"\x00" * 100)
    return p


class TestFailoverSingleMode:
    def test_single_provider_success(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "single")
        p1 = MockLipsyncProvider("seedance")
        register_provider(p1)
        ref = _make_tmp_ref(tmp_path)
        audio = _make_tmp_audio(tmp_path)
        result = lipsync_with_failover(ref, audio)
        assert isinstance(result, FailoverResult)
        assert result.provider_name == "seedance"
        assert len(result.attempts) == 1


class TestFailoverMultiMode:
    def test_primary_succeeds(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        p1 = MockLipsyncProvider("seedance")
        register_provider(p1)
        ref = _make_tmp_ref(tmp_path)
        audio = _make_tmp_audio(tmp_path)
        result = lipsync_with_failover(ref, audio)
        assert result.provider_name == "seedance"

    def test_primary_fails_secondary_succeeds(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        p1 = MockLipsyncProvider("seedance", submit_ok=False)
        p2 = MockLipsyncProvider("heygen", cost=2.0)
        register_provider(p1)
        register_provider(p2)
        ref = _make_tmp_ref(tmp_path)
        audio = _make_tmp_audio(tmp_path)
        result = lipsync_with_failover(ref, audio)
        assert result.provider_name == "heygen"
        assert len(result.attempts) == 2

    def test_all_fail_raises(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        p1 = MockLipsyncProvider("seedance", submit_ok=False)
        p2 = MockLipsyncProvider("heygen", submit_ok=False)
        register_provider(p1)
        register_provider(p2)
        ref = _make_tmp_ref(tmp_path)
        audio = _make_tmp_audio(tmp_path)
        with pytest.raises(NoHealthyLipsyncProviderError):
            lipsync_with_failover(ref, audio)

    def test_no_providers(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        ref = _make_tmp_ref(tmp_path)
        audio = _make_tmp_audio(tmp_path)
        with pytest.raises(NoHealthyLipsyncProviderError):
            lipsync_with_failover(ref, audio)

    def test_evidence_logged(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("LIPSYNC_PROVIDER_MODE", "failover")
        p1 = MockLipsyncProvider("seedance", submit_ok=False)
        p2 = MockLipsyncProvider("heygen", cost=1.5)
        register_provider(p1)
        register_provider(p2)
        ref = _make_tmp_ref(tmp_path)
        audio = _make_tmp_audio(tmp_path)
        result = lipsync_with_failover(ref, audio)
        assert len(result.attempts) == 2
        assert result.attempts[0]["status"] in {"error", "failed"}
        assert result.attempts[1]["status"] == "completed"
