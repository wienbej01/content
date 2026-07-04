"""tests/test_broll_technical_qa.py — TKT-004 model-free b-roll technical checks.

Tests check_broll_technical (frozen-frame + gibberish via ffmpeg only)
and integration through run_contract_media_qa.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import broll_qa


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, check=True)


def make_frozen_clip(path, duration=5, width=320, height=240):
    _ffmpeg(
        "-f", "lavfi", "-i", f"color=c=red:s={width}x{height}:r=24:d={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an", str(path),
    )


def make_moving_clip(path, duration=5, width=320, height=240):
    _ffmpeg(
        "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:d={duration}:rate=24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an", str(path),
    )


class TestCheckBrollTechnical:
    def test_frozen_clip_fails(self, tmp_path):
        clip = tmp_path / "frozen.mp4"
        make_frozen_clip(clip, duration=5)
        result = broll_qa.check_broll_technical(clip)
        assert result["status"] == "fail", f"expected fail, got {result['status']}"
        assert any("FROZEN_VIDEO" in i for i in result["issues"]), \
            f"expected FROZEN_VIDEO issue, got {result['issues']}"

    def test_moving_clip_passes(self, tmp_path):
        clip = tmp_path / "moving.mp4"
        make_moving_clip(clip, duration=5)
        result = broll_qa.check_broll_technical(clip)
        assert result["status"] == "pass", \
            f"expected pass, got {result['status']}: {result['issues']}"
        assert len(result["issues"]) == 0, f"expected no issues, got {result['issues']}"

    def test_missing_file_fails(self, tmp_path):
        clip = tmp_path / "nonexistent.mp4"
        result = broll_qa.check_broll_technical(clip)
        assert result["status"] == "fail"
        assert any("missing" in i.lower() for i in result["issues"])


class TestIntegrationRunContractMediaQa:
    """Integration: run_contract_media_qa records broll_technical validation row."""

    def test_broll_technical_fail_registers_validation(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        clip = tmp_path / "artifact.mp4"
        make_frozen_clip(clip, duration=5)

        os.environ["PRODUCTION_DB_PATH"] = db_path

        import production_db as _db
        _db.migrate(db_path)
        conn = _db.connect(db_path)
        prod_id = "prod_t4"
        ru_id = "ru_t4"
        art_id = "art_t4"
        now = _db._now()
        conn.execute(
            "INSERT INTO productions (id, project_slug, status, code_revision, seed, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (prod_id, "test_t4", "in_progress", "deadbeef", 0, now, now),
        )
        conn.execute(
            "INSERT INTO render_units (id, production_id, ordinal, label, asset_type, "
            "audio_policy, final_audio_source, provider_audio_usage, text_policy, "
            "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
            "slot_index, slot_total, status, metadata_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ru_id, prod_id, 0, "test_unit", "broll", "BROLL_FLEX", "none", "discarded",
             "UNREADABLE_BACKGROUND", 0, 0, 5000, 5000, 0, 1, "generated",
             _db._json({}), now, now),
        )
        conn.execute(
            "INSERT INTO artifacts (id, production_id, kind, uri, storage_backend, sha256, "
            "size_bytes, metadata_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (art_id, prod_id, "media", str(clip), "local",
             "sha256:" + "a" * 64, clip.stat().st_size, _db._json({}), now),
        )
        conn.execute(
            "UPDATE render_units SET active_artifact_id=?, updated_at=? WHERE id=?",
            (art_id, now, ru_id),
        )
        conn.commit()
        conn.close()

        from media_service import run_contract_media_qa
        run_contract_media_qa(db_path, prod_id, ru_id)

        conn = _db.connect(db_path)
        vs = conn.execute(
            "SELECT validator_name, status FROM validations WHERE subject_id=?",
            (ru_id,),
        ).fetchall()
        conn.close()

        validator_names = {v["validator_name"] for v in vs}
        assert "broll_technical" in validator_names, \
            f"expected broll_technical validation, got {validator_names}"
        broll_val = [v for v in vs if v["validator_name"] == "broll_technical"][0]
        assert broll_val["status"] == "fail", \
            f"expected fail for frozen clip, got {broll_val['status']}"

    def test_moving_clip_passes_broll_technical(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        clip = tmp_path / "artifact.mp4"
        make_moving_clip(clip, duration=5)

        os.environ["PRODUCTION_DB_PATH"] = db_path

        import production_db as _db
        _db.migrate(db_path)
        conn = _db.connect(db_path)
        prod_id = "prod_t4m"
        ru_id = "ru_t4m"
        art_id = "art_t4m"
        now = _db._now()
        conn.execute(
            "INSERT INTO productions (id, project_slug, status, code_revision, seed, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (prod_id, "test_t4m", "in_progress", "deadbeef", 0, now, now),
        )
        conn.execute(
            "INSERT INTO render_units (id, production_id, ordinal, label, asset_type, "
            "audio_policy, final_audio_source, provider_audio_usage, text_policy, "
            "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
            "slot_index, slot_total, status, metadata_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ru_id, prod_id, 0, "test_unit", "broll", "BROLL_FLEX", "none", "discarded",
             "UNREADABLE_BACKGROUND", 0, 0, 5000, 5000, 0, 1, "generated",
             _db._json({}), now, now),
        )
        conn.execute(
            "INSERT INTO artifacts (id, production_id, kind, uri, storage_backend, sha256, "
            "size_bytes, metadata_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (art_id, prod_id, "media", str(clip), "local",
             "sha256:" + "a" * 64, clip.stat().st_size, _db._json({}), now),
        )
        conn.execute(
            "UPDATE render_units SET active_artifact_id=?, updated_at=? WHERE id=?",
            (art_id, now, ru_id),
        )
        conn.commit()
        conn.close()

        from media_service import run_contract_media_qa
        run_contract_media_qa(db_path, prod_id, ru_id)

        conn = _db.connect(db_path)
        vs = conn.execute(
            "SELECT validator_name, status FROM validations WHERE subject_id=?",
            (ru_id,),
        ).fetchall()
        conn.close()

        broll_val = [v for v in vs if v["validator_name"] == "broll_technical"]
        assert broll_val, "expected broll_technical validation row"
        assert broll_val[0]["status"] == "pass", \
            f"expected pass for moving clip, got {broll_val[0]['status']}"
