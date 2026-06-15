#!/usr/bin/env python3
"""tests/test_cdb03_generate_reuse.py — CDB-03: generate_media uses clip_db for reuse/record."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db
from clip_db import (
    init_db, order_clip, can_reuse, record_generated, mark_failed, get_clip, get_path,
)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_video(path, dur=5, w=1280, h=720, audio=True):
    """Create a minimal video file via ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={w}x{h}:r=24:d={dur}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={dur}",
                "-c:a", "aac", "-ar", "48000"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
            "-pix_fmt", "yuv420p", "-shortest", str(path)]
    subprocess.run(cmd, capture_output=True, check=True)


def _order_beat(project_id, beat_id, segment_id, required_dur, lipsync=False,
                model="kling3_0", slot_id=None):
    """Helper to order a clip in the DB and return clip_id."""
    return order_clip(
        project_id=project_id,
        source_beat_id=beat_id,
        production_beat_id=beat_id,
        segment_id=segment_id,
        asset_type="generated_video",
        model=model,
        audio_policy="keep_lipsync" if lipsync else "strip",
        lipsync_required=lipsync,
        required_start_sec=0.0,
        required_end_sec=required_dur,
        slot_id=slot_id,
    )


def _make_plan(tmp_path, project_id, beats):
    """Write a minimal media_plan.json."""
    plan = {
        "schema_version": "media_plan_v1",
        "project_id": project_id,
        "beats": beats,
    }
    plan_path = tmp_path / "media_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    return plan_path


# --- Tests ---


