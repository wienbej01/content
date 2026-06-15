#!/usr/bin/env python3
"""qa_final.py — Final-cut gate (G9). Validates the ASSEMBLED output mp4, not source clips.

This is the gate that was missing: it inspects the delivered video for the
defects that source-scope QA cannot see — freezes, black frames, and
audio/video length mismatch.

Checks (ALL fatal):
  1. FREEZE: any frozen span > max_freeze_sec (default 1.5s) → fail
  2. BLACK: any black frame span > max_black_sec (default 0.2s) outside the
     first/last transition windows → fail
  3. LENGTH: |audio_duration - video_duration| > length_tol_sec → fail
  4. SILENCE_TAIL: video continues > tail_tol_sec after audio ends → fail (frozen end frame)

Usage:
  python3 scripts/qa_final.py path/to/final_16x9.mp4
  python3 scripts/qa_final.py path/to/final_16x9.mp4 --record-gate --project-id poc_short_focus
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS = ROOT / "docs" / "channel_universe" / "constraints.json"


def _thresholds():
    t = {"max_freeze_sec": 1.5, "max_black_sec": 0.2, "length_tol_sec": 0.25,
         "tail_tol_sec": 0.25, "transition_window_sec": 0.3}
    if CONSTRAINTS.exists():
        c = json.loads(CONSTRAINTS.read_text())
        t.update(c.get("final_cut_thresholds", {}))
    return t


def _video_duration(path):
    """Probe v:0 stream duration (NOT format/container duration)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        pass
    # Fallback: nb_frames / fps
    r2 = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=nb_frames,r_frame_rate", "-of",
                         "default=noprint_wrappers=1:nokey=1", str(path)],
                        capture_output=True, text=True)
    lines = r2.stdout.strip().splitlines()
    if len(lines) >= 2:
        try:
            nb_frames = int(lines[0])
            fps_parts = lines[1].split("/")
            fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
            if fps > 0 and nb_frames > 0:
                return nb_frames / fps
        except (ValueError, ZeroDivisionError):
            pass
    return None


def _container_duration(path):
    """Probe format/container duration."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def _video_frame_count(path):
    """Probe nb_frames for v:0."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_frames", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


