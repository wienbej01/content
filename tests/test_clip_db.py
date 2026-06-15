#!/usr/bin/env python3
"""tests/test_clip_db.py — Tests for the Clip/Slot Authority Database manager."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Ensure scripts/ is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import clip_db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    """Each test gets its own temp DB."""
    db_file = str(tmp_path / "test_clips.db")
    clip_db._db_path_override = db_file
    clip_db.init_db(db_file)
    yield db_file
    clip_db._db_path_override = None


def _order_basic(db_path, **overrides):
    """Helper to order a basic clip with sensible defaults."""
    defaults = dict(
        project_id="proj001",
        source_beat_id="B004",
        production_beat_id="B004",
        segment_id="seg01",
        asset_type="generated_video",
        model="seedance_2_0",
        audio_policy="keep_lipsync",
        lipsync_required=True,
        required_start_sec=0.0,
        required_end_sec=5.0,
        db_path=db_path,
    )
    defaults.update(overrides)
    return clip_db.order_clip(**defaults)


def _make_tiny_mp4(path):
    """Create a minimal valid mp4 file using ffmpeg."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
        "-c:v", "libx264", "-t", "1", "-pix_fmt", "yuv420p",
        str(path)
    ], capture_output=True, check=True)


# --- Tests ---

def test_init_creates_tables(tmp_db):
    conn = clip_db.get_db(tmp_db)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    names = [t["name"] for t in tables]
    assert "clips" in names
    assert "clip_access_log" in names
    assert "clip_change_requests" in names


def test_order_clip_assigns_canonical_path_and_id(tmp_db):
    clip = _order_basic(tmp_db)
    assert clip["clip_id"] == "proj001::B004::whole"
    assert clip["output_path"] == "assets/media/proj001/seg01/B004.mp4"
    assert clip["status"] == "ordered"


def test_canonical_path_is_deterministic(tmp_db):
    """Same inputs always produce the same path."""
    p1 = clip_db._canonical_path("proj001", "seg01", "B004")
    p2 = clip_db._canonical_path("proj001", "seg01", "B004")
    assert p1 == p2 == "assets/media/proj001/seg01/B004.mp4"


def test_slot_clip_path_includes_slot_id(tmp_db):
    clip = _order_basic(tmp_db, production_beat_id="B004", slot_id="B004-s0")
    assert "B004_B004-s0.mp4" in clip["output_path"]
    assert clip["clip_id"] == "proj001::B004::B004-s0"


def test_can_reuse_false_when_file_missing(tmp_db):
    clip = _order_basic(tmp_db)
    # Record generated attrs but file doesn't exist
    clip_db.record_generated(clip["clip_id"], 5.0, 1920, 1080, True, "abc123", db_path=tmp_db)
    ok, reason = clip_db.can_reuse(clip["clip_id"], db_path=tmp_db)
    assert not ok
    assert "file missing" in reason


def test_can_reuse_false_when_duration_too_short(tmp_db):
    clip = _order_basic(tmp_db, required_start_sec=0.0, required_end_sec=5.0)
    # Create the file
    full_path = clip_db.ROOT / clip["output_path"]
    _make_tiny_mp4(full_path)
    sha = clip_db._sha256_file(full_path)
    # Record with actual duration too short (1s vs required 5s, tolerance 0.25)
    clip_db.record_generated(clip["clip_id"], 1.0, 64, 64, True, sha, db_path=tmp_db)
    ok, reason = clip_db.can_reuse(clip["clip_id"], db_path=tmp_db)
    assert not ok
    assert "actual_dur" in reason
    # Cleanup
    full_path.unlink(missing_ok=True)


def test_can_reuse_false_when_change_requested(tmp_db):
    clip = _order_basic(tmp_db)
    full_path = clip_db.ROOT / clip["output_path"]
    _make_tiny_mp4(full_path)
    sha = clip_db._sha256_file(full_path)
    clip_db.record_generated(clip["clip_id"], 5.5, 64, 64, True, sha, db_path=tmp_db)
    # Now request a change
    clip_db.request_change(clip["clip_id"], "qa_media", "generate_media", "regenerate", "too dark", db_path=tmp_db)
    ok, reason = clip_db.can_reuse(clip["clip_id"], db_path=tmp_db)
    assert not ok
    assert "change_requested" in reason
    full_path.unlink(missing_ok=True)


def test_can_reuse_true_when_valid_and_matches(tmp_db):
    clip = _order_basic(tmp_db)
    full_path = clip_db.ROOT / clip["output_path"]
    _make_tiny_mp4(full_path)
    sha = clip_db._sha256_file(full_path)
    clip_db.record_generated(clip["clip_id"], 5.5, 64, 64, True, sha, db_path=tmp_db)
    clip_db.mark_valid(clip["clip_id"], db_path=tmp_db)
    ok, reason = clip_db.can_reuse(clip["clip_id"], db_path=tmp_db)
    assert ok
    assert reason == "reusable"
    full_path.unlink(missing_ok=True)


def test_request_change_drops_clip_out_of_valid(tmp_db):
    clip = _order_basic(tmp_db)
    clip_db.record_generated(clip["clip_id"], 5.5, 1920, 1080, True, "sha_x", db_path=tmp_db)
    clip_db.mark_valid(clip["clip_id"], db_path=tmp_db)
    # Now request a change
    clip_db.request_change(clip["clip_id"], "qa_media", "generate_media", "regenerate", "wrong angle", db_path=tmp_db)
    c = clip_db.get_clip(clip["clip_id"], db_path=tmp_db)
    assert c["status"] == "change_requested"


