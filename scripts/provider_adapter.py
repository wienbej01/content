"""Sprint 4/R4: Provider Adapter Interface (R4-002).

Abstract interface for external media providers (Higgsfield/Seedance, ElevenLabs, etc.).
The fake adapter is gated behind YT_TEST_MODE and never runs in production.
Real adapters implement submit() / poll() / download() with full provenance.

Usage:
  adapter = get_provider_adapter(provider_name)
  job = adapter.submit(request_payload, idempotency_key)
  state = adapter.poll(job["external_job_id"])
  path = adapter.download(job["external_job_id"], output_path)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent


class ProviderAdapterError(RuntimeError):
    pass


class ProviderAdapter(ABC):
    """Abstract provider adapter."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def submit(self, payload: dict, idempotency_key: str) -> dict:
        """Submit a job. Returns {external_job_id, status, raw_request}."""
        ...

    @abstractmethod
    def poll(self, external_job_id: str) -> dict:
        """Poll job status. Returns {status, raw_response, ...}."""
        ...

    @abstractmethod
    def download(self, external_job_id: str, output_path: Path) -> Path:
        """Download completed artifact. Returns path to downloaded file."""
        ...


class FakeProviderAdapter(ProviderAdapter):
    """Test-only adapter gated behind YT_TEST_MODE."""

    def __init__(self, config: dict):
        super().__init__(config)
        if not _is_test_mode():
            raise ProviderAdapterError(
                "FakeProviderAdapter is only available in YT_TEST_MODE=1"
            )

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        job_id = f"fake_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}"
        raw_request = json.dumps(payload, sort_keys=True, default=str)
        return {
            "external_job_id": job_id,
            "status": "submitted",
            "raw_request": raw_request,
        }

    def poll(self, external_job_id: str) -> dict:
        return {
            "external_job_id": external_job_id,
            "status": "completed",
            "raw_response": json.dumps({"simulated": True, "job_id": external_job_id}),
            "download_url": f"fake://download/{external_job_id}",
        }

    def download(self, external_job_id: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:d=5:r=24",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000:duration=5",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_path),
        ], capture_output=True, check=True)
        return output_path


ADAPTERS = {
    "fake": FakeProviderAdapter,
    "higgsfield": None,
    "elevenlabs": None,
    "kling": None,
}


def _is_test_mode() -> bool:
    return os.environ.get("YT_TEST_MODE") == "1"


def get_provider_adapter(provider_name: str, config: Optional[dict] = None) -> ProviderAdapter:
    if provider_name == "fake" and not _is_test_mode():
        raise ProviderAdapterError(
            f"R4-002: provider '{provider_name}' requires YT_TEST_MODE=1. "
            "Configure a real provider adapter for production."
        )
    if _is_test_mode() and provider_name not in ("fake",):
        return FakeProviderAdapter(config or {})
    adapter_cls = ADAPTERS.get(provider_name)
    if adapter_cls is None:
        raise ProviderAdapterError(f"No adapter registered for provider: {provider_name}")
    return adapter_cls(config or {})


def validate_downloaded_artifact(path: Path, expected_sha256: Optional[str] = None) -> dict:
    """Probe downloaded artifact and verify integrity. Returns {sha256, duration_ms, width, height, has_audio}."""
    if not path.exists() or path.stat().st_size == 0:
        raise ProviderAdapterError(f"Downloaded artifact is empty or missing: {path}")

    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            sha.update(chunk)
    actual_sha = sha.hexdigest()

    if expected_sha256 and actual_sha != expected_sha256:
        raise ProviderAdapterError(
            f"SHA-256 mismatch for {path}: expected {expected_sha256[:16]}, got {actual_sha[:16]}"
        )

    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(path),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise ProviderAdapterError(f"ffprobe failed on {path}: {result.stderr[:200]}")

    probe = json.loads(result.stdout)
    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]

    return {
        "sha256": actual_sha,
        "duration_ms": int(float(fmt.get("duration", 0)) * 1000),
        "width": int(video[0].get("width", 0)) if video else 0,
        "height": int(video[0].get("height", 0)) if video else 0,
        "has_audio": 1 if audio else 0,
        "format_name": fmt.get("format_name", ""),
        "size_bytes": int(fmt.get("size", 0)),
    }
