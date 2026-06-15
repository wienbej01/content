#!/usr/bin/env python3
"""tests/test_normalize_pacing.py — auto pacing normalization system tests."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("normalize_pacing", ROOT / "scripts" / "normalize_pacing.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_audio_with_gap(path, gap=1.5):
    """tone (1s) + silence (gap) + tone (1s)."""
    parts = [f"sine=frequency=300:duration=1.0",
             f"anullsrc=r=44100:cl=mono:d={gap}",
             f"sine=frequency=400:duration=1.0"]
    inputs = []
    for p in parts:
        inputs += ["-f", "lavfi", "-i", p]
    n = len(parts)
    fc = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[o]"
    subprocess.run(["ffmpeg", "-y"] + inputs + ["-filter_complex", fc, "-map", "[o]",
                    "-ar", "44100", str(path)], capture_output=True, check=True)


def test_overlong_pause_trimmed():
    """A silence gap longer than max_pause is trimmed toward the natural length."""
    N = _load()
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "m.mp3"
        _make_audio_with_gap(a, gap=1.6)
        before = N._dur(a)
        rep = N.normalize_master(str(a), total_words=6, max_pause=0.95)
        after = N._dur(a)
        assert rep["pause_fixes"], "should detect the 1.6s over-long pause"
        assert after < before, "trimming should shorten the master"
    print("  ✓ over-long pause detected and trimmed")


def test_no_change_when_within_band():
    """Normal pacing + short pauses → no edits."""
    N = _load()
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "m.mp3"
        _make_audio_with_gap(a, gap=0.4)  # short pause, fine
        rep = N.normalize_master(str(a), total_words=5, target_wps=2.4, max_pause=0.95)
        assert not rep["pause_fixes"], "short pause should not be trimmed"
    print("  ✓ in-band pacing left unchanged")


def test_dry_run_reports_without_editing():
    """Dry-run reports fixes but does not modify the file."""
    N = _load()
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "m.mp3"
        _make_audio_with_gap(a, gap=1.6)
        before = N._dur(a)
        rep = N.normalize_master(str(a), total_words=6, max_pause=0.95, dry_run=True)
        after = N._dur(a)
        assert abs(before - after) < 0.05, "dry-run must not modify the file"
        assert rep["pause_fixes"], "dry-run should still report the fix"
    print("  ✓ dry-run reports without editing")
