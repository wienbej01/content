"""CDB-04: reconcile_duration uses clip_db.coverage_for_beat() to resolve parent→children."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clip_db


def _setup_project(tmp_path, timing_beats, project_id="test_proj"):
    """Create minimal project dir with timing map and media plan."""
    proj = tmp_path / "proj"
    (proj / "narration").mkdir(parents=True)
    timing = {"beats": timing_beats, "total_duration": sum(b["end"] - b["start"] for b in timing_beats), "beat_count": len(timing_beats)}
    (proj / "narration" / "beat_timing_map.json").write_text(json.dumps(timing))
    plan = {"beats": [], "schema_version": "media_plan_2.0", "project_id": project_id}
    (proj / "media_plan.json").write_text(json.dumps(plan))
    return proj


def _order_and_generate(project_id, source_beat_id, production_beat_id, required_dur, actual_dur, slot_id=None):
    """Insert a clip into clip_db and record it as generated."""
    clip_db.init_db()
    clip_db.order_clip(
        project_id=project_id,
        source_beat_id=source_beat_id,
        production_beat_id=production_beat_id,
        segment_id="S01",
        asset_type="generated_video",
        model="seedance_2_0",
        audio_policy="keep_lipsync",
        lipsync_required=1,
        required_start_sec=0.0,
        required_end_sec=required_dur,
        slot_id=slot_id,
    )
    clip_id = f"{project_id}::{production_beat_id}::{slot_id or 's0'}"
    clip_db.record_generated(
        clip_id=clip_id,
        actual_dur_sec=actual_dur,
        actual_width=1920,
        actual_height=1080,
        actual_has_audio=True,
        actual_sha256="abc123",
    )
    return clip_id


def test_parent_beat_resolved_via_children(tmp_path):
    """B005a (11.5s) + B005b (7.8s) in DB with source_beat_id=B005; timing needs 19.3s → PASS."""
    project_id = "test_proj"
    proj = _setup_project(tmp_path, [{"beat_id": "B005", "start": 0.0, "end": 19.3}], project_id)

    _order_and_generate(project_id, "B005", "B005a", 11.5, 11.5, slot_id="s0")
    _order_and_generate(project_id, "B005", "B005b", 7.8, 7.8, slot_id="s1")

    from reconcile_duration import reconcile
    rows, failures, total_deficit = reconcile(str(proj))
    assert len(failures) == 0
    assert total_deficit <= 0.25
    assert rows[0][4] == "OK"


def test_deficit_when_children_short(tmp_path):
    """Children sum < required → FAIL with deficit."""
    project_id = "test_proj"
    proj = _setup_project(tmp_path, [{"beat_id": "B011", "start": 0.0, "end": 20.0}], project_id)

    _order_and_generate(project_id, "B011", "B011a", 10.0, 8.0, slot_id="s0")
    _order_and_generate(project_id, "B011", "B011b", 10.0, 7.0, slot_id="s1")

    from reconcile_duration import reconcile
    rows, failures, total_deficit = reconcile(str(proj))
    assert len(failures) == 1
    assert failures[0][0] == "B011"
    assert failures[0][1] > 0
    assert total_deficit > 0.25


def test_missing_slot_detected(tmp_path):
    """A slot never generated (status != generated/valid) → FAIL."""
    project_id = "test_proj"
    proj = _setup_project(tmp_path, [{"beat_id": "B005", "start": 0.0, "end": 15.0}], project_id)

    # Only order one child, generate it; order second but don't generate
    _order_and_generate(project_id, "B005", "B005a", 7.5, 7.5, slot_id="s0")
    # Order but don't generate B005b
    clip_db.order_clip(
        project_id=project_id,
        source_beat_id="B005",
        production_beat_id="B005b",
        segment_id="S01",
        asset_type="generated_video",
        model="seedance_2_0",
        audio_policy="keep_lipsync",
        lipsync_required=1,
        required_start_sec=7.5,
        required_end_sec=15.0,
        slot_id="s1",
    )

    from reconcile_duration import reconcile
    rows, failures, total_deficit = reconcile(str(proj))
    assert len(failures) == 1
    assert failures[0][0] == "B005"
    assert rows[0][4] == "SLOT_MISSING"


def test_single_beat_no_split(tmp_path):
    """A whole beat (no children) reconciles correctly via DB."""
    project_id = "test_proj"
    proj = _setup_project(tmp_path, [{"beat_id": "B001", "start": 0.0, "end": 8.0}], project_id)

    _order_and_generate(project_id, "B001", "B001", 8.0, 8.2, slot_id="s0")

    from reconcile_duration import reconcile
    rows, failures, total_deficit = reconcile(str(proj))
    assert len(failures) == 0
    assert rows[0][4] == "OK"


def test_csv_written(tmp_path):
    """duration_reconciliation.csv is produced."""
    project_id = "test_proj"
    proj = _setup_project(tmp_path, [{"beat_id": "B001", "start": 0.0, "end": 5.0}], project_id)
    _order_and_generate(project_id, "B001", "B001", 5.0, 5.0, slot_id="s0")

    # Run via subprocess to test full CLI path including CSV write
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reconcile_duration.py"), str(proj)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    assert r.returncode == 0
    csv_path = proj / "duration_reconciliation.csv"
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "B001" in content
    assert "beat_id" in content


def test_legacy_fallback(tmp_path):
    """Project with no clip_db rows falls back to ffprobe logic."""
    project_id = "legacy_proj_no_db"
    proj = tmp_path / "proj"
    (proj / "narration").mkdir(parents=True)
    timing = {"beats": [{"beat_id": "B001", "start": 0.0, "end": 5.0}], "total_duration": 5.0, "beat_count": 1}
    (proj / "narration" / "beat_timing_map.json").write_text(json.dumps(timing))

    # Create a clip file via ffmpeg
    clip_path = proj / "B001.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=320x240:d=5:r=24",
         "-c:v", "libx264", "-t", "5", str(clip_path)],
        capture_output=True, check=True
    )
    plan = {"beats": [{"beat_id": "B001", "output_path": str(clip_path), "asset_type": "generated_video"}],
            "project_id": project_id}
    (proj / "media_plan.json").write_text(json.dumps(plan))

    # No rows in clip_db for this project → should fallback to ffprobe
    from reconcile_duration import reconcile
    rows, failures, total_deficit = reconcile(str(proj))
    assert len(failures) == 0
    assert rows[0][4] == "OK"
