"""S7-T02: Enforce hero temporal policy via structured FFmpeg validator.

Named tests required by the program:
  test_hero_temporal_filter_rejected
  test_unknown_temporal_operation_rejected
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ffmpeg_validator import (
    validate_ffmpeg_command, FFmpegPolicyError,
    FORBIDDEN_FILTERS, FORBIDDEN_FLAGS,
)


def test_hero_temporal_filter_rejected():
    """All forbidden temporal filters are rejected for hero clips."""
    forbidden_ops = [
        (["ffmpeg", "-vf", "atempo=1.5", "input.mp4"], "atempo speed change"),
        (["ffmpeg", "-vf", "setpts=0.5*PTS", "input.mp4"], "setpts speed change"),
        (["ffmpeg", "-vf", "loop=loop=10:1:0", "input.mp4"], "loop"),
        (["ffmpeg", "-vf", "reverse", "input.mp4"], "reverse"),
        (["ffmpeg", "-vf", "tpad=stop_mode=clone:stop_duration=2", "input.mp4"], "freeze extension"),
        (["ffmpeg", "-vf", "minterpolate=fps=60", "input.mp4"], "frame interpolation"),
        (["ffmpeg", "-vf", "trim=start=1:end=2", "input.mp4"], "trim through speech"),
    ]
    for cmd, desc in forbidden_ops:
        with pytest.raises(FFmpegPolicyError, match="BLOCKED"):
            validate_ffmpeg_command(cmd, audio_policy="HERO_SYNC_LOCKED", reason=desc)


def test_hero_identity_setpts_allowed():
    """setpts=PTS-STARTPTS (identity timestamp shift) is permitted for hero."""
    validate_ffmpeg_command(
        ["ffmpeg", "-vf", "setpts=PTS-STARTPTS", "input.mp4"],
        audio_policy="HERO_SYNC_LOCKED", reason="identity setpts",
    )


def test_hero_allowed_filter_passes():
    """Permitted spatial filters (scale, crop, pad) pass for hero."""
    validate_ffmpeg_command(
        ["ffmpeg", "-vf", "scale=1920:1080", "input.mp4"],
        audio_policy="HERO_SYNC_LOCKED", reason="scale",
    )
    validate_ffmpeg_command(
        ["ffmpeg", "-vf", "crop=1280:720:0:0", "input.mp4"],
        audio_policy="HERO_SYNC_LOCKED", reason="crop",
    )


def test_unknown_temporal_operation_rejected():
    """Unknown/unrecognized filters are rejected for hero (fail-closed)."""
    with pytest.raises(FFmpegPolicyError, match="does not permit"):
        validate_ffmpeg_command(
            ["ffmpeg", "-vf", "mysteryfilter=42", "input.mp4"],
            audio_policy="HERO_SYNC_LOCKED", reason="unknown filter",
        )


def test_forbidden_flags_rejected():
    """Forbidden command-line flags are rejected for all clips."""
    for flag in ["-itsoffset", "-stream_loop", "-vsync"]:
        with pytest.raises(FFmpegPolicyError, match="Forbidden flag"):
            validate_ffmpeg_command(
                ["ffmpeg", flag, "0", "input.mp4"],
                audio_policy="HERO_SYNC_LOCKED", reason=f"flag {flag}",
            )


def test_broll_allows_more_filters():
    """BROLL_FLEX clips are not subject to the fail-closed hero policy."""
    # atempo is still forbidden for all clips (global ban on speed change)
    with pytest.raises(FFmpegPolicyError):
        validate_ffmpeg_command(
            ["ffmpeg", "-vf", "atempo=1.5", "input.mp4"],
            audio_policy="BROLL_FLEX", reason="broll atempo",
        )
    # But unknown filters are allowed for broll (not fail-closed)
    validate_ffmpeg_command(
        ["ffmpeg", "-vf", "mysteryfilter=42", "input.mp4"],
        audio_policy="BROLL_FLEX", reason="broll unknown filter",
    )
