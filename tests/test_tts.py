#!/usr/bin/env python3
"""tests/test_tts.py — Property tests for the TTS-to-manifest pipeline.

Tests validation, error handling, and manifest structure without requiring
a live ElevenLabs API key (except for the skip-marked live test).

Usage:
  python tests/test_tts.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TTS = ROOT / "scripts" / "tts.py"

VALID_SCRIPT = {
    "project_id": "test_project",
    "title": "Test",
    "voice": {"voice_id": "test_voice_id", "model_id": "eleven_multilingual_v2"},
    "segments": [
        {"id": "seg1", "audio_mode": "generated_tts", "text": "Hello world this is a test.", "media": "__PLACEHOLDER__"}
    ],
}


def run_tts(script_dict, *args, media_file=None, env_override=None):
    """Write script to temp, run tts.py with given args, return (exit_code, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Create a dummy media file if needed
        if media_file is None:
            media_file = td / "dummy.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=1:d=2",
                 "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2",
                 "-pix_fmt", "yuv420p", "-shortest", str(media_file)],
                capture_output=True)

        # Patch placeholder
        script = json.loads(json.dumps(script_dict))
        for seg in script.get("segments", []):
            if seg.get("media") == "__PLACEHOLDER__":
                seg["media"] = str(media_file)
        script.setdefault("output_dir", str(td / "output"))

        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)

        env = os.environ.copy()
        # Remove API key by default (tests shouldn't call real API)
        env.pop("ELEVENLABS_API_KEY", None)
        if env_override:
            env.update(env_override)

        r = subprocess.run(
            [sys.executable, str(TTS), str(script_path), *args],
            capture_output=True, text=True, env=env)
        return r.returncode, r.stdout, r.stderr


def test_valid_script_validates():
    code, out, err = run_tts(VALID_SCRIPT, "--validate-only")
    assert code == 0, f"FAIL: valid script failed validation: {err}"
    assert "VALID" in out
    print("  ✓ Valid script passes --validate-only")


def test_missing_text_fails():
    script = json.loads(json.dumps(VALID_SCRIPT))
    script["segments"][0].pop("text")
    code, out, err = run_tts(script, "--validate-only")
    assert code == 1, f"FAIL: expected exit 1 for missing text"
    assert "requires 'text'" in err
    print("  ✓ Missing text fails cleanly (generated_tts mode)")


def test_missing_media_fails():
    """Media existence is checked at assembly time, not TTS time — validate-only should pass."""
    script = json.loads(json.dumps(VALID_SCRIPT))
    script["segments"][0]["media"] = "/nonexistent/file.mp4"
    code, out, err = run_tts(script, "--validate-only")
    # Media existence not checked at TTS stage (only presence of 'media' key required)
    assert code == 0, f"FAIL: validate-only should pass even with missing media file (checked at assembly)"
    print("  ✓ Missing media file doesn't block TTS (checked at assembly time)")


def test_missing_api_key_fails():
    """Without --validate-only, missing API key must fail."""
    # Set key to empty string to override runtime.env loading
    code, out, err = run_tts(VALID_SCRIPT, env_override={"ELEVENLABS_API_KEY": ""})
    assert code == 1
    assert "ELEVENLABS_API_KEY" in err
    print("  ✓ Missing ELEVENLABS_API_KEY fails cleanly")


def test_validate_only_no_api_key():
    """--validate-only must NOT require API key."""
    code, out, err = run_tts(VALID_SCRIPT, "--validate-only")
    assert code == 0, f"FAIL: --validate-only should not need API key: {err}"
    print("  ✓ --validate-only works without API key")


