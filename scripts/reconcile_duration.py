#!/usr/bin/env python3
"""reconcile_duration.py — Beat-level duration reconciliation gate.

Compares required visual duration (from timing map) against available clip
duration. Prefers clip_db.coverage_for_beat() which resolves parent→children
lineage (e.g. B005 → B005a + B005b). Falls back to ffprobe-based logic for
legacy projects with no clip_db rows.

Usage:
    python3 scripts/reconcile_duration.py <project_dir>
    python3 scripts/reconcile_duration.py --project-id <id>
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "Videos" / "Projects"
TOLERANCE = 0.25


def probe_duration(path):
    """Get video stream duration from v:0 (not format duration)."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=duration,nb_frames,r_frame_rate",
             "-of", "default=noprint_wrappers=1", str(path)],
            capture_output=True, text=True, timeout=10
        )
    except subprocess.TimeoutExpired:
        return None
    # Try stream duration tag first
    for line in r.stdout.splitlines():
        if line.startswith("duration="):
            try:
                return float(line.split("=", 1)[1])
            except ValueError:
                pass
    # Fallback: nb_frames / fps
    frames = fps = None
    for line in r.stdout.splitlines():
        if line.startswith("nb_frames="):
            try:
                frames = int(line.split("=", 1)[1])
            except ValueError:
                pass
        if line.startswith("r_frame_rate="):
            val = line.split("=", 1)[1]
            if "/" in val:
                n, d = val.split("/")
                try:
                    fps = int(n) / int(d)
                except (ValueError, ZeroDivisionError):
                    pass
    if frames and fps:
        return frames / fps
    return None


def _has_clip_db_rows(project_id):
    """Check whether clip_db has any rows for this project."""
    try:
        import clip_db
        clips = clip_db.list_clips(project_id)
        return len(clips) > 0
    except Exception:
        return False


def _reconcile_via_db(project_dir, timing, plan, project_id):
    """Reconcile using clip_db.coverage_for_beat (resolves parent→children)."""
    import clip_db

    plan_beats = {b["beat_id"]: b for b in plan.get("beats", [])}
    rows = []
    failures = []
    total_deficit = 0.0

    for tb in timing["beats"]:
        beat_id = tb["beat_id"]
        required = tb["end"] - tb["start"]

        # Check if this is a local_graphic in the plan (exact duration, no clip needed)
        pb = plan_beats.get(beat_id)
        if pb and pb.get("asset_type") == "local_graphic":
            rows.append((beat_id, required, required, 0.0, "OK", "local_graphic", pb.get("output_path", "")))
            continue

        cov = clip_db.coverage_for_beat(project_id, beat_id)

        if not cov["slots"]:
            # No clips in DB for this beat — check plan for local_graphic children
            rows.append((beat_id, required, 0.0, required, "MISSING_PLAN", "unknown", ""))
            failures.append((beat_id, required))
            total_deficit += required
            continue

        available = cov["available"]
        deficit = max(0.0, required - available)

        if not cov["all_present"]:
            status = "SLOT_MISSING"
            rows.append((beat_id, required, available, deficit if deficit > 0 else required, status, "generated_video", ""))
            failures.append((beat_id, deficit if deficit > 0 else required))
            total_deficit += deficit if deficit > 0 else required
        elif deficit > TOLERANCE:
            status = "INSUFFICIENT"
            rows.append((beat_id, required, available, deficit, status, "generated_video", ""))
            failures.append((beat_id, deficit))
            total_deficit += deficit
        else:
            rows.append((beat_id, required, available, deficit, "OK", "generated_video", ""))
            total_deficit += deficit

    return rows, failures, total_deficit


