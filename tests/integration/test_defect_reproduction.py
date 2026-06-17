"""R0-002 — Reproduce B001/B008 contamination defects (red-now / green-after anchors).

BUG A (B001): slice_continuous_lipsync widens -ss/-t into master, copying adjacent
    speech when padding with silence instead of generating true silence.
BUG B (B008): lipsync_scoring returns PASS (0.85) on any input with non-zero audio
    energy — a fixed-score placeholder that never detects desync.
BUG R5: assembly mixes per-shot narration slices rather than a single global master,
    causing drift when slices don't align to a common spine.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _audio_energy_at_freq(path: Path, freq: int, width: int = 40) -> float:
    """Measure RMS energy in a narrow frequency band using ffmpeg bandpass."""
    result = subprocess.run([
        "ffmpeg", "-y", "-i", str(path),
        "-af", f"bandpass=f={freq}:w={width},volumedetect",
        "-f", "null", "-",
    ], capture_output=True, text=True)
    import re
    m = re.search(r"mean_volume:\s+(-?\d+\.?\d*)", result.stderr)
    if m:
        return float(m.group(1))
    return -100.0


# ---------------------------------------------------------------------------
# B001: adjacent-speech contamination via master-range pad
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="Red-now — slicer bug B001 fixed in R3")
def test_adjacent_speech_slice_contamination(tone_marked_master, tmp_path):
    """Slice the second beat (880 Hz, 2–4s) and verify no 440 Hz bleed.

    When the slicer pads the 2s speech span to meet the 4s minimum, it
    widens the extraction window *inside the master* instead of generating
    true silence.  The leading silence pulls in the tail of the 440 Hz beat
    (or its mp3 frame-aligned neighbour), which this test catches.
    """
    from slice_continuous_lipsync import slice_hero_from_master, _load_lipsync_limits

    LIPSYNC_MIN, LIPSYNC_MAX = _load_lipsync_limits()
    assert LIPSYNC_MIN == 4.0, "test assumes 4.0s min lipsync duration"

    project_dir = tmp_path / "project"
    nar = project_dir / "narration"
    nar.mkdir(parents=True)
    (nar / "slices").mkdir()

    # Copy the tone-marked master into position.
    master_dest = nar / "continuous.mp3"
    master_dest.write_bytes(tone_marked_master.read_bytes())

    beat_timing = {
        "total_duration": 5.0,
        "beats": [
            {"beat_id": "B001", "start": 0.0, "end": 2.0},
            {"beat_id": "B002", "start": 2.0, "end": 4.0},
        ],
    }
    (nar / "beat_timing_map.json").write_text(json.dumps(beat_timing))

    media_plan = {
        "beats": [
            {"beat_id": "B002", "lipsync_required": True, "audio_slice": None},
        ],
    }
    (project_dir / "media_plan.json").write_text(json.dumps(media_plan))

    plan = slice_hero_from_master(project_dir)

    sliced = next(b for b in plan["beats"] if b["beat_id"] == "B002")
    slice_path = project_dir / sliced["audio_slice"]["path"]
    assert slice_path.exists(), f"slice not found: {slice_path}"

    # The 440 Hz band should be silent because the slice should only
    # cover 2-4s (+ generated silence padding), never 0-2s.
    energy_440 = _audio_energy_at_freq(slice_path, 440)
    assert energy_440 < -30.0, (
        f"440 Hz bleed detected ({energy_440:.1f} dB) — "
        "slice_continuous_lipsync is copying adjacent master speech "
        "instead of generating true silence for padding"
    )


# ---------------------------------------------------------------------------
# B008: placeholder lipsync scorer always returns PASS
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="Red-now — placeholder scorer R6 bug")
def test_placeholder_lipsync_always_passes(tmp_path):
    """A deliberately offset/desynced audio-video pair must not score PASS.

    The current scorer checks audio energy > 0.01 and unconditionally
    returns score=0.85, confidence=0.90, offset=0 — it never detects
    desync.  This test asserts the contract that a real scorer should
    uphold: desynced input must be detected (score < threshold or
    REVIEW_REQUIRED).  The assertion *fails* today because the bug has
    not been fixed, and will *pass* after R6 delivers a real scorer.
    """
    from lipsync_scoring import score_lipsync

    video = tmp_path / "fake.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:duration=2",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video),
    ], capture_output=True, check=True)

    audio = tmp_path / "fake.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=2:sample_rate=44100",
        "-q:a", "9", str(audio),
    ], capture_output=True, check=True)

    result = score_lipsync(video_path=video, audio_path=audio)

    assert result["result_state"] != "PASS", (
        f"Deliberately desynced fixture scored {result['result_state']} "
        f"(score={result['score']:.2f}) — placeholder scorer returns false "
        f"negatives, must be replaced by a real audiovisual scorer in R6"
    )
    assert result["score"] < 0.75, (
        "Desynced fixture must score below PASS threshold"
    )
    assert result["failure_reason"] is not None, (
        "A real scorer must provide a failure reason for desynced input"
    )


# ---------------------------------------------------------------------------
# R5: assembly mixes per-shot narration slices, not a single global master
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="Red-now — assembly R5 bug, uses per-shot narration slices")
def test_assembly_no_single_global_master():
    """assemble.py must mix from a single global master audio spine.

    The current implementation extracts per-shot narration slices via
    ffmpeg -ss/-t (lines 587-591), then overlays each individually.
    This causes timing drift because there is no common audio spine.
    The correct behaviour is a single master-audio track laid end-to-end
    without per-shot splitting.  This assertion *fails* today because
    the bug has not been fixed, and will *pass* after R5.
    """
    source = (ROOT / "scripts" / "assemble.py").read_text()

    has_per_shot_slicing = (
        "nar_slice = tmp" in source
        and "nar_offset" in source
        and "-ss" in source
        and "-t" in source
    )

    assert not has_per_shot_slicing, (
        "assemble.py still extracts per-shot narration slices via ffmpeg -ss/-t. "
        "Must use a single global master audio spine (R5 fix) instead of slicing "
        "narration per shot — timing drift accumulates between independently cut slices."
    )

    uses_global_master = "global_master" in source
    assert uses_global_master, (
        "assemble.py does not use a single global master — R5 not yet implemented"
    )

    assemble_db_source = (ROOT / "scripts" / "assemble_db.py").read_text()
    assert not ("narration_slice" in assemble_db_source), (
        "assemble_db.py uses narration slice terminology"
    )
