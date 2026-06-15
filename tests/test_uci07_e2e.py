"""UCI-07 E2E: slot+split full chain, feedback loop keyed on clip_id, sibling independence."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db


def _make_clip(path, duration=5.0):
    """Create a tiny mp4 via FFmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:s=64x64:d={duration}",
         "-c:v", "libx264", "-t", str(duration), str(path)],
        capture_output=True, check=True)


def _setup_project(tmp_path, project_id, plan_beats, timing_beats, total_dur):
    """Write media_plan.json + beat_timing_map.json + state.json for build_manifest."""
    plan = {"project_id": project_id, "beats": plan_beats}
    (tmp_path / "media_plan.json").write_text(json.dumps(plan))
    narr = tmp_path / "narration"
    narr.mkdir(exist_ok=True)
    timing = {"total_duration": total_dur, "beat_count": len(timing_beats), "beats": timing_beats}
    (narr / "beat_timing_map.json").write_text(json.dumps(timing))
    (tmp_path / "state.json").write_text(json.dumps({"format": "teaser"}))


def _run_manifest(project_dir):
    """Run build_manifest.py as subprocess."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_manifest.py"), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


class TestSlotAndSplitFullChain:
    """Test 1: Slot-expanded beat (1→3) + split beat (1→2) + 2 whole beats = 7 clips E2E."""

    def test_slot_and_split_full_chain(self, tmp_path):
        project_id = "uci07_full"
        clip_db.init_db()

        # --- Order 7 clips ---
        # Beat A: 3 coverage slots (source_beat_id=A001, slot_ids=A001-s0/s1/s2)
        for i in range(3):
            clip_db.order_clip(
                project_id=project_id, source_beat_id="A001",
                production_beat_id="A001", segment_id="S01",
                asset_type="generated_video", model="kling3_0",
                audio_policy="strip", lipsync_required=0,
                required_start_sec=i * 3.0, required_end_sec=(i + 1) * 3.0,
                slot_id=f"A001-s{i}")

        # Beat B: split into B002a, B002b (source_beat_id=B002)
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B002",
            production_beat_id="B002a", segment_id="S02",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=9.0, required_end_sec=13.0,
            split_index=0, split_total=2)
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B002",
            production_beat_id="B002b", segment_id="S02",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=13.0, required_end_sec=17.0,
            split_index=1, split_total=2)

        # Beat C, D: whole beats
        clip_db.order_clip(
            project_id=project_id, source_beat_id="C003",
            production_beat_id="C003", segment_id="S03",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=17.0, required_end_sec=21.0)
        clip_db.order_clip(
            project_id=project_id, source_beat_id="D004",
            production_beat_id="D004", segment_id="S04",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=21.0, required_end_sec=25.0)

        # Verify 7 distinct clip_ids
        all_clips = clip_db.list_clips(project_id)
        assert len(all_clips) == 7
        clip_ids = [c["clip_id"] for c in all_clips]
        assert len(set(clip_ids)) == 7, "clip_ids not unique"

        # --- Generate mock clips + record_generated ---
        for c in all_clips:
            clip_path = ROOT / c["output_path"]
            _make_clip(clip_path, duration=c["required_dur_sec"])
            sha = clip_db._sha256_file(clip_path)
            clip_db.record_generated(
                c["clip_id"], actual_dur_sec=c["required_dur_sec"],
                actual_width=64, actual_height=64, actual_has_audio=False,
                actual_sha256=sha)

        # --- QA marks valid ---
        for c in all_clips:
            clip_db.mark_valid(c["clip_id"])

        # --- Coverage check ---
        cov_a = clip_db.coverage_for_beat(project_id, "A001")
        assert len(cov_a["slots"]) == 3
        assert cov_a["all_present"] is True
        assert cov_a["deficit"] == 0.0

        cov_b = clip_db.coverage_for_beat(project_id, "B002")
        assert len(cov_b["slots"]) == 2
        assert cov_b["all_present"] is True

        # --- assert_all_valid passes ---
        ok, problems = clip_db.assert_all_valid(project_id)
        assert ok is True

        # --- Build manifest ---
        plan_beats = []
        for c in sorted(all_clips, key=lambda x: x["required_start_sec"]):
            plan_beats.append({
                "beat_id": c["production_beat_id"],
                "clip_id": c["clip_id"],
                "source_beat_id": c["source_beat_id"],
                "segment_id": c["production_beat_id"],
                "output_path": c["output_path"],
                "audio_policy": c["audio_policy"],
                "narration_text": "test",
                "required_start_sec": c["required_start_sec"],
                "required_end_sec": c["required_end_sec"],
            })
        timing_beats = [
            {"beat_id": "A001", "start": 0.0, "end": 9.0, "duration": 9.0},
            {"beat_id": "B002", "start": 9.0, "end": 17.0, "duration": 8.0},
            {"beat_id": "C003", "start": 17.0, "end": 21.0, "duration": 4.0},
            {"beat_id": "D004", "start": 21.0, "end": 25.0, "duration": 4.0},
        ]
        _setup_project(tmp_path, project_id, plan_beats, timing_beats, total_dur=25.0)

        rc, stdout, stderr = _run_manifest(tmp_path)
        assert rc == 0, f"manifest build failed: {stderr}"

        manifest = json.loads((tmp_path / "manifest.json").read_text())
        segments = manifest["segments"]

        # 7 segments, one per clip
        assert len(segments) == 7

        # All keyed by clip_id
        seg_ids = [s["clip_id"] for s in segments]
        assert len(set(seg_ids)) == 7

        # Ordered by start time (contiguous)
        timings = [(s["timing_in"], s["timing_out"]) for s in segments]
        for i in range(len(timings) - 1):
            assert timings[i][1] == pytest.approx(timings[i + 1][0], abs=0.01)

        # --- Assemble can resolve every clip path from DB ---
        for seg in segments:
            path = clip_db.get_path(seg["clip_id"])
            assert path is not None
            assert (ROOT / path).exists()

        # Cleanup generated clips
        for c in all_clips:
            p = ROOT / c["output_path"]
            if p.exists():
                p.unlink()
            # Remove empty parent dirs
            try:
                p.parent.rmdir()
            except OSError:
                pass


class TestFeedbackLoopKeyedOnClipId:
    """Test 2: Feedback loop keys on clip_id; sibling unaffected."""

    def test_feedback_loop_keyed_on_clip_id(self, tmp_path):
        project_id = "uci07_feedback"
        clip_db.init_db()

        # Order 2 slots for same beat
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B003",
            production_beat_id="B003", segment_id="S01",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=0.0, required_end_sec=5.0,
            slot_id="B003-s0")
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B003",
            production_beat_id="B003", segment_id="S01",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=5.0, required_end_sec=10.0,
            slot_id="B003-s1")

        cid_s0 = f"{project_id}::B003::B003-s0"
        cid_s1 = f"{project_id}::B003::B003-s1"

        # Generate BOTH — s0 too short (deficit), s1 correct
        path_s0 = clip_db.ROOT / clip_db.get_clip(cid_s0)["output_path"]
        path_s1 = clip_db.ROOT / clip_db.get_clip(cid_s1)["output_path"]
        path_s0.parent.mkdir(parents=True, exist_ok=True)
        path_s0.write_bytes(b"STUB_SHORT")
        path_s1.write_bytes(b"STUB_OK")
        clip_db.record_generated(cid_s0, actual_dur_sec=2.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_s0))
        clip_db.record_generated(cid_s1, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_s1))
        clip_db.mark_valid(cid_s1)  # s1 passes QA

        # QA raises change_request on s0 (keyed by clip_id)
        clip_db.request_change(cid_s0, requested_by="qa_media",
                               target_step="generate_media",
                               change_type="regenerate",
                               reason="actual 2.0s < required 5.0s")

        # assert_all_valid FAILS (s0 not valid)
        ok, problems = clip_db.assert_all_valid(project_id)
        assert ok is False
        # The problem references clip_id, not beat_id
        problem_ids = [p.get("clip_id") for p in problems]
        assert cid_s0 in problem_ids
        assert cid_s1 not in problem_ids

        # Verify s1 is still valid (unaffected by s0's change request)
        s1 = clip_db.get_clip(cid_s1)
        assert s1["status"] == "valid"

        # Regenerate s0 at correct duration
        clip_db.resolve_change(cid_s0, resolved_by="generate_media", outcome="regenerated")
        path_s0.write_bytes(b"STUB_FIXED")
        clip_db.record_generated(cid_s0, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_s0))
        clip_db.mark_valid(cid_s0)

        # assert_all_valid now PASSES
        ok, problems = clip_db.assert_all_valid(project_id)
        assert ok is True

        # Verify change request was resolved and keyed by clip_id
        open_reqs = clip_db.open_change_requests(project_id)
        assert len(open_reqs) == 0


class TestSiblingSlotsIndependent:
    """Test 3: Two slots share beat_id but change request on one doesn't affect the other."""

    def test_sibling_slots_independent(self, tmp_path):
        project_id = "uci07_sibling"
        clip_db.init_db()

        # Two slots sharing beat_id=B003
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B003",
            production_beat_id="B003", segment_id="S01",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=0.0, required_end_sec=5.0,
            slot_id="B003-s0")
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B003",
            production_beat_id="B003", segment_id="S01",
            asset_type="generated_video", model="kling3_0",
            audio_policy="strip", lipsync_required=0,
            required_start_sec=5.0, required_end_sec=10.0,
            slot_id="B003-s1")

        cid_s0 = f"{project_id}::B003::B003-s0"
        cid_s1 = f"{project_id}::B003::B003-s1"

        # Generate and validate BOTH
        path_s0 = clip_db.ROOT / clip_db.get_clip(cid_s0)["output_path"]
        path_s1 = clip_db.ROOT / clip_db.get_clip(cid_s1)["output_path"]
        path_s0.parent.mkdir(parents=True, exist_ok=True)
        path_s0.write_bytes(b"STUB_S0")
        path_s1.write_bytes(b"STUB_S1")
        clip_db.record_generated(cid_s0, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_s0))
        clip_db.mark_valid(cid_s0)
        clip_db.record_generated(cid_s1, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_s1))
        clip_db.mark_valid(cid_s1)

        # Both valid
        ok, _ = clip_db.assert_all_valid(project_id)
        assert ok is True

        # Change request on s0 ONLY
        clip_db.request_change(cid_s0, requested_by="qa_media",
                               target_step="generate_media",
                               change_type="regenerate",
                               reason="visual artifact detected")

        # s0 is now change_requested, s1 STILL valid
        s0 = clip_db.get_clip(cid_s0)
        s1 = clip_db.get_clip(cid_s1)
        assert s0["status"] == "change_requested"
        assert s1["status"] == "valid"

        # assert_all_valid fails only because of s0
        ok, problems = clip_db.assert_all_valid(project_id)
        assert ok is False
        problem_cids = [p.get("clip_id") for p in problems]
        assert cid_s0 in problem_cids
        assert cid_s1 not in problem_cids

        # Resolve s0 → everything passes
        clip_db.resolve_change(cid_s0, resolved_by="generate_media", outcome="regenerated")
        path_s0.write_bytes(b"STUB_S0_V2")
        clip_db.record_generated(cid_s0, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_s0))
        clip_db.mark_valid(cid_s0)

        ok, _ = clip_db.assert_all_valid(project_id)
        assert ok is True
