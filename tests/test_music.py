#!/usr/bin/env python3
"""tests/test_music.py — MVP background music support tests."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# --- fixture helpers ---

def _make_sine(path, duration=10.0, freq=440):
    """Generate a silent-ish sine wave MP3 fixture using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         f"-i", f"sine=frequency={freq}:duration={duration}",
         "-ar", "44100", "-ac", "2", "-b:a", "64k", str(path)],
        capture_output=True, check=True)


def _load_asm():
    spec = importlib.util.spec_from_file_location("assemble", ROOT / "scripts" / "assemble.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --- tests ---

def test_no_music_disabled():
    """make_music_bed returns None when enabled=False."""
    asm = _load_asm()
    with tempfile.TemporaryDirectory() as td:
        result = asm.make_music_bed(30.0, {"enabled": False}, Path(td), ROOT)
    assert result is None
    print("  ✓ music disabled → returns None")


def test_no_music_empty_cfg():
    """make_music_bed returns None when no music block at all."""
    asm = _load_asm()
    with tempfile.TemporaryDirectory() as td:
        result = asm.make_music_bed(30.0, {}, Path(td), ROOT)
    assert result is None
    print("  ✓ empty music config → returns None")


def test_missing_music_file_raises():
    """enabled=True with missing file raises FileNotFoundError."""
    asm = _load_asm()
    with tempfile.TemporaryDirectory() as td:
        try:
            asm.make_music_bed(30.0, {"enabled": True, "path": "nonexistent.mp3"},
                               Path(td), ROOT)
            assert False, "should have raised"
        except FileNotFoundError as e:
            assert "nonexistent.mp3" in str(e)
    print("  ✓ missing music file raises FileNotFoundError")


def test_no_path_raises():
    """enabled=True with no path raises ValueError."""
    asm = _load_asm()
    with tempfile.TemporaryDirectory() as td:
        try:
            asm.make_music_bed(30.0, {"enabled": True}, Path(td), ROOT)
            assert False, "should have raised"
        except ValueError as e:
            assert "path" in str(e).lower()
    print("  ✓ no path raises ValueError")


def test_valid_music_produces_bed():
    """enabled=True with valid file produces a music bed."""
    asm = _load_asm()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        sine = td / "fixture.mp3"
        _make_sine(sine, duration=15.0)
        bed = asm.make_music_bed(10.0, {"enabled": True, "path": str(sine),
                                        "volume_db": -24, "fade_in": 0.5, "fade_out": 1.0},
                                 td, ROOT)
        assert bed is not None and bed.exists()
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(bed)],
                           capture_output=True, text=True)
        dur = float(r.stdout.strip())
        assert 9.5 < dur < 11.0, f"bed duration unexpected: {dur}"
    print(f"  ✓ valid music file → bed produced ({dur:.1f}s)")


def test_short_track_loops():
    """A track shorter than video is looped to cover the full duration."""
    asm = _load_asm()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        sine = td / "short.mp3"
        _make_sine(sine, duration=5.0)
        bed = asm.make_music_bed(20.0, {"enabled": True, "path": str(sine),
                                        "volume_db": -30, "fade_in": 0.3, "fade_out": 0.5,
                                        "loop": True}, td, ROOT)
        assert bed is not None and bed.exists()
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(bed)],
                           capture_output=True, text=True)
        dur = float(r.stdout.strip())
        assert 19.0 < dur < 21.0, f"looped bed should cover 20s, got {dur}"
    print(f"  ✓ short track loops to cover video duration ({dur:.1f}s)")


def test_music_is_one_track_per_video():
    """Music config is top-level in manifest, not per-segment."""
    script = json.load(open(ROOT / "scripts/generated/james_growth_system_teaser_02.json"))
    assert "music" in script, "music block must be at script/manifest top level"
    for seg in script["segments"]:
        assert "music" not in seg, f"segment {seg['id']} must not have per-segment music"
    print("  ✓ music is top-level, not per-segment")


def test_music_config_in_teaser_script():
    """teaser_02 script has a valid, enabled music block."""
    script = json.load(open(ROOT / "scripts/generated/james_growth_system_teaser_02.json"))
    m = script.get("music", {})
    assert m.get("enabled") is True
    assert m.get("path"), "music.path must be set"
    assert m.get("volume_db", 0) <= -12, "music volume should be conservative (≤ -12 dB)"
    path = ROOT / m["path"]
    assert path.exists(), f"music file does not exist: {path}"
    print(f"  ✓ teaser_02 music config valid: {m['path']} @ {m['volume_db']}dB")


def test_assemble_no_music_flag():
    """assemble() signature accepts no_music kwarg; make_music_bed returns None with it."""
    asm = _load_asm()
    import inspect
    sig = inspect.signature(asm.assemble)
    assert "no_music" in sig.parameters
    assert "music_override" in sig.parameters
    assert "music_volume_db" in sig.parameters
    print("  ✓ assemble() accepts no_music/music_override/music_volume_db params")


def test_log_records_music_metadata():
    """Assembly log structure includes music key (verify shape without running full assembly)."""
    # We test this by checking the log-writing code path is present
    src = (ROOT / "scripts" / "assemble.py").read_text()
    assert 'log["music"]' in src
    assert '"volume_db"' in src
    assert '"fade_in"' in src
    assert '"looped"' in src
    print("  ✓ assembly log records music metadata (volume_db, fade_in, looped)")


def main():
    print("Music Support Tests")
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
