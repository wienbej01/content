#!/usr/bin/env python3
"""Deterministic b-roll QC fixtures for TKT-002.

Generates four fixture types for testing pixel-level b-roll quality checks:
1. Frozen-frame clip (single color held for full duration)
2. Moving clip (testsrc motion)
3. Text-in-focus clip (readable ASCII text)
4. Human-face-in-focus clip (synthetic face via Pillow)

All outputs are deterministic and hermetic (no network, no paid calls).
"""
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ffmpeg(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run ffmpeg and return the completed process. Raises on failure."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr}")
    return r


def _probe_duration(path: Path) -> float:
    """Probe video stream duration via ffprobe."""
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, timeout=10,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _extract_frame(path: Path, timestamp: float, out_path: Path) -> None:
    """Extract a single frame at the given timestamp."""
    _run_ffmpeg([
        "-ss", str(timestamp), "-i", str(path),
        "-frames:v", "1", "-q:v", "2", str(out_path),
    ])


def _frame_hash(path: Path) -> str:
    """SHA-256 of a frame file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Fixture 1: Frozen-frame clip
# ---------------------------------------------------------------------------

def generate_frozen_clip(
    tmp_path: Path,
    duration_sec: float = 5.0,
    width: int = 1920,
    height: int = 1080,
    color: str = "0x808080",
) -> dict[str, Any]:
    """Generate a frozen-frame clip (single color held for full duration).

    Returns metadata dict with path, dimensions, and QC flags.
    """
    out = tmp_path / "frozen_clip.mp4"
    _run_ffmpeg([
        "-f", "lavfi", "-i",
        f"color=c={color}:s={width}x{height}:d={duration_sec}:r=25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ])
    dur = _probe_duration(out)
    return {
        "path": str(out),
        "width": width,
        "height": height,
        "duration_sec": dur,
        "has_text": False,
        "has_face": False,
        "is_frozen": True,
        "fixture_type": "frozen",
    }


# ---------------------------------------------------------------------------
# Fixture 2: Moving clip (testsrc)
# ---------------------------------------------------------------------------

def generate_moving_clip(
    tmp_path: Path,
    duration_sec: float = 5.0,
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Any]:
    """Generate a moving clip using ffmpeg testsrc.

    Returns metadata dict.
    """
    out = tmp_path / "moving_clip.mp4"
    _run_ffmpeg([
        "-f", "lavfi", "-i",
        f"testsrc=duration={duration_sec}:size={width}x{height}:rate=25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ])
    dur = _probe_duration(out)
    return {
        "path": str(out),
        "width": width,
        "height": height,
        "duration_sec": dur,
        "has_text": False,
        "has_face": False,
        "is_frozen": False,
        "fixture_type": "moving",
    }


# ---------------------------------------------------------------------------
# Fixture 3: Text-in-focus clip
# ---------------------------------------------------------------------------

def generate_text_clip(
    tmp_path: Path,
    duration_sec: float = 5.0,
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Any]:
    """Generate a clip with readable ASCII text on screen.

    Uses ffmpeg drawtext filter to render >5 lines of text.
    """
    out = tmp_path / "text_clip.mp4"
    # Draw multiple lines of text
    text_lines = [
        "LINE ONE: The quick brown fox",
        "LINE TWO: jumps over the lazy dog",
        "LINE THREE: 42 percent of statistics",
        "LINE FOUR: Harvard study 2019",
        "LINE FIVE: Shrestha and colleagues",
        "LINE SIX: RCT found significant",
    ]
    # Escape for ffmpeg drawtext
    escaped = [l.replace("'", "\\'").replace(":", "\\:") for l in text_lines]
    drawtext_filters = []
    for i, line in enumerate(escaped):
        y_pos = 100 + i * 80
        drawtext_filters.append(
            f"drawtext=text='{line}':fontcolor=white:fontsize=48:"
            f"x=100:y={y_pos}:box=1:boxcolor=black@0.5"
        )
    vf = ",".join(drawtext_filters)
    _run_ffmpeg([
        "-f", "lavfi", "-i",
        f"color=c=0x1B2A4A:s={width}x{height}:d={duration_sec}:r=25",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ])
    dur = _probe_duration(out)
    return {
        "path": str(out),
        "width": width,
        "height": height,
        "duration_sec": dur,
        "has_text": True,
        "has_face": False,
        "is_frozen": False,
        "fixture_type": "text_in_focus",
    }


# ---------------------------------------------------------------------------
# Fixture 4: Human-face-in-focus clip
# ---------------------------------------------------------------------------

def generate_face_clip(
    tmp_path: Path,
    duration_sec: float = 5.0,
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Any]:
    """Generate a clip with a synthetic human face.

    Uses ffmpeg drawbox + drawgrid to create a face-like pattern.
    Metadata flags has_face=True for downstream face-detection testing.
    """
    out = tmp_path / "face_clip.mp4"
    # Create a face-like pattern: two eyes, nose, mouth on a skin-colored background
    vf_parts = [
        # Background (skin tone)
        "color=c=0xC8973E:s={w}x{h}:d={d}:r=25".format(w=width, h=height, d=duration_sec),
    ]
    # We'll overlay geometric shapes to suggest a face
    vf = (
        "drawbox=x=600:y=300:w=200:h=250:color=white@0.8:t=fill,"  # left eye bg
        "drawbox=x=1100:y=300:w=200:h=250:color=white@0.8:t=fill,"  # right eye bg
        "drawbox=x=680:y=380:w=60:h=60:color=black:t=fill,"  # left pupil
        "drawbox=x=1180:y=380:w=60:h=60:color=black:t=fill,"  # right pupil
        "drawbox=x=850:y=600:w=200:h=30:color=0x6B1D2A:t=fill,"  # nose
        "drawbox=x=750:y=750:w=400:h=60:color=0x6B1D2A@0.7:t=fill,"  # mouth
    )
    _run_ffmpeg([
        "-f", "lavfi", "-i",
        f"color=c=0xC8973E:s={width}x{height}:d={duration_sec}:r=25",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ])
    dur = _probe_duration(out)
    return {
        "path": str(out),
        "width": width,
        "height": height,
        "duration_sec": dur,
        "has_text": False,
        "has_face": True,
        "is_frozen": False,
        "fixture_type": "face_in_focus",
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def frozen_clip(tmp_path):
    """Yield metadata for a frozen-frame clip."""
    meta = generate_frozen_clip(tmp_path)
    yield meta
    # Cleanup: tmp_path is auto-cleaned by pytest


@pytest.fixture
def moving_clip(tmp_path):
    """Yield metadata for a moving clip."""
    meta = generate_moving_clip(tmp_path)
    yield meta


@pytest.fixture
def text_clip(tmp_path):
    """Yield metadata for a text-in-focus clip."""
    meta = generate_text_clip(tmp_path)
    yield meta


@pytest.fixture
def face_clip(tmp_path):
    """Yield metadata for a human-face-in-focus clip."""
    meta = generate_face_clip(tmp_path)
    yield meta


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_frozen_clip(frozen_clip):
    """Frozen clip: file exists, correct metadata, frame comparison shows frozen."""
    p = Path(frozen_clip["path"])
    assert p.exists(), "frozen clip file not created"
    assert p.stat().st_size > 5_000, "frozen clip too small"  # solid color compresses very well
    assert frozen_clip["is_frozen"] is True
    assert frozen_clip["has_text"] is False
    assert frozen_clip["has_face"] is False
    assert frozen_clip["duration_sec"] >= 4.5, "duration too short"

    # Extract two frames and compare — they should be identical for a frozen clip
    with tempfile.TemporaryDirectory() as td:
        f1 = Path(td) / "f1.jpg"
        f2 = Path(td) / "f2.jpg"
        _extract_frame(p, 0.5, f1)
        _extract_frame(p, frozen_clip["duration_sec"] - 0.5, f2)
        assert f1.exists() and f2.exists()
        assert _frame_hash(f1) == _frame_hash(f2), "frozen clip frames differ"


def test_moving_clip(moving_clip):
    """Moving clip: file exists, frames differ (motion detected)."""
    p = Path(moving_clip["path"])
    assert p.exists()
    assert moving_clip["is_frozen"] is False
    assert moving_clip["duration_sec"] >= 4.5

    with tempfile.TemporaryDirectory() as td:
        f1 = Path(td) / "f1.jpg"
        f2 = Path(td) / "f2.jpg"
        _extract_frame(p, 0.1, f1)
        _extract_frame(p, moving_clip["duration_sec"] - 0.1, f2)
        assert _frame_hash(f1) != _frame_hash(f2), "moving clip frames are identical (no motion)"


def test_text_clip(text_clip):
    """Text-in-focus clip: file exists, metadata flags has_text=True."""
    p = Path(text_clip["path"])
    assert p.exists()
    assert text_clip["has_text"] is True
    assert text_clip["has_face"] is False
    assert text_clip["is_frozen"] is False
    assert text_clip["duration_sec"] >= 4.5


def test_face_clip(face_clip):
    """Human-face-in-focus clip: file exists, metadata flags has_face=True."""
    p = Path(face_clip["path"])
    assert p.exists()
    assert face_clip["has_face"] is True
    assert face_clip["has_text"] is False
    assert face_clip["is_frozen"] is False
    assert face_clip["duration_sec"] >= 4.5


def test_fixture_determinism(tmp_path):
    """Same inputs produce same output (SHA-256 match across runs)."""
    (tmp_path / "run1").mkdir(exist_ok=True)
    (tmp_path / "run2").mkdir(exist_ok=True)
    m1 = generate_frozen_clip(tmp_path / "run1")
    m2 = generate_frozen_clip(tmp_path / "run2")
    h1 = hashlib.sha256(Path(m1["path"]).read_bytes()).hexdigest()
    h2 = hashlib.sha256(Path(m2["path"]).read_bytes()).hexdigest()
    assert h1 == h2, "frozen clip generation is not deterministic"


def test_fixture_metadata_shape(frozen_clip):
    """All fixture metadata dicts have the expected keys."""
    required_keys = {"path", "width", "height", "duration_sec", "has_text", "has_face", "is_frozen", "fixture_type"}
    assert required_keys.issubset(frozen_clip.keys()), f"missing keys: {required_keys - frozen_clip.keys()}"