def test_reuse_skips_generation_when_valid(tmp_path):
    """A clip recorded as generated with covering duration → can_reuse True → no gen call."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B001", "seg1", required_dur=5.0)
    clip_id = clip["clip_id"]

    # Create a valid video at the canonical path
    out_path = ROOT / clip["output_path"]
    _make_video(out_path, dur=5)
    sha = _sha256(out_path)

    # Record it as generated (covers 5s requirement)
    record_generated(clip_id, actual_dur_sec=5.0, actual_width=1280, actual_height=720,
                     actual_has_audio=False, actual_sha256=sha)

    # Verify can_reuse says True
    reusable, reason = can_reuse(clip_id)
    assert reusable, f"Expected reusable but got: {reason}"

    # Build a plan that references this beat with clip_id
    beat = {
        "beat_id": "B001", "shot_type": "b_roll", "model": "kling3_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    # Mock gates + hf_available + the actual generation call
    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip") as mock_gen:
        import generate_media
        summary = generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    # Generation should NOT have been called
    mock_gen.assert_not_called()
    assert summary["beats_reused"] == 1
    assert summary["beats_generated"] == 0


def test_regenerate_when_duration_short(tmp_path):
    """A clip with actual 10s but required 14s → can_reuse False → generation called."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B002", "seg1", required_dur=14.0)
    clip_id = clip["clip_id"]

    # Create a short video (10s) at canonical path
    out_path = ROOT / clip["output_path"]
    _make_video(out_path, dur=10)
    sha = _sha256(out_path)

    # Record it as generated — but only 10s (insufficient for 14s requirement)
    record_generated(clip_id, actual_dur_sec=10.0, actual_width=1280, actual_height=720,
                     actual_has_audio=False, actual_sha256=sha)

    # can_reuse should be False
    reusable, reason = can_reuse(clip_id)
    assert not reusable
    assert "actual_dur" in reason or "10" in reason

    # Build plan
    beat = {
        "beat_id": "B002", "shot_type": "b_roll", "model": "kling3_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    # Mock generation: simulate creating a 14s clip
    new_vid = out_path  # generation writes to canonical path
    def fake_gen(b, op, **kwargs):
        _make_video(op, dur=14)
        return {"beat_id": "B002", "media_path": str(op), "model": "kling3_0", "duration": 14.0}

    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip", side_effect=fake_gen) as mock_gen:
        import generate_media
        summary = generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    mock_gen.assert_called_once()
    assert summary["beats_generated"] == 1


def test_regenerate_when_change_requested(tmp_path):
    """Open change request → not reusable → regenerate."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B003", "seg1", required_dur=5.0)
    clip_id = clip["clip_id"]

    # Create a valid file + record
    out_path = ROOT / clip["output_path"]
    _make_video(out_path, dur=5)
    sha = _sha256(out_path)
    record_generated(clip_id, actual_dur_sec=5.0, actual_width=1280, actual_height=720,
                     actual_has_audio=False, actual_sha256=sha)

    # Now request a change → status becomes change_requested
    from clip_db import request_change
    request_change(clip_id, requested_by="qa_media", target_step="generate_media",
                   change_type="regenerate", reason="quality issue")

    # can_reuse should be False
    reusable, reason = can_reuse(clip_id)
    assert not reusable
    assert "change_requested" in reason

    # Build plan and verify generation is called
    beat = {
        "beat_id": "B003", "shot_type": "b_roll", "model": "kling3_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    def fake_gen(b, op, **kwargs):
        _make_video(op, dur=5)
        return {"beat_id": "B003", "media_path": str(op), "model": "kling3_0", "duration": 5.0}

    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip", side_effect=fake_gen):
        import generate_media
        summary = generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    assert summary["beats_generated"] == 1


def test_record_generated_writes_actual_attrs(tmp_path):
    """After generation, DB has actual_dur_sec/sha/has_audio."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B004", "seg1", required_dur=6.0)
    clip_id = clip["clip_id"]

    beat = {
        "beat_id": "B004", "shot_type": "b_roll", "model": "kling3_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    out_path = ROOT / clip["output_path"]
    # Ensure no leftover file from previous runs
    out_path.unlink(missing_ok=True)

    def fake_gen(b, op, **kwargs):
        _make_video(op, dur=6, w=1920, h=1080, audio=True)
        return {"beat_id": "B004", "media_path": str(op), "model": "kling3_0", "duration": 6.0}

    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip", side_effect=fake_gen):
        import generate_media
        generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    # Check DB has actual attrs
    row = get_clip(clip_id)
    assert row is not None
    assert row["status"] == "generated"
    assert row["actual_dur_sec"] is not None and row["actual_dur_sec"] > 5.0
    assert row["actual_width"] == 1920
    assert row["actual_height"] == 1080
    assert row["actual_has_audio"] == 1
    assert row["actual_sha256"] is not None and len(row["actual_sha256"]) == 64


def test_failed_generation_marks_failed(tmp_path):
    """Provider fails → clip status 'failed', NOT 'generated'."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B005", "seg1", required_dur=5.0, lipsync=True,
                       model="seedance_2_0")
    clip_id = clip["clip_id"]

    # Create a dummy audio slice (lipsync requires it)
    project_dir = ROOT / "Videos" / "Projects" / project_id
    slice_dir = project_dir / "narration" / "slices"
    slice_dir.mkdir(parents=True, exist_ok=True)
    slice_path = slice_dir / "B005_slice.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                    "-c:a", "libmp3lame", str(slice_path)], capture_output=True, check=True)

    beat = {
        "beat_id": "B005", "shot_type": "hero_lipsync", "model": "seedance_2_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "lipsync_required": True,
        "audio_slice": {"file": f"narration/slices/B005_slice.mp3", "padded_len_sec": 5},
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    def fake_gen_fail(b, op, **kwargs):
        raise RuntimeError("Higgsfield API timeout")

    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip", side_effect=fake_gen_fail), \
         patch("generate_media.time.sleep"), \
         pytest.raises(RuntimeError, match="hero_lipsync generation failed"):
        import generate_media
        generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    row = get_clip(clip_id)
    assert row["status"] == "failed"
    assert "lipsync generation failed" in (row["status_reason"] or "")


def test_generates_to_canonical_db_path(tmp_path):
    """The file is created at clip_db.get_path(clip_id), not a re-derived path."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B006", "seg1", required_dur=5.0)
    clip_id = clip["clip_id"]
    canonical = get_path(clip_id)
    assert canonical is not None

    beat = {
        "beat_id": "B006", "shot_type": "b_roll", "model": "kling3_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    expected_full = ROOT / canonical

    def fake_gen(b, op, **kwargs):
        # Verify that op IS the canonical path
        assert str(op) == str(expected_full), f"Expected {expected_full}, got {op}"
        _make_video(op, dur=5)
        return {"beat_id": "B006", "media_path": str(op), "model": "kling3_0", "duration": 5.0}

    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip", side_effect=fake_gen):
        import generate_media
        generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    assert expected_full.exists()


def test_slot_clip_generates_to_slot_path(tmp_path):
    """Slot clip lands at the {beat}_{slot}.mp4 path (missing-slot bug fix)."""
    init_db()
    project_id = "test_proj"
    clip = _order_beat(project_id, "B007", "seg1", required_dur=5.0, slot_id="B007-s0")
    clip_id = clip["clip_id"]
    canonical = get_path(clip_id)
    # Slot path should contain the slot suffix
    assert "B007_B007-s0.mp4" in canonical

    beat = {
        "beat_id": "B007", "shot_type": "b_roll", "model": "kling3_0",
        "positive_prompt": "test", "clip_id": clip_id,
        "output_path": clip["output_path"],
        "cost": {"est_usd": 1.0, "est_clips": 1},
    }
    plan_path = _make_plan(tmp_path, project_id, [beat])

    expected_full = ROOT / canonical

    def fake_gen(b, op, **kwargs):
        assert "B007_B007-s0.mp4" in str(op)
        _make_video(op, dur=5)
        return {"beat_id": "B007", "media_path": str(op), "model": "kling3_0", "duration": 5.0}

    with patch("generate_media.require_gates"), \
         patch("generate_media.check_hf_available", return_value=(True, "ok")), \
         patch("generate_media._generate_beat_clip", side_effect=fake_gen):
        import generate_media
        generate_media.run_from_media_plan(plan_path, dry_run=False, force=False)

    assert expected_full.exists()
