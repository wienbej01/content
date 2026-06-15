"""CDB-05: qa_media interacts with clip_db — marks valid, raises change requests."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db


def _make_clip(tmp_path, duration=5.0, has_audio=False, width=1280, height=720):
    """Create a minimal valid MP4 clip via FFmpeg with visual variation (passes perceptual QA)."""
    out = tmp_path / "clip.mp4"
    # Use testsrc2 to generate varied frames (not blank/frozen)
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
           f"testsrc2=size={width}x{height}:duration={duration}:rate=30"]
    if has_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-c:v", "libx264", "-c:a", "aac", "-shortest"]
    else:
        cmd += ["-c:v", "libx264", "-an"]
    cmd.append(str(out))
    subprocess.run(cmd, capture_output=True, check=True)
    return out


def _setup_project(tmp_path, beats, project_id="proj01"):
    """Create media plan JSON + order clips in DB, return plan path."""
    clip_db.init_db()
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    plan = {"project_id": project_id, "segments": beats,
            "defaults": {"format": "mp3"}}
    plan_path = proj_dir / "media_plan.json"
    plan_path.write_text(json.dumps(plan))
    return plan_path


def _order_clip(project_id, beat_id, segment_id="S01", required_dur=5.0, lipsync=False):
    """Insert a clip into clip_db, return clip_id."""
    clip_db.init_db()
    clip_db.order_clip(
        project_id=project_id,
        source_beat_id=beat_id,
        production_beat_id=beat_id,
        segment_id=segment_id,
        asset_type="generated_video",
        model="seedance_2_0" if lipsync else "kling3_0",
        audio_policy="keep_lipsync" if lipsync else "strip",
        lipsync_required=int(lipsync),
        required_start_sec=0.0,
        required_end_sec=required_dur,
        slot_id=None,
    )
    return f"{project_id}::{beat_id}::whole"


class TestQaPassMarksValid:
    """test_qa_pass_marks_clip_valid"""

    def test_passing_clip_becomes_valid(self, tmp_path):
        project_id = "proj01"
        clip_path = _make_clip(tmp_path, duration=5.0)
        clip_id = _order_clip(project_id, "B001", required_dur=5.0)

        # Create file at canonical output_path so mark_valid's filesystem check passes
        canonical = clip_db.ROOT / clip_db.get_path(clip_id)
        canonical.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(clip_path), str(canonical))
        sha = clip_db._sha256_file(canonical)

        # Record as generated so it's in 'generated' state
        clip_db.record_generated(clip_id, actual_dur_sec=5.0, actual_width=1280,
                                 actual_height=720, actual_has_audio=False, actual_sha256=sha)

        # Build a plan with the clip pointing to the fixture file
        beats = [{"id": "B001", "beat_id": "B001", "segment_id": "S01",
                  "audio_mode": "generated_tts", "media": str(clip_path)}]
        plan_path = _setup_project(tmp_path, beats, project_id)

        from qa_media import run_qa
        results, _ = run_qa(str(plan_path), project_id=project_id)

        assert results[0]["status"] == "PASS"
        clip = clip_db.get_clip(clip_id)
        assert clip["status"] == "valid"


class TestQaCoverageDeficitRequestsRegenerate:
    """test_qa_coverage_deficit_requests_regenerate"""

    def test_short_clip_raises_regenerate(self, tmp_path):
        project_id = "proj01"
        # Clip is 3s but timing map requires 6s → coverage deficit
        clip_path = _make_clip(tmp_path, duration=3.0)
        clip_id = _order_clip(project_id, "B002", required_dur=6.0)
        clip_db.record_generated(clip_id, actual_dur_sec=3.0, actual_width=1280,
                                 actual_height=720, actual_has_audio=False, actual_sha256="abc")

        beats = [{"id": "B002", "beat_id": "B002", "segment_id": "S01",
                  "audio_mode": "generated_tts", "media": str(clip_path)}]
        plan_path = _setup_project(tmp_path, beats, project_id)

        # Create timing map relative to base (plan dir) so _load_timing_map finds it
        nar_dir = plan_path.parent / "narration"
        nar_dir.mkdir(parents=True, exist_ok=True)
        tm = {"beats": [{"beat_id": "B002", "start": 0.0, "end": 6.0}], "total_duration": 6.0}
        (nar_dir / "beat_timing_map.json").write_text(json.dumps(tm))

        from qa_media import run_qa
        results, passed = run_qa(str(plan_path), project_id=project_id)

        assert not passed
        assert results[0]["status"] == "FAIL"
        clip = clip_db.get_clip(clip_id)
        assert clip["status"] == "change_requested"
        reqs = clip_db.open_change_requests(project_id, target_step="generate_media")
        assert len(reqs) >= 1
        assert reqs[0]["change_type"] == "regenerate"
        assert "COVERAGE_DEFICIT" in reqs[0]["reason"]


class TestQaAudioMismatchRequestsReslice:
    """test_qa_audio_mismatch_requests_reslice"""

    def test_audio_mismatch_routes_to_slice(self, tmp_path):
        project_id = "proj01"
        # Hero lipsync clip with audio that doesn't match speech_len
        clip_path = _make_clip(tmp_path, duration=5.0, has_audio=True)
        clip_id = _order_clip(project_id, "B003", required_dur=5.0, lipsync=True)
        clip_db.record_generated(clip_id, actual_dur_sec=5.0, actual_width=1280,
                                 actual_height=720, actual_has_audio=True, actual_sha256="abc")

        # audio_slice provenance with speech_len that won't match actual audio duration
        beats = [{"id": "B003", "beat_id": "B003", "segment_id": "S01",
                  "audio_mode": "baked_in", "shot_type": "hero_lipsync",
                  "audio_policy": "keep_lipsync", "lipsync_required": True,
                  "media": str(clip_path),
                  "audio_slice": {"speech_len_sec": 99.0, "padded_len_sec": 99.5,
                                  "slice_sha256": "x", "parent_mp3_sha256": "y",
                                  "file": "fake.wav"}}]
        plan_path = _setup_project(tmp_path, beats, project_id)

        from qa_media import run_qa
        results, passed = run_qa(str(plan_path), project_id=project_id)

        assert not passed
        clip = clip_db.get_clip(clip_id)
        assert clip["status"] == "change_requested"
        reqs = clip_db.open_change_requests(project_id, target_step="slice_lipsync")
        assert len(reqs) >= 1
        assert reqs[0]["change_type"] == "re-slice"


class TestQaMissingClipRequestsRegenerate:
    """test_qa_missing_clip_requests_regenerate"""

    def test_missing_clip_routes_to_generate(self, tmp_path):
        project_id = "proj01"
        clip_id = _order_clip(project_id, "B004", required_dur=5.0)
        # Don't generate the file — it's missing

        beats = [{"id": "B004", "beat_id": "B004", "segment_id": "S01",
                  "audio_mode": "generated_tts",
                  "media": str(tmp_path / "nonexistent.mp4")}]
        plan_path = _setup_project(tmp_path, beats, project_id)

        from qa_media import run_qa
        results, passed = run_qa(str(plan_path), project_id=project_id)

        assert not passed
        clip = clip_db.get_clip(clip_id)
        assert clip["status"] == "change_requested"
        reqs = clip_db.open_change_requests(project_id, target_step="generate_media")
        assert any(r["change_type"] == "regenerate" and "MISSING" in r["reason"] for r in reqs)


class TestChangeRequestRoutesToOwningStep:
    """test_change_request_routes_to_owning_step"""

    def test_open_requests_filtered_by_step(self, tmp_path):
        project_id = "proj01"
        clip_db.init_db()
        # Create two clips with different change targets
        cid1 = _order_clip(project_id, "B010", required_dur=5.0)
        cid2 = _order_clip(project_id, "B011", required_dur=5.0)

        clip_db.request_change(cid1, "qa_media", "generate_media", "regenerate", "too short")
        clip_db.request_change(cid2, "qa_media", "slice_lipsync", "re-slice", "audio mismatch")

        gen_reqs = clip_db.open_change_requests(project_id, target_step="generate_media")
        slice_reqs = clip_db.open_change_requests(project_id, target_step="slice_lipsync")

        assert len(gen_reqs) == 1
        assert gen_reqs[0]["clip_id"] == cid1
        assert len(slice_reqs) == 1
        assert slice_reqs[0]["clip_id"] == cid2


class TestQaDoesNotCrashPipeline:
    """test_qa_does_not_crash_pipeline"""

    def test_qa_returns_summary_with_change_requests(self, tmp_path):
        project_id = "proj01"
        clip_path = _make_clip(tmp_path, duration=5.0)
        clip_id = _order_clip(project_id, "B005", required_dur=5.0)

        # Create file at canonical output_path so mark_valid's filesystem check passes
        canonical = clip_db.ROOT / clip_db.get_path(clip_id)
        canonical.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(clip_path), str(canonical))
        sha = clip_db._sha256_file(canonical)
        clip_db.record_generated(clip_id, actual_dur_sec=5.0, actual_width=1280,
                                 actual_height=720, actual_has_audio=False, actual_sha256=sha)

        # One passing, one missing
        cid2 = _order_clip(project_id, "B006", required_dur=5.0)

        beats = [
            {"id": "B005", "beat_id": "B005", "segment_id": "S01",
             "audio_mode": "generated_tts", "media": str(clip_path)},
            {"id": "B006", "beat_id": "B006", "segment_id": "S01",
             "audio_mode": "generated_tts", "media": str(tmp_path / "missing.mp4")},
        ]
        plan_path = _setup_project(tmp_path, beats, project_id)

        from qa_media import run_qa
        results, passed = run_qa(str(plan_path), project_id=project_id)

        # Returns a usable summary (not an exception)
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(passed, bool)
        # One passed, one failed — but we got a result not a crash
        statuses = {r["id"]: r["status"] for r in results}
        assert statuses["B005"] == "PASS"
        assert statuses["B006"] == "FAIL"
