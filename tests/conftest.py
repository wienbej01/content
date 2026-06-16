"""Global test fixtures — isolate runtime databases from the real workspace."""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(autouse=True)
def _isolate_clip_db(tmp_path, monkeypatch):
    """Every test gets its own ephemeral clip DB.

    Sets both the in-process override (for direct imports) and the CLIP_DB_PATH
    env var (inherited by subprocess-launched CLIs) so neither path pollutes the
    real db/clips.db.
    """
    import clip_db
    db_file = str(tmp_path / "test_clips.db")
    clip_db._db_path_override = db_file
    monkeypatch.setenv("CLIP_DB_PATH", db_file)
    yield
    clip_db._db_path_override = None


@pytest.fixture(autouse=True)
def _isolate_production_db(tmp_path, monkeypatch):
    """Every test gets an independent unified production ledger."""
    db_file = str(tmp_path / "test_production.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    try:
        import production_db
        production_db._db_path_override = db_file
    except ImportError:
        production_db = None
    yield
    if production_db is not None:
        production_db._db_path_override = None


def make_clip_file(clip, content=b"FAKE_MEDIA"):
    """Create a stub file at clip's output_path and return its real SHA-256.
    Use this before mark_valid to satisfy filesystem truth checks.
    """
    import clip_db
    full_path = clip_db.ROOT / clip["output_path"]
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    return clip_db._sha256_file(full_path)
