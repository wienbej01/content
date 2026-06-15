"""Global test fixtures — redirect clip_db to temp path so tests never pollute db/clips.db."""
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
