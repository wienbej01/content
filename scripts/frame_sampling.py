"""S15-T004: Deterministic frame sampling utility for semantic-role QA evidence.

This module extracts representative frames from rendered video units to support
post-render semantic-role QA (S15_T003). Frame sampling is evidence INPUT, not
semantic validation by itself — it does NOT create semantic_role_qa pass/fail
evidence. The sampled frames and metadata are consumed by later semantic analysis.

Key invariants:
- Deterministic: same video + config → same frames at same timestamps
- Local only: no paid provider calls, no external AI vision services
- Fail-closed: missing/corrupt/invalid inputs raise clear errors
- Evidence binding: frames are tied to render_unit_id and source artifact_uri
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List

import production_db as _db


class FrameSamplingError(Exception):
    """Frame sampling failed — video missing, corrupt, or invalid config."""
    pass


def _probe_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe.

    Raises FrameSamplingError if video is missing or corrupt.
    """
    if not video_path.exists():
        raise FrameSamplingError(f"BLOCKED_FRAME_SAMPLING_VIDEO_MISSING: video file not found: {video_path}")

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
    ], capture_output=True, text=True, timeout=30)

    if probe.returncode != 0:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT: ffprobe failed on {video_path}: "
            f"{probe.stderr.strip()}"
        )

    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_VIDEO_CORRUPT: could not parse duration from {video_path}"
        )

    if duration <= 0:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_VIDEO_INVALID: video duration is {duration}s (must be positive)"
        )

    return duration


