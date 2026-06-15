"""Tests for scripts/qa_final.py — final stream-integrity gate."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
QA_FINAL = ROOT / "scripts" / "qa_final.py"
DEFECTIVE_MP4 = (ROOT / "Videos" / "Projects" / "using_ai_to_help_memory_retention_short"
                 / "using_ai_to_help_memory_retention_short_16x9.mp4")


def _run_qa(video_path, extra_args=None):
    cmd = [sys.executable, str(QA_FINAL), str(video_path)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))


def _make_valid(path, duration=5, fps=24):
    """Create a valid MP4 with matching video and audio streams (non-static)."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=duration={duration}:size=320x240:rate={fps}",
        "-f", "lavfi", "-i", f"sine=frequency=440:d={duration}",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)
    ], check=True, capture_output=True)


def _make_mismatch(path, video_sec=3, audio_sec=8, fps=24):
    """Create MP4 with short video stream + long audio stream."""
    tmp = Path(path).parent
    v = tmp / "v.mp4"
    a = tmp / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    f"color=c=black:s=320x240:r={fps}:d={video_sec}",
                    "-c:v", "libx264", "-t", str(video_sec), str(v)],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:d={audio_sec}",
                    "-c:a", "mp3", "-t", str(audio_sec), str(a)],
                   check=True, capture_output=True)
    # Mux without -shortest so audio outlasts video
    subprocess.run(["ffmpeg", "-y", "-i", str(v), "-i", str(a),
                    "-c:v", "copy", "-c:a", "copy", str(path)],
                   check=True, capture_output=True)


def test_valid_fixture_passes(tmp_path):
    """A valid MP4 with matching streams passes."""
    mp4 = tmp_path / "valid.mp4"
    _make_valid(mp4, duration=5)
    report_path = tmp_path / "report.json"
    r = _run_qa(mp4, ["--output", str(report_path)])
    assert r.returncode == 0, f"Expected pass, got:\n{r.stdout}\n{r.stderr}"
    report = json.loads(report_path.read_text())
    assert report["status"] == "pass"
    assert report["issues"] == []


def test_short_video_long_audio_fails(tmp_path):
    """Video stream shorter than audio triggers TERMINAL_FREEZE / LENGTH_MISMATCH."""
    mp4 = tmp_path / "mismatch.mp4"
    _make_mismatch(mp4, video_sec=3, audio_sec=8)
    report_path = tmp_path / "report.json"
    r = _run_qa(mp4, ["--output", str(report_path)])
    assert r.returncode == 1, f"Expected fail, got:\n{r.stdout}"
    report = json.loads(report_path.read_text())
    assert report["status"] == "fail"
    issues_text = " ".join(report["issues"])
    assert "LENGTH_MISMATCH" in issues_text or "TERMINAL_FREEZE" in issues_text
    # Mismatch should be ~5s
    vdur = report["video_duration"]
    adur = report["audio_duration"]
    assert abs((adur - vdur) - 5.0) < 1.0, f"Expected ~5s mismatch, got {adur - vdur:.1f}s"


def test_no_frames_fails(tmp_path):
    """Audio-only file (no video stream) must fail."""
    mp4 = tmp_path / "audio_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:d=3",
                    "-c:a", "aac", str(mp4)], check=True, capture_output=True)
    report_path = tmp_path / "report.json"
    r = _run_qa(mp4, ["--output", str(report_path)])
    assert r.returncode == 1
    report = json.loads(report_path.read_text())
    assert report["status"] == "fail"
    issues_text = " ".join(report["issues"])
    assert "NO_FRAMES" in issues_text


def test_container_exceeds_video_fails(tmp_path):
    """Container duration > video stream duration by >0.25s must fail."""
    # Same as mismatch: the container will take the longer audio duration
    mp4 = tmp_path / "container_mismatch.mp4"
    _make_mismatch(mp4, video_sec=3, audio_sec=8)
    report_path = tmp_path / "report.json"
    r = _run_qa(mp4, ["--output", str(report_path)])
    assert r.returncode == 1
    report = json.loads(report_path.read_text())
    issues_text = " ".join(report["issues"])
    assert "CONTAINER_MISMATCH" in issues_text or "LENGTH_MISMATCH" in issues_text


@pytest.mark.skipif(not DEFECTIVE_MP4.exists(), reason="Audited MP4 not present")
def test_existing_defective_mp4_fails(tmp_path):
    """The actual audited defective MP4 must fail with correct durations."""
    report_path = tmp_path / "report.json"
    r = _run_qa(DEFECTIVE_MP4, ["--output", str(report_path)])
    assert r.returncode == 1, f"Expected fail on defective MP4, got:\n{r.stdout}"
    report = json.loads(report_path.read_text())
    assert report["status"] == "fail"
    # Video should be ~83.333s (NOT 146.6s)
    assert report["video_duration"] is not None
    assert 80 < report["video_duration"] < 90, f"video_duration={report['video_duration']}"
    # Audio should be ~146.6s
    assert report["audio_duration"] is not None
    assert 143 < report["audio_duration"] < 150, f"audio_duration={report['audio_duration']}"
    # Mismatch ~63.267s
    mismatch = report["audio_duration"] - report["video_duration"]
    assert 60 < mismatch < 67, f"mismatch={mismatch:.1f}s"
    # Issues mention mismatch
    issues_text = " ".join(report["issues"])
    assert "LENGTH_MISMATCH" in issues_text or "TERMINAL_FREEZE" in issues_text
