"""Tests for TKT-302 b-roll hybrid router."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from broll_router import StockAdapter, GenerativeAdapter, select_adapter


class TestStockAdapter:
    def test_can_handle_when_mode_off(self, monkeypatch):
        monkeypatch.setenv("STOCK_FOOTAGE_MODE", "off")
        adapter = StockAdapter()
        assert adapter.can_handle({}) is False

    def test_can_handle_when_mode_test(self, monkeypatch):
        monkeypatch.setenv("STOCK_FOOTAGE_MODE", "test")
        adapter = StockAdapter()
        assert adapter.can_handle({}) is True

    def test_generate_test_mode(self, monkeypatch):
        monkeypatch.setenv("STOCK_FOOTAGE_MODE", "test")
        adapter = StockAdapter()
        path = adapter.generate({})
        assert path.endswith("sample_clip.mp4")

    def test_cost_zero(self):
        adapter = StockAdapter()
        assert adapter.cost_estimate_usd({}) == 0.0


class TestGenerativeAdapter:
    def test_always_handles(self):
        assert GenerativeAdapter().can_handle({}) is True

    def test_cost_nonzero(self):
        assert GenerativeAdapter().cost_estimate_usd({}) > 0


class TestSelectAdapter:
    def test_generative_mode_returns_generative(self, monkeypatch):
        monkeypatch.setenv("BROLL_ROUTER_MODE", "generative")
        adapter = select_adapter({})
        assert isinstance(adapter, GenerativeAdapter)

    def test_hybrid_mode_prefers_stock(self, monkeypatch):
        monkeypatch.setenv("BROLL_ROUTER_MODE", "hybrid")
        monkeypatch.setenv("STOCK_FOOTAGE_MODE", "test")
        adapter = select_adapter({})
        assert isinstance(adapter, StockAdapter)

    def test_hybrid_mode_falls_back_to_generative(self, monkeypatch):
        monkeypatch.setenv("BROLL_ROUTER_MODE", "hybrid")
        monkeypatch.setenv("STOCK_FOOTAGE_MODE", "off")
        adapter = select_adapter({})
        assert isinstance(adapter, GenerativeAdapter)
