"""Tests for TKT-403 claim strength mapper."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from claim_strength import map_claim_strength, map_claim_strength_for_claim


class TestMapClaimStrength:
    def test_settled_science(self):
        assert map_claim_strength("Research proves that AI transforms productivity.") == "settled_science"
        assert map_claim_strength("Studies show consistent results across trials.") == "settled_science"

    def test_single_study(self):
        assert map_claim_strength("One study found a 2.3% increase in output.") == "single_study"
        assert map_claim_strength("A single trial reported modest gains.") == "single_study"

    def test_quote(self):
        assert map_claim_strength("According to Dr. Smith, AI adoption correlates with output.") == "quote"
        assert map_claim_strength("As noted by the researchers, results were mixed.") == "quote"

    def test_observation(self):
        assert map_claim_strength("An observation suggests further study is needed.") == "observation"
        assert map_claim_strength("One might observe a correlation.") == "observation"

    def test_default_observation(self):
        assert map_claim_strength("The weather is nice today.") == "observation"

    def test_for_claim_dict(self):
        claim = {"claim": "Output grew by 2.3%", "source": {"text": "One study found output grew."}}
        assert map_claim_strength_for_claim(claim) == "single_study"

    def test_for_claim_string(self):
        assert map_claim_strength_for_claim("Research proves this works.") == "settled_science"
