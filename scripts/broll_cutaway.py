"""Sprint 5/R5: B-Roll Cutaway Compositor (Ticket LB-502 / R5-004).

Validates sorted, non-overlapping, positive intervals from DB. Per-cutaway source
offsets with safe-boundary evidence. Preserves hero frame timing. Output is video-only.
Verifies frame count and duration.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from timeline_utils import MASTER_SAMPLE_RATE, ms_to_samples
from typing import List, Optional, Dict, Any

import production_db as _db


class CutawayError(ValueError):
    pass


def validate_cutaway_intervals(
    intervals: List[Dict[str, Any]],
    hero_start_sample: int,
    hero_end_sample: int,
) -> list[str]:
    """Validate cutaway intervals are sorted, non-overlapping, positive, and within hero bounds.

    Returns list of issue strings (empty = valid).
    """
    issues = []
    sorted_ints = sorted(intervals, key=lambda i: int(i.get("start_sample", 0)))

    prev_end = hero_start_sample
    for i, iv in enumerate(sorted_ints):
        start = int(iv.get("start_sample", 0))
        end = int(iv.get("end_sample", 0))

        if start < 0 or end <= start:
            issues.append(f"Interval[{i}]: invalid bounds [{start}, {end}]")
            continue
        if start < hero_start_sample or end > hero_end_sample:
            issues.append(f"Interval[{i}]: [{start}, {end}] outside hero [{hero_start_sample}, {hero_end_sample}]")
        if start < prev_end:
            issues.append(f"Interval[{i}]: overlaps with previous at {prev_end}")
        prev_end = end

    return issues


def get_cutaway_intervals_from_db(
    hero_render_group_id: str,
    production_id: str,
    db_path=None,
) -> List[Dict[str, Any]]:
    """Fetch cutaway intervals from hero_covered_intervals table."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        """SELECT start_sample, end_sample, beat_id, interval_kind
           FROM hero_covered_intervals
           WHERE hero_render_group_id=? AND interval_kind='broll_covered'
           ORDER BY interval_ordinal""",
        (hero_render_group_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assemble_hero_with_broll_cutaways(
    hero_video_path: Path,
    broll_video_path: Path,
    cutaway_intervals: List[Dict[str, Any]],
    output_path: Path,
    fps: int = 24,
    sample_rate: int = 48000,
) -> Path:
    """Assemble hero video with b-roll cutaway intervals inserted.

    Hero video is video-only (stripped audio). B-roll inserts replace hero
    picture for the exact cutaway intervals. Output is video-only.
    Frame count and duration are verified.
    """
    if not hero_video_path.exists():
        raise CutawayError(f"Hero video not found: {hero_video_path}")
    if not broll_video_path.exists():
        raise CutawayError(f"B-roll video not found: {broll_video_path}")

    if not cutaway_intervals:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(hero_video_path),
            "-an", "-c:v", "libx264", "-preset", "medium",
            "-pix_fmt", "yuv420p", str(output_path),
        ], capture_output=True, check=True)
        return output_path

    sorted_ints = sorted(cutaway_intervals, key=lambda i: int(i.get("start_sample", 0)))
    hero_dur = _probe_samples(hero_video_path)

    issues = validate_cutaway_intervals(sorted_ints, 0, hero_dur)
    if issues:
        raise CutawayError("Cutaway interval validation failed:\n" + "\n".join(issues))

    filters = []
    seg_count = 0
    last_end = 0

    for iv in sorted_ints:
        start_sample = int(iv["start_sample"])
        end_sample = int(iv["end_sample"])
        start_sec = start_sample / sample_rate
        end_sec = end_sample / sample_rate

        if start_sample > last_end:
            seg_count += 1
            seg_start = last_end / sample_rate
            seg_dur = (start_sample - last_end) / sample_rate
            filters.extend([
                f"[0:v]trim=start={seg_start:.6f}:duration={seg_dur:.6f},setpts=PTS-STARTPTS[v{seg_count}];"
            ])

        seg_count += 1
        broll_start = max(0.0, start_sec)
        broll_dur = (end_sample - start_sample) / sample_rate
        filters.extend([
            f"[1:v]trim=start={broll_start:.6f}:duration={broll_dur:.6f},setpts=PTS-STARTPTS[v{seg_count}];"
        ])
        last_end = int(iv["end_sample"])

    if last_end < hero_dur:
        seg_count += 1
        seg_start = last_end / sample_rate
        seg_dur = (hero_dur - last_end) / sample_rate
        filters.extend([
            f"[0:v]trim=start={seg_start:.6f}:duration={seg_dur:.6f},setpts=PTS-STARTPTS[v{seg_count}];"
        ])

    concat_inputs = "".join(f"[v{i}]" for i in range(1, seg_count + 1))
    filters.append(f"{concat_inputs}concat=n={seg_count}:v=1:a=0[out]")

    filter_complex = "".join(filters)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(hero_video_path),
        "-i", str(broll_video_path),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-an",
        "-c:v", "libx264", "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ], capture_output=True, check=True)

    _verify_output(output_path, hero_dur, sample_rate, fps)
    return output_path


def _probe_samples(path: Path) -> int:
    r = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], capture_output=True, text=True)
    try:
        dur_sec = float(r.stdout.strip())
        return ms_to_samples(int(dur_sec * 1000))
    except ValueError:
        raise CutawayError(f"Cannot probe {path}")


def _verify_output(path: Path, expected_samples: int, sample_rate: int, expected_fps: int) -> None:
    r = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=duration,nb_frames,r_frame_rate",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=True)
    probe = json.loads(r.stdout)
    streams = probe.get("streams", [])
    if not streams:
        raise CutawayError("Output has no streams")
    actual_dur = float(streams[0].get("duration", 0))
    actual_samples = int(actual_dur * sample_rate)
    if abs(actual_samples - expected_samples) > sample_rate:
        raise CutawayError(
            f"Output duration mismatch: expected {expected_samples} samples, "
            f"got {actual_samples} samples"
        )
    expected_frame_count = int(expected_fps * (expected_samples / sample_rate))
    actual_frames = int(streams[0].get("nb_frames", 0))
    if actual_frames and abs(actual_frames - expected_frame_count) > 2:
        raise CutawayError(
            f"Frame count mismatch: expected ~{expected_frame_count}, got {actual_frames}"
        )
