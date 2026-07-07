"""TKT-503: Curated asset library index and storyboard citation.

Tests: library add -> search workflow, library_asset_id projection resolution,
unknown id rejection, license enforcement.
"""
import json
import os
import subprocess
from pathlib import Path
from PIL import Image

import pytest

import production_db as _db


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test_library.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_library", video_type="short", db_path=db)


@pytest.fixture
def test_video(tmp_path):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         str(tmp_path / "test.mp4")],
        capture_output=True, timeout=10,
    )
    return str(tmp_path / "test.mp4")


class TestLibrary:
    """TKT-503: asset library CLI and projection."""

    def test_library_license_enforcement(self, test_video):
        """library add without --license exits non-zero."""
        from produce_db import library_add
        import sys, io
        old_stderr = sys.stderr
        old_stdout = sys.stdout
        try:
            sys.stderr = open(os.devnull, 'w')
            sys.stdout = io.StringIO()
            with pytest.raises(SystemExit):
                library_add(test_video, license="   ")
        finally:
            sys.stderr.close()
            sys.stdout.close()
            sys.stderr = old_stderr
            sys.stdout = old_stdout

    def test_library_add_and_search(self, db, test_video):
        """Index asset and verify in DB."""
        from produce_db import library_add
        import sys, io

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stderr = open(os.devnull, 'w')
            sys.stdout = io.StringIO()
            library_add(test_video, license="CC-BY-4.0", tags="nature,test", media_kind="video")
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
            sys.stderr.close()
            sys.stderr = old_stderr

        conn = _db.connect(db)
        row = conn.execute(
            "SELECT id, sha256, tags, license FROM asset_library ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["license"] == "CC-BY-4.0"
        assert "nature" in row["tags"]
        assert row["sha256"] is not None

    def test_unknown_library_id_rejected(self, db):
        """Projection of unknown library_asset_id raises RuntimeError."""
        from storyboard_projection import project_canonical

        shot = {
            "shot_id": "S001", "visual_role": "broll_evidence",
            "segment_id": "seg1", "library_asset_id": "lib_nonexistent",
            "visual_concept": "Test concept", "why_this_visual": "Test why",
            "narrative_alignment": "Test alignment",
            "literal_vs_metaphorical": "literal",
            "prompt_intent": "Show a test concept",
            "must_show": [],
            "must_avoid": [],
            "generation_style": "realistic",
            "resolution_vs_drift": "stable",
        }

        with pytest.raises(Exception, match="not found|cannot be projected|Extend _VISUAL_ROLE"):
            project_canonical({
                "storyboard_contract_version": "2.0",
                "shots": [shot],
                "overlays": [],
                "narrative_beats": [],
                "claim_inventory": [],
                "segment_work_orders": [],
            })
