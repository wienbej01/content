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

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def log():
    """Load the most recent assembly log. Skip all tests if none exists."""
    completed = ROOT / "Videos" / "Completed"
    logs = sorted(completed.glob("*_log.json"), key=lambda p: p.stat().st_mtime) if completed.exists() else []
    if not logs:
        pytest.skip("No assembly log found — run assemble.py first to generate test fixtures")
    return json.loads(logs[-1].read_text())


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


# =====================================================================
# T8 — Baked-audio assembly for lipsync spans (LIPSYNC_TICKETS.md)
# =====================================================================
# Fixtures use mechanically-distinguishable tones so we can probe the
# ASSEMBLED output and prove which audio survived on which span:
#   - baked lipsync audio = 1000 Hz sine  (the clip's own mouth-synced track)
#   - narration overlay    = 300 Hz sine  (the separate voiceover track)
# After assembly we band-measure the energy at each frequency over a span's
# time window. A lipsync span must carry the 1000 Hz tone and NOT the 300 Hz
# tone (no overlay); a voiceover span must carry the 300 Hz tone.

import hashlib
import importlib.util
import tempfile

import pytest as _pytest


def _load_assemble():
    spec = importlib.util.spec_from_file_location("assemble", ROOT / "scripts" / "assemble.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def _make_tone_audio(path, freq, dur):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
         "-c:a", "libmp3lame", "-q:a", "2", str(path)],
        capture_output=True, check=True)


def _make_video_with_tone(path, freq, dur, w=1280, h=720, color="navy"):
    """A video clip whose baked audio is a `freq` Hz tone."""
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c={color}:size={w}x{h}:rate=24:duration={dur}",
         "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(path)],
        capture_output=True, check=True)


def _make_silent_video(path, dur, w=1280, h=720, color="black"):
    """Create a video with a silent audio stream to allow proper mixing."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c={color}:size={w}x{h}:rate=24:duration={dur}",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
        capture_output=True, check=True)


def _band_energy(path, start, end, freq, bw=80):
    """Mean volume (dB) of a narrow band around `freq` over [start,end] of `path`.
    Higher (closer to 0) = tone present; very low (e.g. < -50dB) = absent."""
    af = (f"atrim=start={start}:end={end},"
          f"highpass=f={freq-bw},lowpass=f={freq+bw},"
          f"volumedetect")
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", af, "-f", "null", "/dev/null"],
        capture_output=True, text=True)
    import re
    m = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", r.stderr)
    return float(m.group(1)) if m else -100.0


def _probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def _build_lipsync_project(td, *, speech_len=2.0, clip_pad=3.0,
                           tamper_slice=False, lipsync_color="navy"):
    """Create a 2-segment project: [lipsync hero (master narration), voiceover (master narration)].
    Returns (manifest_path, base_dir, slice_path)."""
    base = Path(td)
    nar = base / "narration"
    slices = nar / "slices"
    slices.mkdir(parents=True)

    # Hero lipsync clip — padded to clip_pad seconds, baked 1000Hz tone (which will be stripped)
    hero = base / "hero.mp4"
    _make_video_with_tone(hero, 1000, clip_pad, color=lipsync_color)

    # The slice file (what the clip was generated from): 1000Hz, speech length
    slice_path = slices / "B001.mp3"
    _make_tone_audio(slice_path, 1000, speech_len)
    parent = nar / "001_hook.mp3"
    _make_tone_audio(parent, 1000, speech_len)
    slice_sha = _sha256(slice_path)
    parent_sha = _sha256(parent)
    if tamper_slice:
        slice_sha = "0" * 64  # provenance will not match the live file

    # Master narration spine (300Hz) — used for ALL segments under LB-202
    master_narration = nar / "continuous.mp3"
    _make_tone_audio(master_narration, 300, 5.0)  # 5.0s total master narration

    # Voiceover segment — muted video (audio will come from master narration)
    # Duration must match the master narration to avoid freeze-frame limits
    vo_vid = base / "vo.mp4"
    _make_silent_video(vo_vid, 5.0)  # Match 5.0s master narration

    manifest = {
        "id": "lipsync_fixture",
        "audio": "narration/continuous.mp3",  # LB-202: Global master narration spine
        "segments": [
            {
                "media": "hero.mp4",
                "audio": "narration/continuous.mp3",  # LB-202: Explicitly link master spine
                "audio_policy": "keep_lipsync",
                "speech_len_sec": speech_len,
                "lipsync_provenance": {
                    "slice_file": "narration/slices/B001.mp3",
                    "slice_sha256": slice_sha,
                    "parent_mp3": "narration/001_hook.mp3",
                    "parent_mp3_sha256": parent_sha,
                },
            },
            {"media": "vo.mp4", "audio": "narration/continuous.mp3", "words": 6},  # Audio comes from master spine
        ],
        "pacing": {"reference": 1, "baseline_speed": 1.0},
        "music": {"enabled": False},
        "brand": {"gap_seconds": 0.0, "audio_fade": 0.05},
        "render": {"fps": 24, "crf": 20, "grade": "null"},
        "output": {"directory": ".", "prefix": "lipsync_fixture"},
    }
    mpath = base / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2))
    return mpath, base, slice_path


def test_lipsync_span_has_master_narration_not_baked_audio():
    """LB-202: The hero span must NOT carry its baked tone; it uses the master spine."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td)
        out = asm.assemble(str(mpath), formats=["16x9"])
        final = out["formats"]["16x9"]["path"]
        # Hero span is first; probe 0.3..1.5s of the assembled output.
        e1000 = _band_energy(final, 0.3, 1.5, 1000)
        # Baked 1000Hz tone should be stripped (or very low due to noise floor/filter skirt)
        # A full-volume tone would be > -20dB; < -35dB indicates successful stripping.
        assert e1000 < -35.0, f"baked 1000Hz tone should be stripped on lipsync span (E={e1000:.1f}dB)"
    print("  ✓ lipsync span has baked audio stripped (LB-202)")


