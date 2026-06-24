#!/usr/bin/env python3
"""Diagnostic fixture integrity eval for S00_T001.

Deterministic, local-only, no provider calls.
Outputs machine-readable JSON to eval_result_before.json.
"""
import json
import os
import subprocess
import sys
import hashlib
import pathlib

FIXTURE_PATH = pathlib.Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")
EXPECTED_SHA256 = "35b972d44c3c4e20090a568aa915aa947e8c46865408344a7d4c31df6bca0386"
OUTPUT_PATH = pathlib.Path("reports/karpathy_loop/sprint_00/S00_T001/eval_result_before.json")

results = []
all_pass = True

def check(name, passed, detail, threshold=""):
    global all_pass
    if not passed:
        all_pass = False
    results.append({
        "check": name,
        "pass": bool(passed),
        "detail": str(detail),
        "threshold": threshold
    })

# 1. FILE_EXISTS
if FIXTURE_PATH.exists():
    size = FIXTURE_PATH.stat().st_size
    check("FILE_EXISTS", size > 5_000_000,
          f"fixture exists, size={size} bytes",
          "> 5MB")
else:
    check("FILE_EXISTS", False, "fixture file not found", "> 5MB")
    size = 0

# 2. SHA256_MATCH
if FIXTURE_PATH.exists():
    actual_sha256 = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    check("SHA256_MATCH", actual_sha256 == EXPECTED_SHA256,
          f"sha256={actual_sha256}",
          f"={EXPECTED_SHA256}")
else:
    check("SHA256_MATCH", False, "cannot compute sha256, file missing", f"={EXPECTED_SHA256}")

# 3. FFMPEG_READABLE
ffprobe_result = None
try:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(FIXTURE_PATH)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        ffprobe_result = json.loads(result.stdout)
        check("FFMPEG_READABLE", True,
              f"ffprobe exit={result.returncode}, {len(ffprobe_result.get('streams', []))} streams",
              "exit code 0, valid JSON")
    else:
        check("FFMPEG_READABLE", False,
              f"ffprobe exit={result.returncode}, stderr={result.stderr[:200]}",
              "exit code 0")
except Exception as e:
    check("FFMPEG_READABLE", False, f"ffprobe error: {e}", "exit code 0")

# 4. VIDEO_STREAM
video_dur = None
if ffprobe_result:
    video_streams = [s for s in ffprobe_result.get("streams", []) if s.get("codec_type") == "video"]
    if video_streams:
        vs = video_streams[0]
        codec_ok = vs.get("codec_name") == "h264"
        width_ok = vs.get("width") == 1920
        height_ok = vs.get("height") == 1080
        fps_ok = vs.get("r_frame_rate") == "24/1"
        video_dur = float(vs.get("duration", 0))
        dur_ok = 22.0 <= video_dur <= 24.0
        frames = vs.get("nb_frames", "?")
        frames_ok = frames == "548" if frames != "?" else False

        check("VIDEO_STREAM", codec_ok and width_ok and height_ok and fps_ok,
              f"codec={vs.get('codec_name')} w={vs.get('width')} h={vs.get('height')} "
              f"fps={vs.get('r_frame_rate')} dur={video_dur:.3f}s frames={frames}",
              "codec=h264, 1920x1080, 24fps")
        check("VIDEO_DURATION", dur_ok,
              f"video_duration={video_dur:.3f}s",
              "22.0-24.0s")
        check("FRAME_COUNT", frames_ok,
              f"frame_count={frames}",
              "548 frames")
    else:
        check("VIDEO_STREAM", False, "no video stream found", "codec=h264, 1920x1080, 24fps")
else:
    check("VIDEO_STREAM", False, "ffprobe unavailable", "codec=h264, 1920x1080, 24fps")

# 5. AUDIO_STREAM
audio_dur = None
if ffprobe_result:
    audio_streams = [s for s in ffprobe_result.get("streams", []) if s.get("codec_type") == "audio"]
    if audio_streams:
        audio = audio_streams[0]
        codec_ok = audio.get("codec_name") == "aac"
        sr_ok = audio.get("sample_rate") == "96000"
        ch_ok = audio.get("channels") == 2
        audio_dur = float(audio.get("duration", 0))
        check("AUDIO_STREAM", codec_ok and sr_ok and ch_ok,
              f"codec={audio.get('codec_name')} sr={audio.get('sample_rate')} "
              f"ch={audio.get('channels')} dur={audio_dur:.3f}s",
              "codec=aac, 96kHz, stereo")
        if video_dur and audio_dur:
            adiff = abs(audio_dur - video_dur)
            check("AUDIO_VIDEO_DURATION_DIFF", adiff < 1.0,
                  f"audio_dur={audio_dur:.3f}s vs video_dur={video_dur:.3f}s diff={adiff:.3f}s",
                  "difference < 1.0s")
    else:
        check("AUDIO_STREAM", False, "no audio stream found", "codec=aac, 96kHz, stereo")
else:
    check("AUDIO_STREAM", False, "ffprobe unavailable", "codec=aac, 96kHz, stereo")

# 6. RENDER_LOCK
env_checks = []
for var in ["YT_TEST_MODE", "HIGGSFIELD_DRY_RUN", "KARPATHY_LOOP_RENDER_LOCK"]:
    val = os.environ.get(var)
    if val == "1":
        env_checks.append(f"{var}=1")
    else:
        env_checks.append(f"{var}={val!r} (expected '1')")
env_pass = all(os.environ.get(v) == "1" for v in ["YT_TEST_MODE", "HIGGSFIELD_DRY_RUN", "KARPATHY_LOOP_RENDER_LOCK"])
check("RENDER_LOCK", env_pass,
      "; ".join(env_checks),
      "YT_TEST_MODE=1, HIGGSFIELD_DRY_RUN=1, KARPATHY_LOOP_RENDER_LOCK=1")

# 7. FORMAT_DURATION
if ffprobe_result:
    fmt_dur = float(ffprobe_result.get("format", {}).get("duration", 0))
    check("FORMAT_DURATION", 22.0 <= fmt_dur <= 24.0,
          f"format_duration={fmt_dur:.3f}s",
          "22.0-24.0s")
else:
    check("FORMAT_DURATION", False, "ffprobe unavailable", "22.0-24.0s")

# Assemble result
output = {
    "eval_id": "S00_T001_fixture_integrity",
    "subject": str(FIXTURE_PATH),
    "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",
    "fixture_sha256": EXPECTED_SHA256,
    "timestamp": "2026-06-23T22:59:00+08:00",
    "overall_pass": all_pass,
    "checks": results,
    "summary": {
        "total": len(results),
        "pass": sum(1 for r in results if r["pass"]),
        "fail": sum(1 for r in results if not r["pass"])
    }
}

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(json.dumps(output, indent=2))

print(f"Eval result: {'PASS' if all_pass else 'FAIL'}")
print(f"  {output['summary']['pass']}/{output['summary']['total']} checks passed")
for r in results:
    status = "PASS" if r["pass"] else "FAIL"
    print(f"  [{status}] {r['check']}: {r['detail']}")

sys.exit(0 if all_pass else 1)
