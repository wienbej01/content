"""Deterministic, hermetic b-roll QC fixtures.

Four fixture generators for b-roll pixel-level QA tests:
  1. frozen_clip      — 5.0s single-color frame held for entire duration.
  2. moving_clip      — 5.0s testsrc motion.
  3. text_in_focus    — 5.0s clean slide with >5 readable ASCII text lines.
  4. face_in_focus    — 5.0s synthetic face via Pillow drawing.

All outputs are deterministic and hermetic (no paid calls, no network).
Each generator writes to a temp dir provided by pytest's tmp_path fixture.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont


class BrollFixture(NamedTuple):
    path: Path
    width: int
    height: int
    duration_sec: float
    has_text: bool
    has_face: bool
    is_frozen: bool


_FPS = 24
_DURATION_SEC = 5.0
_WIDTH = 1920
_HEIGHT = 1080
_FRAMES = int(_DURATION_SEC * _FPS)  # 120 frames at 24fps


def _write_video(path: Path, frame_gen, frames: int = _FRAMES, fps: int = _FPS) -> None:
    """ pipe raw RGB frames into ffmpeg via stdin to produce an H.264 mp4. """
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pixel_format", "rgb24",
            "-video_size", f"{_WIDTH}x{_HEIGHT}",
            "-framerate", str(fps),
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-frames:v", str(frames),
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(frames):
            proc.stdin.write(frame_gen())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {proc.returncode} while creating {path}")


def _rgb_frame(pixel: tuple[int, int, int]) -> bytes:
    return (bytes(pixel) * (_WIDTH * _HEIGHT))


def make_frozen_clip(tmp_path: Path) -> BrollFixture:
    """5.0s frozen frame — every frame is identical pixels. """
    out = tmp_path / "frozen_clip.mp4"
    color = (42, 86, 130)

    def frame_gen():
        return _rgb_frame(color)

    _write_video(out, frame_gen)
    return BrollFixture(out, _WIDTH, _HEIGHT, _DURATION_SEC, has_text=False, has_face=False, is_frozen=True)


def _testsrc_frame(seed: int) -> bytes:
    """A single testsrc-like frame: deterministic gradient. """
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            r = (x + seed * 7) & 0xFF
            g = (y + seed * 13) & 0xFF
            b = ((x ^ y) + seed * 3) & 0xFF
            px[x, y] = (r, g, b)
    return img.tobytes()


def make_moving_clip(tmp_path: Path) -> BrollFixture:
    """5.0s motion — each frame visually distinct. """
    out = tmp_path / "moving_clip.mp4"
    counter = 0

    def frame_gen():
        nonlocal counter
        seed = counter
        counter += 1
        return _testsrc_frame(seed)

    _write_video(out, frame_gen)
    return BrollFixture(out, _WIDTH, _HEIGHT, _DURATION_SEC, has_text=False, has_face=False, is_frozen=False)


def make_text_in_focus_clip(tmp_path: Path) -> BrollFixture:
    """5.0s clean slide with >5 readable ASCII text lines. """
    out = tmp_path / "text_in_focus.mp4"
    text_lines = [
        "THE WORLD ECONOMY",
        "Productivity grew by 2.3% annually.",
        "James Harrington — July 2026",
        "MIT Monk Productions",
        "Reference: Federal Reserve Data Series",
        "Key claim: output per hour correlates with AI adoption.",
    ]
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (245, 242, 235))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        subfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52)
    except OSError:
        font = ImageFont.load_default()
        subfont = font
    y = 120
    for i, line in enumerate(text_lines):
        f = font if i == 0 else subfont
        draw.text((140, y), line, fill=(30, 30, 30), font=f)
        y += 140
    frame_bytes = img.tobytes()

    def frame_gen():
        return frame_bytes

    _write_video(out, frame_gen)
    return BrollFixture(out, _WIDTH, _HEIGHT, _DURATION_SEC, has_text=True, has_face=False, is_frozen=True)


def make_face_in_focus_clip(tmp_path: Path) -> BrollFixture:
    """ 5.0s synthetic face via Pillow drawing — produces a region with
    face-like features (two circles for eyes, ellipse for head, etc.)
    sufficient to trigger a face-detection pipeline if one is added. """
    out = tmp_path / "face_in_focus.mp4"
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (200, 170, 140))
    draw = ImageDraw.Draw(img)
    cx, cy = _WIDTH // 2, _HEIGHT // 2
    # head — large ellipse
    draw.ellipse((cx - 220, cy - 280, cx + 220, cy + 280), fill=(225, 190, 155))
    # eyes — dark circles
    draw.ellipse((cx - 100, cy - 90, cx - 30, cy - 20), fill=(250, 250, 250))
    draw.ellipse((cx + 30, cy - 90, cx + 100, cy - 20), fill=(250, 250, 250))
    draw.ellipse((cx - 85, cy - 75, cx - 45, cy - 35), fill=(40, 40, 40))
    draw.ellipse((cx + 45, cy - 75, cx + 85, cy - 35), fill=(40, 40, 40))
    # nose
    draw.line([(cx, cy - 30), (cx - 25, cy + 60), (cx + 25, cy + 60)], fill=(190, 155, 125), width=8)
    # mouth — curved
    draw.arc((cx - 80, cy + 70, cx + 80, cy + 140), start=0, end=180, fill=(150, 60, 60), width=10)
    frame_bytes = img.tobytes()

    def frame_gen():
        return frame_bytes

    _write_video(out, frame_gen)
    return BrollFixture(out, _WIDTH, _HEIGHT, _DURATION_SEC, has_text=False, has_face=True, is_frozen=True)


_ALL_BUILDERS = {
    "frozen": make_frozen_clip,
    "moving": make_moving_clip,
    "text": make_text_in_focus_clip,
    "face": make_face_in_focus_clip,
}


def build_all_fixtures(tmp_path: Path) -> dict[str, BrollFixture]:
    """Build all four fixtures and return them in a dict keyed by name. """
    return {name: builder(tmp_path) for name, builder in _ALL_BUILDERS.items()}
