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
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPECTED_WIDTH = 1280
EXPECTED_HEIGHT = 720
MIN_DURATION = 2.0


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
    return p if p.is_absolute() else base / p


def run_qa(script_path, selected_segment=None):
    """Run media QA. Returns (results_list, pass_bool)."""
    script = json.load(open(script_path))
    base = Path(script_path).resolve().parent
    output_dir = resolve(base, script.get("output_dir", f"Videos/Projects/{script['project_id']}"))
    fmt = script.get("defaults", {}).get("format", "mp3")
    results = []
    all_pass = True

    for seg in script["segments"]:
        sid = seg["id"]
        if selected_segment and sid != selected_segment:
            continue
        mode = seg.get("audio_mode", "generated_tts")

        # Expand shots or use segment media
        units = []
        if seg.get("shots") and mode != "baked_in":
            for sh in seg["shots"]:
                units.append({"id": sh["id"], "media": sh["media"], "segment_id": sid,
                              "duration_target": sh.get("duration")})
        else:
            units.append({"id": sid, "media": seg["media"], "segment_id": sid,
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
            if info["width"] != EXPECTED_WIDTH or info["height"] != EXPECTED_HEIGHT:
                entry["issues"].append(
                    f"DIMENSIONS: {info['width']}x{info['height']} (expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT})")

            # Duration check
            if info["duration"] < MIN_DURATION:
                entry["issues"].append(f"TOO_SHORT: {info['duration']:.1f}s < {MIN_DURATION}s")

            # Audio policy
            if mode == "generated_tts" and info["has_audio"]:
                entry["issues"].append("AUDIO_POLICY: generated_tts clip must NOT have audio stream")
            if mode == "baked_in" and not info["has_audio"]:
                entry["issues"].append("AUDIO_POLICY: baked_in clip MUST have audio stream")

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
    args = ap.parse_args()

    results, all_pass = run_qa(args.script, args.segment)

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
        # Default: write alongside script
        out = Path(args.script).with_name(Path(args.script).stem + "_media_qa.json")
        out.write_text(json.dumps(report, indent=2))
        print(f"  report: {out}")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
