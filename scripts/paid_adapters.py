"""R11: Real provider adapters for paid smoke test.

API keys loaded from env vars or ~/.config/ytchannel/runtime.env.
"""
import hashlib, json, os, subprocess, tempfile, time
from pathlib import Path
from typing import Any, Optional
from provider_adapter import ProviderAdapter, ProviderAdapterError

ROOT = Path(__file__).resolve().parent.parent


def _load_runtime_env() -> dict:
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
    return os.environ.get(key) or _RUNTIME_ENV.get(key, "")


class HiggsfieldSeedanceAdapter(ProviderAdapter):
    """Real Higgsfield Seedance video generation via CLI."""

    def estimate_cost(self, payload: dict) -> float:
        model = payload.get("model", "seedance_2_0")
        duration = float(payload.get("duration_sec", payload.get("duration", 5)))
        # Cost model: $0.04/sec for seedance_2_0, $0.06/sec for seedance_2_0_pro
        rate = 0.06 if "pro" in model else 0.04
        return round(rate * duration, 2)

    # Per-model param schemas (from `higgsfield model get <model>`)
    MODEL_PARAMS = {
        "seedance_2_0": {
            "mode": ("std", "fast"),
            "aspect_ratio": ("auto", "16:9", "9:16", "4:3", "3:4", "1:1", "21:9"),
            "resolution": ("480p", "720p", "1080p"),
            "has_resolution": True,
            "audio_param": ("generate_audio", ("true", "false")),
        },
        "kling3_0": {
            "mode": ("pro", "std", "4k"),
            "aspect_ratio": ("16:9", "9:16", "1:1"),
            "has_resolution": False,
            "audio_param": ("sound", ("on", "off")),
        },
    }

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        prompt = payload.get("prompt", "educational video")
        duration = payload.get("duration_sec", payload.get("duration", 5))
        aspect = payload.get("aspect_ratio", "16:9")
        model = payload.get("model", "seedance_2_0")

        schema = self.MODEL_PARAMS.get(model, self.MODEL_PARAMS["seedance_2_0"])

        args = [
            "higgsfield", "generate", "create",
            model,
            "--prompt", str(prompt),
            "--duration", str(int(duration)),
            "--aspect_ratio", str(aspect),
        ]

        # Mode: use payload value if valid for this model, else use model default
        mode = payload.get("mode")
        if mode and mode in schema["mode"]:
            args.extend(["--mode", str(mode)])
        else:
            args.extend(["--mode", schema["mode"][0]])  # default = first allowed

        # Resolution: only for models that support it
        if schema.get("has_resolution"):
            resolution = payload.get("resolution", "480p")
            if resolution in schema["resolution"]:
                args.extend(["--resolution", str(resolution)])
            else:
                args.extend(["--resolution", "480p"])

        # Audio: seedance uses generate_audio (bool), kling uses sound (on/off)
        audio_param, audio_vals = schema["audio_param"]
        args.extend([f"--{audio_param}", audio_vals[0]])  # default = first (true/on)

        # S9-C06: Hero units carry --image (reference frame) + --audio (master slice).
        # --audio only attaches to seedance_2_0 (I4 invariant: only seedance has lipsync).
        image_path = payload.get("image_path")
        audio_path = payload.get("audio_path")

        if image_path:
            args.extend(["--image", str(image_path)])

        if audio_path:
            # Fail loud if a non-seedance model requests --audio (I4 invariant)
            if "seedance" not in model:
                raise ProviderAdapterError(
                    f"I4 invariant violation: --audio requires seedance_2_0, "
                    f"but model={model} was requested with audio_path={audio_path}. "
                    f"Hero lipsync audio is seedance-only."
                )
            args.extend(["--audio", str(audio_path)])

        # S9-C06: Dry-run mode returns constructed args without calling subprocess
        if os.environ.get("HIGGSFIELD_DRY_RUN") == "1":
            return {
                "dry_run": True,
                "args": args,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }

        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise ProviderAdapterError(f"Higgsfield submit failed: {r.stderr[:500]}")
        job_id = r.stdout.strip()
        return {"external_job_id": job_id, "status": "submitted",
                "raw_request": json.dumps(payload, sort_keys=True, default=str)}

    def poll(self, external_job_id: str) -> dict:
        r = subprocess.run(["higgsfield", "generate", "get", external_job_id],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {"status": "failed", "error": r.stderr[:500]}
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            data = {"state": r.stdout.strip()}
        state = data.get("state", data.get("status", "running"))
        state_map = {"completed": "completed", "done": "completed", "running": "running",
                     "failed": "failed", "submitted": "submitted", "processing": "running"}
        return {"status": state_map.get(state, state), "raw_response": json.dumps(data, default=str)}

    def download(self, external_job_id: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["higgsfield", "generate", "download", external_job_id,
                            "--output", str(output_path)], capture_output=True, text=True)
        if r.returncode != 0 and not output_path.exists():
            raise ProviderAdapterError(f"Higgsfield download failed: {r.stderr[:500]}")
        return output_path


class ElevenLabsAdapter(ProviderAdapter):
    """Real ElevenLabs TTS via REST API."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._api_key = config.get("api_key") or _get_cred("ELEVENLABS_API_KEY")
        self._voice_id = config.get("voice_id") or _get_cred("ELEVENLABS_VOICE_ID")

    def estimate_cost(self, payload: dict) -> float:
        text = payload.get("text", "")
        char_count = len(text)
        # ElevenLabs: ~$0.30 per 1000 chars for multilingual_v2
        return round(0.30 * (char_count / 1000.0), 4)

    def _check_auth(self):
        if not self._api_key:
            raise ProviderAdapterError("ELEVENLABS_API_KEY not set")

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        self._check_auth()
        import urllib.request, urllib.error
        voice_id = self._voice_id or payload.get("voice_id", "")
        text = payload.get("text", "")
        data = json.dumps({"text": text, "model_id": payload.get("model_id", "eleven_multilingual_v2"),
                          "voice_settings": payload.get("voice_settings", {"stability": 0.5, "similarity_boost": 0.75})}).encode()
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                                     data=data, headers={"Content-Type": "application/json", "xi-api-key": self._api_key}, method="POST")
        try:
            resp = urllib.request.urlopen(req)
            audio_data = resp.read()
        except urllib.error.HTTPError as e:
            raise ProviderAdapterError(f"ElevenLabs API error: {e.code}")
        job_id = f"el_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}"
        audio_path = Path(tempfile.mkdtemp(prefix="el_tts_")) / "narration.mp3"
        audio_path.write_bytes(audio_data)
        return {"external_job_id": job_id, "status": "completed",
                "raw_request": json.dumps(payload, sort_keys=True, default=str),
                "audio_path": str(audio_path), "audio_size_bytes": len(audio_data)}

    def poll(self, external_job_id: str) -> dict:
        return {"status": "completed"}

    def download(self, external_job_id: str, output_path: Path) -> Path:
        raise ProviderAdapterError("ElevenLabs returns audio inline")


def _register():
    from provider_adapter import ADAPTERS
    ADAPTERS["higgsfield"] = HiggsfieldSeedanceAdapter
    ADAPTERS["elevenlabs"] = ElevenLabsAdapter

_register()
