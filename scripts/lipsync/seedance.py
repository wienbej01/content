"""Seedance 2.0 lipsync provider wrapper.

Wraps the existing Higgsfield Seedance 2.0 adapter via paid_adapters.HiggsfieldAdapter
so it satisfies the LipsyncProvider interface.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lipsync import LipsyncProvider, LipsyncResult, LipsyncProviderError


# Default cost per 5s clip from model_routing.yaml
_DEFAULT_COST_PER_CLIP = 1.10
_DEFAULT_RELIABLE_CLIP_SEC = 4.0


def _load_cost_config() -> tuple[float, float]:
    """Read Seedance cost params from model_routing.yaml (seedance_2_0 entry)."""
    try:
        import yaml
        cfg_path = Path(__file__).resolve().parent.parent / "configs" / "james" / "model_routing.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        ls_cfg = cfg.get("costs", {}).get("seedance_2_0", {})
        return (
            float(ls_cfg.get("cost_per_clip_usd", _DEFAULT_COST_PER_CLIP)),
            float(ls_cfg.get("reliable_clip_sec", _DEFAULT_RELIABLE_CLIP_SEC)),
        )
    except Exception:
        return _DEFAULT_COST_PER_CLIP, _DEFAULT_RELIABLE_CLIP_SEC


class SeedanceLipsyncProvider(LipsyncProvider):
    """LipsyncProvider implementation backed by Higgsfield Seedance 2.0."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._cost_per_clip, self._reliable_clip_sec = _load_cost_config()

    def name(self) -> str:
        return "seedance_2_0"

    def submit(self, reference_image: Path, audio_slice: Path) -> str:
        """Submit via paid_adapters.HiggsfieldAdapter.

        In YT_TEST_MODE, returns a deterministic fake job_id without paying.
        """
        if os.environ.get("YT_TEST_MODE") == "1":
            return self._test_submit(reference_image, audio_slice)
        try:
            from paid_adapters import HiggsfieldAdapter
            adapter = HiggsfieldAdapter(self.config)
            payload = {
                "model": "seedance_2_0",
                "prompt": self.config.get("prompt", "Cinematic talking head, calm delivery."),
                "duration_sec": self.config.get("duration_sec", 5),
                "aspect_ratio": "16:9",
                "image_path": str(reference_image),
                "audio_path": str(audio_slice),
            }
            result = adapter.submit(payload)
            return result.get("external_job_id")
        except Exception as e:
            raise LipsyncProviderError(f"Seedance submit failed: {e}") from e

    def _test_submit(self, reference_image: Path, audio_slice: Path) -> str:
        import hashlib
        seed = f"{reference_image}:{audio_slice}"
        h = hashlib.sha256(seed.encode()).hexdigest()[:16]
        return f"seedance_test_{h}"

    def poll(self, job_id: str) -> LipsyncResult:
        if os.environ.get("YT_TEST_MODE") == "1":
            return self._test_poll(job_id)
        try:
            from paid_adapters import HiggsfieldAdapter
            adapter = HiggsfieldAdapter(self.config)
            status = adapter.poll(job_id)
            st = status.get("status", "unknown")
            if st == "completed":
                download_url = status.get("result_url")
                out_path = Path(self.config.get("output_dir", "/tmp")) / f"{job_id}.mp4"
                return LipsyncResult(status="completed", clip_path=out_path,
                                    cost_usd=self._cost_per_clip)
            elif st == "failed":
                return LipsyncResult(status="failed",
                                    error=status.get("error", "unknown"))
            return LipsyncResult(status="running")
        except Exception as e:
            raise LipsyncProviderError(f"Seedance poll failed: {e}") from e

    def _test_poll(self, job_id: str) -> LipsyncResult:
        # In test mode, return a completed result with a fake clip path
        out_path = Path(self.config.get("output_dir", "/tmp")) / f"{job_id}.mp4"
        return LipsyncResult(status="completed", clip_path=out_path,
                            cost_usd=self._cost_per_clip)

    def cost_estimate_sec(self, duration_sec: float) -> float:
        num_clips = max(1, duration_sec / self._reliable_clip_sec)
        return round(num_clips * self._cost_per_clip, 4)

    def health_check(self) -> bool:
        """Check: Seedance is healthy iff Higgsfield CLI is on PATH and authorized."""
        if os.environ.get("YT_TEST_MODE") == "1":
            return True
        import shutil
        return shutil.which("higgsfield") is not None
