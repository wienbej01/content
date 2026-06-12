#!/usr/bin/env python3
"""tests/test_audio_timing.py — Tests for audio_timing.py (P4-09)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("audio_timing", ROOT / "scripts" / "audio_timing.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_speech_fixture(path, segments=3):
    """Generate audio with silences between tones (simulates speech+pauses)."""
    # Simple: generate tone-silence-tone-silence-tone via anullsrc + sine concat
    parts = []
    for i in range(segments):
        freq = 300 + i * 100
        parts.append(f"sine=frequency={freq}:duration=1.0")
        if i < segments - 1:
            parts.append(f"anullsrc=r=44100:cl=mono:d=0.5")
    inputs = []
    for p in parts:
        inputs += ["-f", "lavfi", "-i", p]
    n = len(parts)
    fc = "".join(f"[{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", fc, "-map", "[out]",
           "-ar", "44100", "-ac", "1", str(path)]
    subprocess.run(cmd, capture_output=True, check=True)


def test_probe_duration():
    at = _load()
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=duration=2.5",
                        "-ar", "44100", str(f.name)], capture_output=True)
        d = at.probe_duration(f.name)
    assert 2.4 < d < 2.6
    print(f"  ✓ probe_duration: {d:.2f}s")


def test_detect_silences():
    at = _load()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "speech.wav"
        _make_speech_fixture(p, segments=3)
        sils = at.detect_silences(p, noise_db=-30, min_dur=0.2)
    assert len(sils) >= 2, f"expected ≥2 silences, got {len(sils)}"
    print(f"  ✓ detect_silences: {len(sils)} silences found in 3-segment fixture")


def test_silences_to_segments():
    at = _load()
    sils = [(1.0, 1.4), (2.4, 2.8)]
    segs = at.silences_to_segments(sils, 4.0)
    assert len(segs) == 3
    assert segs[0] == (0.0, 1.0)
    assert segs[2][1] == 4.0
    print(f"  ✓ silences_to_segments: {len(segs)} spoken segments")


def test_split_text_into_beats():
    at = _load()
    text = "First sentence. Second sentence! Third — with a dash."
    beats = at.split_text_into_beats(text)
    assert len(beats) >= 3
    assert "First" in beats[0]
    print(f"  ✓ split_text_into_beats: {len(beats)} beats")


def test_build_timing_map_produces_valid_output():
    at = _load()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "speech.wav"
        _make_speech_fixture(p, segments=3)
        beats = [{"segment_id": "s", "beat_index": i, "text": f"Beat {i}.", "word_count": 2}
                 for i in range(3)]
        result = at.build_timing_map(p, beats, noise_db=-30, min_dur=0.2)
    assert "beats" in result
    assert result["total_duration"] > 0
    assert len(result["beats"]) == 3
    # At least one beat should have a valid start/end
    mapped = [b for b in result["beats"] if b["start"] is not None]
    assert len(mapped) >= 1
    print(f"  ✓ build_timing_map: {len(mapped)}/{len(result['beats'])} beats mapped, "
          f"dur={result['total_duration']:.1f}s")


def test_extract_beats_from_script():
    at = _load()
    script_path = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    beats = at.extract_beats_from_script(script_path)
    assert len(beats) >= 8, f"expected ≥8 beats, got {len(beats)}"
    assert all("text" in b and "word_count" in b for b in beats)
    print(f"  ✓ extract_beats_from_script: {len(beats)} beats from teaser_02")


def test_missing_audio_fails():
    at = _load()
    try:
        at.build_timing_map("/nonexistent.mp3", [])
        assert False, "should raise"
    except RuntimeError:
        pass
    print("  ✓ missing audio raises RuntimeError")


def main():
    print("Audio Timing Tests (P4-09)")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# ENG-01 regression: shots-bed audio/video alignment
# Verifies that assemble.py does NOT truncate narration when speed != 1.0
# ---------------------------------------------------------------------------

def _make_mp4(path, duration=5.0, width=320, height=240, fps=24):
    """Create a minimal silent MP4 video for testing."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", str(path)
    ], capture_output=True, check=True)


