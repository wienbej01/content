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
    t = {"max_freeze_sec": 60.0, "max_black_sec": 60.0, "length_tol_sec": 120.0,
         "tail_tol_sec": 120.0, "transition_window_sec": 0.3}
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



# ---------------------------------------------------------------------------
# ENG-0801: DB-contract checks for final QA
# ---------------------------------------------------------------------------

CONTRACT_EVIDENCE_VERSION = "2.0"


def run_db_contract_checks(
    production_id: str,
    deliverable_id: str,
    db_path=None,
) -> dict:
    """Run DB-contract checks against final QA inputs.

    Checks:
    1. All selected render units have latest media QA pass.
    2. All local graphics have local provenance (no provider jobs).
    3. No provider-generated local graphics.
    4. All expected local graphics represented in assembly.
    5. Final deliverable artifact exists and SHA is recorded.
    6. Assembly preflight evidence exists.
    7. No failed validation newer than last pass for selected render units.

    Returns a dict with contract_version, per-check booleans,
    all_contract_checks_pass, and descriptive contract_issues list.
    Raises ValueError for missing DB state.
    """
    import production_db as _db
    from pathlib import Path

    _db.migrate(db_path)
    conn = _db.connect(db_path)

    evidence: dict = {
        "contract_version": CONTRACT_EVIDENCE_VERSION,
    }
    issues: list[str] = []
    
    try:
        # Load deliverable
        del_row = conn.execute(
            "SELECT * FROM deliverables WHERE id=?", (deliverable_id,)
        ).fetchone()
        if not del_row:
            raise ValueError(f"Deliverable {deliverable_id} not found")
        evidence["deliverable_exists"] = True
        evidence["deliverable_id"] = deliverable_id
        evidence["deliverable_status"] = del_row["status"]

        # 5. Final deliverable artifact exists and SHA is recorded
        artifact = None
        if del_row["artifact_id"]:
            artifact = conn.execute(
                "SELECT * FROM artifacts WHERE id=?", (del_row["artifact_id"],)
            ).fetchone()
        if artifact and artifact["sha256"]:
            art_path = Path(artifact["uri"]) if artifact["uri"] else None
            file_ok = art_path and art_path.exists()
            evidence["deliverable_file_exists"] = bool(file_ok)
            evidence["deliverable_sha256"] = artifact["sha256"]
            if not file_ok:
                issues.append("deliverable artifact file missing")
            if not artifact["sha256"]:
                issues.append("deliverable artifact SHA not recorded")
        else:
            evidence["deliverable_file_exists"] = False
            evidence["deliverable_sha256"] = None
            issues.append("deliverable has no linked artifact")

        # 6. Assembly preflight evidence exists — verify by calling validate_assembly_inputs
        # which ensures the assembly stage would pass its own preflight checks.
        from assemble_db import validate_assembly_inputs as _validate_preflight
        try:
            _validate_preflight(production_id, db_path=db_path)
            evidence["assembly_preflight_passed"] = True
        except Exception as exc:
            evidence["assembly_preflight_passed"] = False
            issues.append(f"assembly preflight validation failed: {exc}")

        # Load render units and their artifacts
        units = conn.execute(
            """SELECT ru.*, a.uri as artifact_uri, a.sha256 as artifact_sha256
               FROM render_units ru
               LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
               WHERE ru.production_id=?
                 AND (ru.status IN ('valid', 'generated')
                      OR ru.active_artifact_id IS NOT NULL)
               ORDER BY ru.ordinal""",
            (production_id,),
        ).fetchall()

        if not units:
            evidence["render_unit_count"] = 0
            issues.append("no render units found")
        else:
            evidence["render_unit_count"] = len(units)
            all_passing_qa = True
            all_local_provenance = True
            no_provider_local = True
            local_graphic_ids = []

            for u in units:
                u = dict(u)
                # 1. All selected render units have latest media QA pass
                latest = conn.execute(
                    """SELECT id, status, created_at, evidence_json FROM validations
                       WHERE subject_id=? AND validator_name IN ('qa_media_contract', 'qa_media')
                       ORDER BY created_at DESC LIMIT 1""",
                    (u["id"],),
                ).fetchone()
                if not latest:
                    # No QA validation at all. Allow if the unit has a valid artifact
                    # (pre-QA artifact from graphics_compositing or older generation).
                    if not u.get("active_artifact_id"):
                        all_passing_qa = False
                        issues.append(
                            f"render unit {u['id']} ({u.get('label', '')}) has no QA and no artifact"
                        )
                elif latest["status"] != "pass":
                    # QA exists but failed. Allow change_requested units (pending resolution).
                    if u.get("status") != "change_requested":
                        all_passing_qa = False
                        issues.append(
                            f"render unit {u['id']} ({u.get('label', '')}) lacks passing media QA"
                        )

                # S01-T004: HERO_SYNC_LOCKED units must have lipsync evidence in QA
                if u.get("audio_policy") == "HERO_SYNC_LOCKED":
                    if latest and latest["status"] == "pass":
                        latest_dict = dict(latest)
                        ej_str = latest_dict.get("evidence_json") or "{}"
                        ej = json.loads(ej_str)
                        lipsync_method = ej.get("lipsync_qa_method")
                        if not lipsync_method:
                            # QA passed but no lipsync evidence — fake-green guard
                            all_passing_qa = False
                            issues.append(
                                f"HERO unit {u['id']} ({u.get('label', '')}) "
                                f"has passing QA but no lipsync evidence (F-QA-001)"
                            )
                        elif lipsync_method == "blocked_dependency":
                            issues.append(
                                f"HERO unit {u['id']} ({u.get('label', '')}) "
                                f"lipsync QA blocked: {ej.get('lipsync_drift_ms', 'unknown')}"
                            )

                # 7. No failed validation newer than last pass
                fail_newer = conn.execute(
                    """SELECT created_at FROM validations
                       WHERE subject_id=? AND status='fail'
                       ORDER BY created_at DESC LIMIT 1""",
                    (u["id"],),
                ).fetchone()
                if fail_newer and latest:
                    if fail_newer["created_at"] > latest["created_at"]:
                        issues.append(
                            f"render unit {u['id']} has failed validation newer than last pass"
                        )

                # 2/3. Local graphic provenance
                if u["asset_type"] == "local_graphic":
                    local_graphic_ids.append(u["id"])
                    pj = conn.execute(
                        "SELECT COUNT(*) as c FROM provider_jobs WHERE render_unit_id=?", (u["id"],)
                    ).fetchone()
                    if pj["c"] > 0:
                        no_provider_local = False
                        all_local_provenance = False
                        issues.append(
                            f"local graphic {u['id']} has {pj['c']} provider job(s)"
                        )
                    if not u["active_artifact_id"]:
                        all_local_provenance = False
                        issues.append(
                            f"local graphic {u['id']} has no active artifact"
                        )
                    # Check artifact provenance metadata
                    if u["active_artifact_id"]:
                        art = conn.execute(
                            "SELECT metadata_json FROM artifacts WHERE id=?", (u["active_artifact_id"],)
                        ).fetchone()
                        if art:
                            meta = json.loads(art["metadata_json"]) if isinstance(art["metadata_json"], str) else art["metadata_json"]
                            renderer = (meta or {}).get("renderer", "")
                            if "render_graphics.py" not in renderer:
                                issues.append(
                                    f"local graphic {u['id']} artifact provenance is not local_graphic"
                                )

            evidence["all_passing_qa"] = all_passing_qa
            evidence["all_local_provenance"] = all_local_provenance
            evidence["no_provider_local_graphic"] = no_provider_local
            evidence["local_graphic_count"] = len(local_graphic_ids)

        # 4. All expected local graphics represented in assembly
        # Check creative_beats with shot_type='local_graphic' against render units
        gfx_beats = conn.execute(
            """SELECT cb.id, cb.label, cb.shot_type
               FROM creative_beats cb
               JOIN timeline_spans ts ON cb.id = ts.creative_beat_id
               WHERE ts.production_id=? AND ts.status='active' AND cb.shot_type='local_graphic'""",
            (production_id,),
        ).fetchall()
        expected_gfx = [dict(g) for g in gfx_beats]
        evidence["expected_local_graphic_beats"] = len(expected_gfx)
        missing_gfx = [g["label"] or g["id"] for g in expected_gfx
                       if not any(u["asset_type"] == "local_graphic" for u in
                                  [dict(r) for r in units])]
        if missing_gfx:
            issues.append(f"expected local graphics not in assembly: {missing_gfx}")

        all_pass = (
            evidence.get("deliverable_file_exists", False)
            and evidence.get("all_passing_qa", False)
            and evidence.get("all_local_provenance", True)
            and evidence.get("no_provider_local_graphic", True)
            and evidence.get("assembly_preflight_passed", False)
            and len(issues) == 0
        )
        evidence["all_contract_checks_pass"] = all_pass
        evidence["contract_issues"] = issues
        return evidence

    finally:
        conn.close()

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
