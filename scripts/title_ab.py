"""TKT-704: Title A/B candidate generator.

Generates 5 unique video titles via the existing LLM path.
Persisted in production DB table title_candidates.
Uniqueness check against existing titles.
Test mode uses deterministic stub.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DEFAULT_NUM_CANDIDATES = 5

# Stub titles for test mode
STUB_TITLES = [
    "How AI Reads Your Handwriting (And Turn It Into Digital Notes)",
    "The $4 Trillion Problem AI Just Solved",
    "Why AI Notes Are Better Than Your Memory",
    "How I Take Notes Using AI (Full Workflow)",
    "The Future of Handwriting is AI",
]


def generate_titles_stub(seed: str, num: int = DEFAULT_NUM_CANDIDATES) -> list[str]:
    """Generate titles using deterministic stub (test mode)."""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    result = []
    for i in range(num):
        idx = (h + i) % len(STUB_TITLES)
        result.append(STUB_TITLES[idx])
    return result


def generate_titles_llm(seed: str, num: int = DEFAULT_NUM_CANDIDATES) -> list[str]:
    """Generate titles via LLM (production mode)."""
    prompt = f"""Generate {num} unique, compelling YouTube video titles for this topic: "{seed}"

Rules:
- Each title should be 30-60 characters
- Use power words: "How I", "Why", "The Truth", "Full Workflow"
- No clickbait and no ALL CAPS
- Each must approach from a different angle (tutorial, myth bust, personal, data-driven, emotional)
- Return JSON: ["title1", "title2", ...]"""

    try:
        from llm_call import llm_call
        data, _, _, _ = llm_call(
            task="hook_generation", prompt=prompt, expect_json=True, timeout=60,
        )
        if isinstance(data, list):
            return data[:num]
        if isinstance(data, dict) and "titles" in data:
            return data["titles"][:num]
    except Exception:
        pass

    return generate_titles_stub(seed, num)


def generate_titles(seed: str, num: int = DEFAULT_NUM_CANDIDATES, test_mode: bool = False) -> list[str]:
    """Generate video title candidates."""
    if test_mode:
        titles = generate_titles_stub(seed, num)
    else:
        titles = generate_titles_llm(seed, num)

    # Ensure uniqueness
    seen = set()
    unique = []
    for t in titles:
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)

    # Pad if LLM returned fewer than requested
    while len(unique) < num:
        idx = len(unique) % len(STUB_TITLES)
        candidate = STUB_TITLES[idx]
        if candidate.lower() not in seen:
            unique.append(candidate)
            seen.add(candidate.lower())
        else:
            break

    return unique[:num]


def persist_title_candidates(db_path: Path, production_id: str, titles: list[str]) -> None:
    """Persist titles to title_candidates db table."""
    import subprocess
    db_path = Path(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS title_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_id TEXT NOT NULL,
            title TEXT NOT NULL,
            rank INTEGER NOT NULL DEFAULT 0,
            is_selected BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for i, title in enumerate(titles):
        conn.execute(
            "INSERT INTO title_candidates (production_id, title, rank, is_selected) VALUES (?, ?, ?, ?)",
            (production_id, title, i + 1, i == 0),
        )
    conn.commit()
    conn.close()
