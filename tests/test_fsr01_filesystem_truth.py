"""FSR-01: Filesystem truth — clip DB must reconcile against disk reality."""
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db


def _order(project_id, beat_id, segment_id="S01", asset_type="generated_video", slot_id=None, db_path=None):
    clip_db.init_db(db_path)
    return clip_db.order_clip(
        project_id=project_id, source_beat_id=beat_id,
        production_beat_id=beat_id, segment_id=segment_id,
        asset_type=asset_type, model="kling3_0",
        audio_policy="strip", lipsync_required=0,
        required_start_sec=0.0, required_end_sec=5.0,
        slot_id=slot_id, db_path=db_path)


def _create_file(clip, content=b"FAKE"):
    """Create file at clip's output_path, return real SHA."""
    p = clip_db.ROOT / clip["output_path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return clip_db._sha256_file(p)


# --- Test 1: canonical path is asset_type-aware ---

def test_canonical_path_local_graphic_is_png():
    """local_graphic → .png; generated_video → .mp4."""
    png_path = clip_db._canonical_path("proj", "seg", "B001", asset_type="local_graphic")
    mp4_path = clip_db._canonical_path("proj", "seg", "B001", asset_type="generated_video")
    assert png_path.endswith(".png")
    assert mp4_path.endswith(".mp4")
    # still_image also gets .png
    still_path = clip_db._canonical_path("proj", "seg", "B001", asset_type="still_image")
    assert still_path.endswith(".png")


# --- Test 2: mark_valid rejects missing file ---

def test_mark_valid_rejects_missing_file():
    """mark_valid on a clip whose file is absent → raises, does NOT become valid."""
    clip = _order("fsr01_miss", "B001")
    clip_db.record_generated(clip["clip_id"], 5.0, 64, 64, False, None)
    # File does NOT exist at output_path
    with pytest.raises(FileNotFoundError, match="mark_valid refused"):
        clip_db.mark_valid(clip["clip_id"])
    c = clip_db.get_clip(clip["clip_id"])
    assert c["status"] == "failed"


# --- Test 3: mark_valid rejects SHA mismatch ---

def test_mark_valid_rejects_sha_mismatch():
    """File exists but sha differs → not valid."""
    clip = _order("fsr01_sha", "B001")
    p = clip_db.ROOT / clip["output_path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"original")
    clip_db.record_generated(clip["clip_id"], 5.0, 64, 64, False, "wrong_sha_value")
    with pytest.raises(FileNotFoundError, match="sha256 mismatch"):
        clip_db.mark_valid(clip["clip_id"])
    c = clip_db.get_clip(clip["clip_id"])
    assert c["status"] == "failed"
    p.unlink(missing_ok=True)


# --- Test 4: mark_valid accepts present + matching file ---

def test_mark_valid_accepts_present_matching_file():
    """File exists + sha matches → valid."""
    clip = _order("fsr01_ok", "B001")
    sha = _create_file(clip, b"good_content")
    clip_db.record_generated(clip["clip_id"], 5.0, 64, 64, False, sha)
    clip_db.mark_valid(clip["clip_id"])
    c = clip_db.get_clip(clip["clip_id"])
    assert c["status"] == "valid"
    (clip_db.ROOT / clip["output_path"]).unlink(missing_ok=True)


# --- Test 5: assert_all_valid flags absent file ---

def test_assert_all_valid_flags_absent_file():
    """Clip with status='valid' in DB but missing file → assert_all_valid returns False."""
    clip = _order("fsr01_ghost", "B001")
    sha = _create_file(clip, b"temp")
    clip_db.record_generated(clip["clip_id"], 5.0, 64, 64, False, sha)
    clip_db.mark_valid(clip["clip_id"])
    # Now DELETE the file — DB says valid but filesystem disagrees
    (clip_db.ROOT / clip["output_path"]).unlink()
    ok, problems = clip_db.assert_all_valid("fsr01_ghost")
    assert not ok
    assert any("file missing" in p.get("status_reason", "") for p in problems)


# --- Test 6: assert_all_valid passes when all files present ---

def test_assert_all_valid_passes_when_all_present():
    """All files present + matching → True."""
    clip = _order("fsr01_allok", "B001")
    sha = _create_file(clip, b"content_a")
    clip_db.record_generated(clip["clip_id"], 5.0, 64, 64, False, sha)
    clip_db.mark_valid(clip["clip_id"])
    ok, problems = clip_db.assert_all_valid("fsr01_allok")
    assert ok
    assert problems == []
    (clip_db.ROOT / clip["output_path"]).unlink(missing_ok=True)


# --- Test 7: local_graphic roundtrip (.png end-to-end) ---

def test_local_graphic_roundtrip():
    """Order local_graphic → output_path is .png → create file → mark_valid → get_path returns .png → assert_all_valid passes."""
    clip = _order("fsr01_lg", "B010", asset_type="local_graphic")
    # output_path must be .png
    assert clip["output_path"].endswith(".png"), f"Expected .png, got {clip['output_path']}"
    # Simulate render_graphics writing a .png
    sha = _create_file(clip, b"\x89PNG\r\n\x1a\nfake_png_data")
    clip_db.record_generated(clip["clip_id"], 5.0, 1920, 1080, False, sha)
    clip_db.mark_valid(clip["clip_id"])
    # get_path returns .png
    assert clip_db.get_path(clip["clip_id"]).endswith(".png")
    # assert_all_valid passes (file exists + sha match)
    ok, problems = clip_db.assert_all_valid("fsr01_lg")
    assert ok, f"Expected pass, got problems: {problems}"
    (clip_db.ROOT / clip["output_path"]).unlink(missing_ok=True)
