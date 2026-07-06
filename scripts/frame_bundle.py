"""Frame bundle builder for vision QA.

Deterministic frame extraction from a video artifact, using the existing
frame_sampling module. Frames are written to a production assets directory
with stable per-video naming so repeated calls produce identical paths.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import List, Optional

from frame_sampling import (
    FrameSamplingError,
    sample_frames_from_video,
)

DEFAULT_N_FRAMES = 3
DEFAULT_STRATEGY = "start_middle_end"


def _video_sha(video_path: Path) -> str:
    """Compute a fast content-derived SHA for the video file.

    Reads only the first 64 KiB for speed, which is sufficient for collision
    resistance in the production context where videos are uniquely generated.
    """
    sha = hashlib.sha256()
    with open(video_path, "rb") as f:
        sha.update(f.read(65536))
    return sha.hexdigest()[:16]


def build_frame_bundle(
    artifact_path: Path,
    n: int = DEFAULT_N_FRAMES,
    assets_dir: Optional[Path] = None,
    strategy: str = DEFAULT_STRATEGY,
) -> List[Path]:
    """Extract deterministic frames and return their paths.

    Frames are written to a stable location derived from the video's content
    hash, so repeated calls with the same video produce identical frame paths.

    Args:
        artifact_path: Path to the video file.
        n: Number of frames to extract (3 for start_middle_end, 1-20 for evenly_spaced).
        assets_dir: Root directory for sampled frames. Defaults to
                    outputs/frame_bundles/ relative to the repo root.
        strategy: Sampling strategy ("start_middle_end" or "evenly_spaced").

    Returns:
        List of Path objects for extracted frame images.

    Raises:
        FrameSamplingError: If video is missing, corrupt, or sampling fails.
    """
    if not artifact_path.exists():
        raise FrameSamplingError(
            f"BLOCKED_FRAME_BUNDLE_VIDEO_MISSING: {artifact_path}")

    if assets_dir is None:
        assets_dir = Path(__file__).resolve().parent.parent / "outputs" / "frame_bundles"

    video_sha = _video_sha(artifact_path)
    bundle_dir = assets_dir / video_sha
    existing = sorted(bundle_dir.glob("frame_*.jpg"))
    if len(existing) >= n:
        return existing[:n]

    tmp_dir = bundle_dir.with_name(bundle_dir.name + ".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    frames = sample_frames_from_video(artifact_path, tmp_dir, strategy=strategy, count=n)

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    try:
        tmp_dir.replace(bundle_dir)
    except OSError:
        shutil.move(str(tmp_dir), str(bundle_dir))

    result = sorted(bundle_dir.glob("frame_*.jpg"))
    return result[:n]
