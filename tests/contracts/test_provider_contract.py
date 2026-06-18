"""S3-T01: Provider adapter contract + S3-T02: deterministic valid-media test providers.

Named tests required by the program:
  test_fake_provider_rejected_in_production
  test_provider_cost_recorded
  test_semantic_fingerprint_complete (already in test_provider_fingerprint_lb400)
  test_corrupt_download_rejected
"""
import os
import sys
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import provider_adapter
from provider_adapter import (
    ProviderAdapter, FakeProviderAdapter, ProviderAdapterError,
    get_provider_adapter, validate_downloaded_artifact,
)
import paid_adapters


# --- S3-T01: Adapter contract ---

def test_fake_provider_rejected_in_production(monkeypatch):
    """The fake/test adapter must NOT be usable outside YT_TEST_MODE."""
    monkeypatch.delenv("YT_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(ProviderAdapterError, match="YT_TEST_MODE"):
        get_provider_adapter("fake")

    with pytest.raises(ProviderAdapterError, match="YT_TEST_MODE"):
        FakeProviderAdapter({})


def test_fake_provider_available_in_test_mode(monkeypatch):
    """The fake adapter IS available in YT_TEST_MODE for local deterministic runs."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    adapter = get_provider_adapter("fake")
    assert isinstance(adapter, FakeProviderAdapter)


def test_real_adapters_implement_full_contract():
    """All real adapters must implement the full S3-T01 contract methods."""
    for cls_name, cls in [("HiggsfieldSeedanceAdapter", paid_adapters.HiggsfieldSeedanceAdapter),
                           ("ElevenLabsAdapter", paid_adapters.ElevenLabsAdapter)]:
        assert hasattr(cls, "prepare_request"), f"{cls_name} missing prepare_request"
        assert hasattr(cls, "estimate_cost"), f"{cls_name} missing estimate_cost"
        assert hasattr(cls, "submit"), f"{cls_name} missing submit"
        assert hasattr(cls, "get_external_id"), f"{cls_name} missing get_external_id"
        assert hasattr(cls, "poll"), f"{cls_name} missing poll"
        assert hasattr(cls, "download"), f"{cls_name} missing download"
        assert hasattr(cls, "validate_response"), f"{cls_name} missing validate_response"
        assert hasattr(cls, "record_actual_cost"), f"{cls_name} missing record_actual_cost"
        assert hasattr(cls, "cancel_if_supported"), f"{cls_name} missing cancel_if_supported"


def test_estimate_cost_returns_nonzero_for_real_adapters():
    """Real adapters must return a non-zero cost estimate."""
    higgs = paid_adapters.HiggsfieldSeedanceAdapter({})
    cost = higgs.estimate_cost({"model": "seedance_2_0", "duration_sec": 5})
    assert cost > 0

    el = paid_adapters.ElevenLabsAdapter({})
    cost = el.estimate_cost({"text": "Hello world this is a test"})
    assert cost > 0


# --- S3-T02: Deterministic valid-media test providers ---

@pytest.fixture
def test_mode(monkeypatch):
    monkeypatch.setenv("YT_TEST_MODE", "1")
    yield


def test_fake_provider_generates_valid_video(test_mode, tmp_path):
    """The fake provider generates a REAL valid MP4 (not arbitrary bytes)."""
    adapter = FakeProviderAdapter({"duration_sec": 2})
    result = adapter.submit({"prompt": "test"}, "idem_key_1")
    assert result["status"] == "submitted"

    poll = adapter.poll(result["external_job_id"])
    assert poll["status"] == "completed"

    output = tmp_path / "test.mp4"
    adapter.download(result["external_job_id"], output)

    # The downloaded file must be a valid MP4 (ffprobe succeeds)
    info = validate_downloaded_artifact(output)
    assert info["width"] > 0
    assert info["height"] > 0
    assert info["duration_ms"] > 0
    assert info["has_audio"] == 1


def test_fake_provider_corrupt_download(test_mode, tmp_path):
    """Corrupt download mode writes invalid bytes — validate_downloaded_artifact rejects it."""
    adapter = FakeProviderAdapter({"corrupt_download": True})
    result = adapter.submit({"prompt": "test"}, "idem_corrupt")
    output = tmp_path / "corrupt.mp4"
    adapter.download(result["external_job_id"], output)

    with pytest.raises(ProviderAdapterError, match="ffprobe failed"):
        validate_downloaded_artifact(output)


def test_fake_provider_fail_on_submit(test_mode):
    """fail_on_submit raises ProviderAdapterError."""
    adapter = FakeProviderAdapter({"fail_on_submit": True})
    with pytest.raises(ProviderAdapterError, match="fail_on_submit"):
        adapter.submit({"prompt": "test"}, "idem_fail")


def test_fake_provider_fail_on_poll(test_mode):
    """fail_on_poll returns status='failed'."""
    adapter = FakeProviderAdapter({"fail_on_poll": True})
    result = adapter.submit({"prompt": "test"}, "idem_poll")
    poll = adapter.poll(result["external_job_id"])
    assert poll["status"] == "failed"


def test_fake_provider_fail_on_download(test_mode, tmp_path):
    """fail_on_download raises ProviderAdapterError."""
    adapter = FakeProviderAdapter({"fail_on_download": True})
    result = adapter.submit({"prompt": "test"}, "idem_dl")
    with pytest.raises(ProviderAdapterError, match="fail_on_download"):
        adapter.download(result["external_job_id"], tmp_path / "out.mp4")


def test_fake_provider_timeout(test_mode):
    """timeout mode returns status='running' indefinitely."""
    adapter = FakeProviderAdapter({"timeout": True})
    result = adapter.submit({"prompt": "test"}, "idem_timeout")
    poll = adapter.poll(result["external_job_id"])
    assert poll["status"] == "running"


def test_fake_provider_no_audio(test_mode, tmp_path):
    """no_audio mode generates a video without an audio stream."""
    adapter = FakeProviderAdapter({"duration_sec": 2, "no_audio": True})
    result = adapter.submit({"prompt": "test"}, "idem_noaudio")
    output = tmp_path / "noaudio.mp4"
    adapter.download(result["external_job_id"], output)
    info = validate_downloaded_artifact(output)
    assert info["has_audio"] == 0


def test_fake_provider_audio_offset(test_mode, tmp_path):
    """audio_offset_ms mode generates a video with delayed audio (lipsync offset)."""
    adapter = FakeProviderAdapter({"duration_sec": 3, "audio_offset_ms": 80})
    result = adapter.submit({"prompt": "test"}, "idem_offset")
    output = tmp_path / "offset.mp4"
    adapter.download(result["external_job_id"], output)
    info = validate_downloaded_artifact(output)
    assert info["has_audio"] == 1


def test_fake_provider_short_video(test_mode, tmp_path):
    """short_video mode generates a video shorter than requested."""
    adapter = FakeProviderAdapter({"duration_sec": 4, "short_video": True})
    result = adapter.submit({"prompt": "test"}, "idem_short")
    output = tmp_path / "short.mp4"
    adapter.download(result["external_job_id"], output)
    info = validate_downloaded_artifact(output)
    assert info["duration_ms"] < 3000  # ~2s (half of 4s)


def test_fake_provider_long_video(test_mode, tmp_path):
    """long_video mode generates a video longer than requested."""
    adapter = FakeProviderAdapter({"duration_sec": 2, "long_video": True})
    result = adapter.submit({"prompt": "test"}, "idem_long")
    output = tmp_path / "long.mp4"
    adapter.download(result["external_job_id"], output)
    info = validate_downloaded_artifact(output)
    assert info["duration_ms"] > 3000  # ~4s (double 2s)


def test_fake_provider_deterministic_checksum(test_mode, tmp_path):
    """Same config produces same checksum (deterministic for a given duration)."""
    adapter1 = FakeProviderAdapter({"duration_sec": 2})
    adapter2 = FakeProviderAdapter({"duration_sec": 2})

    r1 = adapter1.submit({"prompt": "test"}, "idem_det_1")
    adapter1.download(r1["external_job_id"], tmp_path / "v1.mp4")
    sha1 = validate_downloaded_artifact(tmp_path / "v1.mp4")["sha256"]

    r2 = adapter2.submit({"prompt": "test"}, "idem_det_2")
    adapter2.download(r2["external_job_id"], tmp_path / "v2.mp4")
    sha2 = validate_downloaded_artifact(tmp_path / "v2.mp4")["sha256"]

    # Same duration + same FFmpeg params → same content (black video + silence)
    assert sha1 == sha2, "deterministic test provider must produce same checksum for same config"


def test_corrupt_download_rejected(test_mode, tmp_path):
    """A corrupt download is rejected by validate_downloaded_artifact (S3 named test)."""
    adapter = FakeProviderAdapter({"corrupt_download": True})
    result = adapter.submit({"prompt": "test"}, "idem_reject")
    output = tmp_path / "reject.mp4"
    adapter.download(result["external_job_id"], output)

    with pytest.raises(ProviderAdapterError):
        validate_downloaded_artifact(output)