def _reconcile_via_ffprobe(project_dir, timing, plan):
    """Legacy fallback: reconcile using direct ffprobe of plan output_paths."""
    plan_beats = {b["beat_id"]: b for b in plan.get("beats", [])}
    rows = []
    failures = []
    total_deficit = 0.0

    for tb in timing["beats"]:
        beat_id = tb["beat_id"]
        required = tb["end"] - tb["start"]
        pb = plan_beats.get(beat_id)

        if not pb:
            rows.append((beat_id, required, 0.0, required, "MISSING_PLAN", "unknown", ""))
            failures.append((beat_id, required))
            total_deficit += required
            continue

        asset_type = pb.get("asset_type", "")
        output_path = pb.get("output_path", "")

        if asset_type == "local_graphic":
            rows.append((beat_id, required, required, 0.0, "OK", asset_type, output_path))
            continue

        full_path = ROOT / output_path if output_path else None
        if not full_path or not full_path.exists():
            rows.append((beat_id, required, 0.0, required, "FILE_MISSING", asset_type, output_path))
            failures.append((beat_id, required))
            total_deficit += required
            continue

        actual = probe_duration(full_path)
        if actual is None:
            rows.append((beat_id, required, 0.0, required, "PROBE_FAIL", asset_type, output_path))
            failures.append((beat_id, required))
            total_deficit += required
            continue

        deficit = max(0.0, required - actual)
        status = "OK" if deficit <= TOLERANCE else "INSUFFICIENT"
        rows.append((beat_id, required, actual, deficit, status, asset_type, output_path))
        if deficit > TOLERANCE:
            failures.append((beat_id, deficit))
        total_deficit += deficit

    return rows, failures, total_deficit


def reconcile(project_dir):
    """Run reconciliation. Returns (rows, failures, total_deficit)."""
    project_dir = Path(project_dir)
    timing_path = project_dir / "narration" / "beat_timing_map.json"
    plan_path = project_dir / "media_plan.json"

    if not timing_path.exists():
        print(f"ERROR: timing map not found: {timing_path}", file=sys.stderr)
        sys.exit(1)
    if not plan_path.exists():
        print(f"ERROR: media plan not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    timing = json.loads(timing_path.read_text())
    plan = json.loads(plan_path.read_text())

    # Derive project_id from plan or dir name
    project_id = plan.get("project_id") or project_dir.name

    # Prefer clip_db if it has rows for this project
    if _has_clip_db_rows(project_id):
        return _reconcile_via_db(project_dir, timing, plan, project_id)

    return _reconcile_via_ffprobe(project_dir, timing, plan)


def write_csv(project_dir, rows):
    """Write duration_reconciliation.csv."""
    out = Path(project_dir) / "duration_reconciliation.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["beat_id", "required_sec", "available_sec", "deficit_sec",
                    "status", "asset_type", "output_path"])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.3f}", f"{r[2]:.3f}", f"{r[3]:.3f}",
                        r[4], r[5], r[6]])
    return out


def main():
    ap = argparse.ArgumentParser(description="Beat-level duration reconciliation gate.")
    ap.add_argument("project_dir", nargs="?", help="Path to project directory")
    ap.add_argument("--project-id", help="Project ID (looks up in Videos/Projects/)")
    args = ap.parse_args()

    if args.project_dir:
        project_dir = Path(args.project_dir)
    elif args.project_id:
        project_dir = PROJECTS / args.project_id
    else:
        ap.error("Provide project_dir or --project-id")

    if not project_dir.is_dir():
        print(f"ERROR: not a directory: {project_dir}", file=sys.stderr)
        sys.exit(1)

    rows, failures, total_deficit = reconcile(project_dir)
    csv_path = write_csv(project_dir, rows)

    # Summary
    print(f"Duration reconciliation: {len(rows)} beats")
    print(f"  CSV: {csv_path}")
    print(f"  Total deficit: {total_deficit:.3f}s")

    if failures or total_deficit > TOLERANCE:
        print(f"\nFAILED — {len(failures)} beat(s) with insufficient coverage:")
        for beat_id, deficit in failures:
            print(f"  {beat_id}: deficit {deficit:.3f}s")
        print(f"\n  Total deficit: {total_deficit:.3f}s (tolerance: {TOLERANCE}s)")
        sys.exit(1)

    print("  ✓ All beats have sufficient visual coverage")
    sys.exit(0)


if __name__ == "__main__":
    main()
