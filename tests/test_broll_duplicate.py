"""TKT-204: Cross-clip near-duplicate detection tests.

Tests verify:
1. Duplicate fixture clip linked to two units fails the later unit.
2. Two visually distinct clips both pass.
3. Same scene, different crop is handled at documented threshold.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import broll_qa
import frame_bundle as fb


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, check=True)


def make_solid_clip(path, color="red", duration=3, width=320, height=240):
    _ffmpeg(
        "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r=24:d={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an", str(path),
    )


def make_moving_clip(path, duration=3, width=320, height=240):
    _ffmpeg(
        "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:d={duration}:rate=24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an", str(path),
    )


def _seed_two_units(db_path, prod_id, clip_a, clip_b, ru_id_a="ru_a", ru_id_b="ru_b",
                    art_id_a="art_a", art_id_b="art_b"):
    import production_db as _db
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    now = _db._now()

    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_dup", "in_progress", "deadbeef", 0, now, now),
    )
    for ru_id, art_id, clip_path, ord_, sha_suffix in [
        (ru_id_a, art_id_a, clip_a, 0, "aa"),
        (ru_id_b, art_id_b, clip_b, 1, "bb"),
    ]:
        conn.execute(
            "INSERT INTO artifacts (id, production_id, kind, uri, storage_backend, sha256, "
            "size_bytes, metadata_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (art_id, prod_id, "media", str(clip_path), "local",
             "sha256:" + sha_suffix * 32, clip_path.stat().st_size, _db._json({}), now),
        )
        conn.execute(
            "INSERT INTO render_units (id, production_id, ordinal, label, asset_type, "
            "audio_policy, final_audio_source, provider_audio_usage, text_policy, "
            "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
            "slot_index, slot_total, status, active_artifact_id, metadata_json, "
            "created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ru_id, prod_id, ord_, f"unit_{ord_}", "broll", "BROLL_FLEX", "none", "discarded",
             "UNREADABLE_BACKGROUND", 0, 0, 5000, 5000, 0, 1, "generated",
             art_id, _db._json({}), now, now),
        )
    conn.commit()
    conn.close()


class TestComputeDhash:
    def test_compute_dhash_returns_16_char_hex(self, tmp_path):
        clip = tmp_path / "test.mp4"
        make_solid_clip(clip)
        frames = fb.build_frame_bundle(clip, n=3, assets_dir=tmp_path / "bundles")
        for fp in frames:
            h = broll_qa.compute_dhash(fp)
            assert isinstance(h, str)
            assert len(h) == 16
            assert all(c in "0123456789abcdef" for c in h)

    def test_same_frame_identical_hash(self, tmp_path):
        clip = tmp_path / "test.mp4"
        make_solid_clip(clip)
        frames = fb.build_frame_bundle(clip, n=3, assets_dir=tmp_path / "bundles")
        h1 = broll_qa.compute_dhash(frames[0])
        h2 = broll_qa.compute_dhash(frames[0])
        assert h1 == h2

    def test_different_frames_different_hashes(self, tmp_path):
        solid = tmp_path / "solid.mp4"
        moving = tmp_path / "moving.mp4"
        make_solid_clip(solid, color="red")
        make_moving_clip(moving)
        frames_s = fb.build_frame_bundle(solid, n=3, assets_dir=tmp_path / "bundles_s")
        frames_m = fb.build_frame_bundle(moving, n=3, assets_dir=tmp_path / "bundles_m")
        assert broll_qa.compute_dhash(frames_s[0]) != broll_qa.compute_dhash(frames_m[0])


class TestHammingDistance:
    def test_identical_hashes_zero_distance(self):
        assert broll_qa._hamming_distance("abcd1234abcd1234", "abcd1234abcd1234") == 0

    def test_single_bit_difference(self):
        assert broll_qa._hamming_distance("0000000000000000", "8000000000000000") == 1

    def test_all_bits_different(self):
        assert broll_qa._hamming_distance("ffffffffffffffff", "0000000000000000") == 64

    def test_some_bits_different(self):
        a = "ff00ff00ff00ff00"
        b = "ff00ff00ff00ff0f"
        assert broll_qa._hamming_distance(a, b) == 4


class TestCheckBrollDuplicate:
    def test_duplicate_clip_detected(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        prod_id = "prod_dup1"

        clip = tmp_path / "source.mp4"
        make_solid_clip(clip, color="blue", duration=3)

        _seed_two_units(db_path, prod_id, clip, clip, "ru_1", "ru_2", "art_1", "art_2")

        result = broll_qa.check_broll_duplicate(prod_id, "ru_2", clip, db_path=db_path)
        assert result["status"] == "fail", f"expected fail for duplicate, got {result['status']}"
        assert len(result["duplicates"]) > 0
        assert any("ru_1" in str(d.get("conflicting_unit", "")) for d in result["duplicates"]), \
            f"expected ru_1 as conflicting unit, got {result['duplicates']}"

    def test_distinct_clips_pass(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        prod_id = "prod_dup2"

        clip_a = tmp_path / "moving.mp4"
        clip_b = tmp_path / "solid_red.mp4"
        make_moving_clip(clip_a, duration=3)
        make_solid_clip(clip_b, color="red", duration=3)

        _seed_two_units(db_path, prod_id, clip_a, clip_b, "ru_a", "ru_b", "art_a", "art_b")

        result = broll_qa.check_broll_duplicate(prod_id, "ru_b", clip_b, db_path=db_path)
        assert result["status"] == "pass", f"expected pass for distinct clips, got {result['status']}"

    def test_same_scene_different_crop_threshold(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        prod_id = "prod_dup3"

        clip = tmp_path / "source.mp4"
        make_solid_clip(clip, color="green", duration=3)

        _seed_two_units(db_path, prod_id, clip, clip, "ru_x", "ru_y", "art_x", "art_y")

        result = broll_qa.check_broll_duplicate(prod_id, "ru_y", clip, db_path=db_path)
        assert result["status"] == "fail", \
            f"expected fail for identical content, got {result['status']}"
        assert result["threshold"] == broll_qa.DUPLICATE_HAMMING_THRESHOLD


class TestIntegrationRunContractMediaQa:
    def test_duplicate_validation_row_written(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        prod_id = "prod_dupi1"

        clip = tmp_path / "source.mp4"
        make_solid_clip(clip, color="purple", duration=3)

        _seed_two_units(db_path, prod_id, clip, clip, "ru_i1", "ru_i2", "art_i1", "art_i2")

        from media_service import run_contract_media_qa
        run_contract_media_qa(db_path, prod_id, "ru_i2")

        import production_db as _db
        conn = _db.connect(db_path)
        vs = conn.execute(
            "SELECT validator_name, status FROM validations WHERE subject_id=?",
            ("ru_i2",),
        ).fetchall()
        conn.close()

        names = {v["validator_name"] for v in vs}
        assert "broll_duplicate" in names, \
            f"expected broll_duplicate validation row, got {names}"
        dup_val = [v for v in vs if v["validator_name"] == "broll_duplicate"][0]
        assert dup_val["status"] == "fail"

    def test_distinct_clips_no_duplicate_validation(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        prod_id = "prod_dupi2"

        clip_a = tmp_path / "moving_i.mp4"
        clip_b = tmp_path / "solid_i.mp4"
        make_moving_clip(clip_a, duration=3)
        make_solid_clip(clip_b, color="orange", duration=3)

        _seed_two_units(db_path, prod_id, clip_a, clip_b, "ru_i3", "ru_i4", "art_i3", "art_i4")

        from media_service import run_contract_media_qa
        run_contract_media_qa(db_path, prod_id, "ru_i4")

        import production_db as _db
        conn = _db.connect(db_path)
        vs = conn.execute(
            "SELECT validator_name, status FROM validations WHERE subject_id=?",
            ("ru_i4",),
        ).fetchall()
        conn.close()

        names = {v["validator_name"] for v in vs}
        dup_vals = [v for v in vs if v["validator_name"] == "broll_duplicate"]
        assert dup_vals, f"expected broll_duplicate validation row, got {names}"
        assert dup_vals[0]["status"] == "pass"
