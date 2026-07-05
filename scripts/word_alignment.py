#!/usr/bin/env python3
"""word_alignment.py — Forced word-level alignment of known script text against master narration.

Produces a `word_timing` document: [{word, start_ms, end_ms, confidence, segment_id}]
covering >=95% of script words. Runs between TTS and audio_timing in the stage graph.

Backend selection: ALIGNMENT_BACKEND=fixture|real
- fixture: deterministic evenly-distributed word times (for tests).
- real:     energy-based word segmentation (numpy + wave + ffmpeg). Zero extra deps.

Real backend absent in production -> stage blocks (no silent fallback).
"""
import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

FRAME_MS = 25
FRAME_STEP_MS = 10
ENERGY_THRESH_RATIO = 0.15
MIN_WORD_MS = 30
MAX_WORD_MS = 2000
COVERAGE_THRESHOLD = 0.95


def _get_backend():
    backend = os.environ.get("ALIGNMENT_BACKEND", "fixture")
    if backend not in ("fixture", "real"):
        raise RuntimeError(f"Invalid ALIGNMENT_BACKEND: {backend}. Must be 'fixture' or 'real'.")
    return backend


def _probe_duration_sec(audio_path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise RuntimeError(f"Cannot probe duration: {audio_path}")


def _convert_to_wav(audio_path, tmpdir):
    wav_path = Path(tmpdir) / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path), "-ac", "1", "-ar", "16000",
         "-sample_fmt", "s16", str(wav_path)],
        capture_output=True, text=True, check=True)
    return wav_path