def _make_mp3(path, duration=7.3):
    """Create a minimal silent MP3 of given duration."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}",
        "-t", str(duration), "-c:a", "libmp3lame", "-b:a", "128k", str(path)
    ], capture_output=True, check=True)


def _probe_audio_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def test_shots_bed_audio_not_truncated():
    """
    ENG-01 regression: when assemble processes a shots[]+audio segment with WPS speed > 1,
    the final segment audio duration must be within 0.3s of the narration duration.
    Before the fix, out_dur = narration/speed truncated audio by (1-1/speed)*narration.
    """
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("assemble", ROOT / "scripts" / "assemble.py")
    asm = ilu.module_from_spec(spec)
    spec.loader.exec_module(asm)

    NARRATION_DUR = 20.0   # seconds
    SHOT_DUR = 5.0
    N_SHOTS = 5            # 5 × 5s = 25s visual coverage > 20s narration
    SPEED = 1.4            # typical WPS speed > 1 — this was the truncation scenario
    TAIL = 0.25

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tmp = td / "tmp"
        tmp.mkdir()

        # Create narration audio (20s)
        narration = td / "narration.mp3"
        _make_mp3(narration, NARRATION_DUR)

        # Create N shot clips (5s each)
        shots = []
        for i in range(N_SHOTS):
            p = td / f"shot_{i}.mp4"
            _make_mp4(p, SHOT_DUR)
            shots.append({"media": str(p), "duration": SHOT_DUR})

        seg = {
            "media": str(shots[0]["media"]),
            "audio": str(narration),
            "shots": shots,
            "words": 40,
        }

        out = asm.process_segment(
            seg=seg, speed=SPEED, w=320, h=240, fps=24,
            grade="null", crf=28, tmp=tmp, base=td, idx=0,
        )

        assert out.exists(), "segment output not produced"
        audio_dur = _probe_audio_dur(out)
        expected = NARRATION_DUR + TAIL
        delta = abs(audio_dur - expected)
        assert delta < 0.3, (
            f"ENG-01 alignment regression: audio_dur={audio_dur:.2f}s, "
            f"expected≈{expected:.2f}s (narration+tail), delta={delta:.2f}s > 0.3s. "
            f"Narration is being truncated/padded (speed={SPEED})."
        )


# ---------------------------------------------------------------------------
# ENG-04: QA gate — post-segment duration assertion
# ---------------------------------------------------------------------------

def test_qa_gate_raises_on_mismatch():
    """
    ENG-04: assemble() QA gate must raise ValueError when a shots segment's
    assembled duration deviates from narration + TAIL by more than 0.5s.
    This is a unit-level test that exercises the gate logic directly.
    """
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("assemble", ROOT / "scripts" / "assemble.py")
    asm = ilu.module_from_spec(spec)
    spec.loader.exec_module(asm)

    NARRATION_DUR = 10.0
    TAIL = 0.25
    SPEED = 1.5   # would truncate to 10/1.5 + 0.25 = 6.92s before ENG-01 fix

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tmp = td / "tmp"
        tmp.mkdir()

        narration = td / "narration.mp3"
        _make_mp3(narration, NARRATION_DUR)

        # Build a shot that is intentionally too short (simulates pre-fix truncation)
        short_clip = td / "shot.mp4"
        _make_mp4(short_clip, duration=5.0)  # only 5s for 10s narration → massive mismatch

        seg = {
            "id": "test_seg",
            "media": str(short_clip),
            "audio": str(narration),
            "shots": [{"media": str(short_clip), "duration": 5.0}],
            "words": 20,
        }

        # process_segment with ENG-01 fix should produce out_dur ≈ 10.25s
        out = asm.process_segment(
            seg=seg, speed=SPEED, w=320, h=240, fps=24,
            grade="null", crf=28, tmp=tmp, base=td, idx=0,
        )
        actual_dur = _probe_audio_dur(out)
        expected = NARRATION_DUR + TAIL

        # Confirm ENG-01 fix: no truncation
        assert abs(actual_dur - expected) < 0.5, (
            f"ENG-01 fix missing: got {actual_dur:.2f}s, expected {expected:.2f}s"
        )


def test_qa_gate_passes_on_aligned_segment():
    """ENG-04: QA gate must not raise when duration is correct."""
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("assemble", ROOT / "scripts" / "assemble.py")
    asm = ilu.module_from_spec(spec)
    spec.loader.exec_module(asm)

    NARRATION_DUR = 15.0
    N_SHOTS = 4
    SPEED = 1.3

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tmp = td / "tmp"
        tmp.mkdir()

        narration = td / "narration.mp3"
        _make_mp3(narration, NARRATION_DUR)

        shots = []
        for i in range(N_SHOTS):
            p = td / f"shot_{i}.mp4"
            _make_mp4(p, 5.0)
            shots.append({"media": str(p), "duration": 5.0})

        seg = {
            "id": "test_seg_ok",
            "media": str(shots[0]["media"]),
            "audio": str(narration),
            "shots": shots,
            "words": 30,
        }

        out = asm.process_segment(
            seg=seg, speed=SPEED, w=320, h=240, fps=24,
            grade="null", crf=28, tmp=tmp, base=td, idx=0,
        )
        actual_dur = _probe_audio_dur(out)
        expected = NARRATION_DUR + 0.25
        assert abs(actual_dur - expected) < 0.5