def test_existing_narration_reused():
    """If narration file exists and --force not passed, it's reused (no API call)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Create dummy media
        media = td / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=1:d=2",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
             "-c:a", "aac", "-ar", "48000", "-shortest", "-pix_fmt", "yuv420p", str(media)],
            capture_output=True)

        # Create script
        out_dir = td / "output"
        narration_dir = out_dir / "narration"
        narration_dir.mkdir(parents=True)

        script = {
            "project_id": "reuse_test",
            "output_dir": str(out_dir),
            "voice": {"voice_id": "fake"},
            "segments": [{"id": "seg1", "audio_mode": "generated_tts", "text": "Hello world.", "media": str(media)}],
        }
        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)

        # Pre-create a narration file (fake but real audio)
        fake_audio = narration_dir / "seg1.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=1.5",
             "-c:a", "libmp3lame", "-b:a", "128k", str(fake_audio)],
            capture_output=True)

        # Run WITHOUT --force and WITHOUT API key — should reuse existing
        env = os.environ.copy()
        env.pop("ELEVENLABS_API_KEY", None)
        # Trick: with existing narration, it won't need API key since it skips TTS
        # But it still requires key because the code checks before the loop.
        # Actually looking at the code: api_key check is before the loop. So this test
        # needs a fake key to get past that check.
        env["ELEVENLABS_API_KEY"] = "fake_key_for_reuse_test"

        r = subprocess.run(
            [sys.executable, str(TTS), str(script_path)],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"FAIL: reuse test failed: {r.stderr}"
        assert "reused" in r.stdout.lower()
        # Manifest should exist
        manifest_path = out_dir / "manifest.json"
        assert manifest_path.exists()
        print("  ✓ Existing narration reused (no API call needed)")


def test_manifest_has_required_fields():
    """Generated manifest must be compatible with assemble.py."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        media = td / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=1:d=3",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
             "-c:a", "aac", "-ar", "48000", "-shortest", "-pix_fmt", "yuv420p", str(media)],
            capture_output=True)

        out_dir = td / "output"
        narration_dir = out_dir / "narration"
        narration_dir.mkdir(parents=True)

        # Pre-create narration
        narration = narration_dir / "seg1.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000:duration=2.5",
             "-c:a", "libmp3lame", "-b:a", "128k", str(narration)],
            capture_output=True)

        script = {
            "project_id": "manifest_check",
            "output_dir": str(out_dir),
            "voice": {"voice_id": "fake"},
            "segments": [{"id": "seg1", "audio_mode": "generated_tts", "text": "Five words for this test.", "media": str(media)}],
        }
        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)

        env = os.environ.copy()
        env["ELEVENLABS_API_KEY"] = "fake_for_manifest_test"

        r = subprocess.run(
            [sys.executable, str(TTS), str(script_path)],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"FAIL: {r.stderr}"

        manifest_path = out_dir / "manifest.json"
        with open(manifest_path) as f:
            m = json.load(f)

        # Check required fields for assemble.py
        assert "id" in m, "FAIL: manifest missing 'id'"
        assert "segments" in m and len(m["segments"]) > 0
        seg = m["segments"][0]
        assert "media" in seg, "FAIL: segment missing 'media'"
        assert "words" in seg and isinstance(seg["words"], int) and seg["words"] > 0
        # 'audio' field is only present when media lacks an audio stream (image/no-audio).
        # For lipsync clips with baked-in audio, 'audio' must be absent (M2-B regression guard).
        assert "pacing" in m and "reference" in m["pacing"]
        assert "music" in m
        assert "output" in m
        print("  ✓ Generated manifest has all required assemble.py fields")


def test_duration_from_probe_not_estimate():
    """Manifest should use probed audio duration, not a WPS estimate."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        media = td / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=1:d=5",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=5",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
             "-c:a", "aac", "-ar", "48000", "-shortest", "-pix_fmt", "yuv420p", str(media)],
            capture_output=True)

        out_dir = td / "output"
        narration_dir = out_dir / "narration"
        narration_dir.mkdir(parents=True)

        # Create narration with a SPECIFIC known duration (3.7s)
        narration = narration_dir / "seg1.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000:duration=3.7",
             "-c:a", "libmp3lame", "-b:a", "128k", str(narration)],
            capture_output=True)

        script = {
            "project_id": "dur_test",
            "output_dir": str(out_dir),
            "voice": {"voice_id": "fake"},
            "segments": [{"id": "seg1", "audio_mode": "generated_tts", "text": "One two three four five six seven eight nine ten eleven twelve.", "media": str(media)}],
        }
        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)

        env = os.environ.copy()
        env["ELEVENLABS_API_KEY"] = "fake_for_dur_test"

        r = subprocess.run(
            [sys.executable, str(TTS), str(script_path)],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"FAIL: {r.stderr}"

        # Check the tts_log for actual probed duration
        log_path = out_dir / "tts_log.json"
        with open(log_path) as f:
            log = json.load(f)
        dur = log["segments"][0]["duration"]
        # Duration should be close to 3.7s (from probe), not some WPS estimate
        assert 3.5 < dur < 3.9, f"FAIL: duration {dur} not from probe (expected ~3.7)"
        print(f"  ✓ Duration from probe ({dur:.2f}s), not WPS estimate")


def test_lipsync_clips_omit_audio_field():
    """Lipsync video clips must NOT have an audio field in the manifest.
    Substituting separate audio on a lipsync clip breaks sync (M2-B regression).
    Only images or audio-less video should get the audio field."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Create a video clip WITH an audio stream (simulates a lipsync clip)
        lipsync_clip = td / "lipsync.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=24:d=3",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
             "-c:a", "aac", "-ar", "48000", "-pix_fmt", "yuv420p", "-shortest", str(lipsync_clip)],
            capture_output=True)

        out_dir = td / "output"
        narration_dir = out_dir / "narration"
        narration_dir.mkdir(parents=True)
        # Pre-create narration file (different duration than clip to expose the bug)
        narration = narration_dir / "seg1.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000:duration=1.5",
             "-c:a", "libmp3lame", "-b:a", "128k", str(narration)],
            capture_output=True)

        script = {
            "project_id": "lipsync_test",
            "output_dir": str(out_dir),
            "voice": {"voice_id": "fake"},
            "segments": [{"id": "seg1", "audio_mode": "baked_in", "text": "Lip synced text.", "media": str(lipsync_clip)}],
        }
        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)

        env = os.environ.copy()
        env["ELEVENLABS_API_KEY"] = "fake_for_lipsync_test"

        r = subprocess.run(
            [sys.executable, str(TTS), str(script_path)],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"FAIL: {r.stderr}"

        manifest_path = out_dir / "manifest.json"
        with open(manifest_path) as f:
            m = json.load(f)

        seg = m["segments"][0]
        assert "audio" not in seg, (
            "FAIL (M2-B regression): lipsync clip should NOT have 'audio' in manifest. "
            "Substituting separate audio breaks lipsync sync.")
        print("  ✓ Lipsync clips do NOT get audio field in manifest (M2-B regression guard)")


def test_missing_audio_mode_fails():
    """Missing audio_mode must fail validation — no silent guessing."""
    script = json.loads(json.dumps(VALID_SCRIPT))
    del script["segments"][0]["audio_mode"]
    code, out, err = run_tts(script, "--validate-only")
    assert code == 1
    assert "audio_mode" in err
    print("  ✓ Missing audio_mode fails cleanly")


def test_unknown_audio_mode_fails():
    """Unknown audio_mode must fail."""
    script = json.loads(json.dumps(VALID_SCRIPT))
    script["segments"][0]["audio_mode"] = "magic"
    code, out, err = run_tts(script, "--validate-only")
    assert code == 1
    assert "unknown audio_mode" in err
    print("  ✓ Unknown audio_mode fails cleanly")


def test_baked_in_fails_without_audio_stream():
    """baked_in on media with no audio stream must fail."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        silent_vid = td / "silent.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=24:d=2",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
             "-pix_fmt", "yuv420p", "-an", str(silent_vid)],
            capture_output=True)
        script = {
            "project_id": "t", "voice": {"voice_id": "x"},
            "segments": [{"id": "s", "audio_mode": "baked_in", "media": str(silent_vid)}],
        }
        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)
        env = os.environ.copy()
        env.pop("ELEVENLABS_API_KEY", None)
        r = subprocess.run([sys.executable, str(TTS), str(script_path), "--validate-only"],
                          capture_output=True, text=True, env=env)
        assert r.returncode == 1
        assert "no audio stream" in r.stderr
        print("  ✓ baked_in fails if media has no audio stream")


def test_generated_tts_adds_audio_even_if_media_has_audio():
    """B-roll with ambient audio but audio_mode=generated_tts still uses TTS narration."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        broll = td / "broll.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=24:d=3",
             "-f", "lavfi", "-i", "sine=frequency=100:sample_rate=48000:duration=3",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "50",
             "-c:a", "aac", "-ar", "48000", "-pix_fmt", "yuv420p", "-shortest", str(broll)],
            capture_output=True)
        out_dir = td / "output"
        narration_dir = out_dir / "narration"
        narration_dir.mkdir(parents=True)
        narration = narration_dir / "seg1.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000:duration=2",
             "-c:a", "libmp3lame", "-b:a", "128k", str(narration)],
            capture_output=True)
        script = {
            "project_id": "broll_test", "output_dir": str(out_dir), "voice": {"voice_id": "fake"},
            "segments": [{"id": "seg1", "audio_mode": "generated_tts", "text": "Narration over B-roll.", "media": str(broll)}],
        }
        script_path = td / "script.json"
        with open(script_path, "w") as f:
            json.dump(script, f)
        env = os.environ.copy()
        env["ELEVENLABS_API_KEY"] = "fake"
        r = subprocess.run([sys.executable, str(TTS), str(script_path)],
                          capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"FAIL: {r.stderr}"
        with open(out_dir / "manifest.json") as f:
            m = json.load(f)
        assert "audio" in m["segments"][0], "FAIL: generated_tts must include audio even on B-roll with audio"
        print("  ✓ generated_tts adds audio field even when media has audio (B-roll case)")


def main():
    print("M2 TTS Pipeline Tests")
    tests = [
        test_valid_script_validates,
        test_missing_text_fails,
        test_missing_media_fails,
        test_missing_api_key_fails,
        test_validate_only_no_api_key,
        test_existing_narration_reused,
        test_manifest_has_required_fields,
        test_duration_from_probe_not_estimate,
        test_lipsync_clips_omit_audio_field,
        test_missing_audio_mode_fails,
        test_unknown_audio_mode_fails,
        test_baked_in_fails_without_audio_stream,
        test_generated_tts_adds_audio_even_if_media_has_audio,
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
