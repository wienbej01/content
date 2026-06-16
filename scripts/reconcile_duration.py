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
# Per-policy coverage tolerance. A "deficit" is how much shorter a generated clip
# is than its planned slot window. The right tolerance depends on whether the
# downstream assembler can ABSORB the shortfall:
#   - keep_lipsync: the clip carries baked mouth-synced audio; any visual deficit
#     desyncs audio, so it must match tightly (LIPSYNC_TOLERANCE).
#   - loopable b-roll (strip audio / continuous VO): the assembler holds the last
#     frame (up to assemble.MAX_FREEZE) or loops the clip, so a sub-MAX_FREEZE
#     deficit is covered imperceptibly and final QA (max_freeze 1.5s) still passes.
# Generative models (kling3_0) return non-deterministic durations (~4.0/5.0/6.0s),
# so exact b-roll coverage is unattainable by planning; the assembler is the
# designed absorber. See the systemic solution report for the durable fix.
LIPSYNC_TOLERANCE = 0.25
# Keep in sync with assemble.MAX_FREEZE (the held-last-frame cap). Loopable b-roll
# deficits up to this are covered in edit and stay well under qa_final's 1.5s freeze.
BROLL_TOLERANCE = 0.5
TOLERANCE = LIPSYNC_TOLERANCE  # back-compat default for any non-policy-aware caller


def _tolerance_for(clip):
    """Coverage tolerance for a clip based on whether the assembler can absorb a
    shortfall. Lipsync must match tightly; loopable b-roll is freeze/loop-covered."""
    is_lipsync = bool(clip.get("lipsync_required")) or clip.get("audio_policy") == "keep_lipsync"
    return LIPSYNC_TOLERANCE if is_lipsync else BROLL_TOLERANCE


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
    """Reconcile using clip_db — keyed by clip_id, no silent drops.

    Iterates ALL clips in the DB for this project (not the stale timing map).
    Each clip carries its own required interval. A count guard ensures every
    DB clip is evaluated — any silent drop is a hard failure.
    """
    import clip_db

    all_db_clips = clip_db.list_clips(project_id)
    rows = []
    failures = []
    total_deficit = 0.0
    evaluated_clip_ids = set()

    for clip in all_db_clips:
        clip_id = clip["clip_id"]
        beat_id = clip.get("production_beat_id") or clip.get("source_beat_id")
        required = clip["required_dur_sec"]
        asset_type = clip.get("asset_type", "generated_video")

        evaluated_clip_ids.add(clip_id)

        # local_graphic: exact duration, no clip file needed
        if asset_type == "local_graphic":
            rows.append((clip_id, required, required, 0.0, "OK", "local_graphic", clip.get("output_path", "")))
            continue

        actual = clip.get("actual_dur_sec")
        if not actual or clip.get("status") not in ("generated", "valid"):
            rows.append((clip_id, required, 0.0, required, "SLOT_MISSING", asset_type, clip.get("output_path", "")))
            failures.append((clip_id, required))
            total_deficit += required
            continue

        deficit = max(0.0, required - actual)
        tol = _tolerance_for(clip)
        if deficit > tol:
            rows.append((clip_id, required, actual, deficit, "INSUFFICIENT", asset_type, clip.get("output_path", "")))
            failures.append((clip_id, deficit))
            total_deficit += deficit
        else:
            rows.append((clip_id, required, actual, deficit, "OK", asset_type, clip.get("output_path", "")))
            total_deficit += deficit

    # UCI-03 COUNT GUARD: every DB clip must have been evaluated (no silent drops)
    all_db_clip_ids = {c["clip_id"] for c in all_db_clips}
    dropped = all_db_clip_ids - evaluated_clip_ids
    if dropped:
        raise RuntimeError(
            f"RECONCILE GUARD FAILED: {len(dropped)} clip(s) silently dropped from "
            f"reconciliation: {sorted(dropped)}"
        )

    return rows, failures, total_deficit


def _reconcile_via_ffprobe(project_dir, timing, plan):
    """Legacy fallback: reconcile per-clip using ffprobe of plan output_paths.

    Iterates plan beats keyed by clip_id (or beat_id for legacy). Does NOT
    collapse multiple clips sharing a beat_id into one dict entry.
    """
    rows = []
    failures = []
    total_deficit = 0.0

    for b in plan.get("beats", []):
        clip_id = b.get("clip_id") or b.get("beat_id")
        required = b.get("required_end_sec", 0) - b.get("required_start_sec", 0)
        if required <= 0:
            # Fallback: try timing map
            timing_by_id = {t["beat_id"]: t for t in timing.get("beats", [])}
            t = timing_by_id.get(b["beat_id"])
            if t:
                required = t["end"] - t["start"]
            else:
                required = 0.0

        asset_type = b.get("asset_type", "")
        output_path = b.get("output_path", "")

        if asset_type == "local_graphic":
            rows.append((clip_id, required, required, 0.0, "OK", asset_type, output_path))
            continue

        full_path = ROOT / output_path if output_path else None
        if not full_path or not full_path.exists():
            rows.append((clip_id, required, 0.0, required, "FILE_MISSING", asset_type, output_path))
            failures.append((clip_id, required))
            total_deficit += required
            continue

        actual = probe_duration(full_path)
        if actual is None:
            rows.append((clip_id, required, 0.0, required, "PROBE_FAIL", asset_type, output_path))
            failures.append((clip_id, required))
            total_deficit += required
            continue

        deficit = max(0.0, required - actual)
        # ffprobe fallback reads plan beats; derive policy from the beat fields.
        tol = _tolerance_for(b)
        status = "OK" if deficit <= tol else "INSUFFICIENT"
        rows.append((clip_id, required, actual, deficit, status, asset_type, output_path))
        if deficit > tol:
            failures.append((clip_id, deficit))
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

    # Fail only on per-clip coverage failures. The previous `total_deficit > TOLERANCE`
    # check summed INDEPENDENT per-clip shortfalls (two unrelated 0.28s b-roll gaps at
    # different points = 0.56s "total") and hard-failed — but each gap is absorbed
    # separately by the assembler at its own position, so the sum is not a real defect.
    if failures:
        print(f"\nFAILED — {len(failures)} beat(s) with insufficient coverage:")
        for beat_id, deficit in failures:
            print(f"  {beat_id}: deficit {deficit:.3f}s")
        print(f"\n  (lipsync tolerance {LIPSYNC_TOLERANCE}s; loopable b-roll tolerance "
              f"{BROLL_TOLERANCE}s — assembler freeze/loop absorbs the rest)")
        sys.exit(1)

    print("  ✓ All beats have sufficient visual coverage")
    sys.exit(0)


if __name__ == "__main__":
    main()
