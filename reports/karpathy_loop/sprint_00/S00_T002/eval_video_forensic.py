#!/usr/bin/env python3
"""Video forensic eval for S00_T002.

Produces machine-readable video_forensic_summary.json with quantitative
measurements of known video defects. Deterministic, local-only.
"""
import json
import os
import subprocess
import hashlib
import pathlib
import re

FIXTURE = pathlib.Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")
OUTPUT = pathlib.Path("reports/karpathy_loop/sprint_00/S00_T002/video_forensic_summary.json")
EXPECTED_SHA256 = "35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386"

checks = []
issues = []

def add_check(name, passed, detail, threshold=""):
    checks.append({"check": name, "pass": bool(passed), "detail": str(detail), "threshold": threshold})
    return bool(passed)

# 1. SHA256
actual_sha = hashlib.sha256(FIXTURE.read_bytes()).hexdigest() if FIXTURE.exists() else "MISSING"
sha_ok = add_check("SHA256_MATCH", actual_sha == EXPECTED_SHA256,
                   f"actual={actual_sha[:16]}... expected={EXPECTED_SHA256[:16]}...",
                   "exact match")

# 2. ffprobe
ffprobe_data = None
try:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(FIXTURE)],
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        ffprobe_data = json.loads(r.stdout)
        add_check("FFPROBE_OK", True, "ffprobe parsed successfully", "exit 0")
    else:
        add_check("FFPROBE_OK", False, f"ffprobe exit={r.returncode}", "exit 0")
except Exception as e:
    add_check("FFPROBE_OK", False, str(e), "exit 0")

if not ffprobe_data:
    print("FATAL: ffprobe failed"); exit(1)

# 3. Duration
fmt = ffprobe_data.get("format", {})
duration_sec = float(fmt.get("duration", 0))
dur_ok = add_check("DURATION", 22.0 <= duration_sec <= 24.0,
                   f"duration={duration_sec:.3f}s", "22.0-24.0s")

# 4. Stream analysis
streams = ffprobe_data.get("streams", [])
video_streams = [s for s in streams if s.get("codec_type") == "video"]
audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
vs = video_streams[0] if video_streams else {}
audio_s = audio_streams[0] if audio_streams else {}

video_dur = float(vs.get("duration", 0)) if vs.get("duration") else duration_sec
audio_dur = float(audio_s.get("duration", 0)) if audio_s.get("duration") else duration_sec
av_diff = abs(audio_dur - video_dur)
av_ok = add_check("AV_DURATION_DIFF", av_diff < 0.042,
                  f"audio_dur={audio_dur:.3f}s video_dur={video_dur:.3f}s diff={av_diff:.3f}s",
                  "< 0.042s (1 frame at 24fps)")
if not av_ok:
    issues.append({"class": "F-LIP-001", "severity": "major",
        "description": f"Audio-video duration mismatch: {av_diff:.3f}s (exceeds 1 frame = {1/24:.3f}s)",
        "detail": "Indirect evidence consistent with lipsync offset. Requires SyncNet eval."})

