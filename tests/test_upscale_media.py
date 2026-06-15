#!/usr/bin/env python3
"""tests/test_upscale_media.py — stage 6.5 upscaler tests (ffmpeg path, no spend)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("upscale_media", ROOT / "scripts" / "upscale_media.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_720_clip(path, audio=True):
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:d=2:rate=24"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=300:duration=2", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, capture_output=True, check=True)


def test_ffmpeg_upscale_to_1080():
    U = _load()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mp4"; dst = Path(td) / "out.mp4"
        _make_720_clip(src)
        U.upscale_ffmpeg(src, dst, (1920, 1080))
        w, h = U._probe_dims(dst)
        assert (w, h) == (1920, 1080), f"expected 1920x1080, got {w}x{h}"
    print("  ✓ ffmpeg upscale 720p → 1080p")


def test_upscale_preserves_audio():
    U = _load()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mp4"; dst = Path(td) / "out.mp4"
        _make_720_clip(src, audio=True)
        U.upscale_ffmpeg(src, dst, (1920, 1080))
        probe = subprocess.run(["ffprobe", "-v", "quiet", "-select_streams", "a",
                                "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(dst)],
                               capture_output=True, text=True)
        assert "audio" in probe.stdout, "upscale must preserve the audio stream (lipsync)"
    print("  ✓ upscale preserves audio (lipsync intact)")


def test_already_hires_skipped():
    """A clip already at/above target is not re-upscaled (idempotent)."""
    U = _load()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        clip = ROOT / "assets" / "media" / "_uptest" / "B001.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:d=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], capture_output=True, check=True)
        plan = {"beats": [{"beat_id": "B001", "asset_type": "generated_video",
                           "output_path": str(clip.relative_to(ROOT))}]}
        pp = td / "plan.json"; pp.write_text(json.dumps(plan))
        rep = U.upscale_plan(pp, (1920, 1080))
        assert rep["results"][0]["status"] == "already_hires"
        clip.unlink(missing_ok=True)
    print("  ✓ already-hires clip skipped (idempotent)")


def test_engine_chain_reports():
    """Engine is reported (ffmpeg-hq baseline always available)."""
    U = _load()
    with tempfile.TemporaryDirectory() as td:
        pp = Path(td) / "plan.json"
        pp.write_text(json.dumps({"beats": []}))
        rep = U.upscale_plan(pp, (1920, 1080))
        assert rep["engine"] in ("realesrgan", "ffmpeg-hq")
    print(f"  ✓ engine chain reports ({_load().__name__})")
