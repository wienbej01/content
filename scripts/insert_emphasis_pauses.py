#!/usr/bin/env python3
"""insert_emphasis_pauses.py — insert emphasis silences into the continuous master.

For each key_point beat (storyboard, pause_before_sec > 0), insert a silence of
that length into the continuous master at the beat's start time, then rebuild the
beat timing map against the new master.

This is part of the key-point emphasis system: the pause lands the payoff line.
Operates on ONE master file (no re-generation, no timbre change).

Usage:
  python3 scripts/insert_emphasis_pauses.py <project_dir>
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def insert_pauses(project_dir):
    project_dir = Path(project_dir)
    nar = project_dir / "narration"
    master = nar / "continuous.mp3"
    sb = json.load(open(project_dir / "storyboard.json"))
    bt = json.load(open(nar / "beat_timing_map.json"))
    bt_by_id = {b["beat_id"]: b for b in bt["beats"]}

    # Collect (insert_at_sec, pause_len) for key points with a pause, sorted by time desc
    # (insert from the end backwards so earlier offsets stay valid).
    inserts = []
    for b in sb["beats"]:
        pause = b.get("pause_before_sec", 0) or 0
        if b.get("key_point") and pause > 0 and b["beat_id"] in bt_by_id:
            start = bt_by_id[b["beat_id"]]["start"]
            inserts.append((start, pause, b["beat_id"]))
    if not inserts:
        print("  no emphasis pauses to insert")
        return
    inserts.sort(key=lambda x: x[0], reverse=True)

    # Build an ffmpeg filter that splices silence at each insert point.
    # Easiest robust approach: split master into segments at the insert points and
    # interleave silence. Do it iteratively with a working file.
    work = nar / "_work.mp3"
    subprocess.run(["cp", str(master), str(work)])

    for start, pause, bid in inserts:
        total = _dur(work)
        head = nar / "_head.wav"
        tail = nar / "_tail.wav"
        sil = nar / "_sil.wav"
        # head: 0..start ; tail: start..end ; silence: pause
        subprocess.run(["ffmpeg", "-y", "-i", str(work), "-filter_complex",
                        f"[0:a]atrim=0:{start},asetpts=N/SR/TB[h]", "-map", "[h]",
                        "-ar", "44100", str(head)], capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(work), "-filter_complex",
                        f"[0:a]atrim=start={start},asetpts=N/SR/TB[t]", "-map", "[t]",
                        "-ar", "44100", str(tail)], capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"anullsrc=r=44100:cl=mono:d={pause}", "-ar", "44100", str(sil)],
                       capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(head), "-i", str(sil), "-i", str(tail),
                        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
                        "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(work)],
                       capture_output=True)
        for f in (head, tail, sil):
            f.unlink(missing_ok=True)
        print(f"  inserted {pause}s pause before {bid} at {start:.1f}s")

    subprocess.run(["cp", str(work), str(master)])
    work.unlink(missing_ok=True)

    # Rebuild beat timing map against the new master
    sys.path.insert(0, str(ROOT / "scripts"))
    from audio_timing import build_storyboard_timing_map
    beats = sorted([b for b in sb["beats"] if b.get("narration_text")],
                   key=lambda b: b.get("order", 0))
    new_bt = build_storyboard_timing_map(str(master), beats)
    (nar / "beat_timing_map.json").write_text(json.dumps(new_bt, indent=2))
    print(f"  master now {new_bt['total_duration']}s; timing map rebuilt")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    args = ap.parse_args(argv)
    insert_pauses(args.project_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
