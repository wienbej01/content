#!/usr/bin/env python3
"""Lipsync eval harness — fallback mouth-motion/audio-envelope proxy.

Priority:
1. SyncNet — NOT AVAILABLE in this environment
2. Wav2Lip LSE — NOT AVAILABLE in this environment
3. mouth_motion_proxy — cross-correlation of audio envelope vs visual activity

Output: JSON with eval_name, method, offset_ms, confidence, status.

Usage:
  python3 scripts/evals/eval_lipsync.py --video <path> --out <json> --subject-id <id>
"""
import argparse
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HAS_NUMPY = False
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None

FRAME_WIDTH = 160
FRAME_HEIGHT = 90
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT  # grayscale, 1 byte per pixel
AUDIO_SR = 48000
ENVELOPE_WINDOW_MS = 50
ENVELOPE_WINDOW_SAMPLES = int(AUDIO_SR * ENVELOPE_WINDOW_MS / 1000)


def extract_audio_envelope(video_path: Path, tmp_dir: Path) -> dict:
    """Extract audio from video and compute RMS energy envelope.

    Returns dict with: envelope (list of RMS values per window),
    sample_rate, frame_rate.
    """
    audio_path = tmp_dir / "audio.wav"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(AUDIO_SR), "-ac", "1",
            str(audio_path),
        ], capture_output=True, check=True, timeout=60)
    except subprocess.CalledProcessError:
        return None

    if not audio_path.exists():
        return None

    data = audio_path.read_bytes()
    # Find data chunk
    data_start = data.find(b'data')
    if data_start < 0:
        return None
    data_size = struct.unpack_from('<I', data, data_start + 4)[0]
    raw_audio = data[data_start + 8:data_start + 8 + data_size]

    # Convert 16-bit PCM to float
    samples_fmt = f'<{len(raw_audio) // 2}h'
    samples = list(struct.unpack_from(samples_fmt, raw_audio))
    samples_f = np.array(samples, dtype=np.float64) if HAS_NUMPY else samples

    # Compute RMS envelope over windows
    envelope = []
    if HAS_NUMPY:
        n_windows = max(1, len(samples_f) // ENVELOPE_WINDOW_SAMPLES)
        for i in range(n_windows):
            start = i * ENVELOPE_WINDOW_SAMPLES
            end = min(start + ENVELOPE_WINDOW_SAMPLES, len(samples_f))
            window = samples_f[start:end]
            rms = float(np.sqrt(np.mean(window ** 2)))
            envelope.append(rms)
    else:
        n_windows = max(1, len(samples_f) // ENVELOPE_WINDOW_SAMPLES)
        for i in range(n_windows):
            start = i * ENVELOPE_WINDOW_SAMPLES
            end = min(start + ENVELOPE_WINDOW_SAMPLES, len(samples_f))
            window = samples_f[start:end]
            mean_sq = sum(s * s for s in window) / max(1, len(window))
            rms = math.sqrt(mean_sq)
            envelope.append(rms)

    total_samples = len(samples)
    duration_sec = total_samples / float(AUDIO_SR)

    return {
        "envelope": envelope,
        "sample_rate": AUDIO_SR,
        "duration_sec": round(duration_sec, 4),
        "frame_rate": round(1000.0 / ENVELOPE_WINDOW_MS, 1),
    }


def compute_visual_activity(video_path: Path, tmp_dir: Path) -> dict:
    """Extract low-res grayscale frames and compute frame-difference signal.

    Returns dict with: signal (list of mean pixel change per frame),
    frame_count, duration_sec, fps.
    """
    try:
        probe_r = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate,duration",
            "-of", "json", str(video_path),
        ], capture_output=True, text=True, timeout=15)
        probe = json.loads(probe_r.stdout)
        streams = probe.get("streams", [{}])
        fps_str = streams[0].get("r_frame_rate", "24/1") if streams else "24/1"
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) > 0 else 24.0
    except Exception:
        fps = 24.0

    # Extract frames as raw grayscale via ffmpeg pipe
    try:
        proc = subprocess.Popen([
            "ffmpeg", "-y", "-i", str(video_path),
            "-f", "rawvideo", "-pix_fmt", "gray",
            "-s", f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
            "-an", "-vcodec", "rawvideo", "-",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_data, stderr_data = proc.communicate(timeout=120)
    except subprocess.SubprocessError:
        return None

    if proc.returncode != 0 or len(stdout_data) == 0:
        return None

    n_frames = len(stdout_data) // FRAME_SIZE
    if n_frames == 0:
        return None

    # Reshape into frames, compute frame differences
    if HAS_NUMPY:
        raw = np.frombuffer(stdout_data, dtype=np.uint8)
        raw = raw[:n_frames * FRAME_SIZE]
        frames = raw.reshape(n_frames, FRAME_SIZE).astype(np.float64)
        diffs = np.abs(np.diff(frames, axis=0))
        signal = list(np.mean(diffs, axis=1))
    else:
        signal = []
        prev_frame = None
        for i in range(n_frames):
            start = i * FRAME_SIZE
            end = start + FRAME_SIZE
            frame = stdout_data[start:end]
            frame_f = [float(b) for b in frame]
            if prev_frame is not None:
                diff = sum(abs(a - b) for a, b in zip(frame_f, prev_frame)) / max(1, len(frame_f))
                signal.append(diff)
            prev_frame = frame_f

    duration_sec = n_frames / fps if fps > 0 else 0
    return {
        "signal": signal,
        "frame_count": n_frames - 1,
        "duration_sec": round(duration_sec, 4),
        "fps": fps,
        "width": FRAME_WIDTH,
        "height": FRAME_HEIGHT,
    }


def correlate_signals(audio: dict, visual: dict) -> dict:
    """Cross-correlate audio envelope and visual activity signals.

    Returns offset_ms, confidence.
    """
    if not HAS_NUMPY or audio is None or visual is None:
        return {"offset_ms": None, "confidence": 0.0}

    a = np.array(audio["envelope"], dtype=np.float64)
    v = np.array(visual["signal"], dtype=np.float64)

    min_len = min(len(a), len(v))
    if min_len < 5:
        return {"offset_ms": None, "confidence": 0.0}

    a = a[:min_len]
    v = v[:min_len]

    # Normalize
    a_norm = (a - np.mean(a)) / (np.std(a) + 1e-10)
    v_norm = (v - np.mean(v)) / (np.std(v) + 1e-10)

    # Cross-correlate
    corr = np.correlate(a_norm, v_norm, mode='same')
    max_corr = float(np.max(np.abs(corr)))
    norm_factor = min_len * np.sqrt(np.mean(a_norm ** 2) * np.mean(v_norm ** 2)) + 1e-10
    confidence = min(1.0, max(0.0, max_corr / norm_factor))

    # Find peak offset
    peak_idx = int(np.argmax(np.abs(corr)))
    center = min_len // 2
    offset_frames = peak_idx - center

    # Convert offset to ms (using audio envelope window rate)
    envelope_fps = audio["frame_rate"]
    offset_ms = round(offset_frames / envelope_fps * 1000, 2) if envelope_fps > 0 else 0

    return {"offset_ms": offset_ms, "confidence": round(confidence, 4)}


def analyze_video(video_path: Path, subject_id: str = "") -> dict:
    """Run the full lipsync eval on a video file."""
    with tempfile.TemporaryDirectory(prefix="lipsync_eval_") as td:
        tmp_dir = Path(td)

        audio = extract_audio_envelope(video_path, tmp_dir)
        visual = compute_visual_activity(video_path, tmp_dir)

        if audio is None:
            return _blocked_result("no_audio", f"Could not extract audio from {video_path}", subject_id)

        if visual is None:
            return _blocked_result("no_video", f"Could not extract frames from {video_path}", subject_id)

        corr = correlate_signals(audio, visual)
        offset_ms = corr["offset_ms"]
        confidence = corr["confidence"]

        # Determine status
        warn_ms = 100
        fail_ms = 160

        if offset_ms is None:
            status = "diagnostic"
        elif abs(offset_ms) >= fail_ms:
            status = "fail"
        elif abs(offset_ms) >= warn_ms:
            status = "warn"
        else:
            status = "diagnostic"

        return {
            "eval_name": "lipsync",
            "method": "mouth_motion_proxy",
            "subject_id": subject_id,
            "face_track_found": False,
            "offset_ms": offset_ms,
            "confidence": confidence,
            "thresholds": {
                "warn_offset_ms": warn_ms,
                "fail_offset_ms": fail_ms,
            },
            "status": status,
            "dependency_status": "available" if HAS_NUMPY else "blocked_dependency",
            "provisional": True,
            "note": "Fallback proxy: audio envelope vs visual frame-diff correlation. "
                    "Not definitive. No face tracking available.",
        }


def _blocked_result(reason: str, detail: str, subject_id: str = "") -> dict:
    return {
        "eval_name": "lipsync",
        "method": "mouth_motion_proxy",
        "subject_id": subject_id,
        "face_track_found": False,
        "offset_ms": None,
        "confidence": 0.0,
        "thresholds": {"warn_offset_ms": 100, "fail_offset_ms": 160},
        "status": "blocked",
        "blocked_reason": reason,
        "blocked_detail": detail,
        "provisional": True,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lipsync eval harness")
    ap.add_argument("--video", required=True, type=Path, help="Video file path")
    ap.add_argument("--out", required=True, type=Path, help="Output JSON path")
    ap.add_argument("--subject-id", default="", help="Render unit ID or other subject identifier")
    args = ap.parse_args(argv)

    if not args.video.exists():
        result = _blocked_result("missing_video", f"Video not found: {args.video}", args.subject_id)
    else:
        result = analyze_video(args.video, args.subject_id)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Lipsync eval for {args.subject_id or args.video.name}")
    print(f"  Method: {result['method']}")
    print(f"  Status: {result['status']}")
    if result.get("offset_ms") is not None:
        print(f"  Offset: {result['offset_ms']:.2f}ms")
    if result.get("confidence"):
        print(f"  Confidence: {result['confidence']:.4f}")
    print(f"  Output: {args.out}")

    return 0 if result["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
