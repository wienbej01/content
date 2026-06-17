"""test_lipsync_provenance.py — TKT-04: Lipsync audio provenance hardening tests."""
import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def _make_tone_mp3(path, freq=220, dur=3.0):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
         "-c:a", "libmp3lame", "-q:a", "2", str(path)],
        capture_output=True, check=True)


def _make_clip(path, duration=3.0, audio=True):
    af = ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"] if audio else []
    maps = ["-map", "0:v", "-map", "1:a"] if audio else ["-map", "0:v"]
    # Use testsrc2 to avoid BLANK_SCREEN/FROZEN_VIDEO perceptual QA failures
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"testsrc2=size=1280x720:duration={duration}:rate=24",
         *af, *maps,
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
         "-c:a", "aac", "-b:a", "128k",
         "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True)


def _build_project(td, *, speech_len=3.0, clip_audio=True, tamper_slice=False, remove_slice=False):
    """Build a minimal project fixture with one lipsync beat.

    Returns (media_plan_path, project_dir).
    """
    td = Path(td)
    nar = td / "narration"
    slices = nar / "slices"
    slices.mkdir(parents=True)

    # Create master continuous.mp3
    master = nar / "continuous.mp3"
    _make_tone_mp3(master, freq=220, dur=speech_len + 2.0)

    # Create slice
    slice_path = slices / "B001.mp3"
    _make_tone_mp3(slice_path, freq=220, dur=speech_len)
    slice_sha = _sha256(slice_path)

    # Tamper slice after recording hash
    if tamper_slice:
        _make_tone_mp3(slice_path, freq=880, dur=speech_len)

    # Remove slice entirely
    if remove_slice:
        slice_path.unlink()

    # Create clip
    clip_path = td / "assets" / "media" / "001_hook" / "B001.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    _make_clip(clip_path, duration=speech_len, audio=clip_audio)

    plan = {
        "project_id": "test_proj",
        "defaults": {"format": "mp3"},
        "beats": [{
            "beat_id": "B001",
            "segment_id": "001_hook",
            "audio_policy": "keep_lipsync",
            "shot_type": "hero_lipsync",
            "lipsync_required": True,
            "output_path": str(clip_path.relative_to(td)),
            "audio_slice": {
                "file": "narration/slices/B001.mp3",
                "path": "narration/slices/B001.mp3",
                "sha256": slice_sha,
                "slice_sha256": slice_sha,
                "start_sec": 0.0,
                "end_sec": float(speech_len),
                "speech_len_sec": float(speech_len),
                "padded_len_sec": max(4, int(speech_len) + 1),
                "master_sha256": _sha256(master),
                "parent_mp3_sha256": _sha256(master),
                "parent_mp3": "narration/continuous.mp3",
                "master_start_sec": 0.0,
                "master_end_sec": float(speech_len),
            },
        }],
    }
    pp = td / "media_plan.json"
    pp.write_text(json.dumps(plan, indent=2))
    return pp, td


# ---- Test 1: slice hash recorded correctly by slice_continuous_lipsync ----

def test_slice_hash_recorded():
    """Run slice_continuous_lipsync on a fixture; verify audio_slice.sha256 matches file."""
    from slice_continuous_lipsync import slice_hero_from_master

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        nar = td / "narration"
        nar.mkdir()
        # Create a master
        master = nar / "continuous.mp3"
        _make_tone_mp3(master, freq=220, dur=5.0)
        # Create beat_timing_map
        bt = {"beats": [{"beat_id": "B001", "start": 0.0, "end": 3.0}]}
        (nar / "beat_timing_map.json").write_text(json.dumps(bt))
        # Create media_plan with one lipsync beat
        plan = {
            "project_id": "test_proj",
            "beats": [{"beat_id": "B001", "lipsync_required": True}],
        }
        (td / "media_plan.json").write_text(json.dumps(plan))

        result = slice_hero_from_master(str(td))
        beat = result["beats"][0]
        audio_slice = beat["audio_slice"]

        slice_path = td / audio_slice["file"]
        assert slice_path.exists(), "slice file must exist"
        live_sha = _sha256(slice_path)
        assert audio_slice["sha256"] == live_sha
        assert audio_slice["slice_sha256"] == live_sha
        canonical_wav = nar / "continuous_canonical.wav"
        assert audio_slice["master_sha256"] == _sha256(canonical_wav)
        assert audio_slice["master_start_sec"] == 0.0
        assert audio_slice["master_end_sec"] is not None


# ---- Test 2: tampered slice fails QA with PROVENANCE message ----

def test_tampered_slice_fails_qa():
    """Tampered slice (different bytes) must fail QA with PROVENANCE error."""
    import qa_media

    with tempfile.TemporaryDirectory() as td:
        pp, _ = _build_project(td, speech_len=4.0, tamper_slice=True)
        results, ok = qa_media.run_qa(str(pp))

    assert not ok, "tampered slice must fail QA"
    issues = results[0]["issues"]
    assert any("PROVENANCE" in i and "hash mismatch" in i for i in issues), \
        f"Expected PROVENANCE hash mismatch, got: {issues}"


# ---- Test 3: missing slice fails QA ----

def test_missing_slice_fails_qa():
    """Slice referenced in media_plan but missing from disk must fail QA."""
    import qa_media

    with tempfile.TemporaryDirectory() as td:
        pp, _ = _build_project(td, speech_len=4.0, remove_slice=True)
        results, ok = qa_media.run_qa(str(pp))

    assert not ok, "missing slice must fail QA"
    issues = results[0]["issues"]
    assert any("PROVENANCE" in i and "missing" in i.lower() for i in issues), \
        f"Expected PROVENANCE missing error, got: {issues}"


# ---- Test 4: silent hero clip fails QA ----

def test_silent_hero_clip_fails_qa():
    """Hero lipsync clip with no audio stream must fail QA."""
    import qa_media

    with tempfile.TemporaryDirectory() as td:
        pp, _ = _build_project(td, speech_len=4.0, clip_audio=False)
        results, ok = qa_media.run_qa(str(pp))

    assert not ok, "silent hero clip must fail QA"
    issues = results[0]["issues"]
    assert any("LIPSYNC" in i and "audio stream" in i for i in issues), \
        f"Expected SILENT_HERO / audio stream error, got: {issues}"


# ---- Test 5: valid provenance passes ----

def test_provenance_ok_passes():
    """Valid slice with matching hash must pass QA."""
    import qa_media

    with tempfile.TemporaryDirectory() as td:
        pp, _ = _build_project(td, speech_len=4.0)
        results, ok = qa_media.run_qa(str(pp))

    assert ok, f"valid provenance should pass, issues={results[0].get('issues', [])}"
    assert results[0]["status"] == "PASS"
