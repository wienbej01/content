#!/usr/bin/env python3
"""Compensated hero remux helper (S08-T002).

Takes a provider-generated hero video, source slice audio, and measured
offset_ms. Produces a compensated MP4 where the source audio is delayed
by the offset to match the video timing.

Usage:
  python3 scripts/evals/remux_compensated_hero.py \
      --video <provider_video.mp4> \
      --source-audio <source_slice.wav> \
      --offset-ms 0 \
      --out /tmp/compensated.mp4 \
      --provider-job-id <id>  # optional: stores path in DB
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


from scripts.compensate import compensate as remux


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compensated hero remux")
    ap.add_argument("--video", type=Path, required=True, help="Provider video MP4")
    ap.add_argument("--source-audio", type=Path, required=True, help="Source slice WAV")
    ap.add_argument("--offset-ms", type=int, default=0, help="Measured offset in ms")
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
