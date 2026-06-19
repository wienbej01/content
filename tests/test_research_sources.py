"""Tests for research.py reputable-domain allowlist, sorting, capping, and prompt guidance.

Hermeticity (D-018): the sorting/capping/query tests below call gather_research() — the real
search -> reputable-sort -> cap -> build_research_prompt logic, factored out of research()
with NO kiro-cli call. The assertions are on the prompt / captured queries, which are exactly
what gather_research produces. Only brave_search (external web I/O, not available in CI) is
mocked; the logic under test is exercised for real. Do NOT rewrite these to call research()
with dry_run=False — that reaches the kiro-cli synthesis subprocess and stalls the suite when
kiro-cli is unavailable (pytest's thread-timeout cannot recover).
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from research import (
    REPUTABLE_DOMAINS,
    MAX_RESULTS_FOR_PROMPT,
    _is_reputable,
    build_research_prompt,
    gather_research,
)


def test_is_reputable():
    """_is_reputable matches known reputable domains and rejects unknown ones."""
    assert _is_reputable("https://hbr.org/2024/some-article")
    assert _is_reputable("https://www.stanford.edu/research/paper")
    assert _is_reputable("https://arxiv.org/abs/2401.12345")
    assert _is_reputable("https://sloanreview.mit.edu/article/x")
    assert not _is_reputable("https://randomblog.com/listicle")
    assert not _is_reputable("https://medium.com/some-post")
    assert not _is_reputable("")
    assert not _is_reputable(None)


def test_reputable_sorted_first():
    """Reputable results are ordered before non-reputable in the list passed to prompt."""
    mixed = [
        {"title": "Blog", "url": "https://randomblog.com/x", "description": "a"},
        {"title": "HBR", "url": "https://hbr.org/2024/y", "description": "b"},
        {"title": "Medium", "url": "https://medium.com/z", "description": "c"},
        {"title": "Nature", "url": "https://nature.com/article", "description": "d"},
    ]
    captured_queries = []

    def mock_brave(query, count=8):
        captured_queries.append(query)
        return mixed if not captured_queries[:-1] else []

    with patch("research.brave_search", side_effect=mock_brave):
        results, prompt = gather_research("test topic")

    # Verify prompt has reputable results first
    hbr_pos = prompt.find("hbr.org")
    nature_pos = prompt.find("nature.com")
    blog_pos = prompt.find("randomblog.com")
    medium_pos = prompt.find("medium.com")
    assert hbr_pos < blog_pos
    assert nature_pos < medium_pos


def test_prompt_has_reputable_guidance():
    """build_research_prompt instructs preferring reputable domains + target 6-10 claims."""
    results = [
        {"title": "Study", "url": "https://nature.com/a", "description": "x", "reputable": True},
        {"title": "Blog", "url": "https://blog.com/b", "description": "y", "reputable": False},
    ]
    prompt = build_research_prompt("AI productivity", "short", search_results=results)
    assert "PREFER sources from reputable domains" in prompt
    assert "[REPUTABLE]" in prompt
    assert "[web]" in prompt
    assert "6-10" in prompt
    assert "4-8 paragraphs" in prompt


def test_domain_targeted_queries_present():
    """research() query list includes site: targeted queries."""
    captured_queries = []

    def mock_brave(query, count=8):
        captured_queries.append(query)
        return []

    with patch("research.brave_search", side_effect=mock_brave):
        gather_research("deep work focus")

    query_text = " ".join(captured_queries)
    assert "site:hbr.org" in query_text
    assert "site:nature.com" in query_text
    assert "site:arxiv.org" in query_text
    assert len(captured_queries) == 6


def test_results_capped():
    """With many results, total passed to prompt is capped and reputable kept preferentially."""
    # Generate 40 results: 15 reputable + 25 non-reputable
    results = []
    for i in range(15):
        results.append({"title": f"R{i}", "url": f"https://nature.com/a{i}", "description": ""})
    for i in range(25):
        results.append({"title": f"B{i}", "url": f"https://randomblog{i}.com/x", "description": ""})

    call_count = [0]

    def mock_brave(query, count=8):
        call_count[0] += 1
        if call_count[0] == 1:
            return results
        return []

    with patch("research.brave_search", side_effect=mock_brave):
        results, prompt = gather_research("test")

    # Count how many results appear in prompt (each has a URL: line)
    url_lines = [l for l in prompt.splitlines() if l.strip().startswith("URL:")]
    assert len(url_lines) <= MAX_RESULTS_FOR_PROMPT
    # All 15 reputable should be kept (they fit within cap)
    assert prompt.count("nature.com") >= 15


def test_min_sources_unchanged():
    """Prompt still states the >=3 minimum and TED-as-trend-only rule."""
    prompt = build_research_prompt("AI topic", "short", search_results=[
        {"title": "X", "url": "https://x.com/a", "description": "", "reputable": False}
    ])
    assert "THREE independent credible sources" in prompt or "at least THREE" in prompt.upper() or "THREE" in prompt
    assert "TED" in prompt
    assert "trend input ONLY" in prompt or "trend input only" in prompt.lower()
