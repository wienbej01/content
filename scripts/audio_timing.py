#!/usr/bin/env python3
"""audio_timing.py — Build a timing map from a narration audio file + script text.

Detects sentence boundaries via ffmpeg silencedetect, then maps each text beat
to its [start, end] timestamp in the audio. Foundation for continuous-voiceover assembly.

Usage:
  python3 scripts/audio_timing.py narration.mp3 --script scripts/generated/script.json
  python3 scripts/audio_timing.py narration.mp3 --text "Sentence one. Sentence two."
  python3 scripts/audio_timing.py narration.mp3 --script script.json --output timing.json

Requires: ffmpeg (silencedetect filter). No TTS/API calls. Stdlib only.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Silence detection defaults (tuned for narrated speech)
SILENCE_THRESH_DB = -35   # dB below which is silence
SILENCE_MIN_DUR = 0.25    # minimum silence duration to count as a gap


def probe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def detect_silences(audio_path, noise_db=SILENCE_THRESH_DB, min_dur=SILENCE_MIN_DUR):
    """Run ffmpeg silencedetect, return list of (start, end) silence intervals."""
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    stderr = r.stderr

    silences = []
    starts = re.findall(r"silence_start: ([\d.]+)", stderr)
    ends = re.findall(r"silence_end: ([\d.]+)", stderr)
    for s, e in zip(starts, ends):
        silences.append((float(s), float(e)))
    return silences


def silences_to_segments(silences, total_duration):
    """Convert silence gaps into spoken segments: [(start, end), ...]."""
    segments = []
    pos = 0.0
    for sil_start, sil_end in silences:
        if sil_start > pos + 0.05:
            segments.append((round(pos, 3), round(sil_start, 3)))
        pos = sil_end
    # Final segment after last silence
    if pos < total_duration - 0.05:
        segments.append((round(pos, 3), round(total_duration, 3)))
    return segments


def split_text_into_beats(text):
    """Split text into sentence-level beats by punctuation."""
    # Split on sentence-ending punctuation + em-dash followed by space/capital
    parts = re.split(r'(?<=[.!?])\s+|(?<=—)\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def extract_beats_from_script(script_path):
    """Extract ordered beat texts from a script JSON."""
    script = json.load(open(script_path))
    beats = []
    for seg in script["segments"]:
        text = seg.get("text", "")
        if text:
            # Split each segment text into sub-beats (sentences)
            sub = split_text_into_beats(text)
            for i, s in enumerate(sub):
                beats.append({
                    "segment_id": seg["id"],
                    "beat_index": i,
                    "text": s,
                    "word_count": len(s.split()),
                })
    return beats


def build_storyboard_timing_map(audio_path, storyboard_beats, noise_db=SILENCE_THRESH_DB, min_dur=SILENCE_MIN_DUR, canonical_duration_sec=None):
    """Map storyboard beats (ordered, with narration_text) to [start, end] in continuous audio.

    Each beat gets a proportional share of the master duration based on word count,
    with boundaries snapped to the nearest detected silence (±0.4s).

    Args:
        audio_path: path to the continuous master MP3/wav.
        storyboard_beats: list of dicts with at least {beat_id, narration_text}.
        noise_db, min_dur: silence detection params.

    Returns:
        dict with 'beats' list [{beat_id, start, end, duration}, ...] and metadata.
    """
    if canonical_duration_sec is not None:
        total_dur = canonical_duration_sec
    else:
        total_dur = probe_duration(audio_path)
        if not total_dur:
            raise RuntimeError(f"Cannot probe duration: {audio_path}")

    # Word counts per beat
    word_counts = []
    for b in storyboard_beats:
        text = b.get("narration_text") or ""
        word_counts.append(len(text.split()))
    total_words = sum(word_counts) or 1

    # Proportional boundaries (cumulative)
    boundaries = [0.0]
    cum = 0
    for wc in word_counts:
        cum += wc
        boundaries.append(round(cum / total_words * total_dur, 4))
    # Ensure last boundary == total_dur
    boundaries[-1] = round(total_dur, 4)

    # Detect silences for snapping
    silences = detect_silences(audio_path, noise_db, min_dur)
    # Silence midpoints
    silence_mids = [round((s + e) / 2, 4) for s, e in silences]

    # Snap internal boundaries to nearest silence within SNAP_WINDOW
    SNAP_WINDOW = 0.4
    snapped = [boundaries[0]]
    for i in range(1, len(boundaries) - 1):
        raw = boundaries[i]
        candidates = [m for m in silence_mids if abs(m - raw) <= SNAP_WINDOW]
        snapped.append(min(candidates, key=lambda m: abs(m - raw)) if candidates else raw)
    snapped.append(boundaries[-1])

    # Ensure monotonically increasing
    for i in range(1, len(snapped)):
        if snapped[i] <= snapped[i - 1]:
            snapped[i] = snapped[i - 1] + 0.01

    # Enforce minimum beat duration (4s for beats with no narration)
    MIN_BEAT_SEC = 3.0
    for i in range(1, len(snapped) - 1):
        dur = snapped[i + 1] - snapped[i]
        if dur < MIN_BEAT_SEC:
            needed = MIN_BEAT_SEC - dur
            # Steal from left neighbor if possible
            if i > 0 and snapped[i] - snapped[i - 1] > needed + 0.1:
                snapped[i] -= needed
            # Otherwise steal from right neighbor
            elif i < len(snapped) - 2:
                snapped[i + 1] += needed

    # Build output
    beat_timings = []
    for i, b in enumerate(storyboard_beats):
        start = round(snapped[i], 3)
        end = round(snapped[i + 1], 3)
        beat_timings.append({
            "label": b.get("label") or b["beat_id"],
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
        })

    return {
        "audio_path": str(audio_path),
        "total_duration": round(total_dur, 3),
        "beat_count": len(storyboard_beats),
        "beats": beat_timings,
    }


def build_timing_map(audio_path, beats, noise_db=SILENCE_THRESH_DB, min_dur=SILENCE_MIN_DUR):
    """Build the full timing map: detect audio segments, align to text beats."""
    total_dur = probe_duration(audio_path)
    if not total_dur:
        raise RuntimeError(f"Cannot probe duration: {audio_path}")

    silences = detect_silences(audio_path, noise_db, min_dur)
    spoken = silences_to_segments(silences, total_dur)

    # Align: try 1:1 mapping. If counts differ, flag but still map what we can.
    flags = []
    if len(spoken) != len(beats):
        flags.append(f"beat_count_mismatch: {len(beats)} text beats vs {len(spoken)} audio segments")

    timing = []
    for i, beat in enumerate(beats):
        if i < len(spoken):
            start, end = spoken[i]
            dur = round(end - start, 3)
            wps = round(beat["word_count"] / dur, 2) if dur > 0 else 0
            pause = round(spoken[i + 1][0] - end, 3) if i + 1 < len(spoken) else 0
        else:
            start = end = dur = wps = pause = None
            flags.append(f"beat_{i}_no_audio_segment")

        timing.append({
            "beat_id": f"{beat.get('segment_id', 'beat')}_{beat['beat_index']:02d}",
            "segment_id": beat.get("segment_id"),
            "text": beat["text"],
            "word_count": beat["word_count"],
            "start": start,
            "end": end,
            "duration": dur,
            "wps": wps,
            "pause_after": pause,
        })

    # Flag issues
    for t in timing:
        if t["wps"] and t["wps"] < 1.5:
            flags.append(f"{t['beat_id']}: very_slow ({t['wps']} wps)")
        if t["pause_after"] and t["pause_after"] > 1.5:
            flags.append(f"{t['beat_id']}: long_pause ({t['pause_after']}s)")

    return {
        "audio_path": str(audio_path),
        "total_duration": round(total_dur, 3),
        "silence_threshold_db": noise_db,
        "silence_min_dur": min_dur,
        "audio_segments_detected": len(spoken),
        "text_beats": len(beats),
        "beats": timing,
        "flags": flags,
    }


def build_word_boundary_timing_map(storyboard_beats, word_timing_words, total_duration_ms, word_timing_doc=None):
    """Map storyboard beats to [start, end] using measured word boundaries from forced alignment.

    Each beat boundary is placed at the midpoint of the inter-word silence gap
    between the last word of the preceding beat and the first word of the next beat.
    When words are flush (no gap), the boundary is placed at the end of the last word
    in the preceding beat (tie-break rule: earliest boundary that keeps words intact).

    Args:
        storyboard_beats: list of dicts with {beat_id, narration_text, narration_word_span: [start, end]}.
        word_timing_words: list of dicts [{word, start_ms, end_ms, ...}] in spoken order.
        total_duration_ms: total audio duration in milliseconds.
        word_timing_doc: optional full word_timing document for metadata.

    Returns:
        dict with 'beats' list [{label, start, end, duration}, ...], timing_precision='word',
        and metadata.
    """
    words = word_timing_words
    if not words or not storyboard_beats:
        raise ValueError("word_timing_words and storyboard_beats must not be empty")

    total_dur_sec = total_duration_ms / 1000.0
    beat_count = len(storyboard_beats)

    def _gap_midpoint(word_idx):
        """Return the midpoint of the gap between word_idx-1 and word_idx, in ms.

        If the gap is <= 0 (flush words), returns the end of word_idx-1.
        Boundary is the gap midpoint: (prev_end + next_start) / 2.
        Tie-break for flush words (gap <= 0): boundary at prev_end, keeping words intact.
        """
        if word_idx <= 0:
            return 0.0
        if word_idx >= len(words):
            return total_duration_ms
        prev_end = words[word_idx - 1]["end_ms"]
        next_start = words[word_idx]["start_ms"]
        gap = next_start - prev_end
        if gap <= 0.001:
            return prev_end
        return (prev_end + next_start) / 2.0

    # Compute boundaries at cumulative word indices from narration_word_span
    boundaries_ms = [0.0]
    for i in range(1, beat_count):
        w_idx = storyboard_beats[i].get("narration_word_span", [0, 0])[0]
        boundaries_ms.append(_gap_midpoint(w_idx))
    boundaries_ms.append(total_duration_ms)

    # Ensure monotonic
    for i in range(1, len(boundaries_ms)):
        if boundaries_ms[i] <= boundaries_ms[i - 1]:
            boundaries_ms[i] = boundaries_ms[i - 1] + 0.01

    # Build output
    beat_timings = []
    for i, b in enumerate(storyboard_beats):
        start = round(boundaries_ms[i] / 1000.0, 3)
        end = round(boundaries_ms[i + 1] / 1000.0, 3)
        beat_timings.append({
            "label": b.get("label") or b["beat_id"],
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
        })

    result = {
        "total_duration": round(total_dur_sec, 3),
        "beat_count": beat_count,
        "beats": beat_timings,
        "timing_precision": "word",
        "alignment_backend": word_timing_doc["metadata"]["backend"] if word_timing_doc and "metadata" in word_timing_doc else "unknown",
    }
    if word_timing_doc and "metadata" in word_timing_doc:
        result["alignment_coverage"] = word_timing_doc["metadata"].get("coverage")
        result["aligned_words"] = word_timing_doc["metadata"].get("aligned_words")
        result["total_words"] = word_timing_doc["metadata"].get("total_words")

    return result


def main():
    ap = argparse.ArgumentParser(description="Build a timing map from narration audio + script text.")
    ap.add_argument("audio", help="Path to narration audio file (MP3/WAV)")
    ap.add_argument("--script", default=None, help="Script JSON (extracts segment texts as beats)")
    ap.add_argument("--storyboard", default=None, help="Storyboard JSON (maps beat_id → [start,end] using narration_text)")
    ap.add_argument("--text", default=None, help="Raw text to split into beats (alternative to --script)")
    ap.add_argument("--output", "-o", default=None, help="Output timing map JSON (default: stdout)")
    ap.add_argument("--noise-db", type=int, default=SILENCE_THRESH_DB, help=f"Silence threshold dB (default {SILENCE_THRESH_DB})")
    ap.add_argument("--min-silence", type=float, default=SILENCE_MIN_DUR, help=f"Min silence duration (default {SILENCE_MIN_DUR})")
    args = ap.parse_args()

    audio = Path(args.audio)
    if not audio.exists():
        print(f"ERROR: audio file not found: {audio}", file=sys.stderr)
        sys.exit(1)

    if args.storyboard:
        sb = json.loads(Path(args.storyboard).read_text())
        beats = sb.get("beats", [])
        timing = build_storyboard_timing_map(audio, beats, args.noise_db, args.min_silence)
    else:
        if args.script:
            beats = extract_beats_from_script(args.script)
        elif args.text:
            subs = split_text_into_beats(args.text)
            beats = [{"segment_id": "input", "beat_index": i, "text": s, "word_count": len(s.split())}
                     for i, s in enumerate(subs)]
        else:
            beats = []
        timing = build_timing_map(audio, beats, args.noise_db, args.min_silence)

    out = json.dumps(timing, indent=2)
    if args.output:
        Path(args.output).write_text(out)
        print(f"Timing map: {args.output} ({timing.get('beat_count', timing.get('audio_segments_detected', '?'))} beats, "
              f"{len(timing.get('flags', []))} flags)")
    else:
        print(out)

    if timing.get("flags"):
        print(f"\nFlags ({len(timing['flags'])}):", file=sys.stderr)
        for f in timing["flags"]:
            print(f"  ⚠ {f}", file=sys.stderr)


if __name__ == "__main__":
    main()
