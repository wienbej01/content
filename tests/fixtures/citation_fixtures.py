"""Deterministic, hermetic citation verification fixtures.

Three fixture generators for the citation QC ticket (TKT-401/TKT-402):
  1. correctly_sourced  — every key_claim.source.url body contains claim material.
  2. fabricated         — one or more key_claim.url bodies do NOT contain claimed content.
  3. mixed              — some sourced, some fabricated.

Each fixture writes JSON brief files to tmp_path plus the referenced local HTML files,
so tests run fully offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple


class CitationFixture(NamedTuple):
    brief_path: Path
    source_dir: Path
    label: str  # 'correctly_sourced' | 'fabricated' | 'mixed'


_SLIDE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <article>
    <h1>{title}</h1>
    <p>{body}</p>
    <p>Published: {year}</p>
  </article>
</body></html>
"""


def _write_html(path: Path, title: str, body: str, year: str = "2026") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_SLIDE_HTML_TEMPLATE.format(title=title, body=body, year=year))


def _claim_to_ngrams(claim: str) -> set[str]:
    lowered = re.sub(r"[^0-9a-z]+", " ", claim.lower()).split()
    return set(lowered)


def _stable_url(filename: str) -> str:
    return f"local.test/{filename}"


def make_correctly_sourced(tmp_path: Path) -> CitationFixture:
    src_dir = tmp_path / "sources_correct"
    src_dir.mkdir(parents=True, exist_ok=True)
    claims = [
        {
            "claim": "Productivity grew by 2.3% annually between 2018 and 2024.",
            "source": {
                "title": "OECD Productivity Outlook 2024",
                "url": _stable_url("oecd.html"),
                "author": "OECD",
                "year": 2024,
                "url_host": "oecd.org",
            },
        },
        {
            "claim": "Remote workers report 13% higher sustained output than on-site peers.",
            "source": {
                "title": "Stanford WFH Research 2024",
                "url": _stable_url("stanford.html"),
                "author": "Nicholas Bloom",
                "year": 2024,
                "url_host": "stanford.edu",
            },
        },
        {
            "claim": "Bloom found hybrid schedules improve retention by 8%.",
            "source": {
                "title": "Bloom Hybrid Retention Study",
                "url": _stable_url("hybrid.html"),
                "author": "Nicholas Bloom",
                "year": 2024,
                "url_host": "stanford.edu",
            },
        },
    ]
    _write_html(src_dir / "oecd.html",
                "OECD Productivity Outlook 2024",
                "Productivity grew by 2.3% annually between 2018 and 2024.")
    _write_html(src_dir / "stanford.html",
                "Stanford WFH Research 2024",
                "Remote workers report 13% higher sustained output than on-site peers.")
    _write_html(src_dir / "hybrid.html",
                "Bloom Hybrid Retention Study",
                "Bloom found hybrid schedules improve retention by 8%.")

    brief_path = tmp_path / "brief_correct.json"
    brief = {
        "seed": "using AI to help memory retention",
        "angle": "professional leverage",
        "key_claims": claims,
        "research_text": " ".join(c["claim"] for c in claims),
        "sources": [
            {"title": c["source"]["title"], "url": c["source"]["url"], "year": c["source"]["year"]}
            for c in claims
        ],
        "suggested_titles": ["Test Title A", "Test Title B", "Test Title C"],
    }
    brief_path.write_text(json.dumps(brief, indent=2))
    return CitationFixture(brief_path, src_dir, "correctly_sourced")


def make_fabricated(tmp_path: Path) -> CitationFixture:
    src_dir = tmp_path / "sources_fabricated"
    src_dir.mkdir(parents=True, exist_ok=True)
    claims = [
        {
            "claim": "Productivity grew by 2.3% annually between 2018 and 2024.",
            "source": {
                "title": "OECD Productivity Outlook 2024",
                "url": _stable_url("oecd.html"),
                "author": "OECD",
                "year": 2024,
                "url_host": "oecd.org",
            },
        },
        {
            "claim": "Remote workers report 13% higher sustained output than on-site peers.",
            "source": {
                "title": "Stanford WFH Research 2024",
                "url": _stable_url("bogus.html"),
                "author": "NotADoctor",
                "year": 2024,
                "url_host": "example.com",
            },
        },
    ]
    _write_html(src_dir / "oecd.html",
                "OECD Productivity Outlook 2024",
                "Productivity grew by 2.3% annually between 2018 and 2024.")
    _write_html(src_dir / "bogus.html",
                "A Totally Unrelated Recipe",
                "Combine two tablespoons of flour with sugar and cinnamon.")

    brief_path = tmp_path / "brief_fabricated.json"
    brief = {
        "seed": "using AI to help memory retention",
        "angle": "professional leverage",
        "key_claims": claims,
        "research_text": claims[0]["claim"],
        "sources": [
            {"title": c["source"]["title"], "url": c["source"]["url"], "year": c["source"]["year"]}
            for c in claims
        ],
        "suggested_titles": ["Test Title A", "Test Title B", "Test Title C"],
    }
    brief_path.write_text(json.dumps(brief, indent=2))
    return CitationFixture(brief_path, src_dir, "fabricated")


def make_mixed(tmp_path: Path) -> CitationFixture:
    src_dir = tmp_path / "sources_mixed"
    src_dir.mkdir(parents=True, exist_ok=True)
    claims = [
        {
            "claim": "Productivity grew by 2.3% annually between 2018 and 2024.",
            "source": {
                "title": "OECD Productivity Outlook 2024",
                "url": _stable_url("real.html"),
                "author": "OECD",
                "year": 2024,
                "url_host": "oecd.org",
            },
        },
        {
            "claim": "Hybrid schedules improve retention by 8%.",
            "source": {
                "title": "Unrelated Recipe Page",
                "url": _stable_url("fake.html"),
                "author": "Noam Chomsky",
                "year": 2024,
                "url_host": "example.com",
            },
        },
    ]
    _write_html(src_dir / "real.html",
                "OECD Productivity Outlook 2024",
                "Productivity grew by 2.3% annually between 2018 and 2024.")
    _write_html(src_dir / "fake.html",
                "Easy Cinnamon Rolls",
                "Combine two tablespoons of flour with one stick of butter and cinnamon sugar. Bake for twelve minutes.")

    brief_path = tmp_path / "brief_mixed.json"
    brief = {
        "seed": "using AI to help memory retention",
        "angle": "professional leverage",
        "key_claims": claims,
        "research_text": claims[0]["claim"],
        "sources": [
            {"title": c["source"]["title"], "url": c["source"]["url"], "year": c["source"]["year"]}
            for c in claims
        ],
        "suggested_titles": ["Test Title A", "Test Title B", "Test Title C"],
    }
    brief_path.write_text(json.dumps(brief, indent=2))
    return CitationFixture(brief_path, src_dir, "mixed")


_ALL_BUILDERS = {
    "correctly_sourced": make_correctly_sourced,
    "fabricated": make_fabricated,
    "mixed": make_mixed,
}


def build_all_fixtures(tmp_path: Path) -> dict[str, CitationFixture]:
    return {name: builder(tmp_path) for name, builder in _ALL_BUILDERS.items()}
