"""Tests for scripts/reconcile_duration.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "reconcile_duration.py"
AUDITED_PROJECT = ROOT / "Videos" / "Projects" / "using_ai_to_help_memory_retention_short"


def _make_clip(path, duration):
    """Generate a silent video clip of given duration using ffmpeg."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=black:s=1920x1080:d={duration}:r=24",
         "-c:v", "libx264", "-t", str(duration), str(path)],
        capture_output=True, check=True
    )


def _setup_project(tmp, beats_timing, beats_plan, create_clips=True):
    """Create a minimal project dir with timing map + media plan + optional clips."""
    proj = Path(tmp)
    (proj / "narration").mkdir(parents=True)
    timing = {"beats": beats_timing, "total_duration": sum(b["end"] - b["start"] for b in beats_timing), "beat_count": len(beats_timing)}
    (proj / "narration" / "beat_timing_map.json").write_text(json.dumps(timing))

    plan_beats = []
    for bp in beats_plan:
        plan_beats.append(bp)
        if create_clips and bp.get("output_path") and bp.get("asset_type") != "local_graphic":
            clip_path = ROOT / bp["output_path"] if bp["output_path"].startswith("assets/") else proj / bp["output_path"]
            # For tests, put clips inside tmp dir
            clip_path = proj / f"{bp['beat_id']}.mp4"
            bp["output_path"] = str(clip_path)
            _make_clip(clip_path, bp.get("_test_duration", 5.0))

    plan = {"beats": plan_beats, "schema_version": "media_plan_2.0", "project_id": "test"}
    (proj / "media_plan.json").write_text(json.dumps(plan))
    return proj


def _run(project_dir):
    """Run reconcile_duration.py, return (returncode, stdout, stderr)."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(project_dir)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    return r.returncode, r.stdout, r.stderr


def test_sufficient_coverage_passes(tmp_path):
    """Beat requires 5s, clip is 5s → exit 0."""
    proj = _setup_project(
        tmp_path,
        [{"beat_id": "B001", "start": 0.0, "end": 5.0}],
        [{"beat_id": "B001", "output_path": "B001.mp4", "asset_type": "generated_video", "_test_duration": 5.0}]
    )
    rc, stdout, _ = _run(proj)
    assert rc == 0
    assert "sufficient" in stdout.lower() or "✓" in stdout


def test_deficit_fails(tmp_path):
    """Beat requires 10s, clip is 5s → exit 1, deficit=5.0s."""
    proj = _setup_project(
        tmp_path,
        [{"beat_id": "B001", "start": 0.0, "end": 10.0}],
        [{"beat_id": "B001", "output_path": "B001.mp4", "asset_type": "generated_video", "_test_duration": 5.0}]
    )
    rc, stdout, _ = _run(proj)
    assert rc == 1
    assert "B001" in stdout
    assert "FAILED" in stdout or "deficit" in stdout.lower()


def test_missing_clip_fails(tmp_path):
    """Beat references nonexistent file → exit 1."""
    proj = Path(tmp_path)
    (proj / "narration").mkdir(parents=True)
    timing = {"beats": [{"beat_id": "B001", "start": 0.0, "end": 5.0}], "total_duration": 5.0, "beat_count": 1}
    (proj / "narration" / "beat_timing_map.json").write_text(json.dumps(timing))
    plan = {"beats": [{"beat_id": "B001", "output_path": "nonexistent/B001.mp4", "asset_type": "generated_video"}]}
    (proj / "media_plan.json").write_text(json.dumps(plan))

    rc, stdout, _ = _run(proj)
    assert rc == 1
    assert "B001" in stdout


def test_local_graphic_coverage(tmp_path):
    """local_graphic beat → always sufficient, no probe needed."""
    proj = _setup_project(
        tmp_path,
        [{"beat_id": "B001", "start": 0.0, "end": 20.0}],
        [{"beat_id": "B001", "output_path": "", "asset_type": "local_graphic"}],
        create_clips=False
    )
    rc, stdout, _ = _run(proj)
    assert rc == 0


def test_total_deficit_accumulates(tmp_path):
    """Per-clip policy (2026-06-16): independent small b-roll deficits are absorbed
    by the assembler at each position and must NOT hard-fail by summing. Three b-roll
    beats each ~0.2s short (< 0.5s b-roll tolerance) now PASS — previously the summed
    ~0.6s wrongly failed and triggered needless regeneration (whack-a-mole)."""
    proj = _setup_project(
        tmp_path,
        [
            {"beat_id": "B001", "start": 0.0, "end": 5.2},
            {"beat_id": "B002", "start": 5.2, "end": 10.4},
            {"beat_id": "B003", "start": 10.4, "end": 15.6},
        ],
        [
            {"beat_id": "B001", "output_path": "B001.mp4", "asset_type": "generated_video", "audio_policy": "strip", "_test_duration": 5.0},
            {"beat_id": "B002", "output_path": "B002.mp4", "asset_type": "generated_video", "audio_policy": "strip", "_test_duration": 5.0},
            {"beat_id": "B003", "output_path": "B003.mp4", "asset_type": "generated_video", "audio_policy": "strip", "_test_duration": 5.0},
        ]
    )
    rc, stdout, _ = _run(proj)
    # Each beat ~0.2s short, within the 0.5s b-roll tolerance → assembler covers → pass.
    assert rc == 0, f"small independent b-roll deficits should pass, stdout={stdout}"


def test_broll_large_deficit_still_fails(tmp_path):
    """A b-roll clip short by MORE than the assembler can freeze-cover (>0.5s) still fails."""
    proj = _setup_project(
        tmp_path,
        [{"beat_id": "B001", "start": 0.0, "end": 7.0}],
        [{"beat_id": "B001", "output_path": "B001.mp4", "asset_type": "generated_video",
          "audio_policy": "strip", "_test_duration": 5.0}],  # 2.0s deficit > 0.5s
    )
    rc, stdout, _ = _run(proj)
    assert rc == 1, f"a 2.0s b-roll deficit exceeds freeze coverage and must fail, stdout={stdout}"


def test_lipsync_small_deficit_still_fails(tmp_path):
    """Lipsync stays STRICT: a 0.4s deficit (under the b-roll tolerance but over the
    0.25s lipsync tolerance) must still fail — baked audio cannot be freeze-padded."""
    proj = _setup_project(
        tmp_path,
        [{"beat_id": "B001", "start": 0.0, "end": 5.4}],
        [{"beat_id": "B001", "output_path": "B001.mp4", "asset_type": "generated_video",
          "audio_policy": "keep_lipsync", "lipsync_required": True, "_test_duration": 5.0}],  # 0.4s deficit
    )
    rc, stdout, _ = _run(proj)
    assert rc == 1, f"lipsync deficit > 0.25s must fail (strict), stdout={stdout}"


def test_audited_project_reconcile_passes():
    """Run against the REAL audited project dir; expect it to PASS after repair.
    
    Note: This project historically had a ~63s deficit and was used to verify
    the failure gate. It has since been successfully repaired and regenerated.
    This test now verifies that the repaired project correctly passes reconciliation.
    """
    if not AUDITED_PROJECT.is_dir():
        pytest.skip("Audited project not available")
    rc, stdout, _ = _run(AUDITED_PROJECT)
    assert rc == 0, f"Expected repaired project to pass, got:\n{stdout}"
    assert "All beats have sufficient visual coverage" in stdout