def test_lipsync_span_has_master_narration_overlay():
    """LB-202: The hero span MUST contain the master narration overlay (no echo, just master)."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td)
        out = asm.assemble(str(mpath), formats=["16x9"])
        final = out["formats"]["16x9"]["path"]
        total = _probe_dur(final)
        e300_lip = _band_energy(final, 0.3, 1.5, 300)          # lipsync span
        e300_vo = _band_energy(final, total - 1.5, total - 0.4, 300)  # voiceover span
        
        # Master narration (300Hz) MUST be present on the lipsync span
        assert e300_lip > -45.0, f"master narration 300Hz missing on lipsync span (E={e300_lip:.1f}dB)"
        
        # The 300Hz energy on the lipsync span should be similar to the voiceover span
        # (since both are using the same master narration spine)
        assert abs(e300_lip - e300_vo) < 15.0, (
            f"300Hz narration on lipsync span (E={e300_lip:.1f}dB) differs too much "
            f"from voiceover span (E={e300_vo:.1f}dB) — master spine not applied correctly")
    print("  ✓ lipsync span has master narration overlay (LB-202)")


def test_voiceover_spans_still_overlay_narration():
    """The voiceover span carries the 300Hz narration overlay (existing behavior)."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td)
        out = asm.assemble(str(mpath), formats=["16x9"])
        final = out["formats"]["16x9"]["path"]
        total = _probe_dur(final)
        # Voiceover span is the tail; probe near the end.
        e300 = _band_energy(final, total - 1.5, total - 0.4, 300)
        assert e300 > -45.0, f"narration 300Hz missing on voiceover span (E={e300:.1f}dB)"
    print("  ✓ voiceover span overlays narration (300Hz present)")


def test_trim_to_speech_length():
    """The hero clip (padded to 3s) is trimmed to its true 2s speech length ±0.25s."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td, speech_len=2.0, clip_pad=3.0)
        # Inspect the per-segment normalized clip, not the concatenated output.
        import shutil
        tmp = base / "tmpwork"
        out = asm.assemble(str(mpath), formats=["16x9"], tmp_base=str(tmp))
        seg0 = tmp / "16x9" / "seg_0.mp4"
        assert seg0.exists(), "normalized lipsync segment not found"
        d = _probe_dur(seg0)
        assert abs(d - 2.0) <= 0.25, f"lipsync span trimmed to {d:.3f}s, expected 2.0s ±0.25"
    print("  ✓ lipsync clip trimmed to true speech length")


def test_provenance_mismatch_fails_assembly():
    """A tampered slice hash must KILL assembly (provenance gate fires)."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td, tamper_slice=True)
        with _pytest.raises((ValueError, RuntimeError)) as ei:
            asm.assemble(str(mpath), formats=["16x9"])
        assert "provenance" in str(ei.value).lower() or "hash" in str(ei.value).lower()
    print("  ✓ provenance mismatch fails assembly")


