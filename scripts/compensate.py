"""Compensated hero remux — delay source audio to match video timing (R-LS-3).

Extracted from scripts/evals/remux_compensated_hero.py for importable reuse.
The CLI wrapper in that file remains functional.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


COMPENSATION_MIN_OFFSET_MS = 40
COMPENSATION_MAX_OFFSET_MS = 400


def compensate(video_path: Path, audio_path: Path, offset_ms: int, output_path: Path) -> dict:
    """Generate compensated remux with ffmpeg.

    The source audio is delayed by ``offset_ms`` using the ``adelay`` filter.
    Video stream is copied (no re-encode) to avoid generational loss.

    Sign convention: a negative offset (diagnostic LEADS source) means the
    source audio needs to be delayed to align with the video.
    """
    if not video_path.exists():
        return {"error": f"Video not found: {video_path}"}
    if not audio_path.exists():
        return {"error": f"Audio not found: {audio_path}"}

    delay_ms = abs(offset_ms)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-af", f"adelay={delay_ms}|{delay_ms}",
        "-shortest",
        str(output_path),
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return {"error": f"ffmpeg failed (exit={r.returncode}): {r.stderr[:300]}"}
    except subprocess.TimeoutExpired:
        return {"error": "fffmpeg timed out"}
    except FileNotFoundError:
        return {"error": "ffmpeg not found"}

    if not output_path.exists():
        return {"error": "Output file not created"}

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
         "-of", "json", str(output_path)],
        capture_output=True, text=True, timeout=15,
    )
    probe_data = json.loads(probe.stdout) if probe.returncode == 0 else {}

    return {
        "output_path": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "duration_sec": round(float(probe_data.get("format", {}).get("duration", 0)), 3),
        "offset_ms_applied": delay_ms if offset_ms < 0 else -delay_ms,
        "method": "ffmpeg_copy_video_adelay_source",
    }
