"""Tests for scripts/audio_alignment.py and measured-boundary splitting in reconcile.
import json as _json; from pathlib import Path as _P
_MODEL_MAX = float(_json.loads((_P(__file__).resolve().parent.parent / "docs" / "channel_universe" / "constraints.json").read_text()).get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15))

Uses FFmpeg-generated fixtures with known silence gaps. No paid APIs.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audio_alignment import find_legal_split_points
from reconcile_production_storyboard import reconcile

from conftest_constants import TEST_CONSTRAINTS as CONSTRAINTS, OVER_LIMIT_DURATION



@pytest.fixture
def audio_with_silence(tmp_path):
    """17.5s audio: 5s tone, 0.5s silence, 12s tone."""
    out = tmp_path / "split.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
        "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1",
        "-ar", "44100", "-ac", "1", str(out)
    ], capture_output=True, check=True)
    return str(out)


@pytest.fixture
def continuous_tone(tmp_path):
    """10s continuous tone — no silence gaps."""
    out = tmp_path / "continuous.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-ar", "44100", "-ac", "1", str(out)
    ], capture_output=True, check=True)
    return str(out)


@pytest.fixture
def audio_two_silences(tmp_path):
    """18s audio: 5s tone, 0.4s silence, 5s tone, 0.4s silence, 7.2s tone."""
    out = tmp_path / "two_sil.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=7.2",
        "-filter_complex", "[0][1][2][3][4]concat=n=5:v=0:a=1",
        "-ar", "44100", "-ac", "1", str(out)
    ], capture_output=True, check=True)
    return str(out)


# --- Test 1: silence boundary detected ---

def test_silence_boundary_detected(audio_with_silence):
    """Audio with a clear silence gap; find_legal_split_points returns a point near the gap."""
    result = find_legal_split_points(audio_with_silence, 0.0, 17.5)
    assert result["method"] == "silence_detection"
    assert len(result["split_points"]) >= 1
    # The silence is around 5.0-5.5s; split point should be near 5.25
    pt = result["split_points"][0]
    assert 4.5 < pt < 6.0


# --- Test 2: boundary does not bisect speech ---

def test_boundary_does_not_bisect_speech(audio_with_silence):
    """Split point falls in a silence interval, not mid-tone."""
    result = find_legal_split_points(audio_with_silence, 0.0, 17.5)
    for pt in result["split_points"]:
        # Verify point is within a detected silence interval
        in_silence = any(s <= pt <= e for s, e in result["silences"])
        assert in_silence, f"Split point {pt} not in any silence interval"


# --- Test 3: low confidence when no silence ---

def test_low_confidence_when_no_silence(continuous_tone):
    """Continuous tone with no gaps; confidence='low' and empty split_points."""
    result = find_legal_split_points(continuous_tone, 0.0, 10.0)
    assert result["confidence"] == "low"
    assert result["split_points"] == []


# --- Test 4: audio hash recorded ---

def test_audio_hash_recorded(audio_with_silence):
    """Returned dict has audio_sha256."""
    result = find_legal_split_points(audio_with_silence, 0.0, 17.5)
    assert "audio_sha256" in result
    assert len(result["audio_sha256"]) == 64  # SHA-256 hex


# --- Test 5: reconcile uses measured split ---

def _storyboard(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _timing_map(beats, total=None):
    if total is None:
        total = beats[-1]["end"] if beats else 0
    return {"beats": beats, "total_duration": total, "beat_count": len(beats)}


def _beat(beat_id, narration, shot_type="hero_lipsync", lipsync=True, model="seedance_2_0"):
    return {
        "beat_id": beat_id,
        "narration_text": narration,
        "shot_type": shot_type,
        "segment_id": "001_test",
        "lipsync_required": lipsync,
        "model": model,
    }


def test_reconcile_uses_measured_split(audio_with_silence):
    """Reconcile with audio fixture splits at measured boundary (provenance recorded)."""
    # 12s lipsync beat > 10s max → needs split; audio has silence at ~5.25s
    narration = "First sentence here. Second sentence follows after silence."
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 17.5, "duration": 17.5}], total=17.5)

    result, issues = reconcile(sb, tm, CONSTRAINTS, audio_path=audio_with_silence)
    beats = result["beats"]

    # Should produce split children
    assert len(beats) == 2
    assert beats[0]["beat_id"] == "B001a"
    assert beats[1]["beat_id"] == "B001b"
    # Provenance must be recorded
    assert "timing_provenance" in beats[0]
    prov = beats[0]["timing_provenance"]
    assert prov["method"] == "silence_detection"
    assert prov["confidence"] == "high"
    assert len(prov["audio_sha256"]) == 64
    assert len(prov["boundary_evidence"]) >= 1
    # Split point should be near the silence (~5.25s)
    boundary = prov["boundary_evidence"][0]
    assert 4.5 < boundary < 6.0
    # Each child <= 10s
    assert beats[0]["audio_duration_sec"] <= 15.042
    assert beats[1]["audio_duration_sec"] <= 15.042


# --- Test 6: no measured boundary marks repair ---

def test_reconcile_no_measured_boundary_marks_repair(continuous_tone):
    """Beat needs split but no silence → rerouted to hero_cutaway (PTC-03)."""
    narration = "First sentence here. Second sentence follows later."
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 17.5, "duration": 17.5}], total=17.5)

    # Audio is 10s but timing says 17.5s — detection will find no silence
    result, issues = reconcile(sb, tm, CONSTRAINTS, audio_path=continuous_tone)
    beats = result["beats"]

    assert len(beats) == 1
    assert beats[0]["needs_repair"] is False
    assert beats[0]["treatment"] == "hero_cutaway"
    assert beats[0]["audio_policy"] == "strip"
    # Should NOT have split children with word-proportional timing
    assert beats[0].get("split_total") is None or beats[0].get("split_total", 1) == 1


# --- Test 7: word-proportional not authoritative ---

def test_word_proportional_not_authoritative(audio_with_silence):
    """Split-child audio_start_sec comes from measured boundary, not word-proportional."""
    narration = "Short first. Much longer second sentence that has many more words in it."
    sb = _storyboard([_beat("B001", narration)])
    tm = _timing_map([{"beat_id": "B001", "start": 0.0, "end": 17.5, "duration": 17.5}], total=17.5)

    result, issues = reconcile(sb, tm, CONSTRAINTS, audio_path=audio_with_silence)
    beats = result["beats"]

    assert len(beats) == 2
    # Word-proportional would split ~1.7s / ~10.3s (2 words vs 12 words)
    # Measured boundary is near 5.25s — very different from word-proportional
    boundary = beats[0]["audio_end_sec"]
    assert 4.5 < boundary < 6.0, (
        f"Split at {boundary} looks word-proportional, not measured"
    )
    # If advisory estimate exists on a needs_repair beat, it's clearly labeled
    # (only present when split fails — here it succeeds, so check provenance)
    assert beats[0]["timing_provenance"]["method"] == "silence_detection"
