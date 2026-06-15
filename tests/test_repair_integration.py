"""PTC-04: Repair loop integration and fail-closed CLI semantics."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RECONCILE = ROOT / "scripts" / "reconcile_production_storyboard.py"
PRODUCE = ROOT / "scripts" / "produce.py"

sys.path.insert(0, str(ROOT / "scripts"))


def _storyboard(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _beat(beat_id, narration, shot_type="hero_lipsync"):
    return {
        "beat_id": beat_id,
        "narration_text": narration,
        "shot_type": shot_type,
        "segment_id": "001_test",
        "lipsync_required": shot_type == "hero_lipsync",
        "model": "seedance_2_0",
    }


def _timing_map(entries, total=None):
    if total is None:
        total = entries[-1]["end"] if entries else 0
    return {"beats": entries, "total_duration": total, "beat_count": len(entries)}


def _write_project(tmp_path, sb, tm, audio=False):
    """Write storyboard + timing_map files. Optionally create a dummy audio file."""
    (tmp_path / "storyboard.json").write_text(json.dumps(sb))
    narr = tmp_path / "narration"
    narr.mkdir(exist_ok=True)
    (narr / "beat_timing_map.json").write_text(json.dumps(tm))
    if audio:
        # Create minimal mp3 stub (reconcile only needs existence for path arg)
        (narr / "continuous.mp3").write_bytes(b"\xff\xfb\x90\x00" * 100)
    return tmp_path


# ─── Test 1: reconcile exits non-zero on unresolved needs_repair ──────────

def test_reconcile_cli_exits_nonzero_on_unresolved(tmp_path):
    """Without audio, overlong hero beat -> needs_repair -> exit 1, but preview written."""
    narration = "First sentence is fine. Second sentence is also fine."
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])
    _write_project(tmp_path, sb, tm, audio=False)

    output = tmp_path / "production_storyboard.json"
    r = subprocess.run(
        [sys.executable, str(RECONCILE),
         "--storyboard", str(tmp_path / "storyboard.json"),
         "--timing-map", str(tmp_path / "narration" / "beat_timing_map.json"),
         "--output", str(output),
         "--dry-run"],
        capture_output=True, text=True
    )
    assert r.returncode != 0, f"Expected exit 1, got 0. stdout: {r.stdout}"
    # Preview should still be written
    assert output.exists(), "Dry-run preview was not written"
    data = json.loads(output.read_text())
    assert any(b.get("needs_repair") for b in data["beats"])


# ─── Test 2: reconcile exits zero when resolved ───────────────────────────

def test_reconcile_cli_exits_zero_when_resolved(tmp_path):
    """Short beat (within limits) -> resolves cleanly -> exit 0."""
    sb = _storyboard([_beat("B001", "A short sentence.")])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 5.0, "duration": 5.0}])
    _write_project(tmp_path, sb, tm, audio=False)

    output = tmp_path / "production_storyboard.json"
    r = subprocess.run(
        [sys.executable, str(RECONCILE),
         "--storyboard", str(tmp_path / "storyboard.json"),
         "--timing-map", str(tmp_path / "narration" / "beat_timing_map.json"),
         "--output", str(output)],
        capture_output=True, text=True
    )
    assert r.returncode == 0, f"Expected exit 0, got {r.returncode}. stderr: {r.stderr}"
    assert output.exists()
    data = json.loads(output.read_text())
    assert not any(b.get("needs_repair") for b in data["beats"])


# ─── Test 3: review invoked with --output in produce.py ───────────────────

def test_review_called_with_output():
    """produce.py step_production_storyboard invokes review with --output."""
    source = PRODUCE.read_text()
    assert "review_production_storyboard.py" in source
    # Find the review invocation section and check --output is present
    lines = source.split("\n")
    in_review_block = False
    found_output = False
    for line in lines:
        if "review_production_storyboard.py" in line:
            in_review_block = True
        if in_review_block:
            if "--output" in line:
                found_output = True
                break
            # review invocation is a subprocess list - check within 5 lines
            if line.strip().startswith("]"):
                break
    assert found_output, "review_production_storyboard.py invocation missing --output"


# ─── Test 4: repair wired in produce.py ───────────────────────────────────

def test_repair_wired_in_produce():
    """produce.py references repair_storyboard_beats.py."""
    source = PRODUCE.read_text()
    assert "repair_storyboard_beats.py" in source, (
        "produce.py does not reference repair_storyboard_beats.py"
    )


# ─── Test 5: invalid output not promoted over valid existing ──────────────

def test_invalid_output_not_promoted(tmp_path):
    """Existing valid production_storyboard.json not overwritten by invalid result."""
    # Create a valid existing production storyboard
    valid_sb = {
        "schema_version": "2.0",
        "project_id": "test",
        "total_beats": 1,
        "master_audio_duration_sec": 5.0,
        "beats": [{
            "beat_id": "B001",
            "segment_id": "001_test",
            "order": 1,
            "source_beat_id": "B001",
            "audio_start_sec": 0.0,
            "audio_end_sec": 5.0,
            "audio_duration_sec": 5.0,
            "shot_type": "hero_lipsync",
            "visual_brief": "test",
            "narration_text": "hello",
            "needs_repair": False,
            "coverage_plan": [{"slot": 1, "start": 0.0, "end": 5.0,
                               "required_duration_sec": 5.0, "model": "seedance_2_0"}],
        }]
    }
    output = tmp_path / "production_storyboard.json"
    output.write_text(json.dumps(valid_sb))
    original_content = output.read_text()

    # Now run reconcile with overlong beat that will need repair (no audio)
    narration = "First sentence. Second sentence."
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])
    (tmp_path / "storyboard.json").write_text(json.dumps(sb))
    narr = tmp_path / "narration"
    narr.mkdir(exist_ok=True)
    (narr / "beat_timing_map.json").write_text(json.dumps(tm))

    r = subprocess.run(
        [sys.executable, str(RECONCILE),
         "--storyboard", str(tmp_path / "storyboard.json"),
         "--timing-map", str(tmp_path / "narration" / "beat_timing_map.json"),
         "--output", str(output)],
        capture_output=True, text=True
    )
    assert r.returncode != 0
    # Original valid file should be preserved
    assert output.read_text() == original_content, "Valid production_storyboard.json was overwritten"
    # Diagnostic should exist
    diag = output.with_suffix(".invalid.json")
    assert diag.exists(), "Diagnostic file not written"


# ─── Test 6: repair failure raises RuntimeError ───────────────────────────

def test_repair_failure_raises(tmp_path, monkeypatch):
    """If repair returns still-invalid output, step_production_storyboard raises RuntimeError."""
    from unittest.mock import patch, MagicMock
    from produce import step_production_storyboard

    project_dir = tmp_path
    (project_dir / "storyboard.json").write_text(json.dumps(
        _storyboard([_beat("B001", "First. Second.")])
    ))
    narr = project_dir / "narration"
    narr.mkdir()
    (narr / "beat_timing_map.json").write_text(json.dumps(
        _timing_map([{"beat_id": "B001", "start": 0.0, "end": 18.0, "duration": 18.0}])
    ))
    (narr / "continuous.mp3").write_bytes(b"\xff\xfb\x90\x00" * 100)

    # Mock subprocess.run to simulate reconcile failing then repair failing
    call_count = {"n": 0}

    def mock_run(cmd, **kwargs):
        call_count["n"] += 1
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""

        if "reconcile_production_storyboard.py" in str(cmd):
            # Write invalid output with needs_repair
            invalid = {
                "schema_version": "2.0", "project_id": "test",
                "total_beats": 1, "master_audio_duration_sec": 14.0,
                "beats": [{"beat_id": "B001", "segment_id": "001_test",
                           "needs_repair": True, "audio_start_sec": 0.0,
                           "audio_end_sec": 14.0, "audio_duration_sec": 14.0,
                           "source_beat_id": "B001", "shot_type": "hero_lipsync",
                           "narration_text": "First. Second.",
                           "coverage_plan": [{"slot": 1, "start": 0.0, "end": 14.0,
                                              "required_duration_sec": 14.0, "model": "seedance_2_0"}]}]
            }
            out_path = project_dir / "production_storyboard.json"
            out_path.write_text(json.dumps(invalid))
            result.returncode = 1
        elif "repair_storyboard_beats.py" in str(cmd):
            # Repair also fails - write output still with needs_repair
            result.returncode = 1
        else:
            result.returncode = 0
        return result

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(RuntimeError, match="[Rr]epair"):
            step_production_storyboard(project_dir, {})
