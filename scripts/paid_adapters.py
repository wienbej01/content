"""R11: Real provider adapters for paid smoke test.

API keys loaded from env vars or ~/.config/ytchannel/runtime.env.
"""
import hashlib, json, os, re, subprocess, tempfile, time
from pathlib import Path
from typing import Any, Optional
from provider_adapter import ProviderAdapter, ProviderAdapterError

import media_contract as _contract

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


# ---------------------------------------------------------------------------
# Poll error classification helpers
# ---------------------------------------------------------------------------
RETRYABLE_PATTERNS = [
    "timeout", "timed out", "connection", "unavailable", "429", "too many requests",
    "rate limit", "temporarily", "try again", "server error", "500", "502", "503",
    "internal error", "capacity",
    "cannot reach", "cannot connect", "connection refused", "connection reset",
    "broken pipe", "eof", "hang up",
]
PERMANENT_PATTERNS = [
    "moderation", "rejected", "content policy", "safety", "inappropriate",
    "invalid parameter", "invalid input", "unsupported", "not allowed",
    "quota exceeded", "billing", "expired", "disabled",
]


def _classify_retryable(error_text: str) -> bool:
    """Classify whether a provider failure is retryable based on error text patterns."""
    text = error_text.lower()
    for pattern in RETRYABLE_PATTERNS:
        if pattern in text:
            return True
    for pattern in PERMANENT_PATTERNS:
        if pattern in text:
            return False
    # Unknown failures are treated as non-retryable (safer)
    return False


def _extract_table_error(table_text: str) -> str:
    """Try to extract error/reason columns from a Higgsfield CLI table output.
    
    The table format uses multi-space column separators or fixed-width layout.
    We split on 2+ spaces to handle multi-word values like "Seedance 2.0"
    and "2026-06-22 13:16".
    """
    lines = [l for l in table_text.splitlines() if l.strip()]
    if len(lines) < 2:
        return ""
    # Split header row on 2+ spaces to determine column count
    header_cols = re.split(r" {2,}", lines[0].strip())
    data_cols = re.split(r" {2,}", lines[1].strip()) if len(lines) > 1 else []
    # Standard columns: ID, DATE, MODEL, STATUS, URL = 5
    if len(data_cols) > 5:
        extra = data_cols[5:]
        return " ".join(extra).strip()
    return ""

# ---------------------------------------------------------------------------
# S10-C10: Submit error classification — retryable (network) vs permanent (app)
# ---------------------------------------------------------------------------
SUBMIT_RETRYABLE_PATTERNS = [
    "cannot reach", "cannot connect", "connection refused",
    "connection reset", "timeout", "timed out",
    "temporarily unavailable", "service unavailable",
    "503", "502", "504", "429",
    "dns", "resolve", "name resolution",
    "network", "no route to host",
    "broken pipe", "connection closed",
    "eof", "hang up",
]
SUBMIT_PERMANENT_PATTERNS = [
    "invalid", "not found", "unauthorized", "forbidden",
    "401", "403", "404",
    "content policy", "moderation", "rejected",
    "insufficient", "quota", "billing",
    "not supported", "bad request",
]


def _is_submit_error_retryable(error_text: str) -> bool:
    """Classify submit errors: retryable (network blip) vs permanent (app rejection).
    
    Network errors may self-resolve in seconds. App errors (invalid params,
    content moderation, auth) must not be retried — they will keep failing.
    """
    text = error_text.lower()
    for pattern in SUBMIT_PERMANENT_PATTERNS:
        if pattern in text:
            return False
    for pattern in SUBMIT_RETRYABLE_PATTERNS:
        if pattern in text:
            return True
    return False  # Unknown errors → safe default (don't retry)


