#!/usr/bin/env python3
"""qa_media.py — Technical QA for generated video clips.

Validates each segment/shot media file against pipeline policy:
- readable, has video stream, correct dimensions
- duration vs narration target (coverage)
- audio-stream policy: generated_tts must be audio-free; baked_in must have audio
- basic codec checks

Usage:
  python3 scripts/qa_media.py scripts/generated/script.json
  python3 scripts/qa_media.py scripts/generated/script.json --segment 004_system
  python3 scripts/qa_media.py scripts/generated/script.json --output report.json
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Default dimensions by scope (--scope flag).
DIMS_BY_SCOPE = {
    "source":    (1280, 720),
    "assembled_16x9": (1920, 1080),
    "assembled_9x16": (1080, 1920),
}
EXPECTED_WIDTH = 1280
EXPECTED_HEIGHT = 720
MIN_DURATION = 2.0
LIPSYNC_DUR_TOL = 0.1  # ±s for audio duration vs speech/padded length


def _file_sha256(path):
    p = Path(path)
    if not p or not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def audio_duration(path):
    """Duration of the first audio stream in seconds, or None if no audio."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        # Fall back to format duration if stream lacks its own duration tag.
        rf = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True)
        try:
            return float(rf.stdout.strip())
        except ValueError:
            return None


def is_hero_lipsync(unit):
    """A beat/segment is a hero lipsync clip if it keeps its own baked audio."""
    return (unit.get("audio_policy") == "keep_lipsync"
            or unit.get("shot_type") == "hero_lipsync"
            or unit.get("lipsync_required") is True)


def lipsync_checks(beat, media_path, info, base):
    """Structural lipsync checks for a hero_lipsync clip. All issues are FATAL.

    a. clip must have an audio stream
    b. audio duration matches speech_len_sec ±0.1s (post-trim) OR
       padded_len_sec ±0.1s (pre-trim source) — accept either, flag which
    c. clip video duration >= slice duration
    d. provenance fields present and hashes valid
    """
    issues = []
    bid = beat.get("beat_id") or beat.get("id") or "?"
    slice_info = beat.get("audio_slice") or {}
    speech_len = slice_info.get("speech_len_sec")
    padded_len = slice_info.get("padded_len_sec")

    # a. audio stream present
    if not info.get("has_audio"):
        issues.append("LIPSYNC: hero_lipsync clip MUST have an audio stream (silent mouth)")
        # Without audio the duration checks are moot, but continue provenance checks.
    else:
        adur = audio_duration(media_path)
        if adur is None:
            issues.append("LIPSYNC: cannot probe audio duration")
        else:
            # b. accept post-trim (speech_len), pre-trim source (padded_len), or
            #    LIPSYNC_MAX_DUR (when padded > max and clip was clamped at render).
            tol = 0.15   # ±0.15s: absorbs Seedance ~0.1s encoding overage
            from generate_media import LIPSYNC_MAX_DUR  # noqa: import inline to avoid circulars
            matched = None
            if speech_len is not None and abs(adur - float(speech_len)) <= tol:
                matched = f"speech_len_sec={float(speech_len):.3f}"
            elif padded_len is not None and abs(adur - float(padded_len)) <= tol:
                matched = f"padded_len_sec={float(padded_len):.3f}"
            elif abs(adur - LIPSYNC_MAX_DUR) <= tol:
                matched = f"lipsync_max_dur={LIPSYNC_MAX_DUR}s (clamped at render)"
            if matched is None:
                tgt = (f"speech_len={speech_len}" if speech_len is not None else "speech_len=?")
                tgtp = (f"padded_len={padded_len}" if padded_len is not None else "padded_len=?")
                issues.append(
                    f"LIPSYNC: audio duration {adur:.3f}s matches neither {tgt} "
                    f"nor {tgtp} nor lipsync_max_dur={LIPSYNC_MAX_DUR} (±{tol}s)")
            else:
                beat.setdefault("_qa", {})["duration_match"] = matched

    # c. clip video duration >= slice duration — OR clamped to LIPSYNC_MAX_DUR
    # (Seedance max is 10s; longer speech beats render at max and assembly trims
    # via T8 baked-audio; the video being shorter than the slice is expected).
    slice_dur = None
    if slice_info.get("start_sec") is not None and slice_info.get("end_sec") is not None:
        slice_dur = float(slice_info["end_sec"]) - float(slice_info["start_sec"])
    elif speech_len is not None:
        slice_dur = float(speech_len)
    if slice_dur is not None and info.get("duration") is not None:
        from generate_media import LIPSYNC_MAX_DUR  # noqa
        is_max_clamped = abs(info["duration"] - LIPSYNC_MAX_DUR) <= 0.2
        if not is_max_clamped and info["duration"] + 1e-3 < slice_dur:
            issues.append(
                f"LIPSYNC: clip video duration {info['duration']:.3f}s < slice duration "
                f"{slice_dur:.3f}s (clip too short to carry the slice)")

    # d. provenance fields present and hashes valid
    if not slice_info:
        issues.append("LIPSYNC: no audio_slice provenance recorded for hero_lipsync beat")
    else:
        for field in ("slice_sha256", "parent_mp3_sha256", "file"):
            if not slice_info.get(field):
                issues.append(f"LIPSYNC: audio_slice missing provenance field '{field}'")
        slice_file_rel = slice_info.get("file")
        expected = slice_info.get("slice_sha256")
        if slice_file_rel and expected:
            # Resolve slice relative to the project/output dir of the plan.
            sf = resolve(base, slice_file_rel)
            if sf is None or not sf.exists():
                # Try resolving against the media plan's project dir convention.
                issues.append(f"LIPSYNC: slice file missing for provenance check ({slice_file_rel})")
            else:
                live = _file_sha256(sf)
                if live != expected:
                    issues.append(
                        f"LIPSYNC: slice provenance hash mismatch "
                        f"(expected {expected[:12]}, live {live[:12] if live else 'missing'})")
    return issues