def test_resolve_change_returns_clip_to_flow(tmp_db):
    clip = _order_basic(tmp_db)
    clip_db.record_generated(clip["clip_id"], 5.5, 1920, 1080, True, "sha_x", db_path=tmp_db)
    clip_db.mark_valid(clip["clip_id"], db_path=tmp_db)
    clip_db.request_change(clip["clip_id"], "qa_media", "generate_media", "regenerate", "too dark", db_path=tmp_db)
    # Resolve
    clip_db.resolve_change(clip["clip_id"], "generate_media", "regenerated successfully", db_path=tmp_db)
    c = clip_db.get_clip(clip["clip_id"], db_path=tmp_db)
    assert c["status"] == "ordered"  # back in flow, ready to re-generate


def test_assert_all_valid_fails_with_open_request(tmp_db):
    clip = _order_basic(tmp_db)
    clip_db.record_generated(clip["clip_id"], 5.5, 1920, 1080, True, "sha_x", db_path=tmp_db)
    clip_db.mark_valid(clip["clip_id"], db_path=tmp_db)
    clip_db.request_change(clip["clip_id"], "reconcile", "generate_media", "regenerate", "short", db_path=tmp_db)
    ok, problems = clip_db.assert_all_valid("proj001", db_path=tmp_db)
    assert not ok
    assert len(problems) > 0


def test_assert_all_valid_passes_when_all_valid(tmp_db):
    clip = _order_basic(tmp_db)
    clip_db.record_generated(clip["clip_id"], 5.5, 1920, 1080, True, "sha_x", db_path=tmp_db)
    clip_db.mark_valid(clip["clip_id"], db_path=tmp_db)
    ok, problems = clip_db.assert_all_valid("proj001", db_path=tmp_db)
    assert ok
    assert problems == []


def test_coverage_for_beat_sums_children(tmp_db):
    """B005a + B005b sum to cover B005 (parent→child resolution)."""
    _order_basic(tmp_db, source_beat_id="B005", production_beat_id="B005a",
                 required_start_sec=0.0, required_end_sec=5.0, split_index=0, split_total=2)
    _order_basic(tmp_db, source_beat_id="B005", production_beat_id="B005b",
                 required_start_sec=5.0, required_end_sec=10.0, split_index=1, split_total=2)
    # Record both generated
    clip_db.record_generated("proj001::B005a::whole", 5.0, 1920, 1080, False, "sha_a", db_path=tmp_db)
    clip_db.record_generated("proj001::B005b::whole", 5.0, 1920, 1080, False, "sha_b", db_path=tmp_db)
    cov = clip_db.coverage_for_beat("proj001", "B005", db_path=tmp_db)
    assert cov["required"] == 10.0
    assert cov["available"] == 10.0
    assert cov["deficit"] == 0.0
    assert cov["all_present"]
    assert len(cov["slots"]) == 2


def test_coverage_for_beat_reports_deficit(tmp_db):
    """Children sum < required → deficit reported."""
    _order_basic(tmp_db, source_beat_id="B006", production_beat_id="B006a",
                 required_start_sec=0.0, required_end_sec=7.0, split_index=0, split_total=2)
    _order_basic(tmp_db, source_beat_id="B006", production_beat_id="B006b",
                 required_start_sec=7.0, required_end_sec=14.0, split_index=1, split_total=2)
    # Only one child generated, with short duration
    clip_db.record_generated("proj001::B006a::whole", 5.0, 1920, 1080, False, "sha_a", db_path=tmp_db)
    cov = clip_db.coverage_for_beat("proj001", "B006", db_path=tmp_db)
    assert cov["required"] == 14.0
    assert cov["available"] == 5.0
    assert cov["deficit"] == 9.0
    assert not cov["all_present"]


def test_access_log_records_actions(tmp_db):
    clip = _order_basic(tmp_db)
    clip_db.record_generated(clip["clip_id"], 5.5, 1920, 1080, True, "sha_x", db_path=tmp_db)
    clip_db.mark_valid(clip["clip_id"], db_path=tmp_db)
    conn = clip_db.get_db(tmp_db)
    logs = conn.execute("SELECT * FROM clip_access_log WHERE clip_id=? ORDER BY id",
                        (clip["clip_id"],)).fetchall()
    conn.close()
    actions = [l["action"] for l in logs]
    assert "order" in actions
    assert "generate" in actions
    assert "validate" in actions


def test_open_change_requests_routes_to_target_step(tmp_db):
    clip = _order_basic(tmp_db)
    clip_db.request_change(clip["clip_id"], "qa_media", "generate_media", "regenerate", "bad", db_path=tmp_db)
    # Also create another clip with request to a different step
    clip2 = _order_basic(tmp_db, production_beat_id="B099", source_beat_id="B099")
    clip_db.request_change(clip2["clip_id"], "reconcile", "slice_lipsync", "re-slice", "audio mismatch", db_path=tmp_db)

    # Filter by target_step
    gen_reqs = clip_db.open_change_requests("proj001", target_step="generate_media", db_path=tmp_db)
    assert len(gen_reqs) == 1
    assert gen_reqs[0]["clip_id"] == clip["clip_id"]

    slice_reqs = clip_db.open_change_requests("proj001", target_step="slice_lipsync", db_path=tmp_db)
    assert len(slice_reqs) == 1
    assert slice_reqs[0]["clip_id"] == clip2["clip_id"]

    # Unfiltered returns all
    all_reqs = clip_db.open_change_requests("proj001", db_path=tmp_db)
    assert len(all_reqs) == 2
