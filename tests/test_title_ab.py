#!/usr/bin/env python3
"""TKT-704 + TKT-705 tests for title A/B candidates + pre-publish checklist."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.title_ab import (
    generate_titles_stub,
    generate_titles,
    persist_title_candidates,
    DEFAULT_NUM_CANDIDATES,
)


def test_generate_titles_stub():
    """Stub generates 5 unique titles."""
    titles = generate_titles_stub("how ai takes notes")
    assert len(titles) == 5
    # All unique
    assert len(set(t.lower() for t in titles)) == 5


def test_generate_titles_deterministic():
    """Same seed produces same titles (stub mode)."""
    t1 = generate_titles_stub("test seed")
    t2 = generate_titles_stub("test seed")
    assert t1 == t2


def test_generate_titles_test_mode():
    """generate_titles in test_mode uses stub."""
    titles = generate_titles("test topic", test_mode=True)
    assert len(titles) == DEFAULT_NUM_CANDIDATES


def test_generate_titles_unique():
    """All titles are unique."""
    titles = generate_titles("ai handwriting recognition", test_mode=True)
    assert len(set(t.lower() for t in titles)) == len(titles)


def test_persist_title_candidates():
    """Titles persisted to SQLite."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test.db"
        titles = ["Title A", "Title B", "Title C"]
        persist_title_candidates(db_path, "prod_123", titles)

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT production_id, title, rank FROM title_candidates WHERE production_id=? ORDER BY rank",
            ("prod_123",)
        ).fetchall()
        conn.close()

        assert len(rows) == 3
        assert rows[0][1] == "Title A"
        assert rows[0][2] == 1
        assert rows[2][2] == 3
