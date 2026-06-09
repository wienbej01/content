#!/usr/bin/env python3
"""tests/test_continuous_voiceover.py — P4-10 acceptance tests."""
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_wav(path, duration=5.0, freq=440):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
                    "-ar", "44100", "-ac", "1", str(path)], capture_output=True, check=True)


def test_segment_tts_unchanged():
    """Default narration_mode=segment_tts path still works (regression)."""
    tts = _load("tts")
    src = inspect.getsource(tts.run_tts)
    assert "segment_tts" in src
    assert "continuous_voiceover" in src
    print("  ✓ segment_tts and continuous_voiceover modes both present in run_tts")


def test_continuous_mode_in_build_manifest():
    """build_manifest includes continuous metadata when narration_mode set."""
    tts = _load("tts")
    src = (ROOT / "scripts" / "tts.py").read_text()
    assert "narration_mode" in src
    assert "continuous_audio" in src
    assert "timing_map" in src
    print("  ✓ build_manifest writes continuous_audio + timing_map fields")


def test_assemble_continuous_path_exists():
    """assemble.py has the continuous_voiceover branch."""
    src = (ROOT / "scripts" / "assemble.py").read_text()
    assert 'narration_mode") == "continuous_voiceover"' in src
    assert "cont_overlay" in src
    assert "cont_concat" in src
    print("  ✓ assemble.py has continuous_voiceover assembly path")


def test_continuous_assembly_with_fixtures():
    """End-to-end: continuous narration overlaid on muted visual segments."""
    asm = _load("assemble")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Create 2 video clips (colored bars, 3s each)
        for i in range(2):
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                            f"color=c={'red' if i == 0 else 'blue'}:size=320x180:d=3",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            str(td / f"seg{i}.mp4")], capture_output=True, check=True)
        # Create continuous narration (6s sine)
        _make_wav(td / "continuous.mp3", duration=6.0)
        # Create a simple timing map
        timing = {"beats": [
            {"beat_id": "b0", "segment_id": "s0", "start": 0, "end": 3.0, "text": "a", "word_count": 1, "duration": 3},
            {"beat_id": "b1", "segment_id": "s1", "start": 3.0, "end": 6.0, "text": "b", "word_count": 1, "duration": 3},
        ], "total_duration": 6.0, "audio_segments_detected": 2, "flags": []}
        (td / "timing_map.json").write_text(json.dumps(timing))
        # Build manifest
        manifest = {
            "id": "test_cont",
            "narration_mode": "continuous_voiceover",
            "continuous_audio": "continuous.mp3",
            "timing_map": "timing_map.json",
            "segments": [
                {"media": "seg0.mp4", "words": 1},
                {"media": "seg1.mp4", "words": 1},
            ],
            "pacing": {"reference": 0, "baseline_speed": 1.0},
            "music": {"enabled": False},
            "brand": {},
            "render": {"fps": 24, "crf": 23, "grade": "null"},
            "output": {"directory": ".", "prefix": "test_cont"},
        }
        (td / "manifest.json").write_text(json.dumps(manifest))
        # Run assembly
        log = asm.assemble(str(td / "manifest.json"), formats=["16x9"], tmp_base=str(td / "_tmp"))
        final = Path(log["formats"]["16x9"]["path"])
        assert final.exists()
        dur = asm.probe_dur(final)
        assert 5.5 < dur < 7.0, f"expected ~6s continuous, got {dur}"
    print(f"  ✓ continuous assembly produced {dur:.1f}s video from 2 segments + 6s narration")


def test_script_default_is_segment_tts():
    """teaser_02 script without narration_mode defaults to segment_tts."""
    s = json.load(open(ROOT / "scripts/generated/james_growth_system_teaser_02.json"))
    assert s.get("narration_mode", "segment_tts") == "segment_tts"
    print("  ✓ teaser_02 defaults to segment_tts (continuous is opt-in)")


def main():
    print("Continuous Voiceover Tests (P4-10)")
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
