#!/usr/bin/env python3
"""tests/test_media_pack.py — Property tests for media_pack.py."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA_PACK = ROOT / "scripts" / "media_pack.py"
TTS = ROOT / "scripts" / "tts.py"


def make_video(path, dur=3, with_audio=True, w=1920, h=1080):
    audio = ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={dur}"] if with_audio else []
    shortest = ["-shortest"] if with_audio else []
    an = [] if with_audio else ["-an"]
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=24:d={dur}",
         *audio, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
         "-c:a", "aac", "-ar", "48000", *an, "-pix_fmt", "yuv420p", *shortest, str(path)],
        capture_output=True)


def make_image(path, w=1920, h=1080):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={w}x{h}",
         "-frames:v", "1", str(path)], capture_output=True)


def run_mp(script_dict, *args, td=None):
    if td is None:
        td = Path(tempfile.mkdtemp())
    script_path = td / "script.json"
    with open(script_path, "w") as f:
        json.dump(script_dict, f)
    r = subprocess.run(
        [sys.executable, str(MEDIA_PACK), str(script_path), *args],
        capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr, td


def test_brief_generated():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vid = td / "clip.mp4"
        make_video(vid)
        script = {
            "project_id": "brief_test", "output_dir": str(td / "out"),
            "segments": [{"id": "seg1", "audio_mode": "baked_in", "text": "Hi", "media": str(vid)}],
        }
        code, out, err, _ = run_mp(script, "--brief", td=td)
        assert code == 0, f"FAIL: {err}"
        brief_path = td / "out" / "media_brief.json"
        assert brief_path.exists(), "FAIL: media_brief.json not created"
        brief = json.load(open(brief_path))
        assert brief["segments"][0]["id"] == "seg1"
        print("  ✓ Media brief generated from script")


def test_expected_paths_deterministic():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        script = {
            "project_id": "det_test", "output_dir": str(td / "out"),
            "segments": [
                {"id": "001_hook", "audio_mode": "generated_tts", "text": "Hook",
                 "media_request": {"type": "image"}},
            ],
        }
        code, out, err, _ = run_mp(script, "--brief", td=td)
        brief = json.load(open(td / "out" / "media_brief.json"))
        exp = brief["segments"][0]["expected_path"]
        assert "001_hook.png" in exp
        print("  ✓ Expected paths are deterministic by segment id")


def test_missing_required_media_fails():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "baked_in", "text": "x",
                          "media": str(td / "nonexist.mp4"),
                          "media_request": {"type": "lipsync_video", "required": True}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 1
        assert "MISSING" in out or "MISSING" in err
        print("  ✓ Missing required media fails cleanly")


def test_optional_missing_warns():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "silent",
                          "media": str(td / "nonexist.mp4"),
                          "media_request": {"type": "broll_video", "required": False}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 0  # should not fail
        assert "optional" in out.lower() or "⚠" in out
        print("  ✓ Optional missing media warns but does not fail")


def test_baked_in_no_audio_fails():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vid = td / "silent.mp4"
        make_video(vid, with_audio=False)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "baked_in", "media": str(vid),
                          "media_request": {"type": "lipsync_video"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 1
        assert "NO audio" in out or "no audio" in (out + err).lower()
        print("  ✓ baked_in fails if media has no audio stream")


def test_generated_tts_allows_image():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        img = td / "slide.png"
        make_image(img)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "generated_tts", "text": "Hi",
                          "media": str(img), "media_request": {"type": "image"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 0, f"FAIL: {out}{err}"
        print("  ✓ generated_tts allows image media")


def test_generated_tts_broll_with_audio_warns():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vid = td / "broll.mp4"
        make_video(vid, with_audio=True)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "generated_tts", "text": "Narration",
                          "media": str(vid), "media_request": {"type": "broll_video"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 0
        assert "replaced by generated" in out.lower() or "⚠" in out
        print("  ✓ generated_tts on B-roll with audio warns (audio will be replaced)")


def test_silent_no_text_required():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        img = td / "title.png"
        make_image(img)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "silent", "media": str(img),
                          "media_request": {"type": "title_card"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 0, f"FAIL: {out}{err}"
        print("  ✓ silent segment does not require text")


def test_orientation_mismatch_warns():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vid = td / "portrait.mp4"
        make_video(vid, w=1080, h=1920)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "baked_in", "media": str(vid),
                          "media_request": {"type": "lipsync_video", "orientation": "landscape"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 0  # warn not fail
        assert "portrait" in out.lower() or "⚠" in out
        print("  ✓ Orientation mismatch warns but does not fail")


def test_unknown_media_type_fails():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vid = td / "clip.mp4"
        make_video(vid)
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "baked_in", "media": str(vid),
                          "media_request": {"type": "hologram"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 1
        assert "unknown" in (out + err).lower()
        print("  ✓ Unknown media_request.type fails cleanly")


def test_unknown_extension_fails():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bad = td / "clip.xyz"
        bad.write_text("fake")
        script = {
            "project_id": "t", "output_dir": str(td / "out"),
            "segments": [{"id": "s", "audio_mode": "baked_in", "media": str(bad),
                          "media_request": {"type": "lipsync_video"}}],
        }
        code, out, err, _ = run_mp(script, "--validate", td=td)
        assert code == 1
        assert "extension" in (out + err).lower() or "expected video" in (out + err).lower()
        print("  ✓ Unknown file extension fails cleanly")


def test_write_ready_script_passes_tts_validate():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vid = td / "clip.mp4"
        make_video(vid)
        out_dir = td / "out"
        script = {
            "project_id": "ready_test", "output_dir": str(out_dir),
            "voice": {"voice_id": "fake"},
            "segments": [{"id": "seg1", "audio_mode": "baked_in", "text": "Hello.",
                          "media": str(vid), "media_request": {"type": "lipsync_video"}}],
        }
        code, out, err, _ = run_mp(script, "--write-ready-script", td=td)
        assert code == 0, f"FAIL: {out}{err}"
        ready_path = out_dir / "script_with_media.json"
        assert ready_path.exists()

        # Validate with tts.py --validate-only
        env = os.environ.copy()
        env.pop("ELEVENLABS_API_KEY", None)
        env["ELEVENLABS_VOICE_ID"] = "fake_for_test"
        r = subprocess.run(
            [sys.executable, str(TTS), str(ready_path), "--validate-only"],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"FAIL: tts.py rejected ready script: {r.stderr}"
        print("  ✓ --write-ready-script produces script accepted by tts.py --validate-only")


def main():
    print("M3 Media Pack Tests")
    tests = [
        test_brief_generated,
        test_expected_paths_deterministic,
        test_missing_required_media_fails,
        test_optional_missing_warns,
        test_baked_in_no_audio_fails,
        test_generated_tts_allows_image,
        test_generated_tts_broll_with_audio_warns,
        test_silent_no_text_required,
        test_orientation_mismatch_warns,
        test_unknown_media_type_fails,
        test_unknown_extension_fails,
        test_write_ready_script_passes_tts_validate,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: UNEXPECTED: {e}")
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
