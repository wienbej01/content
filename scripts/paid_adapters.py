"""R11: Real provider adapters for paid smoke test.

HiggsfieldSeedanceAdapter — wraps the Higgsfield CLI for video generation.
ElevenLabsAdapter — wraps the ElevenLabs API for TTS narration.

API keys are loaded from:
  1. Environment variables (highest priority)
  2. ~/.config/ytchannel/runtime.env (legacy fallback)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from provider_adapter import ProviderAdapter, ProviderAdapterError

ROOT = Path(__file__).resolve().parent.parent


def _load_runtime_env() -> dict:
    """Load key-value pairs from ~/.config/ytchannel/runtime.env if present."""
    env_path = Path.home() / ".config" / "ytchannel" / "runtime.env"
    if not env_path.exists():
        return {}
    result = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip()
    return result


_RUNTIME_ENV = _load_runtime_env()


def _get_cred(key: str) -> str:
    """Get credential: env var first, then runtime.env."""
    val = os.environ.get(key)
    if val:
        return val
    return _RUNTIME_ENV.get(key, "")


class HiggsfieldSeedanceAdapter(ProviderAdapter):
    """Real Higgsfield/Seedance video generation via CLI."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._cli = config.get("cli_path", "higgsfield")
        self._api_key = config.get("api_key") or _get_cred("HIGGSFIELD_API_KEY")

    def _check_auth(self):
        if not self._api_key:
            raise ProviderAdapterError(
                "HIGGSFIELD_API_KEY not set. Run 'higgsfield login' or export HIGGSFIELD_API_KEY."
            )

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        self._check_auth()
        job_id = f"hf_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}"

        request_file = Path(tempfile.mkdtemp(prefix="hf_req_")) / "request.json"
        request_file.write_text(json.dumps({
            "model": payload.get("model", "seedance_2_0"),
            "image_path": payload.get("image_path", ""),
            "audio_path": payload.get("audio_path", ""),
            "prompt": payload.get("prompt", ""),
            "negative_prompt": payload.get("negative_prompt", ""),
            "duration_sec": payload.get("duration_sec", 5),
            "aspect_ratio": payload.get("aspect_ratio", "16:9"),
        }, indent=2))

        r = subprocess.run([
            self._cli, "generate",
            "--request", str(request_file),
            "--output-dir", str(request_file.parent),
        ], capture_output=True, text=True, env={**os.environ, "HIGGSFIELD_API_KEY": self._api_key})

        if r.returncode != 0:
            raise ProviderAdapterError(f"Higgsfield submit failed: {r.stderr[:500]}")

        try:
            result = json.loads(r.stdout)
            return {
                "external_job_id": result.get("job_id", job_id),
                "status": "submitted",
                "raw_request": json.dumps(payload, sort_keys=True, default=str),
            }
        except json.JSONDecodeError:
            return {
                "external_job_id": job_id,
                "status": "submitted",
                "raw_request": json.dumps(payload, sort_keys=True, default=str),
                "raw_response": r.stdout[:1000],
            }

    def poll(self, external_job_id: str) -> dict:
        self._check_auth()
        r = subprocess.run([
            self._cli, "status", external_job_id,
        ], capture_output=True, text=True, env={**os.environ, "HIGGSFIELD_API_KEY": self._api_key})

        if r.returncode != 0:
            return {"status": "failed", "error": r.stderr[:500], "raw_response": r.stderr}

        try:
            result = json.loads(r.stdout)
        except json.JSONDecodeError:
            result = {"output": r.stdout}

        status_map = {
            "completed": "completed",
            "done": "completed",
            "processing": "running",
            "running": "running",
            "failed": "failed",
            "submitted": "submitted",
        }
        raw_status = result.get("status", result.get("state", "running"))
        return {
            "status": status_map.get(raw_status, raw_status),
            "raw_response": json.dumps(result, default=str),
            "download_url": result.get("download_url") or result.get("output_path"),
        }

    def download(self, external_job_id: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([
            self._cli, "download", external_job_id, "--output", str(output_path),
        ], capture_output=True, text=True, env={**os.environ, "HIGGSFIELD_API_KEY": self._api_key})

        if r.returncode != 0:
            raise ProviderAdapterError(f"Higgsfield download failed: {r.stderr[:500]}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ProviderAdapterError(f"Download produced empty file: {output_path}")

        return output_path


class ElevenLabsAdapter(ProviderAdapter):
    """Real ElevenLabs TTS narration generation."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._api_key = config.get("api_key") or _get_cred("ELEVENLABS_API_KEY")
        self._voice_id = config.get("voice_id") or _get_cred("ELEVENLABS_VOICE_ID")

    def _check_auth(self):
        if not self._api_key:
            raise ProviderAdapterError(
                "ELEVENLABS_API_KEY not set. Add to ~/.config/ytchannel/runtime.env or export ELEVENLABS_API_KEY."
            )

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        self._check_auth()
        import urllib.request, urllib.error

        voice_id = self._voice_id or payload.get("voice_id", "")
        text = payload.get("text", "")

        if not voice_id or not text:
            raise ProviderAdapterError("voice_id and text are required for ElevenLabs TTS")

        data = json.dumps({
            "text": text,
            "model_id": payload.get("model_id", "eleven_multilingual_v2"),
            "voice_settings": payload.get("voice_settings", {
                "stability": 0.5,
                "similarity_boost": 0.75,
            }),
        }).encode()

        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=data,
            headers={
                "Content-Type": "application/json",
                "xi-api-key": self._api_key,
            },
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req)
            audio_data = resp.read()
        except urllib.error.HTTPError as e:
            raise ProviderAdapterError(f"ElevenLabs API error: {e.code} {e.reason}")

        if not audio_data:
            raise ProviderAdapterError("ElevenLabs returned empty audio")

        job_id = f"el_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}"
        audio_path = Path(tempfile.mkdtemp(prefix="el_tts_")) / "narration.mp3"
        audio_path.write_bytes(audio_data)

        return {
            "external_job_id": job_id,
            "status": "completed",
            "raw_request": json.dumps(payload, sort_keys=True, default=str),
            "audio_path": str(audio_path),
            "audio_size_bytes": len(audio_data),
        }

    def poll(self, external_job_id: str) -> dict:
        return {"status": "completed", "raw_response": json.dumps({"status": "completed"})}

    def download(self, external_job_id: str, output_path: Path) -> Path:
        raise ProviderAdapterError("ElevenLabs adapter returns audio inline; use submit() output path")


def _register_real_adapters():
    """Register real adapters if credentials are available."""
    from provider_adapter import ADAPTERS
    ADAPTERS["higgsfield"] = HiggsfieldSeedanceAdapter
    ADAPTERS["elevenlabs"] = ElevenLabsAdapter


_register_real_adapters()
