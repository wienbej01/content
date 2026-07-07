"""Tests for TKT-401 citation verification pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from citation_verify import fetch_and_extract, extract_entities, verify_claim, verify_brief


class TestFetchAndExtract:
    def test_file_url(self, tmp_path: Path):
        html = "<html><body><p>Productivity grew by 2.3% annually.</p></body></html>"
        fixture = tmp_path / "test.html"
        fixture.write_text(html)
        text = fetch_and_extract(f"file://{fixture}")
        assert "Productivity grew" in text

    def test_strips_tags(self, tmp_path: Path):
        html = "<html><script>var x = 1;</script><body><p>Content here.</p><style>.a{}</style></body></html>"
        fixture = tmp_path / "test.html"
        fixture.write_text(html)
        text = fetch_and_extract(f"file://{fixture}")
        assert "Content here" in text
        assert "var x" not in text
        assert ".a{}" not in text

    def test_non_file_in_test_mode_raises(self, monkeypatch):
        monkeypatch.setenv("YT_TEST_MODE", "1")
        with pytest.raises(RuntimeError):
            fetch_and_extract("https://example.com")


class TestExtractEntities:
    def test_extracts_capitalized_names(self):
        text = "According to James Harrington and Nicholas Bloom, productivity rose."
        entities = extract_entities(text)
        assert "James Harrington" in entities["names"] or "Nicholas Bloom" in entities["names"]

    def test_extracts_years(self):
        text = "The 2024 study by Smith found output grew by 2.3% in 2019."
        entities = extract_entities(text)
        assert "2024" in entities["years"] or "2019" in entities["years"]

    def test_extracts_percentages(self):
        text = "Productivity grew by 2.3% annually between 2018 and 2024."
        entities = extract_entities(text)
        assert "2.3%" in entities["percentages"]


class TestVerifyClaim:
    def test_perfect_match(self):
        claim = "Productivity grew by 2.3% annually"
        source = "Productivity grew by 2.3% annually between 2018 and 2024."
        score = verify_claim(claim, source)
        assert score >= 0.8

    def test_no_match(self):
        claim = "Hybrid schedules improve retention by 8%"
        source = "Combine two tablespoons of flour with sugar and cinnamon."
        score = verify_claim(claim, source)
        assert score < 0.3

    def test_partial_match(self):
        claim = "Output correlates with AI adoption"
        source = "A study found output correlates with machine learning usage."
        score = verify_claim(claim, source)
        assert 0.3 <= score <= 0.9

    def test_empty_claim_returns_zero(self):
        assert verify_claim("", "some source text") == 0.0


class TestVerifyBrief:
    def test_correctly_sourced(self, tmp_path: Path):
        src = tmp_path / "real.html"
        src.write_text("<html><body>Productivity grew by 2.3% annually.</body></html>")
        brief = {
            "key_claims": [
                {"claim": "Productivity grew by 2.3% annually", "source": {"url": f"file://{src}"}}
            ]
        }
        results = verify_brief(brief)
        assert len(results) == 1
        assert results[0]["verified"] is True
        assert results[0]["confidence"] >= 0.6

    def test_fabricated(self, tmp_path: Path):
        src = tmp_path / "fake.html"
        src.write_text("<html><body>A recipe for cinnamon rolls with flour and sugar.</body></html>")
        brief = {
            "key_claims": [
                {"claim": "Productivity grew by 2.3% annually", "source": {"url": f"file://{src}"}}
            ]
        }
        results = verify_brief(brief)
        assert results[0]["verified"] is False
        assert results[0]["confidence"] < 0.6

    def test_no_source_url_error(self):
        brief = {
            "key_claims": [
                {"claim": "Productivity grew by 2.3% annually"}
            ]
        }
        results = verify_brief(brief)
        assert results[0]["verified"] is False
        assert results[0]["error"] == "no source URL"
