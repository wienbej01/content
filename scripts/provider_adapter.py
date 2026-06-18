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
    """Abstract provider adapter (S3-T01: full contract).

    A provider adapter encapsulates all interaction with an external media
    generation service. The contract methods cover the full lifecycle:
    prepare → estimate cost → submit → poll → download → validate → record cost.
    Production must reject test adapters (FakeProviderAdapter); the test adapter
    is only available in YT_TEST_MODE.
    """

    def __init__(self, config: dict):
        self.config = config

    def prepare_request(self, render_unit: dict, render_plan: dict) -> dict:
        """Compile a provider request payload from a render unit + plan.

        Default implementation builds a standard payload; subclasses may override
        to add provider-specific fields (model parameters, references, etc.).
        Returns the request payload dict.
        """
        return {
            "asset_type": render_unit.get("asset_type"),
            "model": render_unit.get("model"),
            "duration_sec": (render_unit.get("required_duration_ms") or 0) / 1000.0,
            "audio_policy": render_unit.get("audio_policy"),
            "prompt": render_plan.get("prompt", ""),
            "negative_prompt": render_plan.get("negative_prompt", ""),
            "aspect_ratio": render_plan.get("aspect_ratio", "16:9"),
        }

    def estimate_cost(self, payload: dict) -> float:
        """Estimate the cost of a request in USD before submission.

        Subclasses must override to return the provider's per-request cost.
        """
        return 0.0

    @abstractmethod
    def submit(self, payload: dict, idempotency_key: str) -> dict:
        """Submit a job. Returns {external_job_id, status, raw_request}."""
        ...

    def get_external_id(self, submit_result: dict) -> str:
        """Extract the external job ID from a submit result.

        Default implementation reads the 'external_job_id' key.
        """
        return submit_result.get("external_job_id", "")

    @abstractmethod
    def poll(self, external_job_id: str) -> dict:
        """Poll job status. Returns {status, raw_response, ...}."""
        ...

    @abstractmethod
    def download(self, external_job_id: str, output_path: Path) -> Path:
        """Download completed artifact. Returns path to downloaded file."""
        ...

    def validate_response(self, downloaded_path: Path, expected_metadata: Optional[dict] = None) -> dict:
        """Validate a downloaded provider response.

        Default implementation delegates to validate_downloaded_artifact (ffprobe
        + SHA). Subclasses may override for provider-specific checks.
        """
        expected_sha = expected_metadata.get("sha256") if expected_metadata else None
        return validate_downloaded_artifact(downloaded_path, expected_sha256=expected_sha)

    def record_actual_cost(self, provider_job_id: str, actual_usd: float, db_path=None) -> dict:
        """Record the actual cost of a completed provider job.

        Delegates to media_service / production_db cost_events. Subclasses may
        override to compute cost from the provider response.
        """
        import production_db as _db
        now = _db._now()
        with _db.transaction(db_path) as conn:
            job = conn.execute(
                "SELECT production_id, provider, operation FROM provider_jobs WHERE id=?",
                (provider_job_id,),
            ).fetchone()
            if not job:
                return {}
            conn.execute(
                """INSERT INTO cost_events
                   (id, production_id, provider_job_id, provider, operation,
                    actual_usd, currency, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (_db._id("cost"), job["production_id"], provider_job_id,
                 job["provider"], job["operation"], actual_usd, "USD", now),
            )
            _db.append_event(
                job["production_id"], "cost_recorded",
                payload={"provider_job_id": provider_job_id, "actual_usd": actual_usd},
                conn=conn,
            )
            return {"provider_job_id": provider_job_id, "actual_usd": actual_usd}

    def cancel_if_supported(self, external_job_id: str) -> dict:
        """Attempt to cancel an in-progress job.

        Default implementation returns unsupported. Subclasses override if the
        provider supports cancellation.
        """
        return {"external_job_id": external_job_id, "cancelled": False,
                "reason": "cancellation not supported by this provider"}


class FakeProviderAdapter(ProviderAdapter):
    """Test-only adapter gated behind YT_TEST_MODE (S3-T02).

    Generates REAL valid media (not arbitrary bytes) via FFmpeg so that
    downstream QA (ffprobe, lipsync, assembly) works correctly. Supports
    controllable failure, offset, corruption, and delay via config to exercise
    the crash matrix and QA failure paths.

    Config keys:
      fail_on_submit: bool       — submit() raises ProviderAdapterError
      fail_on_poll: bool         — poll() returns status='failed'
      fail_on_download: bool     — download() raises ProviderAdapterError
      corrupt_download: bool     — download() writes invalid bytes
      delay_sec: float           — sleep before submit/poll/download
      audio_offset_ms: int       — shift audio track by N ms (lipsync offset)
      short_video: bool          — generate video shorter than requested
      long_video: bool           — generate video longer than requested
      no_audio: bool             — generate video without audio stream
      duplicate_audio: bool      — generate video with duplicated audio stream
      timeout: bool              — poll() returns status='running' forever
    """

    def __init__(self, config: dict):
        super().__init__(config)
        if not _is_test_mode():
            raise ProviderAdapterError(
                "FakeProviderAdapter is only available in YT_TEST_MODE=1")

    def estimate_cost(self, payload: dict) -> float:
        return self.config.get("cost_per_clip_usd", 0.0)

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        if self.config.get("fail_on_submit"):
            raise ProviderAdapterError("FakeProviderAdapter: fail_on_submit configured")
        _delay = self.config.get("delay_sec", 0)
        if _delay:
            time.sleep(_delay)
        job_id = f"fake_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}"
        raw_request = json.dumps(payload, sort_keys=True, default=str)
        return {
            "external_job_id": job_id,
            "status": "submitted",
            "raw_request": raw_request,
        }

    def poll(self, external_job_id: str) -> dict:
        if self.config.get("fail_on_poll"):
            return {
                "external_job_id": external_job_id,
                "status": "failed",
                "raw_response": json.dumps({"simulated": True, "error": "fail_on_poll"}),
                "error": "FakeProviderAdapter: fail_on_poll configured",
            }
        if self.config.get("timeout"):
            return {
                "external_job_id": external_job_id,
                "status": "running",
                "raw_response": json.dumps({"simulated": True, "state": "processing"}),
            }
        return {
            "external_job_id": external_job_id,
            "status": "completed",
            "raw_response": json.dumps({"simulated": True, "job_id": external_job_id}),
            "download_url": f"fake://download/{external_job_id}",
        }

    def download(self, external_job_id: str, output_path: Path) -> Path:
        if self.config.get("fail_on_download"):
            raise ProviderAdapterError("FakeProviderAdapter: fail_on_download configured")
        if self.config.get("corrupt_download"):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"not a valid mp4 file")
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = self.config.get("duration_sec", 5)
        if self.config.get("short_video"):
            duration = max(1, duration * 0.5)
        elif self.config.get("long_video"):
            duration = duration * 2

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:d={duration}:r=24",
        ]
        if self.config.get("no_audio"):
            cmd = cmd + ["-an"]
        elif self.config.get("audio_offset_ms"):
            cmd = cmd + ["-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={duration}",
                         "-af", f"adelay={self.config['audio_offset_ms']}|{self.config['audio_offset_ms']}",
                         "-shortest"]
        elif self.config.get("duplicate_audio"):
            cmd = cmd + ["-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={duration}",
                         "-filter_complex", "[1:a][1:a]amerge=inputs=2[a]",
                         "-map", "0:v", "-map", "[a]", "-shortest"]
        else:
            cmd = cmd + ["-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=48000:duration={duration}",
                         "-shortest"]
        cmd = cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]

        subprocess.run(cmd, capture_output=True, check=True)
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
