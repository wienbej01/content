#!/usr/bin/env python3
"""Deterministic research citation fixtures for TKT-003.

Generates three fixture types for testing citation verification:
1. Correctly sourced brief — every key_claim URL points to local HTML containing the claimed content
2. Fabricated brief — one or more key_claim URLs point to local HTML that does NOT contain the claimed content
3. Mixed brief — some claims are sourced, some are fabricated

All outputs are deterministic and hermetic (no network, no paid calls).
"""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Fixture 1: Correctly sourced brief
# ---------------------------------------------------------------------------

CORRECT_SOURCE_HTML = """<!DOCTYPE html>
<html><head><title>Research Brief</title></head>
<body>
<h1>Study Findings</h1>
<p>Shrestha and colleagues (2019) found that 42% of professionals
experience significant productivity loss due to context switching.</p>
<p>The randomized controlled trial at Harvard Business School
demonstrated a 23% improvement in task completion speed when
using structured focus blocks.</p>
<p>Dr. Sarah Mitchell's 2021 study published in the Journal of
Applied Psychology reported that workers who batch email checks
three times daily saw a 17% reduction in perceived stress.</p>
</body></html>
"""


def generate_correctly_sourced_brief(tmp_path: Path) -> dict[str, Any]:
    """Generate a research brief where every claim's URL points to matching local HTML."""
    tmp_path.mkdir(exist_ok=True, parents=True)
    html_path = tmp_path / "source_correct.html"
    html_path.write_text(CORRECT_SOURCE_HTML)

    brief = {
        "seed": "using AI to help memory retention",
        "angle": "AI tools can significantly improve knowledge workers' productivity when used with structured focus techniques.",
        "key_claims": [
            {
                "claim": "42% of professionals experience significant productivity loss due to context switching",
                "source": {
                    "title": "Study on Context Switching",
                    "author_or_site": "Shrestha and colleagues",
                    "year": "2019",
                    "url": str(html_path),
                },
            },
            {
                "claim": "23% improvement in task completion speed when using structured focus blocks",
                "source": {
                    "title": "Harvard Business School RCT",
                    "author_or_site": "Harvard Business School",
                    "year": "2020",
                    "url": str(html_path),
                },
            },
            {
                "claim": "17% reduction in perceived stress when batching email checks three times daily",
                "source": {
                    "title": "Email Batching Study",
                    "author_or_site": "Dr. Sarah Mitchell",
                    "year": "2021",
                    "url": str(html_path),
                },
            },
        ],
        "research_text": "Sourced research text mentioning Shrestha, Harvard Business School, and Dr. Sarah Mitchell.",
        "sources": [
            {"title": "Study on Context Switching", "url": str(html_path), "year": "2019"},
        ],
        "suggested_titles": ["How AI Boosts Memory", "The Focus Formula", "Stop Context Switching"],
    }

    brief_path = tmp_path / "research_brief_correct.json"
    _write_json(brief_path, brief)

    return {
        "brief_path": str(brief_path),
        "html_path": str(html_path),
        "brief": brief,
        "is_fabricated": False,
        "fixture_type": "correctly_sourced",
    }


# ---------------------------------------------------------------------------
# Fixture 2: Fabricated brief
# ---------------------------------------------------------------------------

FABRICATED_SOURCE_HTML = """<!DOCTYPE html>
<html><head><title>Chocolate Cake Recipe</title></head>
<body>
<h1>Grandma's Chocolate Cake</h1>
<p>Ingredients: 2 cups flour, 1 cup sugar, 3 eggs, 1/2 cup cocoa powder,
1 cup milk, 1 tsp vanilla. Bake at 350F for 30 minutes.</p>
<p>This recipe has been in our family since 1952.</p>
</body></html>
"""


def generate_fabricated_brief(tmp_path: Path) -> dict[str, Any]:
    """Generate a research brief where one or more claims point to unrelated HTML."""
    tmp_path.mkdir(exist_ok=True, parents=True)
    html_path = tmp_path / "source_fabricated.html"
    html_path.write_text(FABRICATED_SOURCE_HTML)

    brief = {
        "seed": "using AI to help memory retention",
        "angle": "AI tools can significantly improve knowledge workers' productivity.",
        "key_claims": [
            {
                "claim": "42% of professionals experience significant productivity loss due to context switching",
                "source": {
                    "title": "Study on Context Switching",
                    "author_or_site": "Shrestha and colleagues",
                    "year": "2019",
                    "url": str(html_path),  # This URL does NOT contain the claim
                },
            },
        ],
        "research_text": "Fabricated research text that does not match the source.",
        "sources": [
            {"title": "Chocolate Cake Recipe", "url": str(html_path), "year": "1952"},
        ],
        "suggested_titles": ["How AI Boosts Memory"],
    }

    brief_path = tmp_path / "research_brief_fabricated.json"
    _write_json(brief_path, brief)

    return {
        "brief_path": str(brief_path),
        "html_path": str(html_path),
        "brief": brief,
        "is_fabricated": True,
        "fixture_type": "fabricated",
    }


# ---------------------------------------------------------------------------
# Fixture 3: Mixed brief
# ---------------------------------------------------------------------------

