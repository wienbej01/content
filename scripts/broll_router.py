"""TKT-302: B-roll hybrid router.

Priority-ordered router for b-roll generation:
  1. Stock adapter (Pexels — external footage)
  2. Still + depth-warped adapter (CPU/MiDaS)
  3. Generative adapter (Kling/Seedance)

Config flag: BROLL_ROUTER_MODE = generative|hybrid (default generative).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


class BrollAdapter(ABC):
    @abstractmethod
    def can_handle(self, beat: dict) -> bool:
        ...

    @abstractmethod
    def generate(self, beat: dict) -> str:
        """Return clip path."""
        ...

    @abstractmethod
    def cost_estimate_usd(self, beat: dict) -> float:
        ...


class StockAdapter(BrollAdapter):
    def can_handle(self, beat: dict) -> bool:
        return os.environ.get("STOCK_FOOTAGE_MODE", "off") != "off"

    def generate(self, beat: dict) -> str:
        env = os.environ.get("STOCK_FOOTAGE_MODE", "off")
        if env == "test":
            return str(Path(__file__).parent / ".." / "tests" / "fixtures" / "stock" / "sample_clip.mp4")
        return ""

    def cost_estimate_usd(self, beat: dict) -> float:
        return 0.0


class StillDepthAdapter(BrollAdapter):
    def can_handle(self, beat: dict) -> bool:
        return False

    def generate(self, beat: dict) -> str:
        return ""

    def cost_estimate_usd(self, beat: dict) -> float:
        return 0.0


class GenerativeAdapter(BrollAdapter):
    def can_handle(self, beat: dict) -> bool:
        return True

    def generate(self, beat: dict) -> str:
        return ""

    def cost_estimate_usd(self, beat: dict) -> float:
        return 1.0


_ADAPTERS = [StockAdapter(), StillDepthAdapter(), GenerativeAdapter()]


def select_adapter(beat: dict) -> BrollAdapter | None:
    """Return highest-priority adapter that can handle the beat."""
    mode = os.environ.get("BROLL_ROUTER_MODE", "generative")
    if mode == "generative":
        return next((a for a in _ADAPTERS if isinstance(a, GenerativeAdapter)), None)
    for adapter in _ADAPTERS:
        if adapter.can_handle(beat):
            return adapter
    return None
