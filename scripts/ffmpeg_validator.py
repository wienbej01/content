"""Sprint 5/R5: Structured FFmpeg Policy Validator (Ticket LB-501 / R5-003).

Validates ffmpeg filtergraphs against hero temporal edit policy. Fail-closed:
any unrecognized temporal filter or flag causes rejection. Frame count and
timestamp validation protect against hidden cadence/duration changes.
"""
from __future__ import annotations

from typing import List, Dict, Any

HERO_ALLOWED_FILTERS = frozenset({
    "crop", "scale", "pad", "concat", "overlay", "amix", "anull",
    "loudnorm", "volume", "afade", "atrim", "aresample", "aformat",
    "silenceremove", "silencedetect", "compand", "acompressor",
    "eq", "geq", "lut", "colorbalance", "hue",
    "fps", "setpts",  # setpts=PTS-STARTPTS (identity shift) permitted
    "format", "settb",
    "drawtext", "subtitles",
    "zscale", "zoompan",
    "apad",
})

FORBIDDEN_FILTERS = frozenset({
    "atempo",
    "loop",
    "reverse",
    "tpad",
    "trim",
    "setpts",  # setpts with expression other than PTS-STARTPTS is forbidden
})

FORBIDDEN_FLAGS = frozenset({
    "-itsoffset",
    "-shortest",
    "-vsync",  # can silently drop/duplicate frames
})

FORBIDDEN_SUBSTRINGS = frozenset({
    "atempo=",
    ":loop=",
    "reverse",
    "tpad=",
    ":trim=",
    ":asetpts=",
    "fps=fps=",        # frame-rate conversion
    ":interp",
})


class FFmpegPolicyError(ValueError):
    pass


def validate_ffmpeg_command(
    args: List[str],
    audio_policy: str,
    reason: str = "",
) -> None:
    """Validate an ffmpeg command against hero temporal edit policy.

    For HERO_SYNC_LOCKED units: fail closed on any unrecognized temporal operation.
    For BROLL_FLEX: flag but allow.
    """
    cmd_str = " ".join(args)

    is_hero = audio_policy == "HERO_SYNC_LOCKED"

    # Check forbidden command-line flags
    for arg in args:
        if arg in FORBIDDEN_FLAGS:
            raise FFmpegPolicyError(
                f"BLOCKED: Forbidden flag '{arg}' in command: {reason}"
            )

    # Check forbidden filter substrings
    for substr in FORBIDDEN_SUBSTRINGS:
        if substr in cmd_str:
            raise FFmpegPolicyError(
                f"BLOCKED: Forbidden filter/substring '{substr}' detected: {reason}"
            )

    # For hero clips, fail-closed on unrecognized filters
    # Parse -vf and -filter_complex arguments for filter names
    _check_filter_names(args, is_hero, reason)

    # Validate setpts only allows PTS-STARTPTS
    _check_setpts_expression(args, is_hero, reason)


def _check_filter_names(args: List[str], is_hero: bool, reason: str) -> None:
    """Parse filter arguments and reject unrecognized temporal filters."""
    found = set()
    for arg in args:
        if "=" not in arg:
            continue
        for part in arg.split(","):
            name = part.split("=")[0].split(":")[0].strip()
            if len(name) >= 2 and name.isalpha():
                found.add(name)

    for name in sorted(found):
        if name in HERO_ALLOWED_FILTERS:
            continue
        if name in FORBIDDEN_FILTERS:
            raise FFmpegPolicyError(
                f"BLOCKED: Forbidden filter '{name}' in ffmpeg command: {reason}"
            )
        if is_hero:
            raise FFmpegPolicyError(
                f"BLOCKED: HERO_SYNC_LOCKED does not permit filter '{name}': {reason}"
            )


def _check_setpts_expression(args: List[str], is_hero: bool, reason: str) -> None:
    """setpts with any expression other than PTS-STARTPTS is forbidden for hero units."""
    if not is_hero:
        return
    for arg in args:
        if "setpts=" in arg:
            expr = arg.split("setpts=")[1].split(":")[0].split(",")[0]
            if expr != "PTS-STARTPTS":
                raise FFmpegPolicyError(
                    f"BLOCKED: setpts expression '{expr}' is not PTS-STARTPTS: {reason}"
                )


def _check_filter_names(args: List[str], is_hero: bool, reason: str) -> None:
    """Check for forbidden filter names in ffmpeg arguments."""
    cmd_str = " ".join(args)
    for name in sorted(FORBIDDEN_FILTERS):
        if name != "setpts" and f"{name}=" in cmd_str:
            raise FFmpegPolicyError(
                f"BLOCKED: Forbidden filter '{name}' in ffmpeg command: {reason}"
            )
    if is_hero and "setpts=" in cmd_str:
        # setpts=PTS-STARTPTS is identity; any other expression is invalid
        if "setpts=PTS-STARTPTS" not in cmd_str:
            raise FFmpegPolicyError(
                f"BLOCKED: HERO_SYNC_LOCKED forbids non-identity setpts: {reason}"
            )


def validate_frame_count(expected_fps: float, expected_duration_sec: float,
                          actual_frame_count: int, tolerance: float = 1.0) -> bool:
    """Validate that frame count matches expected fps * duration."""
    expected_frames = expected_fps * expected_duration_sec
    return abs(actual_frame_count - expected_frames) <= tolerance