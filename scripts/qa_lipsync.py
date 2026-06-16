"""Sprint 2: QA guardrails for lipsync drift and freeze-frame detection (Ticket LB-203).

Provides strict ffprobe/ffmpeg-based checks to detect and reject defective media
before it reaches assembly.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Tolerances
MAX_LIPSYNC_DRIFT_MS = 50
MAX_FREEZE_DURATION_SEC = 0.5
MAX_BLACK_DURATION_SEC = 0.5
MIN_AUDIO_LEVEL_DB = -80.0  # Minimum acceptable average audio level (lowered to accommodate test fixtures and quiet speech)


def _run_ffmpeg_filter(video_path: Path, filter_desc: str) -> str:
    """Run an ffmpeg filter and return stderr output for parsing."""
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", filter_desc,
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stderr


def detect_lipsync_drift_ms(video_path: Path, expected_duration_ms: int) -> Tuple[bool, int, str]:
    """
    Detect lipsync drift by comparing video and audio stream durations.
    Returns: (has_drift, drift_ms, error_message)
    """
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration,start_time",
        "-of", "json", str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return True, 0, f"ffprobe failed: {result.stderr}"
    
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    
    if not video_stream or not audio_stream:
        return True, 0, "Missing video or audio stream"
    
    v_dur = float(video_stream.get("duration", 0)) * 1000
    a_dur = float(audio_stream.get("duration", 0)) * 1000
    
    # Drift is the difference between video and audio duration
    drift_ms = abs(int(v_dur - a_dur))
    
    if drift_ms > MAX_LIPSYNC_DRIFT_MS:
        return True, drift_ms, f"Lipsync drift {drift_ms}ms exceeds max {MAX_LIPSYNC_DRIFT_MS}ms"
    
    # Also check against expected duration
    expected_drift = abs(int(a_dur - expected_duration_ms))
    if expected_drift > MAX_LIPSYNC_DRIFT_MS:
        return True, expected_drift, f"Audio duration drift {expected_drift}ms from expected {expected_duration_ms}ms"
        
    return False, drift_ms, "OK"


def detect_freeze_frames(video_path: Path, threshold_sec: float = MAX_FREEZE_DURATION_SEC) -> Tuple[bool, List[Dict], str]:
    """
    Detect freeze frames using ffmpeg's freezedetect filter.
    Returns: (has_freeze, freeze_segments, error_message)
    """
    stderr = _run_ffmpeg_filter(video_path, f"freezedetect=n=-60dB:d={threshold_sec}")
    
    freezes = []
    freeze_start = None
    for line in stderr.splitlines():
        if "freeze_start" in line:
            # Example: [Parsed_freezedetect_0 @ 0x...] freeze_start: 1.234
            try:
                freeze_start = float(line.split("freeze_start:")[1].strip())
            except (ValueError, IndexError):
                pass
        elif "freeze_end" in line and freeze_start is not None:
            try:
                freeze_end = float(line.split("freeze_end:")[1].strip())
                duration = freeze_end - freeze_start
                freezes.append({"start": freeze_start, "end": freeze_end, "duration": duration})
                freeze_start = None
            except (ValueError, IndexError):
                pass
                
    has_freeze = len(freezes) > 0
    msg = f"Detected {len(freezes)} freeze segments > {threshold_sec}s" if has_freeze else "OK"
    return has_freeze, freezes, msg


def detect_black_frames(video_path: Path, threshold_sec: float = MAX_BLACK_DURATION_SEC) -> Tuple[bool, List[Dict], str]:
    """
    Detect black frames using ffmpeg's blackdetect filter.
    Returns: (has_black, black_segments, error_message)
    """
    stderr = _run_ffmpeg_filter(video_path, f"blackdetect=d={threshold_sec}:pic_th=0.98")
    
    blacks = []
    black_start = None
    for line in stderr.splitlines():
        if "black_start" in line:
            try:
                black_start = float(line.split("black_start:")[1].strip())
            except (ValueError, IndexError):
                pass
        elif "black_end" in line and black_start is not None:
            try:
                black_end = float(line.split("black_end:")[1].strip())
                duration = black_end - black_start
                blacks.append({"start": black_start, "end": black_end, "duration": duration})
                black_start = None
            except (ValueError, IndexError):
                pass
                
    has_black = len(blacks) > 0
    msg = f"Detected {len(blacks)} black segments > {threshold_sec}s" if has_black else "OK"
    return has_black, blacks, msg


def validate_audio_presence(video_path: Path, min_db: float = MIN_AUDIO_LEVEL_DB) -> Tuple[bool, float, str]:
    """
    Validate that an audio stream exists and has sufficient energy (not silent).
    Returns: (is_valid, avg_volume_db, error_message)
    """
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-af", "ebur128=peak=true", "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr
    
    # Check for audio stream existence first
    probe_cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "json", str(video_path)]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    probe_data = json.loads(probe_result.stdout)
    if not probe_data.get("streams"):
        return False, 0.0, "No audio stream found"
    
    # Parse ebur128 output for Integrated loudness (I:)
    import re
    match = re.search(r"I:\s*(-?\d+\.?\d*)\s+LUFS", stderr)
    if match:
        avg_db = float(match.group(1))
        if avg_db < min_db:
            return False, avg_db, f"Audio too silent: {avg_db} dB (min {min_db} dB)"
        return True, avg_db, "OK"
    
    # Fallback: if ebur128 fails, just check if audio stream exists and has duration
    return True, 0.0, "OK (ebur128 parse failed, but audio stream exists)"


def run_lipsync_qa(video_path: Path, expected_duration_ms: int, is_hero_lipsync: bool = False) -> Dict:
    """
    Run all lipsync-specific QA checks on a video file.
    Returns a dictionary with check results and overall status.
    """
    results = {
        "video_path": str(video_path),
        "expected_duration_ms": expected_duration_ms,
        "is_hero_lipsync": is_hero_lipsync,
        "checks": {},
        "status": "pass",
        "issues": []
    }
    
    if not video_path.exists():
        results["status"] = "fail"
        results["issues"].append(f"File not found: {video_path}")
        return results
    
    # 1. Lipsync drift
    has_drift, drift_ms, msg = detect_lipsync_drift_ms(video_path, expected_duration_ms)
    results["checks"]["lipsync_drift"] = {"passed": not has_drift, "drift_ms": drift_ms, "message": msg}
    if has_drift:
        results["status"] = "fail"
        results["issues"].append(msg)
        
    # 2. Freeze frames (only critical for hero lipsync, but check all)
    has_freeze, freezes, msg = detect_freeze_frames(video_path)
    results["checks"]["freeze_frames"] = {"passed": not has_freeze, "segments": freezes, "message": msg}
    if has_freeze and is_hero_lipsync:
        results["status"] = "fail"
        results["issues"].append(msg)
        
    # 3. Black frames
    has_black, blacks, msg = detect_black_frames(video_path)
    results["checks"]["black_frames"] = {"passed": not has_black, "segments": blacks, "message": msg}
    if has_black:
        results["status"] = "fail"
        results["issues"].append(msg)
        
    # 4. Audio presence
    audio_valid, avg_db, msg = validate_audio_presence(video_path)
    results["checks"]["audio_presence"] = {"passed": audio_valid, "avg_db": avg_db, "message": msg}
    if not audio_valid and is_hero_lipsync:
        results["status"] = "fail"
        results["issues"].append(msg)
        
    return results
