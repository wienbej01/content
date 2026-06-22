"""smoke_config.py — Strict smoke config loader for DB-native media platform.

Loads and validates configs/strict_smoke.yaml.

The config controls:
- strict_media_contract: bool — fail on any media contract violation
- strict_provider_prompt_text_free: bool — fail if provider prompts contain text risks
- strict_local_graphics: bool — fail if local graphic would be sent to provider
- strict_final_qa_contract: bool — fail if final QA contract checks are incomplete
- allow_ocr_unavailable: bool — allow missing OCR to pass QA (default: false)
- max_paid_provider_jobs: int — hard cap on concurrent paid provider jobs
- max_total_usd: float — hard cap on total estimated spend per production

All fields have safe defaults. Missing fields do not crash — they return
the default value for the requested accessor method.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import os
import yaml

ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = ROOT / "configs" / "strict_smoke.yaml"

# ---------------------------------------------------------------------------
# Safe defaults (mirror the YAML values so missing config is not a crash)
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    "strict_media_contract": True,
    "strict_provider_prompt_text_free": True,
    "strict_local_graphics": True,
    "strict_final_qa_contract": True,
    "allow_ocr_unavailable": False,
    "max_paid_provider_jobs": 20,
    "max_total_usd": 5.00,
}


class SmokeConfig:
    """Immutable config snapshot loaded from strict_smoke.yaml.

    Usage:
        cfg = SmokeConfig.load()
        if cfg.strict_media_contract:
            ...
        cap = cfg.max_paid_provider_jobs
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = dict(_DEFAULTS)
        self._data.update(data)

    # --- accessors ---
    @property
    def strict_media_contract(self) -> bool:
        return bool(self._data.get("strict_media_contract", True))

    @property
    def strict_provider_prompt_text_free(self) -> bool:
        return bool(self._data.get("strict_provider_prompt_text_free", True))

    @property
    def strict_local_graphics(self) -> bool:
        return bool(self._data.get("strict_local_graphics", True))

    @property
    def strict_final_qa_contract(self) -> bool:
        return bool(self._data.get("strict_final_qa_contract", True))

    @property
    def allow_ocr_unavailable(self) -> bool:
        return bool(self._data.get("allow_ocr_unavailable", False))

    @property
    def max_paid_provider_jobs(self) -> int:
        return int(self._data.get("max_paid_provider_jobs", 2))

    @property
    def max_total_usd(self) -> float:
        return float(self._data.get("max_total_usd", 0.25))

    # --- structured access ---
    @property
    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> SmokeConfig:
        """Load config from YAML, falling back to defaults for any missing field.

        Args:
            path: path to the YAML config file. Defaults to configs/strict_smoke.yaml.

        Returns:
            SmokeConfig with values merged over safe defaults.
        """
        env_path = os.environ.get("SMOKE_CONFIG_PATH")
        p = path or (Path(env_path) if env_path else _DEFAULT_CONFIG_PATH)
        data: dict[str, Any] = {}
        if p.exists():
            raw = p.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict):
                data = parsed
        return cls(data)
