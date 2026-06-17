"""CDB-06 E2E: Full closed loop — deficit → change request → fix → valid → manifest proceeds."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db

SCRIPT = ROOT / "scripts" / "build_manifest.py"


def _make_clip(path, duration=5.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:s=64x64:d={duration}",
         "-c:v", "libx264", "-t", str(duration), str(path)],
        capture_output=True, check=True)


def _fixtures(tmp_path, project_id, beats):
    """Write plan + timing for build_manifest."""
    plan = {"project_id": project_id, "beats": beats}
    (tmp_path / "media_plan.json").write_text(json.dumps(plan))
    narr = tmp_path / "narration"
    narr.mkdir(exist_ok=True)
    timing_beats = [{"beat_id": b["beat_id"], "start": i * 7.0, "end": (i + 1) * 7.0,
                     "duration": 7.0} for i, b in enumerate(beats)]
    timing = {"total_duration": len(beats) * 7.0, "beat_count": len(beats), "beats": timing_beats}
    (narr / "beat_timing_map.json").write_text(json.dumps(timing))
    (tmp_path / "state.json").write_text(json.dumps({"format": "teaser"}))


def _run(project_dir):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


class TestFullLoopDeficitThenFixed:
    """Prove: order → generate short → QA raises change → blocked → regen → valid → proceed."""

    def test_full_loop_deficit_then_fixed(self, tmp_path):
        project_id = "e2e_proj"
        clip_db.init_db()

        # --- Step 1: Order clips (parent B001 split into 2 children) ---
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B001",
            production_beat_id="B001a", segment_id="S01",
            asset_type="generated_video", model="kling3_0",
            audio_policy="BROLL_FLEX", lipsync_required=0,
            required_start_sec=0.0, required_end_sec=7.0, slot_id=None)
        clip_db.order_clip(
            project_id=project_id, source_beat_id="B001",
            production_beat_id="B001b", segment_id="S01",
            asset_type="generated_video", model="kling3_0",
            audio_policy="BROLL_FLEX", lipsync_required=0,
            required_start_sec=7.0, required_end_sec=14.0, slot_id=None)

        cid_a = f"{project_id}::B001a::whole"
        cid_b = f"{project_id}::B001b::whole"

        # --- Step 2: Generate SHORT clips (deficit) ---
        clip_db.record_generated(cid_a, actual_dur_sec=4.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256="sha_a1")
        clip_db.record_generated(cid_b, actual_dur_sec=4.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256="sha_b1")

        # --- Step 3: QA raises change requests (clips too short) ---
        clip_db.request_change(cid_a, requested_by="qa_media", target_step="generate_media",
                               change_type="regenerate", reason="actual 4.0s < required 7.0s")
        clip_db.request_change(cid_b, requested_by="qa_media", target_step="generate_media",
                               change_type="regenerate", reason="actual 4.0s < required 7.0s")

        # --- Step 4: assert_all_valid FAILS → manifest blocked ---
        ok, problems = clip_db.assert_all_valid(project_id)
        assert ok is False
        assert len(problems) >= 2

        # Also verify via CLI
        beats = [
            {"beat_id": "B001a", "segment_id": "S01", "output_path": "clips/B001a.mp4",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT", "narration_text": "test a"},
            {"beat_id": "B001b", "segment_id": "S01", "output_path": "clips/B001b.mp4",
             "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT", "narration_text": "test b"},
        ]
        _fixtures(tmp_path, project_id, beats)
        _make_clip(tmp_path / "clips" / "B001a.mp4", duration=7.0)
        _make_clip(tmp_path / "clips" / "B001b.mp4", duration=7.0)

        rc, _, stderr = _run(tmp_path)
        assert rc == 1, f"Expected blocked, got rc=0: {stderr}"
        assert "golden-truth gate FAILED" in stderr

        # --- Step 5: Regenerate at correct duration + resolve changes ---
        path_a = clip_db.ROOT / clip_db.get_path(cid_a)
        path_b = clip_db.ROOT / clip_db.get_path(cid_b)
        path_a.parent.mkdir(parents=True, exist_ok=True)
        path_a.write_bytes(b"REGEN_A")
        path_b.write_bytes(b"REGEN_B")
        clip_db.record_generated(cid_a, actual_dur_sec=7.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_a))
        clip_db.resolve_change(cid_a, resolved_by="generate_media", outcome="regenerated")

        clip_db.record_generated(cid_b, actual_dur_sec=7.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256=clip_db._sha256_file(path_b))
        clip_db.resolve_change(cid_b, resolved_by="generate_media", outcome="regenerated")

        # Mark valid after successful regen
        clip_db.mark_valid(cid_a, validated_by="qa_media")
        clip_db.mark_valid(cid_b, validated_by="qa_media")

        # --- Step 6: assert_all_valid PASSES → manifest builds ---
        ok, problems = clip_db.assert_all_valid(project_id)
        assert ok is True
        assert problems == []

        rc, _, stderr = _run(tmp_path)
        assert rc == 0, f"Expected success after fix, got: {stderr}"
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert len(manifest["segments"]) == 2