def generate_mixed_brief(tmp_path: Path) -> dict[str, Any]:
    """Generate a brief where some claims are sourced and some are fabricated."""
    tmp_path.mkdir(exist_ok=True, parents=True)
    correct_html = tmp_path / "source_mixed_correct.html"
    correct_html.write_text(CORRECT_SOURCE_HTML)

    fabricated_html = tmp_path / "source_mixed_fabricated.html"
    fabricated_html.write_text(FABRICATED_SOURCE_HTML)

    brief = {
        "seed": "using AI to help memory retention",
        "angle": "AI tools can improve productivity.",
        "key_claims": [
            {
                "claim": "42% of professionals experience significant productivity loss due to context switching",
                "source": {
                    "title": "Study on Context Switching",
                    "author_or_site": "Shrestha and colleagues",
                    "year": "2019",
                    "url": str(correct_html),  # This one IS correct
                },
            },
            {
                "claim": "17% reduction in perceived stress when batching email checks three times daily",
                "source": {
                    "title": "Email Batching Study",
                    "author_or_site": "Dr. Sarah Mitchell",
                    "year": "2021",
                    "url": str(fabricated_html),  # This one is FABRICATED
                },
            },
        ],
        "research_text": "Mixed research text.",
        "sources": [
            {"title": "Study on Context Switching", "url": str(correct_html), "year": "2019"},
            {"title": "Chocolate Cake Recipe", "url": str(fabricated_html), "year": "1952"},
        ],
        "suggested_titles": ["How AI Boosts Memory"],
    }

    brief_path = tmp_path / "research_brief_mixed.json"
    _write_json(brief_path, brief)

    return {
        "brief_path": str(brief_path),
        "html_paths": [str(correct_html), str(fabricated_html)],
        "brief": brief,
        "is_fabricated": False,  # Mixed: not all fabricated
        "has_fabricated_claim": True,
        "fixture_type": "mixed",
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def correctly_sourced_brief(tmp_path):
    yield generate_correctly_sourced_brief(tmp_path)


@pytest.fixture
def fabricated_brief(tmp_path):
    yield generate_fabricated_brief(tmp_path)


@pytest.fixture
def mixed_brief(tmp_path):
    yield generate_mixed_brief(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_correctly_sourced(correctly_sourced_brief):
    """Correctly sourced brief: every claim's URL contains the claimed content."""
    meta = correctly_sourced_brief
    assert Path(meta["brief_path"]).exists()
    assert Path(meta["html_path"]).exists()
    assert meta["is_fabricated"] is False

    # Read the HTML and verify the claimed content is present
    html = Path(meta["html_path"]).read_text()
    for claim in meta["brief"]["key_claims"]:
        # Extract key terms from the claim (numbers, names)
        key_terms = []
        for word in claim["claim"].split():
            if word[0].isupper() or word[0].isdigit():
                key_terms.append(word)
        # At least one key term should appear in the HTML
        assert any(term in html for term in key_terms), f"No key terms from claim found in HTML: {key_terms}"


def test_fabricated(fabricated_brief):
    """Fabricated brief: the claim's URL does NOT contain the claimed content."""
    meta = fabricated_brief
    assert Path(meta["brief_path"]).exists()
    assert Path(meta["html_path"]).exists()
    assert meta["is_fabricated"] is True

    html = Path(meta["html_path"]).read_text()
    for claim in meta["brief"]["key_claims"]:
        # The claim mentions "42% of professionals" — the HTML is a cake recipe
        key_terms = []
        for word in claim["claim"].split():
            if word[0].isdigit():
                key_terms.append(word)
        # The key numeric terms should NOT be in the HTML
        for term in key_terms:
            assert term not in html, f"Key term '{term}' found in fabricated HTML (should not be)"


def test_mixed(mixed_brief):
    """Mixed brief: some claims are sourced, some are fabricated."""
    meta = mixed_brief
    assert Path(meta["brief_path"]).exists()
    assert meta["has_fabricated_claim"] is True
    assert meta["fixture_type"] == "mixed"

    brief = _read_json(Path(meta["brief_path"]))
    assert len(brief["key_claims"]) == 2


def test_fixture_determinism(tmp_path):
    """Same inputs produce same HTML output (SHA-256 match across runs)."""
    m1 = generate_correctly_sourced_brief(tmp_path / "run1")
    m2 = generate_correctly_sourced_brief(tmp_path / "run2")
    # Compare the HTML source (deterministic), not the brief JSON (contains absolute paths)
    h1 = _sha256(Path(m1["html_path"]))
    h2 = _sha256(Path(m2["html_path"]))
    assert h1 == h2, "correctly sourced HTML generation is not deterministic"


def test_brief_json_schema(correctly_sourced_brief):
    """Brief JSON has the expected schema."""
    brief = correctly_sourced_brief["brief"]
    assert "seed" in brief
    assert "angle" in brief
    assert "key_claims" in brief
    assert "research_text" in brief
    assert "sources" in brief
    assert "suggested_titles" in brief
    for claim in brief["key_claims"]:
        assert "claim" in claim
        assert "source" in claim
        assert "url" in claim["source"]