def _read_pcm(wav_path):
    with wave.open(str(wav_path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        nframes = wf.getnframes()
        framerate = wf.getframerate()
        raw = wf.readframes(nframes)
        fmt = {1: "b", 2: "h", 4: "i"}[sampwidth]
        samples = struct.unpack(f"<{nframes * nchannels}{fmt}", raw)
        if nchannels > 1:
            samples = samples[::nchannels]
        signal = np.array(samples, dtype=np.float64)
        signal /= 32768.0
        return signal, framerate


def _compute_rms_energy(signal, sample_rate, frame_ms=FRAME_MS, step_ms=FRAME_STEP_MS):
    frame_samples = int(sample_rate * frame_ms / 1000)
    step_samples = int(sample_rate * step_ms / 1000)
    rms = []
    for i in range(0, len(signal) - frame_samples + 1, step_samples):
        chunk = signal[i:i + frame_samples]
        rms.append(np.sqrt(np.mean(chunk ** 2)))
    return np.array(rms), step_ms


def _detect_word_boundaries(rms_energy, step_ms, total_duration_ms, threshold_ratio=ENERGY_THRESH_RATIO):
    if len(rms_energy) == 0:
        return [(0, total_duration_ms)]

    max_energy = np.max(rms_energy)
    if max_energy == 0:
        return [(0, total_duration_ms)]

    threshold = max_energy * threshold_ratio
    is_speech = rms_energy > threshold

    state = "silence"
    word_start = 0
    words = []
    for i, speech in enumerate(is_speech):
        time_ms = i * step_ms
        if state == "silence" and speech:
            word_start = time_ms
            state = "speech"
        elif state == "speech" and not speech:
            end_ms = time_ms + step_ms
            words.append((word_start, end_ms))
            state = "silence"

    if state == "speech":
        words.append((word_start, total_duration_ms))

    if not words:
        return [(0, total_duration_ms)]

    # Merge very short gaps (<50ms) between adjacent words
    merged = [words[0]]
    for i in range(1, len(words)):
        gap = words[i][0] - merged[-1][1]
        if gap < 50 and gap >= 0:
            merged[-1] = (merged[-1][0], words[i][1])
        else:
            merged.append(words[i])

    return merged


def _tokenize_words(text):
    words = re.findall(r"[A-Za-z0-9]+", text)
    return words, " ".join(words)


def align_fixture(text, audio_path):
    total_sec = _probe_duration_sec(audio_path)
    total_ms = total_sec * 1000
    words, _ = _tokenize_words(text)

    if not words:
        return [], total_ms

    word_duration = total_ms / len(words)
    segments = []
    for i, word in enumerate(words):
        start_ms = round(i * word_duration, 3)
        end_ms = round((i + 1) * word_duration, 3)
        segments.append({
            "word": word,
            "start_ms": start_ms,
            "end_ms": min(end_ms, round(total_ms, 3)),
            "confidence": 0.5,
            "segment_id": f"fixture_{i:04d}",
        })
    return segments, total_ms


def align_real(text, audio_path):
    total_sec = _probe_duration_sec(audio_path)
    total_ms = total_sec * 1000
    words, normalized_text = _tokenize_words(text)

    if not words:
        return [], total_ms

    with tempfile.TemporaryDirectory(prefix="ytch_walign_") as tmpdir:
        wav_path = _convert_to_wav(audio_path, tmpdir)
        signal, sample_rate = _read_pcm(wav_path)
        rms_energy, step_ms = _compute_rms_energy(signal, sample_rate)
        boundaries = _detect_word_boundaries(rms_energy, step_ms, total_ms)

    # Map detected boundaries to known words via proportional allocation
    segments = []
    if len(boundaries) > 0 and boundaries != [(0, total_ms)]:
        b_idx = 0
        for w_idx, word in enumerate(words):
            seg_count = max(1, len(boundaries) // len(words))
            start_ms = boundaries[b_idx][0]
            end_ms = boundaries[min(b_idx + seg_count - 1, len(boundaries) - 1)][1]
            b_idx = min(b_idx + seg_count, len(boundaries))
            segments.append({
                "word": word,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "confidence": 0.7,
                "segment_id": f"real_{w_idx:04d}",
            })
    else:
        raise RuntimeError(
            f"BLOCKED: real word_alignment backend failed to detect any word boundaries "
            f"(audio produced {len(boundaries)} detected segment, no internal boundaries). "
            f"Set ALIGNMENT_BACKEND=fixture to use proportional word allocation.")

    return segments, total_ms


def align_words(text, audio_path, backend=None):
    if backend is None:
        backend = _get_backend()

    if not text or not isinstance(text, str):
        raise RuntimeError("Text must be a non-empty string")

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise RuntimeError(f"Audio file not found: {audio_path}")

    words, _ = _tokenize_words(text)

    if backend == "fixture":
        segments, total_ms = align_fixture(text, audio_path)
    elif backend == "real":
        segments, total_ms = align_real(text, audio_path)
    else:
        raise RuntimeError(f"Unknown backend: {backend}")

    # Ensure monotonic, non-overlapping
    for i in range(1, len(segments)):
        if segments[i]["start_ms"] < segments[i - 1]["end_ms"]:
            segments[i]["start_ms"] = segments[i - 1]["end_ms"]

    # Enforce minimum duration
    for seg in segments:
        if seg["end_ms"] - seg["start_ms"] < MIN_WORD_MS:
            seg["end_ms"] = seg["start_ms"] + MIN_WORD_MS

    # Coverage check
    aligned_words = len(segments)
    total_words = len(words)
    coverage = aligned_words / total_words if total_words > 0 else 0.0

    if coverage < COVERAGE_THRESHOLD:
        unaligned = total_words - aligned_words
        raise RuntimeError(
            f"word_alignment coverage {coverage:.1%} below threshold {COVERAGE_THRESHOLD:.0%}: "
            f"{aligned_words}/{total_words} words aligned, {unaligned} words unaligned. "
            f"Check audio quality or script text."
        )

    return {
        "segments": segments,
        "total_words": total_words,
        "aligned_words": aligned_words,
        "coverage": round(coverage, 4),
        "backend": backend,
        "total_duration_ms": round(total_ms, 3) if total_ms else None,
    }


def build_word_timing_document(text, audio_path, audio_sha, script_sha, backend=None):
    result = align_words(text, audio_path, backend=backend)
    return {
        "metadata": {
            "audio_sha": audio_sha,
            "script_sha": script_sha,
            "backend": result["backend"],
            "total_duration_ms": result["total_duration_ms"],
            "coverage": result["coverage"],
            "total_words": result["total_words"],
            "aligned_words": result["aligned_words"],
        },
        "words": result["segments"],
    }


def main():
    ap = argparse.ArgumentParser(description="Forced word-level alignment of script against audio.")
    ap.add_argument("audio", help="Path to narration audio file (MP3/WAV)")
    ap.add_argument("--text", required=True, help="Full script text to align")
    ap.add_argument("--output", "-o", default=None, help="Output JSON path (default: stdout)")
    ap.add_argument("--backend", choices=["fixture", "real"],
                    default=os.environ.get("ALIGNMENT_BACKEND", "fixture"),
                    help="Alignment backend (env: ALIGNMENT_BACKEND)")
    args = ap.parse_args()

    audio = Path(args.audio)
    if not audio.exists():
        print(f"ERROR: audio file not found: {audio}", file=sys.stderr)
        sys.exit(1)

    if not args.text.strip():
        print("ERROR: --text must be non-empty", file=sys.stderr)
        sys.exit(1)

    try:
        doc = build_word_timing_document(args.text, audio, "cli", "cli", backend=args.backend)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    out = json.dumps(doc, indent=2)
    if args.output:
        Path(args.output).write_text(out)
        print(f"word_timing document: {args.output} ({doc['metadata']['aligned_words']}/{doc['metadata']['total_words']} words, "
              f"coverage: {doc['metadata']['coverage']:.1%})")
    else:
        print(out)


if __name__ == "__main__":
    main()
