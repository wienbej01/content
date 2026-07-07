"""Tests for TKT-404 source diversity gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from source_diversity import check_source_diversity


class TestSourceDiversityOff:
    def test_off_mode_always_passes(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DIVERSITY_MODE", "off")
        brief = {"key_claims": [{"source": {"author": "Smith"}}] * 10}
        result = check_source_diversity(brief)
        assert result["passed"] is True
        assert result["mode"] == "off"


class TestSourceDiversityOn:
    def test_single_source_80_percent_rejected(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DIVERSITY_MODE", "on")
        claims = [{"source": {"author": "Smith"}}] * 8 + [{"source": {"author": "Jones"}}] * 2
        brief = {"key_claims": claims}
        result = check_source_diversity(brief)
        assert result["passed"] is False
        assert result["max_fraction"] >= 0.4
        assert result["dominant_source"] == "Smith"

    def test_diverse_sources_pass(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DIVERSITY_MODE", "on")
        claims = [{"source": {"author": f"Author_{i}"}} for i in range(10)]
        brief = {"key_claims": claims}
        result = check_source_diversity(brief)
        assert result["passed"] is True

    def test_empty_claims_pass(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DIVERSITY_MODE", "on")
        result = check_source_diversity({"key_claims": []})
        assert result["passed"] is True

    def test_no_sources_pass(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DIVERSITY_MODE", "on")
        brief = {"key_claims": [{"claim": "some claim"}]}
        result = check_source_diversity(brief)
        assert result["passed"] is True
