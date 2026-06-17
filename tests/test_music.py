"""TKT-10: Music bed implementation and verification tests."""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def make_sine_wav(path, duration=3.0, freq=440):
    """Generate a sine-wave audio file using ffmpeg."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"sine=frequency={freq}:duration={duration}",
        "-ac", "2", "-ar", "48000", str(path)
    ], capture_output=True, check=True)


def make_test_video(path, duration=3.0):
    """Generate a silent test video clip."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=blue:s=320x180:d={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k", "-ar", "48000", "-ac", "2",
        str(path)
    ], capture_output=True, check=True)


def write_manifest(tmp, music_cfg, fmt="explainer"):
    """Write a minimal continuous_voiceover manifest for testing music."""
    clip = tmp / "clip.mp4"
    make_test_video(clip, duration=3.0)
    narration = tmp / "narration.mp3"
    make_sine_wav(narration, duration=3.0, freq=300)

    manifest = {
        "id": "test_music",
        "format": fmt,
        "narration_mode": "continuous_voiceover",
        "continuous_audio": "narration.mp3",
        "segments": [{"id": "seg_0", "media": "clip.mp4", "audio_policy": "BROLL_FLEX", "final_audio_source": "none", "provider_audio_usage": "discarded", "text_policy": "NO_VISIBLE_TEXT", "words": 10}],
        "music": music_cfg,
        "render": {"fps": 24, "crf": 28},
        "output": {"directory": "out", "prefix": "test"},
        "pacing": {}
    }
    manifest_path = tmp / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def run_assemble(manifest_path, fmt="16x9"):
    """Run assemble.py and return (returncode, stderr)."""
    r = subprocess.run(
        ["python3", str(SCRIPTS / "assemble.py"), str(manifest_path),
         "--formats", fmt],
        capture_output=True, text=True, cwd=manifest_path.parent
    )
    return r.returncode, r.stderr


class TestMusicRequired:
    def test_required_music_missing_path_fails(self, tmp_path):
        """Music enabled=true but path doesn't exist -> RuntimeError."""
        music_cfg = {"enabled": True, "path": "nonexistent_music.mp3"}
        manifest_path = write_manifest(tmp_path, music_cfg)
        rc, stderr = run_assemble(manifest_path)
        assert rc != 0
        assert "not found" in stderr.lower() or "RuntimeError" in stderr

    def test_required_format_but_disabled_fails(self, tmp_path):
        """Format=short requires music per constraints, but enabled=false -> RuntimeError."""
        music_cfg = {"enabled": False}
        manifest_path = write_manifest(tmp_path, music_cfg, fmt="short")
        rc, stderr = run_assemble(manifest_path)
        assert rc != 0
        assert "required" in stderr.lower() or "Music is required" in stderr


class TestMusicBed:
    def test_music_bed_mixes_correctly(self, tmp_path):
        """Valid music bed assembles correctly."""
        music_file = tmp_path / "music.mp3"
        make_sine_wav(music_file, duration=5.0, freq=880)
        music_cfg = {
            "enabled": True,
            "path": "music.mp3",
            "volume_db": -24,
            "fade_in": 0.5,
            "fade_out": 0.5,
            "loop": False
        }
        manifest_path = write_manifest(tmp_path, music_cfg)
        rc, stderr = run_assemble(manifest_path)
        assert rc == 0, f"Assembly failed: {stderr}"
        out = tmp_path / "out" / "test_16x9.mp4"
        assert out.exists()
        # Verify output has audio stream
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True)
        assert "audio" in probe.stdout

    def test_optional_music_disabled_ok(self, tmp_path):
        """Format=teaser not in required_for_formats, music disabled -> no error."""
        music_cfg = {"enabled": False}
        manifest_path = write_manifest(tmp_path, music_cfg, fmt="teaser")
        rc, stderr = run_assemble(manifest_path)
        assert rc == 0, f"Assembly failed unexpectedly: {stderr}"
