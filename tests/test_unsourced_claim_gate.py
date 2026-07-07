"""Tests for TKT-402 unsourced named claim hard gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from write_script import check_unsourced_named_claims, detect_unsourced_named_claims


class TestCheckUnsourcedClaims:
    def _make_brief(self, claims=None, research_text="", sources=None):
        return {
            "research_text": research_text,
            "key_claims": claims or [],
            "sources": sources or [],
        }

    def test_no_claims_ok(self):
        brief = self._make_brief()
        result = check_unsourced_named_claims("", brief, mode="block")
        assert result["blocked"] is False

    def test_warn_mode_returns_claims(self):
        brief = self._make_brief(
            research_text="Smith and Jones found output correlates with AI adoption.",
            claims=[{"claim": "Output correlates with AI adoption", "source": {"url": "http://x.com"}}]
        )
        script_text = "Harold Pemberton published findings that AI triples output."
        result = check_unsourced_named_claims(script_text, brief, mode="warn")
        assert result["blocked"] is False
        assert len(result["claims"]) >= 1

    def test_block_mode_blocks_unknown_claim(self):
        brief = self._make_brief(
            research_text="Smith and Jones found output correlates with AI adoption.",
            claims=[{"claim": "Output correlates with AI adoption", "source": {"url": "http://x.com"}}]
        )
        script_text = "Harold Pemberton published findings that AI triples output."
        result = check_unsourced_named_claims(script_text, brief, mode="block")
        assert result["blocked"] is True
        assert "BLOCKED_UNSOURCED_NAMED_CLAIM" in result["error"]
        assert len(result["claims"]) >= 1

    def test_block_mode_allows_sourced_claims(self):
        brief = self._make_brief(
            research_text="According to Dr. Harold Pemberton, research proves adoption matters.",
            claims=[{"claim": "Dr. Pemberton proved adoption matters", "source": {"url": "http://x.com"}}]
        )
        script_text = "According to Dr. Harold Pemberton, research proves adoption matters."
        result = check_unsourced_named_claims(script_text, brief, mode="block")
        assert result["blocked"] is False

    def test_mode_default_warn(self):
        brief = self._make_brief()
        result = check_unsourced_named_claims("Some script text", brief)
        assert "blocked" in result
        assert "claims" in result