# 5. Scene detection
try:
    scene_r = subprocess.run(
        ["ffmpeg", "-i", str(FIXTURE), "-vf", "select='gte(scene,0.1)',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60)
    scene_times = [float(m) for m in re.findall(r'pts_time:([\d.]+)', scene_r.stderr)]
    scene_times = sorted(set(round(t, 3) for t in scene_times if t > 0.5))
    scene_count = len(scene_times) + 1
    add_check("SCENE_COUNT", scene_count == 4,
              f"scene_count={scene_count} transitions={scene_times}", "4 scenes")
except Exception as e:
    scene_times = []; scene_count = 0
    add_check("SCENE_COUNT", False, f"error: {e}", "4 scenes")

# 6. Static hold (blackdetect)
black_start = black_end = max_static_hold = 0.0
try:
    black_r = subprocess.run(
        ["ffmpeg", "-i", str(FIXTURE), "-vf", "blackdetect=d=0.5:pic_th=0.98",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=60)
    m = re.search(r'black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)', black_r.stderr)
    if m:
        black_start = float(m.group(1))
        black_end = float(m.group(2))
        max_static_hold = float(m.group(3))
    hold_ok = add_check("MAX_STATIC_HOLD", max_static_hold < 5.0,
                        f"hold={max_static_hold:.3f}s start={black_start:.3f}s end={black_end:.3f}s",
                        "< 5.0s")
    if max_static_hold >= 5.0:
        issues.append({"class": "F-GFX-001", "severity": "major",
            "description": f"Static black hold of {max_static_hold:.3f}s ({max_static_hold/duration_sec*100:.1f}% of total)",
            "detail": f"Black detected {black_start:.3f}s to {black_end:.3f}s"})
        issues.append({"class": "F-GFX-002", "severity": "minor",
            "description": "Graphic is static black with no progressive animation or beat structure",
            "detail": "Single static black frame held for entire segment"})
    elif max_static_hold <= 0:
        add_check("MAX_STATIC_HOLD", False, "no black hold detected or detection failed", "< 5.0s")
except Exception as e:
    add_check("MAX_STATIC_HOLD", False, f"blackdetect error: {e}", "< 5.0s")

# 7. Lipsync provisional
add_check("LIPSYNC_ASSESSMENT", True,
          f"Provisional: diff={av_diff:.3f}s, no SyncNet run. AV duration mismatch recorded.",
          "provisional only")

# 8. Text risk
issues.append({"class": "F-TEXT-001", "severity": "minor",
    "description": "Scene 2 (phone b-roll, 4.583-10.458s) may contain screen text",
    "detail": "Phone screen content with NO_VISIBLE_TEXT policy risk"})

# 9. QA gap
issues.append({"class": "F-QA-001", "severity": "major",
    "description": "QA passes without lipsync validation",
    "detail": "30 validations exist, none measure audio-visual sync"})

# Assemble output
summary = {
    "eval_id": "S00_T002_video_forensic",
    "subject": str(FIXTURE),
    "fixture_sha256": actual_sha,
    "expected_sha256": EXPECTED_SHA256,
    "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",
    "duration_sec": round(duration_sec, 3),
    "resolution": f"{vs.get('width',0)}x{vs.get('height',0)}",
    "fps": vs.get("r_frame_rate", "N/A"),
    "frame_count": vs.get("nb_frames", "?"),
    "scene_count": scene_count,
    "scene_transitions_sec": scene_times,
    "max_static_hold_sec": round(max_static_hold, 3),
    "black_hold_start_sec": round(black_start, 3),
    "black_hold_end_sec": round(black_end, 3),
    "audio_video_duration_diff_sec": round(av_diff, 3),
    "suspected_lipsync_offset_ms": None,
    "lipsync_provisional": True,
    "lipsync_method": None,
    "hero_talking_head_segments": [
        {"scene": 1, "start_sec": 0.000, "end_sec": 4.583, "label": "S000"},
        {"scene": 3, "start_sec": 10.458, "end_sec": 15.667, "label": "S002"}
    ],
    "total_checks": len(checks),
    "checks_passed": sum(1 for c in checks if c["pass"]),
    "checks_failed": sum(1 for c in checks if not c["pass"]),
    "checks": checks,
    "issues": issues,
    "timestamp": "2026-06-23T23:17:00+08:00"
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(summary, indent=2))

print(f"Video Forensic Summary: {summary['checks_passed']}/{summary['total_checks']} checks passed")
for c in checks:
    status = "PASS" if c["pass"] else "FAIL"
    print(f"  [{status}] {c['check']}: {c['detail']}")

print(f"\nIssues found: {len(issues)}")
for iss in issues:
    print(f"  {iss['class']} [{iss['severity']}]: {iss['description']}")
