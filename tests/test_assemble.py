#!/usr/bin/env python3
"""tests/test_assemble.py — Property tests for the assembly engine.

Validates outputs meet production quality requirements without
asserting exact byte-level content (lossy encoding is non-deterministic).

Usage:
  python tests/test_assemble.py                    # run against sample manifest
  python tests/test_assemble.py path/to/manifest.json
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def probe(path, entry):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entry,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return r.stdout.strip()


def silence_gaps(path, threshold_db=-35, min_dur=1.5):
    """Find silence gaps longer than min_dur. Returns list of (start, duration)."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path),
         "-af", f"silencedetect=noise={threshold_db}dB:d={min_dur}",
         "-f", "null", "/dev/null"],
        capture_output=True, text=True)
    import re
    starts = re.findall(r"silence_start: ([0-9.]+)", r.stderr)
    durations = re.findall(r"silence_duration: ([0-9.]+)", r.stderr)
    return list(zip([float(s) for s in starts], [float(d) for d in durations]))


def test_outputs_exist(log):
    """Both format files must exist."""
    for fmt, info in log["formats"].items():
        p = Path(info["path"])
        assert p.exists(), f"FAIL: {fmt} output missing: {p}"
    print("  ✓ Both output files exist")


def test_duration_sane(log):
    """Duration must be within ±2s of each other (same content, different crop)."""
    durs = [info["duration_s"] for info in log["formats"].values()]
    if len(durs) >= 2:
        diff = abs(durs[0] - durs[1])
        assert diff < 2.0, f"FAIL: format durations differ by {diff:.1f}s"
    for d in durs:
        assert 5 < d < 600, f"FAIL: duration {d}s out of sane range"
    print(f"  ✓ Durations sane ({durs})")


def test_resolution(log):
    """Each format has correct resolution."""
    expected = {"16x9": (1920, 1080), "9x16": (1080, 1920)}
    for fmt, info in log["formats"].items():
        p = info["path"]
        res = probe(p, "stream=width,height")
        w, h = res.strip().split("\n")[:2]
        exp = expected.get(fmt)
        if exp:
            assert (int(w), int(h)) == exp, f"FAIL: {fmt} resolution {w}x{h} != {exp}"
    print("  ✓ Resolutions correct")


def test_audio_present(log):
    """Audio stream must exist in both outputs."""
    for fmt, info in log["formats"].items():
        streams = probe(info["path"], "stream=codec_type")
        assert "audio" in streams, f"FAIL: {fmt} has no audio stream"
    print("  ✓ Audio streams present")


def test_volume_range(log):
    """Mean volume must be in broadcast range (-22 to -12 dB)."""
    for fmt, info in log["formats"].items():
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", info["path"],
             "-af", "volumedetect", "-f", "null", "/dev/null"],
            capture_output=True, text=True)
        import re
        m = re.search(r"mean_volume: ([-0-9.]+)", r.stderr)
        assert m, f"FAIL: couldn't measure volume for {fmt}"
        vol = float(m.group(1))
        assert -22 < vol < -12, f"FAIL: {fmt} mean volume {vol} dB outside [-22, -12]"
    print(f"  ✓ Volume in broadcast range")


def test_no_long_silence(log):
    """No silence gap > 2s during the main content (excludes endcard region at the end)."""
    for fmt, info in log["formats"].items():
        gaps = silence_gaps(info["path"], threshold_db=-40, min_dur=2.0)
        dur = info["duration_s"]
        # Filter: keep only gaps that START before the endcard region (last 4s)
        content_gaps = [(s, d) for s, d in gaps if s < dur - 4.0]
        assert len(content_gaps) == 0, (
            f"FAIL: {fmt} has {len(content_gaps)} long silence gap(s) in content: "
            f"{[(f'{s:.1f}s start, {d:.1f}s dur') for s, d in content_gaps]}")
    print("  ✓ No long silence gaps in content")


def test_pacing_aligned(log):
    """All segment speeds should produce aligned WPS (within 15% of target)."""
    pacing = log.get("pacing", {})
    target = pacing.get("target_wps", 0)
    wps = pacing.get("wps_per_segment", [])
    speeds = pacing.get("speeds", [])
    if not target or not wps or not speeds:
        print("  ⊘ Pacing data not in log (skipped)")
        return
    for i, (w, s) in enumerate(zip(wps, speeds)):
        rendered_wps = w * s
        deviation = abs(rendered_wps - target) / target
        assert deviation < 0.15, (
            f"FAIL: segment {i} rendered WPS {rendered_wps:.2f} deviates "
            f"{deviation*100:.0f}% from target {target:.2f}")
    print(f"  ✓ Pacing aligned (target {target:.2f} wps, all within 15%)")


def run_tests(log_path):
    print(f"Testing outputs from: {log_path}")
    with open(log_path) as f:
        log = json.load(f)

    tests = [
        test_outputs_exist,
        test_duration_sane,
        test_resolution,
        test_audio_present,
        test_volume_range,
        test_no_long_silence,
        test_pacing_aligned,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t(log)
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {e}")
            failed += 1

    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed} tests")
    return failed == 0


def main():
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        log_path = sys.argv[1]
    else:
        # Find the most recent log in Videos/Completed
        completed = ROOT / "Videos" / "Completed"
        logs = sorted(completed.glob("*_log.json"), key=lambda p: p.stat().st_mtime)
        if not logs:
            sys.exit("No log files found. Run assemble.py first.")
        log_path = logs[-1]

    success = run_tests(log_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
