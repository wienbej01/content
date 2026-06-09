#!/usr/bin/env python3
"""tests/test_qa_media.py — P4-12 media technical QA tests."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("qa_media", ROOT / "scripts" / "qa_media.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_clip(path, duration=5, width=1280, height=720, audio=False):
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:size={width}x{height}:d={duration}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=duration={duration}"]
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "64k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, capture_output=True, check=True)


def test_pass_generated_tts_no_audio():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=False)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert ok and results[0]["status"] == "pass"
    print("  ✓ generated_tts without audio → pass")


def test_fail_generated_tts_with_audio():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=True)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "AUDIO_POLICY" in results[0]["issues"][0]
    print("  ✓ generated_tts WITH audio → fail (AUDIO_POLICY)")


def test_fail_baked_in_without_audio():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, audio=False)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "baked_in", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "AUDIO_POLICY" in results[0]["issues"][0]
    print("  ✓ baked_in WITHOUT audio → fail (AUDIO_POLICY)")


def test_fail_missing_file():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": "/nonexistent.mp4"}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "MISSING" in results[0]["issues"][0]
    print("  ✓ missing file → fail (MISSING)")


def test_fail_wrong_dimensions():
    qa = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = td / "clip.mp4"
        _make_clip(clip, width=640, height=480)
        script = {"project_id": "t", "segments": [
            {"id": "s1", "audio_mode": "generated_tts", "media": str(clip)}
        ], "defaults": {"format": "mp3"}}
        sp = td / "script.json"
        sp.write_text(json.dumps(script))
        results, ok = qa.run_qa(str(sp))
    assert not ok and "DIMENSIONS" in results[0]["issues"][0]
    print("  ✓ wrong dimensions → fail (DIMENSIONS)")


def test_real_teaser_qa():
    """Run QA on actual teaser_02 script — report but don't assert all pass."""
    qa = _load()
    sp = ROOT / "scripts/generated/james_growth_system_teaser_02.json"
    if not sp.exists():
        print("  ⊘ teaser_02 script not found (skipped)")
        return
    results, ok = qa.run_qa(str(sp))
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    print(f"  ✓ teaser_02 QA: {passed} pass, {failed} fail (info only)")


def main():
    print("Media Technical QA Tests (P4-12)")
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