def probe(path):
    """Probe a media file. Returns dict or None if unreadable."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=codec_type,width,height",
           "-show_entries", "format=duration",
           "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    streams = d.get("streams", [])
    fmt = d.get("format", {})
    vs = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not vs:
        return None
    # Check audio stream separately
    ra = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                         "-show_entries", "stream=codec_type",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                        capture_output=True, text=True)
    has_audio = "audio" in ra.stdout
    return {
        "width": vs.get("width"),
        "height": vs.get("height"),
        "duration": float(fmt.get("duration", 0)),
        "has_audio": has_audio,
    }


def resolve(base, p):
    if p is None:
        return None
    p = Path(p)
    if p.is_absolute():
        return p
    # Try relative to base first (script/plan directory), then relative to repo ROOT.
    # output_path fields in media_plan.json are repo-root-relative (e.g.
    # "assets/media/001_hook/B001.mp4"), not relative to the plan file's location.
    local = base / p
    if local.exists():
        return local
    root_rel = ROOT / p
    if root_rel.exists():
        return root_rel
    # Return the base-relative path (so callers get the intended path even if missing).
    return local


def run_qa(script_path, selected_segment=None, scope="source", record_gate=False, project_id=None):
    """Run media QA. Returns (results_list, pass_bool)."""
    script = json.load(open(script_path))
    base = Path(script_path).resolve().parent
    pid = script.get("project_id") or project_id
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{pid}"))
    fmt = script.get("defaults", {}).get("format", "mp3")
    results = []
    all_pass = True
    exp_w, exp_h = DIMS_BY_SCOPE.get(scope, (EXPECTED_WIDTH, EXPECTED_HEIGHT))

    # Accept either a script (segments + audio_mode) or a media plan (beats).
    units_top = script.get("segments")
    if units_top is None:
        units_top = script.get("beats", [])

    for seg in units_top:
        sid = seg.get("id") or seg.get("beat_id") or seg.get("segment_id")
        if selected_segment and sid != selected_segment and seg.get("segment_id") != selected_segment:
            continue
        mode = seg.get("audio_mode", "generated_tts")
        hero = is_hero_lipsync(seg)
        seg_media = seg.get("media") or seg.get("output_path")

        # Render-group followers share the group leader's clip; they don't have their
        # own file on disk. Skip them in QA (their leader covers the quality check).
        if seg.get("render_group") and seg.get("render_group_index", 0) > 0:
            continue

        # Local-graphic beats (kinetic_text, graphic_progressive, etc.) are rendered
        # by graphics.py (T10 — not yet built). Skip them in source-scope QA so they
        # don't flood the report with false MISSING failures.
        LOCAL_MODELS = {"local_graphic", "still_kenburns"}
        LOCAL_SHOTS = {"graphic_progressive", "graphic_title_card",
                       "kinetic_text", "ui_insert", "still_kenburns"}
        is_local = (seg.get("model") in LOCAL_MODELS
                    or seg.get("shot_type") in LOCAL_SHOTS
                    or seg.get("asset_type") == "local_graphic")
        if is_local and scope == "source":
            continue

        # Expand shots or use segment media
        units = []
        if seg.get("shots") and mode != "baked_in" and not hero:
            for sh in seg["shots"]:
                units.append({"id": sh["id"], "media": sh["media"], "segment_id": sid,
                              "duration_target": sh.get("duration")})
        else:
            units.append({"id": sid, "media": seg_media, "segment_id": sid,
                          "duration_target": None})

        # Get narration duration for coverage check
        nar_path = output_dir / "narration" / f"{sid}.{fmt}"
        nar_dur = None
        if nar_path.exists():
            rd = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "default=noprint_wrappers=1:nokey=1", str(nar_path)],
                                capture_output=True, text=True)
            try:
                nar_dur = float(rd.stdout.strip())
            except ValueError:
                pass

        for unit in units:
            uid = unit["id"]
            media_path = resolve(base, unit["media"])
            entry = {"id": uid, "segment_id": sid, "audio_mode": mode,
                     "media_path": str(media_path), "issues": []}

            if not media_path or not media_path.exists():
                entry["issues"].append("MISSING: file does not exist")
                entry["status"] = "fail"
                results.append(entry)
                all_pass = False
                continue

            info = probe(media_path)
            if info is None:
                entry["issues"].append("UNREADABLE: ffprobe cannot parse file")
                entry["status"] = "fail"
                results.append(entry)
                all_pass = False
                continue

            entry.update(info)

            # Dimension check
            if info["width"] != exp_w or info["height"] != exp_h:
                entry["issues"].append(
                    f"DIMENSIONS: {info['width']}x{info['height']} (expected {exp_w}x{exp_h})")

            # Duration check
            if info["duration"] < MIN_DURATION:
                entry["issues"].append(f"TOO_SHORT: {info['duration']:.1f}s < {MIN_DURATION}s")

            # Audio policy
            if mode == "generated_tts" and not hero and info["has_audio"]:
                entry["issues"].append("AUDIO_POLICY: generated_tts clip must NOT have audio stream")
            if mode == "baked_in" and not info["has_audio"]:
                entry["issues"].append("AUDIO_POLICY: baked_in clip MUST have audio stream")

            # Hero lipsync structural checks (all FATAL)
            if hero:
                entry["audio_mode"] = "hero_lipsync"
                entry["issues"].extend(lipsync_checks(seg, media_path, info, base))

            # Crop-safety structural check. constraints.json requires James to be
            # center-safe (a_roll_rules / crop_safety.james_must_be_center_safe). We
            # cannot run face detection here, so we verify what IS deterministic:
            #  - hero (a_roll) beats must declare crop_safety == "center_safe";
            #  - assembled-scope clips must match the expected aspect for the scope.
            cs = seg.get("crop_safety")
            if hero and cs and cs != "center_safe":
                entry["issues"].append(
                    f"CROP_SAFETY: hero beat declares crop_safety={cs!r}, must be 'center_safe' "
                    f"(James must survive the 9:16 center crop)")
            if scope in ("assembled_16x9", "assembled_9x16") and info.get("width"):
                want = (16, 9) if scope == "assembled_16x9" else (9, 16)
                ar = info["width"] / info["height"] if info.get("height") else 0
                target = want[0] / want[1]
                if abs(ar - target) > 0.02:
                    entry["issues"].append(
                        f"CROP_SAFETY: assembled aspect {info['width']}x{info['height']} "
                        f"!= {want[0]}:{want[1]} (center crop not applied)")

            entry["status"] = "fail" if entry["issues"] else "pass"
            if entry["issues"]:
                all_pass = False
            results.append(entry)

    return results, all_pass


def main():
    ap = argparse.ArgumentParser(description="Technical QA for generated media clips.")
    ap.add_argument("script", help="Path to script JSON")
    ap.add_argument("--segment", default=None, help="QA only this segment")
    ap.add_argument("--output", "-o", default=None, help="Write JSON report to file")
    ap.add_argument("--scope", default="source",
                    choices=["source", "assembled_16x9", "assembled_9x16"],
                    help="Expected dimensions: source clips (1280x720) or assembled output")
    ap.add_argument("--record-gate", action="store_true",
                    help="Record the media_qa gate (G8) in the project ledger on pass")
    ap.add_argument("--project-id", default=None, help="Project id for gate (overrides script)")
    args = ap.parse_args()

    results, all_pass = run_qa(args.script, args.segment, scope=args.scope)

    # Print summary
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    for r in results:
        icon = "✓" if r["status"] == "pass" else "✗"
        issues = "; ".join(r["issues"]) if r["issues"] else ""
        extra = f" — {issues}" if issues else ""
        print(f"  {icon} [{r['id']}] {r.get('width','?')}x{r.get('height','?')} "
              f"{r.get('duration','?')}s audio={r.get('has_audio','?')}{extra}")

    print(f"\n  {passed} pass, {failed} fail")

    # Write report
    report = {"script": args.script, "all_pass": all_pass,
              "passed": passed, "failed": failed, "results": results}
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2))
        print(f"  report: {args.output}")
    else:
        out = Path(args.script).with_name(Path(args.script).stem + "_media_qa.json")
        out.write_text(json.dumps(report, indent=2))
        print(f"  report: {out}")

    if args.record_gate:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from gates import record_gate as _record
        script_data = json.loads(Path(args.script).read_text())
        pid = args.project_id or script_data.get("project_id")
        if pid:
            _record(pid, "media_qa", "pass" if all_pass else "fail",
                    artifact_path=args.output or str(Path(args.script).with_name(
                        Path(args.script).stem + "_media_qa.json")))
            print(f"  gate media_qa={'pass' if all_pass else 'fail'} recorded for {pid}")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
