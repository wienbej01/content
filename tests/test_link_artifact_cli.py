import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRODUCE_DB = ROOT / "scripts" / "produce_db.py"


@pytest.fixture
def test_prod_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["PRODUCTION_DB_PATH"] = db_path

    import production_db as _db
    _db.migrate(db_path)

    conn = _db.connect(db_path)
    now = _db._now()

    prod_id = "prod_link"
    ru_id = "ru_reused"
    ru_non_reused = "ru_hero"

    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_link", "in_progress", "deadbeef", 0, now, now),
    )
    conn.execute(
        "INSERT INTO render_units (id, production_id, ordinal, label, asset_type, "
        "audio_policy, final_audio_source, provider_audio_usage, text_policy, "
        "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
        "slot_index, slot_total, status, metadata_json, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ru_id, prod_id, 0, "reused_unit", "reused", "BROLL_FLEX", "none", "discarded",
         "UNREADABLE_BACKGROUND", 0, 0, 5000, 5000, 0, 1, "ordered",
         _db._json({}), now, now),
    )
    conn.execute(
        "INSERT INTO render_units (id, production_id, ordinal, label, asset_type, "
        "audio_policy, final_audio_source, provider_audio_usage, text_policy, "
        "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
        "slot_index, slot_total, status, metadata_json, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ru_non_reused, prod_id, 1, "hero_unit", "lipsync_video", "HERO_SYNC_LOCKED",
         "provider_audio", "final_mix", "NO_VISIBLE_TEXT", 1, 0, 5000, 5000, 0, 1,
         "ordered", _db._json({}), now, now),
    )
    conn.commit()
    conn.close()

    _db._db_path_override = db_path

    yield {"db_path": db_path, "prod_id": prod_id, "ru_id": ru_id,
           "ru_non_reused": ru_non_reused}

    _db._db_path_override = None
    if "PRODUCTION_DB_PATH" in os.environ:
        del os.environ["PRODUCTION_DB_PATH"]


def _run_cli(*args, db_path=None):
    env = os.environ.copy()
    if db_path:
        env["PRODUCTION_DB_PATH"] = db_path
    cmd = [sys.executable, str(PRODUCE_DB)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), env=env)


def _make_test_video(path, duration=5):
    import subprocess as sp
    sp.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=duration={duration}:size=320x240:rate=24",
        "-f", "lavfi", "-i",
        f"sine=frequency=440:duration={duration}",
        "-shortest", "-c:v", "libx264", "-c:a", "aac",
        str(path),
    ], capture_output=True, check=True)
    return path


class TestLinkArtifactCLI:
    def test_link_valid_file_to_reused_unit(self, test_prod_db):
        db_path = test_prod_db["db_path"]
        prod_id = test_prod_db["prod_id"]
        ru_id = test_prod_db["ru_id"]

        video = Path(db_path).parent / "test_reuse.mp4"
        _make_test_video(video, duration=5)

        result = _run_cli("link-artifact", prod_id, ru_id, str(video),
                          db_path=db_path)
        assert result.returncode == 0, f"link-artifact failed: {result.stderr}"

        output = json.loads(result.stdout)
        assert output["artifact_id"].startswith("art")
        assert "sha256" in output

        import production_db as _db
        conn = _db.connect(db_path)
        ru = conn.execute("SELECT status, active_artifact_id FROM render_units WHERE id=?",
                          (ru_id,)).fetchone()
        conn.close()
        assert ru is not None
        assert ru["status"] == "generated", \
            f"expected status 'generated', got '{ru['status']}'"
        assert ru["active_artifact_id"] == output["artifact_id"]

    def test_non_reused_unit_rejected(self, test_prod_db):
        db_path = test_prod_db["db_path"]
        prod_id = test_prod_db["prod_id"]
        ru_non = test_prod_db["ru_non_reused"]

        video = Path(db_path).parent / "test_reuse2.mp4"
        _make_test_video(video, duration=5)

        import production_db as _db
        pre_units = _db.connect(db_path).execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru_non,)).fetchall()

        result = _run_cli("link-artifact", prod_id, ru_non, str(video),
                          db_path=db_path)
        assert result.returncode != 0, \
            f"expected non-zero exit for non-reused unit, got {result.returncode}"

        conn = _db.connect(db_path)
        post = conn.execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru_non,)).fetchone()
        conn.close()
        assert post["status"] == pre_units[0]["status"], \
            "DB must be unchanged for non-reused unit"
        assert post["active_artifact_id"] == pre_units[0]["active_artifact_id"]

    def test_missing_file_rejected(self, test_prod_db):
        db_path = test_prod_db["db_path"]
        prod_id = test_prod_db["prod_id"]
        ru_id = test_prod_db["ru_id"]

        missing = str(Path(db_path).parent / "does_not_exist.mp4")

        import production_db as _db
        pre_units = _db.connect(db_path).execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru_id,)).fetchall()

        result = _run_cli("link-artifact", prod_id, ru_id, missing,
                          db_path=db_path)
        assert result.returncode != 0, \
            f"expected non-zero exit for missing file, got {result.returncode}"

        conn = _db.connect(db_path)
        post = conn.execute(
            "SELECT status, active_artifact_id FROM render_units WHERE id=?",
            (ru_id,)).fetchone()
        conn.close()
        assert post["status"] == pre_units[0]["status"], \
            "DB must be unchanged after missing file"
        assert post["active_artifact_id"] == pre_units[0]["active_artifact_id"]

    def test_second_link_attempt_rejected(self, test_prod_db):
        db_path = test_prod_db["db_path"]
        prod_id = test_prod_db["prod_id"]
        ru_id = test_prod_db["ru_id"]

        video1 = Path(db_path).parent / "test_first.mp4"
        video2 = Path(db_path).parent / "test_second.mp4"
        _make_test_video(video1, duration=5)
        _make_test_video(video2, duration=5)

        result1 = _run_cli("link-artifact", prod_id, ru_id, str(video1),
                           db_path=db_path)
        assert result1.returncode == 0, f"first link failed: {result1.stderr}"

        result2 = _run_cli("link-artifact", prod_id, ru_id, str(video2),
                           db_path=db_path)
        assert result2.returncode != 0, \
            f"expected non-zero exit for second link, got {result2.returncode}"

        import production_db as _db
        conn = _db.connect(db_path)
        ru = conn.execute(
            "SELECT status, active_artifact_id, actual_render_duration_ms "
            "FROM render_units WHERE id=?", (ru_id,)).fetchone()
        conn.close()
        art1 = json.loads(result1.stdout)
        assert ru["active_artifact_id"] == art1["artifact_id"], \
            "active_artifact must still point to first link"
        assert ru["status"] == "generated"
