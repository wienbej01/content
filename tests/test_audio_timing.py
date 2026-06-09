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
