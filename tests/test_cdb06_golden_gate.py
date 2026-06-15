"""CDB-06: Golden-truth gate — build_manifest blocked unless all clips valid."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db

SCRIPT = ROOT / "scripts" / "build_manifest.py"


def _order(project_id, beat_id, segment_id="S01", dur=5.0, lipsync=False):
    clip_db.init_db()
    clip_db.order_clip(
        project_id=project_id, source_beat_id=beat_id,
        production_beat_id=beat_id, segment_id=segment_id,
        asset_type="generated_video",
        model="seedance_2_0" if lipsync else "kling3_0",
        audio_policy="keep_lipsync" if lipsync else "strip",
        lipsync_required=int(lipsync),
        required_start_sec=0.0, required_end_sec=dur, slot_id=None,
    )
    return f"{project_id}::{beat_id}::whole"


def _make_clip(path, duration=5.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:s=64x64:d={duration}",
         "-c:v", "libx264", "-t", str(duration), str(path)],
        capture_output=True, check=True)


def _fixtures(tmp_path, project_id="proj01", beats=None):
    """Write minimal plan + timing for build_manifest."""
    if beats is None:
        beats = [{"beat_id": "B001", "segment_id": "S01",
                  "output_path": "clips/B001.mp4", "audio_policy": "strip",
                  "narration_text": "test"}]
    plan = {"project_id": project_id, "beats": beats}
    (tmp_path / "media_plan.json").write_text(json.dumps(plan))
    narr = tmp_path / "narration"
    narr.mkdir(exist_ok=True)
    timing_beats = [{"beat_id": b["beat_id"], "start": i * 5.0, "end": (i + 1) * 5.0,
                     "duration": 5.0} for i, b in enumerate(beats)]
    timing = {"total_duration": len(beats) * 5.0, "beat_count": len(beats), "beats": timing_beats}
    (narr / "beat_timing_map.json").write_text(json.dumps(timing))
    # Create clip files
    for b in beats:
        _make_clip(tmp_path / b["output_path"])
    (tmp_path / "state.json").write_text(json.dumps({"format": "teaser"}))


def _run(project_dir):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


class TestGoldenGate:

    def test_manifest_blocked_when_clip_not_valid(self, tmp_path):
        """Clip in 'generated' (not 'valid') blocks manifest."""
        project_id = "proj01"
        _fixtures(tmp_path, project_id)
        cid = _order(project_id, "B001")
        clip_db.record_generated(cid, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256="abc")
        # status is 'generated', not 'valid'
        rc, _, stderr = _run(tmp_path)
        assert rc == 1
        assert "golden-truth gate FAILED" in stderr
        assert "B001" in stderr

    def test_manifest_blocked_when_open_change_request(self, tmp_path):
        """Clip with open change request blocks manifest with reason + target_step."""
        project_id = "proj02"
        _fixtures(tmp_path, project_id)
        cid = _order(project_id, "B001")
        clip_db.record_generated(cid, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256="abc")
        clip_db.mark_valid(cid)
        clip_db.request_change(cid, requested_by="qa_media", target_step="generate_media",
                               change_type="regenerate", reason="too short")
        rc, _, stderr = _run(tmp_path)
        assert rc == 1
        assert "golden-truth gate FAILED" in stderr
        assert "generate_media" in stderr
        assert "too short" in stderr

    def test_manifest_proceeds_when_all_valid(self, tmp_path):
        """All clips valid → manifest builds successfully."""
        project_id = "proj03"
        _fixtures(tmp_path, project_id)
        cid = _order(project_id, "B001")
        clip_db.record_generated(cid, actual_dur_sec=5.0, actual_width=64,
                                 actual_height=64, actual_has_audio=False, actual_sha256="abc")
        clip_db.mark_valid(cid)
        rc, _, stderr = _run(tmp_path)
        assert rc == 0, f"Expected success, got: {stderr}"
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert len(manifest["segments"]) == 1

    def test_legacy_no_clips_skips_assertion(self, tmp_path):
        """Project with no clip_db rows → manifest builds with warning."""
        _fixtures(tmp_path, "legacy_proj")
        rc, _, stderr = _run(tmp_path)
        assert rc == 0, f"Expected success for legacy, got: {stderr}"
        assert "legacy" in stderr.lower() or "skipping" in stderr.lower()
        assert (tmp_path / "manifest.json").exists()
