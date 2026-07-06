"""Compensated hero remux — delay source audio to match video timing (R-LS-3).

Extracted from scripts/evals/remux_compensated_hero.py for importable reuse.
The CLI wrapper in that file remains functional.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


COMPENSATION_MIN_OFFSET_MS = 160
COMPENSATION_MAX_OFFSET_MS = 600


def compensate(video_path: Path, audio_path: Path, offset_ms: int, output_path: Path) -> dict:
    """Generate compensated remux with ffmpeg.

    Directional correction based on offset sign:
    - Positive offset (audio LAGS video): advance audio by trimming the
      leading ``offset_ms`` from the audio track, bringing it forward to
      align with the earlier mouth motion.
    - Negative offset (audio LEADS video): delay audio by ``|offset_ms|``
      using the ``adelay`` filter, pushing it back to align with the
      later mouth motion.

    Video stream is copied (no re-encode) to avoid generational loss.
    Sign convention matches the cross-correlation scorer: positive means
    audio lags mouth, negative means audio leads mouth.
    """
    if not video_path.exists():
        return {"error": f"Video not found: {video_path}"}
    if not audio_path.exists():
        return {"error": f"Audio not found: {audio_path}"}

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if offset_ms > 0:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-af", f"atrim=start={offset_ms}ms,asetpts=PTS-STARTPTS",
            "-shortest",
            str(output_path),
        ]
        applied_ms = -offset_ms
    else:
        delay_ms = abs(offset_ms)
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
        applied_ms = delay_ms

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
        "offset_ms_applied": applied_ms,
        "offset_ms_measured": offset_ms,
        "method": "ffmpeg_copy_video_directional",
    }
