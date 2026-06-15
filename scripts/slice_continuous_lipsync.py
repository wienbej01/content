#!/usr/bin/env python3
"""slice_continuous_lipsync.py — cut hero-lipsync audio slices from the continuous master.

In continuous_voiceover mode there is ONE master (continuous.mp3) + a
beat_timing_map (beat_id -> [start,end]). Hero lipsync beats need an audio slice
to feed Seedance; that slice must equal the beat's span in the master so the
generated mouth matches the master audio when the (muted) clip is placed there.

This is the continuous-mode equivalent of compile_media_prompts.slice_hero_beats,
which assumes per-segment narration files.

Populates each hero_lipsync beat's media_plan entry with audio_slice + provenance
(sha256 of the slice + parent master), matching the schema assemble.py/qa_media.py
expect.

Usage:
  python3 scripts/slice_continuous_lipsync.py <project_dir>
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from artifact_fingerprint import write_fingerprint

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS_PATH = ROOT / "docs" / "channel_universe" / "constraints.json"


def _load_lipsync_limits():
    """Load min/max clip durations from constraints.json lipsync_render_rules."""
    if CONSTRAINTS_PATH.exists():
        rules = json.loads(CONSTRAINTS_PATH.read_text()).get("lipsync_render_rules", {})
        return (rules.get("min_clip_duration_sec", 4),
                rules.get("max_clip_duration_sec", 15))
    return 4, 15


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def slice_hero_from_master(project_dir):
    project_dir = Path(project_dir).resolve()
    nar = project_dir / "narration"
    master = nar / "continuous.mp3"
    slices_dir = nar / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)

    plan_path = project_dir / "media_plan.json"
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else None
    bt = json.loads((nar / "beat_timing_map.json").read_text())
    bt_by_id = {b["beat_id"]: b for b in bt["beats"]}
    parent_sha = _sha(master)

    target_beats = []
    if plan:
        target_beats = [b for b in plan["beats"] if b.get("lipsync_required")]
    if not target_beats:
        print("  no lipsync beats in media plan")
        return plan

    LIPSYNC_MIN, LIPSYNC_MAX = _load_lipsync_limits()

    for b in target_beats:
        bid = b["beat_id"]
        t = bt_by_id.get(bid)
        if not t:
            # Production storyboard split children have timing directly in the beat
            if b.get("audio_start_sec") is not None and b.get("audio_end_sec") is not None:
                t = {"start": b["audio_start_sec"], "end": b["audio_end_sec"]}
            else:
                print(f"  WARN: {bid} not in beat_timing_map and no audio_start/end; skipped")
                continue
        start = max(0.0, t["start"] - 0.15)         # small lead-in
        speech_len = round(t["end"] - t["start"], 3)
        padded = max(math.ceil(speech_len + 0.2), LIPSYNC_MIN)

        # Hard reject: over-max spans must be split, never silently truncated.
        if padded > LIPSYNC_MAX:
            raise ValueError(
                f"Beat {bid}: speech span {speech_len:.3f}s exceeds Seedance max "
                f"{LIPSYNC_MAX:.1f}s. Beat must be split in storyboard or routed to b-roll.")

        # Track padding provenance for sub-minimum beats.
        padded_from = None
        padded_to = None
        if speech_len + 0.2 < LIPSYNC_MIN:
            padded_from = round(speech_len + 0.2, 3)
            padded_to = LIPSYNC_MIN

        slice_path = slices_dir / f"{bid}.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", str(master), "-ss", f"{start}",
                        "-t", f"{padded}", "-c", "copy", str(slice_path)],
                       capture_output=True)
        if not slice_path.exists():
            print(f"  WARN: failed to slice {bid}")
            continue
        slice_sha = _sha(slice_path)
        b["audio_slice"] = {
            "file": str(slice_path.relative_to(project_dir)),
            "path": str(slice_path.relative_to(project_dir)),
            "sha256": slice_sha,
            "slice_sha256": slice_sha,
            "start_sec": round(start, 3),
            "end_sec": round(start + padded, 3),
            "speech_len_sec": speech_len,
            "padded_len_sec": padded,
            "master_sha256": parent_sha,
            "master_start_sec": round(start, 3),
            "master_end_sec": round(start + padded, 3),
            "parent_mp3_sha256": parent_sha,
            "parent_mp3": "narration/continuous.mp3",
        }
        if padded_from is not None:
            b["audio_slice"]["padded_from_sec"] = padded_from
            b["audio_slice"]["padded_to_sec"] = padded_to

        write_fingerprint(
            slice_path,
            producer="slice_continuous_lipsync",
            producer_version="1.2",
            upstream_hashes=[parent_sha],
            project_id=project_dir.name,
        )
        print(f"  sliced {bid}: {speech_len}s speech, {padded}s clip")

    plan_path.write_text(json.dumps(plan, indent=2))
    return plan


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    args = ap.parse_args(argv)
    slice_hero_from_master(args.project_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