def _extract_frame_at_time(
    video_path: Path,
    output_path: Path,
    timestamp_sec: float,
) -> bool:
    """Extract a single frame at timestamp_sec using ffmpeg.

    Returns True if frame was extracted successfully and is non-empty.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run([
        "ffmpeg", "-y", "-ss", f"{timestamp_sec:.3f}",
        "-i", str(video_path), "-vframes", "1",
        "-q:v", "2", str(output_path),
    ], capture_output=True, timeout=30)

    if result.returncode != 0:
        return False

    return output_path.exists() and output_path.stat().st_size > 100  # Minimum ~100 bytes for a valid JPEG


def _calculate_timestamps(
    strategy: str,
    duration_sec: float,
    count: int,
) -> List[float]:
    """Calculate frame extraction timestamps based on strategy.

    Strategies:
    - "start_middle_end": Extract at 25%, 50%, 75% of duration (count=3 fixed)
    - "evenly_spaced": Extract (count) frames evenly distributed, avoiding exact edges

    Returns list of timestamps in seconds.
    """
    if duration_sec <= 0:
        raise FrameSamplingError(f"BLOCKED_FRAME_SAMPLING_INVALID: duration {duration_sec}s is invalid")

    if strategy == "start_middle_end":
        if count != 3:
            raise FrameSamplingError(
                f"BLOCKED_FRAME_SAMPLING_INVALID: start_middle_end strategy requires count=3, got {count}"
            )
        # Avoid exact edges (0%, 100%) in case of fade-in/fade-out
        return [duration_sec * 0.25, duration_sec * 0.5, duration_sec * 0.75]

    elif strategy == "evenly_spaced":
        if count < 1 or count > 20:
            raise FrameSamplingError(
                f"BLOCKED_FRAME_SAMPLING_INVALID: count must be 1-20, got {count}"
            )
        # Distribute evenly, avoiding exact edges (first/last 5%)
        if count == 1:
            return [duration_sec * 0.5]
        margin = duration_sec * 0.05
        usable = duration_sec - 2 * margin
        step = usable / (count - 1) if count > 1 else 0
        return [margin + i * step for i in range(count)]

    else:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_INVALID: unknown strategy '{strategy}'. "
            f"Supported: start_middle_end, evenly_spaced"
        )


def sample_frames_from_video(
    video_path: Path,
    output_dir: Path,
    strategy: str = "start_middle_end",
    count: int = 3,
) -> List[Path]:
    """Extract representative frames from a video file.

    Args:
        video_path: Path to source video file.
        output_dir: Directory to write sampled frames (will be created if needed).
        strategy: "start_middle_end" (fixed 3 frames at 25%/50%/75%) or
                   "evenly_spaced" (configurable count, distributed evenly).
        count: Number of frames to extract (required for evenly_spaced).

    Returns:
        List of Path objects for successfully extracted frame images.

    Raises:
        FrameSamplingError: If video is missing, corrupt, or config is invalid.
    """
    duration = _probe_video_duration(video_path)
    timestamps = _calculate_timestamps(strategy, duration, count)

    frames = []
    for i, ts in enumerate(timestamps):
        output_path = output_dir / f"frame_{i:03d}_{ts:06.3f}s.jpg"
        if _extract_frame_at_time(video_path, output_path, ts):
            frames.append(output_path)

    if not frames:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_FAILED: extracted 0 frames from {video_path}"
        )

    return frames


def sample_frames_for_render_unit(
    production_id: str,
    render_unit_id: str,
    output_base_dir: Path,
    strategy: str = "start_middle_end",
    count: int = 3,
    db_path=None,
) -> Dict[str, Any]:
    """Sample frames from a render_unit's video artifact and record metadata.

    This is the primary entry point for S15_T004 frame sampling. It:
    1. Looks up the render_unit and its active artifact from the DB.
    2. Extracts frames using the specified strategy.
    3. Returns metadata including frame paths, timestamps, and source info.

    NOTE: This does NOT create semantic_role_qa validation evidence. Frame sampling
    is evidence INPUT for later semantic analysis — not a pass/fail verdict itself.

    Args:
        production_id: Production ID.
        render_unit_id: Render unit ID.
        output_base_dir: Base directory for frame output (frames will be placed in
                         output_base_dir/production_id/render_unit_id/).
        strategy: "start_middle_end" or "evenly_spaced".
        count: Number of frames (for evenly_spaced).
        db_path: Production database path.

    Returns:
        Dict with:
        - render_unit_id: str
        - artifact_uri: str (source video)
        - visual_role: Optional[str] (from render_unit, if set)
        - strategy: str
        - count: int
        - frames: List[dict] with path, timestamp_sec, frame_index
        - duration_sec: float (video duration)
        - sampled_at: str (ISO timestamp)

    Raises:
        FrameSamplingError: If unit not found, artifact missing, or sampling fails.
    """
    conn = _db.connect(db_path)

    # Look up render_unit and its active artifact
    unit = conn.execute(
        """SELECT ru.id, ru.active_artifact_id, ru.visual_role, ru.status, a.uri as artifact_uri
           FROM render_units ru
           LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
           WHERE ru.production_id=? AND ru.id=?""",
        (production_id, render_unit_id),
    ).fetchone()

    if unit is None:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_UNIT_NOT_FOUND: render_unit {render_unit_id} "
            f"not found in production {production_id}"
        )

    if unit["artifact_uri"] is None:
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_NO_ARTIFACT: render_unit {render_unit_id} has no artifact_uri"
        )

    video_path = Path(unit["artifact_uri"])
    if not video_path.is_absolute():
        # Resolve relative to production artifact store if needed
        # For now, require absolute paths
        raise FrameSamplingError(
            f"BLOCKED_FRAME_SAMPLING_INVALID_PATH: artifact_uri is not absolute: {unit['artifact_uri']}"
        )

    # Create output directory
    unit_output_dir = output_base_dir / production_id / render_unit_id
    unit_output_dir.mkdir(parents=True, exist_ok=True)

    # Sample frames
    frame_paths = sample_frames_from_video(video_path, unit_output_dir, strategy, count)

    # Build metadata
    metadata = {
        "render_unit_id": render_unit_id,
        "production_id": production_id,
        "artifact_uri": unit["artifact_uri"],
        "visual_role": unit["visual_role"],
        "strategy": strategy,
        "count": len(frame_paths),
        "duration_sec": _probe_video_duration(video_path),  # Re-probe for metadata
        "sampled_at": _db._now(),
        "frames": [
            {
                "frame_index": i,
                "path": str(fp),
                "timestamp_sec": _parse_timestamp_from_path(fp),
            }
            for i, fp in enumerate(frame_paths)
        ],
    }

    return metadata


def _parse_timestamp_from_path(frame_path: Path) -> float:
    """Parse timestamp from frame filename generated by this module.

    Expected format: frame_XXX_YYY.YYYs.jpg where YYY.YYY is timestamp.
    """
    stem = frame_path.stem  # e.g., "frame_000_2.500s"
    if "s" in stem:
        try:
            return float(stem.split("_")[-1].rstrip("s"))
        except (ValueError, IndexError):
            pass
    return 0.0