def _audio_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                        "-show_entries", "stream=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def check_freezes(path, total_dur, max_freeze):
    """Return list of (start, dur) freeze spans exceeding max_freeze."""
    r = subprocess.run(["ffmpeg", "-i", str(path), "-vf",
                        "freezedetect=n=0.003:d=1.0", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", r.stderr)]
    durs = [float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", r.stderr)]
    spans = []
    for i, s in enumerate(starts):
        d = durs[i] if i < len(durs) else (total_dur - s if total_dur else 0)
        if d > max_freeze:
            spans.append((round(s, 2), round(d, 2)))
    return spans


def check_blacks(path, total_dur, max_black, transition_window):
    """Return list of (start, end) black spans that are NOT in the lead-in/lead-out
    transition windows and exceed max_black."""
    r = subprocess.run(["ffmpeg", "-i", str(path), "-vf",
                        "blackdetect=d=0.05:pix_th=0.10", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    spans = []
    for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)", r.stderr):
        start, end = float(m.group(1)), float(m.group(2))
        dur = end - start
        # Allow black at the very start (fade-in) and very end (fade-out)
        in_lead_in = start <= transition_window
        in_lead_out = total_dur and (total_dur - end) <= transition_window
        if dur > max_black and not in_lead_in and not in_lead_out:
            spans.append((round(start, 2), round(end, 2)))
    return spans


def run_final_qa(video_path, exempt_spans=None):
    """Run all final-cut checks. Returns (report dict, pass bool).

    exempt_spans: optional list of (start, end) seconds that are INTENTIONAL static
    graphic cards (title/framework/kinetic) — freeze detection is skipped inside them
    (a held title card is not a broken-video freeze). Frozen b-roll/hero tails are
    still flagged."""
    t = _thresholds()
    p = Path(video_path)
    exempt_spans = exempt_spans or []
    issues = []
    if not p.exists():
        return {"video": str(p), "status": "fail",
                "issues": ["MISSING: final cut file does not exist"]}, False

    vdur = _video_duration(p)
    adur = _audio_duration(p)
    cdur = _container_duration(p)
    frames = _video_frame_count(p)

    def _in_exempt(t0, t1):
        for (s, e) in exempt_spans:
            overlap = max(0, min(t1, e) - max(t0, s))
            if overlap >= 0.6 * (t1 - t0):
                return True
        return False

    # 0. Frame count sanity
    if frames is None or frames == 0:
        issues.append("NO_FRAMES: video stream has 0 or missing frame count")

    # 1. Freezes (skip those inside intentional graphic-card spans)
    freezes = check_freezes(p, vdur, t["max_freeze_sec"]) if vdur else []
    for s, d in freezes:
        if _in_exempt(s, s + d):
            continue
        issues.append(f"FREEZE: {d}s frozen span at {s}s (> {t['max_freeze_sec']}s limit)")

    # 2. Black frames
    blacks = check_blacks(p, vdur, t["max_black_sec"], t["transition_window_sec"]) if vdur else []
    for s, e in blacks:
        issues.append(f"BLACK: black frames {s}s-{e}s (outside transition windows)")

    # 3. Container vs video stream duration
    if cdur is not None and vdur is not None:
        if cdur - vdur > t["length_tol_sec"]:
            issues.append(f"CONTAINER_MISMATCH: container {cdur:.1f}s vs video stream {vdur:.1f}s "
                          f"(delta {cdur - vdur:.1f}s > {t['length_tol_sec']}s tolerance)")

    # 4. Length mismatch (video vs audio)
    if vdur is not None and adur is not None:
        mismatch = abs(vdur - adur)
        if mismatch > t["length_tol_sec"]:
            issues.append(f"LENGTH_MISMATCH: video {vdur:.1f}s vs audio {adur:.1f}s "
                          f"(delta {mismatch:.1f}s > {t['length_tol_sec']}s tolerance)")
        # 5. Terminal freeze: audio outlasts video (dominant failure mode)
        if adur - vdur > t["length_tol_sec"]:
            issues.append(f"TERMINAL_FREEZE: video EOF at {vdur:.1f}s but audio continues to "
                          f"{adur:.1f}s (audio outlasts video by {adur - vdur:.1f}s)")
        # Frozen tail (video continues after audio ends)
        if vdur - adur > t["tail_tol_sec"]:
            issues.append(f"FROZEN_TAIL: video runs {vdur - adur:.1f}s past audio end "
                          f"(likely frozen end frame)")

    report = {
        "video": str(p),
        "video_duration": round(vdur, 2) if vdur else None,
        "audio_duration": round(adur, 2) if adur else None,
        "container_duration": round(cdur, 2) if cdur else None,
        "frame_count": frames,
        "freeze_spans": freezes,
        "black_spans": blacks,
        "thresholds": t,
        "issues": issues,
        "status": "fail" if issues else "pass",
    }
    return report, not issues


def main(argv=None):
    ap = argparse.ArgumentParser(description="Final-cut gate (G9) — validates assembled output.")
    ap.add_argument("video", help="Path to the assembled final mp4")
    ap.add_argument("--record-gate", action="store_true")
    ap.add_argument("--project-id")
    ap.add_argument("--output", help="Write JSON report to this path")
    ap.add_argument("--storyboard", help="Storyboard JSON — exempt graphic-card spans from freeze")
    ap.add_argument("--beat-timing", help="beat_timing_map.json (with --storyboard)")
    args = ap.parse_args(argv)

    # Derive exempt (graphic-card) spans from storyboard + beat timing.
    exempt = []
    if args.storyboard and args.beat_timing:
        sb = json.loads(Path(args.storyboard).read_text())
        bt = {b["beat_id"]: b for b in json.loads(Path(args.beat_timing).read_text())["beats"]}
        GRAPHIC = {"graphic_progressive", "graphic_title_card", "kinetic_text", "ui_insert"}
        for b in sb.get("beats", []):
            if b.get("shot_type") in GRAPHIC and b["beat_id"] in bt:
                t = bt[b["beat_id"]]
                exempt.append((t["start"], t["end"]))

    report, ok = run_final_qa(args.video, exempt_spans=exempt)

    for issue in report["issues"]:
        print(f"  ✗ {issue}")
    if ok:
        print(f"  ✓ final cut PASS — no freeze, no stray black, audio==video "
              f"({report['video_duration']}s)")

    # Write report: explicit --output or default beside the video
    output_path = args.output or str(Path(args.video).parent / "final_qa_report.json")
    Path(output_path).write_text(json.dumps(report, indent=2))

    if args.record_gate and args.project_id:
        sys.path.insert(0, str(ROOT / "scripts"))
        from gates import record_gate
        record_gate(args.project_id, "final_cut", "pass" if ok else "fail",
                    artifact_path=args.video,
                    extra={"issues": report["issues"]})
        print(f"  gate final_cut={'pass' if ok else 'fail'} recorded for {args.project_id}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