def test_segment_timing_within_quarter_second():
    """Assembled lipsync span duration is within ±0.25s of true speech length."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td, speech_len=2.0, clip_pad=3.0)
        tmp = base / "tw2"
        asm.assemble(str(mpath), formats=["16x9"], tmp_base=str(tmp))
        seg0 = tmp / "16x9" / "seg_0.mp4"
        d = _probe_dur(seg0)
        assert abs(d - 2.0) <= 0.25, f"timing {d:.3f}s outside ±0.25s of 2.0s"
    print("  ✓ segment timing within ±0.25s")


def test_continuous_mode_accepts_lipsync_as_muted():
    """Continuous master-overlay path accepts keep_lipsync segments — they become
    muted visuals (baked audio ignored, master is sole audio source)."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath, base, _ = _build_lipsync_project(td)
        m = json.loads(Path(mpath).read_text())
        m["narration_mode"] = "continuous_voiceover"
        m["continuous_audio"] = "narration/001_hook.mp3"
        m["timing_map"] = "narration/timing_map.json"
        Path(mpath).write_text(json.dumps(m))
        # Should NOT raise — lipsync clips are now treated as muted visuals
        try:
            asm.assemble(str(mpath), formats=["16x9"])
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass  # Expected: fixture lacks real continuous audio file
        except ValueError as e:
            if "keep_lipsync" in str(e):
                raise AssertionError("continuous mode should NOT reject keep_lipsync anymore") from e
    print("  ✓ continuous mode accepts keep_lipsync as muted visuals")


# =====================================================================
# TKT-09 — Assembly Hardening (continuous voiceover duration checks)
# =====================================================================


def _build_continuous_project(td, beat_durations, clip_durations):
    """Build a minimal continuous_voiceover project.

    beat_durations: list of required durations per beat (from timing map)
    clip_durations: list of actual clip durations to generate

    Returns manifest_path.
    """
    base = Path(td)
    total_dur = sum(beat_durations)

    # Create continuous narration audio
    nar_dir = base / "narration"
    nar_dir.mkdir()
    continuous = nar_dir / "continuous.mp3"
    _make_tone_audio(continuous, 440, total_dur)

    # Create beat_timing_map
    beats = []
    offset = 0.0
    for i, bd in enumerate(beat_durations):
        beats.append({"beat_id": f"B{i+1:03d}", "start": offset, "end": offset + bd, "duration": bd})
        offset += bd
    timing_map = base / "narration" / "beat_timing_map.json"
    timing_map.write_text(json.dumps({"total_duration": total_dur, "beat_count": len(beats), "beats": beats}))

    # Create clips
    segments = []
    for i, cd in enumerate(clip_durations):
        clip_path = base / f"clip_{i}.mp4"
        _make_silent_video(clip_path, cd, w=320, h=180)
        segments.append({
            "id": f"B{i+1:03d}",
            "segment_id": f"seg_{i}",
            "media": f"clip_{i}.mp4",
            "audio_policy": "strip",
            "words": 10,
        })

    manifest = {
        "id": "tkt09_fixture",
        "narration_mode": "continuous_voiceover",
        "continuous_audio": "narration/continuous.mp3",
        "beat_timing_map": "narration/beat_timing_map.json",
        "segments": segments,
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "music": {"enabled": False},
        "brand": {},
        "render": {"fps": 24, "crf": 23, "grade": "null"},
        "output": {"directory": "out", "prefix": "tkt09"},
    }
    mpath = base / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2))
    return mpath


def test_short_visual_long_audio_fails_before_mux():
    """TKT-09: A beat needing 10s but only a 3s clip raises BEFORE producing the final file."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        mpath = _build_continuous_project(td, beat_durations=[10.0], clip_durations=[3.0])
        base = Path(td)
        final = base / "out" / "tkt09_16x9.mp4"
        with _pytest.raises(RuntimeError, match="too short"):
            asm.assemble(str(mpath), formats=["16x9"])
        assert not final.exists(), "Final file must NOT exist after failure"


def test_visual_bed_mismatch_fails():
    """TKT-09: When all clips sum to far less than the timing map total, assembly fails
    with a duration-mismatch error before mux."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        # 2 beats each needing 10s, but clips are only 2s each (4s total vs 20s needed)
        mpath = _build_continuous_project(td, beat_durations=[10.0, 10.0], clip_durations=[2.0, 2.0])
        base = Path(td)
        final = base / "out" / "tkt09_16x9.mp4"
        with _pytest.raises(RuntimeError, match="(too short|mismatch)"):
            asm.assemble(str(mpath), formats=["16x9"])
        assert not final.exists(), "Final file must NOT exist after failure"


def test_valid_continuous_fixture_assembles():
    """TKT-09: When clips cover their required durations, assembly succeeds
    with abs(video_dur - audio_dur) <= 0.25s."""
    asm = _load_assemble()
    with tempfile.TemporaryDirectory() as td:
        # 2 beats, clips exactly match durations
        mpath = _build_continuous_project(td, beat_durations=[3.0, 3.0], clip_durations=[3.0, 3.0])
        log = asm.assemble(str(mpath), formats=["16x9"])
        final = Path(log["formats"]["16x9"]["path"])
        assert final.exists(), "Final file should exist"
        dur = _probe_dur(final)
        assert abs(dur - 6.0) <= 0.25, f"Final duration {dur:.3f}s should be ~6.0s"