class HiggsfieldSeedanceAdapter(ProviderAdapter):
    """Real Higgsfield Seedance video generation via CLI."""

    def estimate_cost(self, payload: dict) -> float:
        model = payload.get("model", "seedance_2_0")
        duration = float(payload.get("duration_sec", payload.get("duration", 5)))
        # Cost model: $0.04/sec for seedance_2_0, $0.06/sec for seedance_2_0_pro
        rate = 0.06 if "pro" in model else 0.04
        return round(rate * duration, 2)

    # Provider capability mapping: which features each model supports
    PROVIDER_CAPABILITIES = {
        "seedance_2_0": {
            "supports_negative_prompt": False,
            "supports_audio_path": True,
        },
        "kling3_0": {
            "supports_negative_prompt": False,
            "supports_audio_path": False,
        },
    }

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
        # ENG-0202: Adapter-level second guard — enforce contract before any args build
        asset_type = payload.get("asset_type")
        if asset_type and not _contract.is_provider_eligible_asset_type(asset_type):
            raise ProviderAdapterError(
                f"BLOCKED: provider adapter received forbidden asset_type={asset_type}"
            )
        prompt = payload.get("prompt", "")
        reasons = _contract.detect_provider_prompt_text_risks(prompt)
        if reasons:
            raise ProviderAdapterError(
                "BLOCKED: provider adapter received risky prompt. "
                + "; ".join(reasons)
            )
        text_policy = payload.get("text_policy", "")
        if text_policy and text_policy.strip().upper() == "DETERMINISTIC_GRAPHIC":
            raise ProviderAdapterError(
                "BLOCKED: provider adapter received deterministic text spec"
            )

        prompt = payload.get("prompt", "educational video")
        duration = payload.get("duration_sec", payload.get("duration", 5))
        duration_cli = max(1, int(float(duration)))
        aspect = payload.get("aspect_ratio", "16:9")
        model = payload.get("model", "seedance_2_0")

        schema = self.MODEL_PARAMS.get(model, self.MODEL_PARAMS["seedance_2_0"])

        args = [
            "higgsfield", "generate", "create",
            model,
            "--prompt", str(prompt),
            "--duration", str(duration_cli),
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

        # S9-C06: Hero units carry --image (reference frame) + --audio (master slice).
        # --audio only attaches to seedance_2_0 (I4 invariant: only seedance has lipsync).
        image_path = payload.get("image_path")
        audio_path = payload.get("audio_path")

        # REPAIR-601B-W2: when a conditioning audio slice is supplied (hero path),
        # tell the provider NOT to generate its own audio — the slice is authoritative.
        audio_param, audio_vals = schema["audio_param"]
        if audio_path:
            args.extend([f"--{audio_param}", audio_vals[1]])  # false/off
        else:
            args.extend([f"--{audio_param}", audio_vals[0]])  # true/on

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

        # ENG-0203: Capability-gate negative_prompt
        negative_prompt = payload.get("negative_prompt")
        omitted_reason = None
        cap = self.PROVIDER_CAPABILITIES.get(model, {})
        if negative_prompt:
            if cap.get("supports_negative_prompt"):
                args.extend(["--negative_prompt", str(negative_prompt)])
            else:
                omitted_reason = "provider_capability"

        # S9-C06: Dry-run mode returns constructed args without calling subprocess
        if os.environ.get("HIGGSFIELD_DRY_RUN") == "1":
            result = {
                "dry_run": True,
                "args": args,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
            if omitted_reason:
                result["negative_prompt_omitted"] = True
                result["omitted_reason"] = omitted_reason
            return result

        # S10-C10: Retry loop for transient network errors (Cannot reach, timeout, 5xx)
        last_error = None
        for attempt in range(1, 4):
            r = subprocess.run(args, capture_output=True, text=True)
            if r.returncode == 0:
                # Higgsfield CLI may return a table or extra text, not just the UUID.
                # Store only the UUID so later `higgsfield generate get <id>` calls work.
                m = re.search(
                    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                    r.stdout,
                )
                if not m:
                    raise ProviderAdapterError(
                        f"Higgsfield submit returned no UUID: stdout={r.stdout[:500]} stderr={r.stderr[:500]}"
                    )
                job_id = m.group(0)

                return {"external_job_id": job_id, "status": "submitted",
                        "raw_request": json.dumps(payload, sort_keys=True, default=str),
                        "attempts": attempt}

            last_error = (r.stderr or "").strip()
            retryable = _is_submit_error_retryable(last_error)
            if not retryable:
                break  # Don't retry permanent errors (invalid param, auth, moderation)
            if attempt < 3:
                import time as _time
                _time.sleep(2)

        raise ProviderAdapterError(
            f"Higgsfield submit failed after {attempt} attempt(s): {last_error[:500]}"
        )

    def poll(self, external_job_id: str) -> dict:
        r = subprocess.run(["higgsfield", "generate", "get", external_job_id],
                           capture_output=True, text=True)
        if r.returncode != 0:
            # CLI error: capture full stderr for diagnostics
            err_text = r.stderr.strip()
            return {
                "status": "failed",
                "error": f"CLI exit {r.returncode}: {err_text[:500]}",
                "raw_response": err_text,
                "retryable": False,
                "failure_reason": "cli_error",
            }

        raw = r.stdout.strip()

        # Preferred path: JSON output from the CLI/API.
        try:
            data = json.loads(raw)
            state = str(data.get("state", data.get("status", "running"))).lower()
            state_map = {
                "completed": "completed",
                "done": "completed",
                "running": "running",
                "failed": "failed",
                "submitted": "submitted",
                "processing": "running",
                "waiting": "running",
                "queued": "running",
            }
            status = state_map.get(state, "running")
            result = {
                "status": status,
                "raw_response": json.dumps(data, default=str),
            }
            if status == "failed":
                # Extract structured error info from JSON response
                err_msg = data.get("error") or data.get("message") or data.get("error_message") or "unknown"
                err_code = data.get("error_code") or data.get("code") or ""
                reason = data.get("reason") or data.get("failure_reason") or ""
                detail = err_msg
                if reason:
                    detail = f"{err_msg} (reason: {reason})"
                if err_code:
                    detail = f"[{err_code}] {detail}"
                result["error"] = detail
                result["failure_reason"] = reason or err_msg
                result["failure_code"] = err_code
                # Classify retryability
                result["retryable"] = _classify_retryable(detail)
            return result
        except json.JSONDecodeError:
            pass

        # Observed path: Higgsfield CLI returns a human-readable table, e.g.
        # ID DATE MODEL STATUS URL ... completed ...
        lowered = raw.lower()
        padded = f" {lowered} "

        if " failed " in padded or "\nfailed" in lowered:
            # Try to extract any error/reason column from the table
            extra_ctx = _extract_table_error(raw)
            detail = extra_ctx or raw[:500]
            return {
                "status": "failed",
                "raw_response": raw,
                "error": detail,
                "retryable": _classify_retryable(detail),
                "failure_reason": extra_ctx or "provider_returned_failed",
            }

        if " completed " in padded or "\ncompleted" in lowered:
            return {"status": "completed", "raw_response": raw}

        if (
            " waiting " in padded
            or " running " in padded
            or " processing " in padded
            or " submitted " in padded
            or " queued " in padded
        ):
            return {"status": "running", "raw_response": raw}

        # Unknown non-JSON text: do not poison provider_jobs.status with the raw table.
        # Treat as running so the next resume can poll again.
        return {"status": "running", "raw_response": raw}

    def download(self, external_job_id: str, output_path: Path) -> Path:
        # Download a completed Higgsfield video to output_path.
        #
        # Some Higgsfield CLI versions do not accept:
        #   higgsfield generate download <id> --output <path>
        # They do expose the final CloudFront MP4 URL in:
        #   higgsfield generate get <id>
        # So this method prefers direct URL download, then falls back through
        # common CLI download syntaxes.
        import shutil
        import urllib.request

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _accept_candidate(candidate: Path) -> Path | None:
            candidate = Path(candidate)
            if candidate.exists() and candidate.stat().st_size > 0:
                if candidate.resolve() != output_path.resolve():
                    shutil.copy2(candidate, output_path)
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
            return None

        get_result = subprocess.run(
            ["higgsfield", "generate", "get", external_job_id],
            capture_output=True,
            text=True,
        )
        get_raw = (get_result.stdout or "") + "\n" + (get_result.stderr or "")

        m = re.search(r"https?://[^\s]+?\.mp4(?:\?[^\s]+)?", get_raw)
        if m:
            url = m.group(0).rstrip(" ,;|)]}")
            try:
                urllib.request.urlretrieve(url, str(output_path))
                accepted = _accept_candidate(output_path)
                if accepted:
                    return accepted
            except Exception as e:
                last_url_error = str(e)
            else:
                last_url_error = "downloaded URL but output file was missing or empty"
        else:
            last_url_error = f"no .mp4 URL found in generate get output: {get_raw[:500]}"

        attempts = [
            ["higgsfield", "generate", "download", external_job_id, str(output_path)],
            ["higgsfield", "generate", "download", external_job_id, "-o", str(output_path)],
            ["higgsfield", "generate", "download", external_job_id, "--path", str(output_path)],
            ["higgsfield", "generate", "download", external_job_id, "--dir", str(output_path.parent)],
        ]

        errors = [f"url_download: {last_url_error}"]
        for cmd in attempts:
            r = subprocess.run(cmd, capture_output=True, text=True)
            accepted = _accept_candidate(output_path)
            if accepted:
                return accepted

            candidates = sorted(
                output_path.parent.glob("*.mp4"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            for candidate in candidates:
                accepted = _accept_candidate(candidate)
                if accepted:
                    return accepted

            errors.append(
                f"{' '.join(cmd)} -> rc={r.returncode} stderr={r.stderr[:250]} stdout={r.stdout[:250]}"
            )

        with tempfile.TemporaryDirectory(prefix="hf_download_") as td:
            td_path = Path(td)
            r = subprocess.run(
                ["higgsfield", "generate", "download", external_job_id],
                capture_output=True,
                text=True,
                cwd=str(td_path),
            )
            candidates = sorted(
                td_path.glob("*.mp4"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            for candidate in candidates:
                accepted = _accept_candidate(candidate)
                if accepted:
                    return accepted
            errors.append(
                f"cwd temp download -> rc={r.returncode} stderr={r.stderr[:250]} stdout={r.stdout[:250]}"
            )

        raise ProviderAdapterError(
            "Higgsfield download failed for "
            f"{external_job_id}: " + " | ".join(errors)[:1200]
        )


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
        body = {"text": text, "model_id": payload.get("model_id", "eleven_multilingual_v2"),
                "voice_settings": payload.get("voice_settings", {"stability": 0.5, "similarity_boost": 0.75})}
        # Pass speed at top level if provided (ElevenLabs v1 API supports it for newer models)
        vs = payload.get("voice_settings", {})
        speed = vs.get("speed") if isinstance(vs, dict) else None
        if speed is not None:
            body["speed"] = speed
        data = json.dumps(body).encode()
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
