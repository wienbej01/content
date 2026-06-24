#!/usr/bin/env python3
"""Compensated hero remux helper (S08-T002).

Takes a provider-generated hero video, source slice audio, and measured
offset_ms. Produces a compensated MP4 where the source audio is delayed
by the offset to match the video timing.

Usage:
  python3 scripts/evals/remux_compensated_hero.py \
      --video <provider_video.mp4> \
      --source-audio <source_slice.wav> \
      --offset-ms -575 \
      --out /tmp/compensated.mp4 \
      --provider-job-id <id>  # optional: stores path in DB
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def remux(video_path: Path, audio_path: Path, offset_ms: int, output_path: Path) -> dict:
    """Generate compensated remux with ffmpeg.

    The source audio is delayed by |offset_ms| using the adelay filter.
    Sign convention: negative offset (diagnostic LEADS source) means source
    audio needs to be delayed (adelay) to align with the video.
    """
    if not video_path.exists():
        return {"error": f"Video not found: {video_path}"}
    if not audio_path.exists():
        return {"error": f"Audio not found: {audio_path}"}

    # adelay is always positive — it adds silence at the start
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
        return {"error": "ffmpeg timed out"}
    except FileNotFoundError:
        return {"error": "ffmpeg not found"}

    if not output_path.exists():
        return {"error": "Output file not created"}

    # Probe output
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


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compensated hero remux")
    ap.add_argument("--video", type=Path, required=True, help="Provider video MP4")
    ap.add_argument("--source-audio", type=Path, required=True, help="Source slice WAV")
    ap.add_argument("--offset-ms", type=int, default=-575, help="Measured offset in ms")
    ap.add_argument("--out", type=Path, required=True, help="Output MP4 path")
    ap.add_argument("--provider-job-id", default=None, help="Store path in provider_jobs DB")
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = remux(args.video, args.source_audio, args.offset_ms, args.out)

    # Store in DB if provider_job_id given
    if args.provider_job_id and "error" not in result:
        db_path = args.db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE provider_jobs SET compensated_artifact_path=? WHERE id=?",
            (str(args.out), args.provider_job_id),
        )
        conn.commit()
        conn.close()
        result["db_updated"] = True

    if args.out.parent:
        args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    # Also write as .json next to the output
    json_path = args.out.parent / f"{args.out.stem}.json" if args.out.suffix else args.out.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2))

    if "error" in result:
        print(f"  [✗] {result['error']}")
        return 1
    else:
        print(f"  [✓] Compensated remux: {result['output_path']}")
        print(f"       Size: {result['size_bytes']} bytes, Duration: {result['duration_sec']}s")
        print(f"       Offset applied: {result['offset_ms_applied']}ms")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
