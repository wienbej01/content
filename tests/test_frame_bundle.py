"""TKT-201: Frame bundle builder tests.

Tests verify:
1. Deterministic frame extraction (same video -> same frame paths).
2. Clear failure on missing video.
3. Frames are written to stable sha-named directory.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import frame_bundle as fb
from frame_sampling import FrameSamplingError


@pytest.fixture
def fake_video_path(tmp_path):
    video_path = tmp_path / "test_video.mp4"
    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=3:r=30",
        "-pix_fmt", "yuv420p",
        str(video_path),
    ], capture_output=True, timeout=30)
    if result.returncode != 0 or not video_path.exists():
        pytest.skip(f"Could not create test video: {result.stderr.decode()}")
    return video_path


class TestBuildFrameBundle:

    def test_extracts_frames_from_valid_video(self, fake_video_path, tmp_path):
        assets_dir = tmp_path / "frame_bundles"
        frames = fb.build_frame_bundle(fake_video_path, n=3, assets_dir=assets_dir)
        assert len(frames) >= 1
        for f in frames:
            assert f.exists()
            assert f.suffix == ".jpg"
            assert f.stat().st_size > 100

    def test_deterministic_across_two_runs(self, fake_video_path, tmp_path):
        assets_dir = tmp_path / "frame_bundles"
        frames1 = fb.build_frame_bundle(fake_video_path, n=3, assets_dir=assets_dir)
        frames2 = fb.build_frame_bundle(fake_video_path, n=3, assets_dir=assets_dir)
        assert len(frames1) == len(frames2)
        for f1, f2 in zip(frames1, frames2):
            assert str(f1) == str(f2)

    def test_missing_video_raises(self, tmp_path):
        missing = tmp_path / "nonexistent.mp4"
        with pytest.raises(FrameSamplingError, match="VIDEO_MISSING"):
            fb.build_frame_bundle(missing, n=3, assets_dir=tmp_path / "bundles")

    def test_uses_stable_sha_named_directory(self, fake_video_path, tmp_path):
        assets_dir = tmp_path / "frame_bundles"
        frames = fb.build_frame_bundle(fake_video_path, n=3, assets_dir=assets_dir)
        # directory name should be a 16-char hex string
        for f in frames:
            parent_name = f.parent.name
            assert len(parent_name) == 16
            assert all(c in "0123456789abcdef" for c in parent_name)
            assert f.parent.parent == assets_dir

    def test_different_videos_get_different_dirs(self, fake_video_path, tmp_path):
        assets_dir = tmp_path / "frame_bundles"

        video2_path = tmp_path / "test_video2.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=320x240:d=2:r=30",
            "-pix_fmt", "yuv420p",
            str(video2_path),
        ], capture_output=True, timeout=30)

        frames1 = fb.build_frame_bundle(fake_video_path, n=3, assets_dir=assets_dir)
        frames2 = fb.build_frame_bundle(video2_path, n=3, assets_dir=assets_dir)
        dirs = {f.parent.name for f in frames1 + frames2}
        assert len(dirs) == 2

    def test_accepts_strategy_evenly_spaced(self, fake_video_path, tmp_path):
        assets_dir = tmp_path / "frame_bundles"
        frames = fb.build_frame_bundle(
            fake_video_path, n=5, assets_dir=assets_dir, strategy="evenly_spaced")
        assert len(frames) >= 1
        for f in frames:
            assert f.exists()
