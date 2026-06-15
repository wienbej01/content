#!/usr/bin/env python3
"""emphasis_pause.py — clean pre-payoff pauses by EXTENDING existing silence gaps.

The right way to add a deliberate pause before a hero/payoff line WITHOUT the
prosody distortion of ElevenLabs <break> tags: find the natural silence gap that
already exists between the preceding sentence and the payoff, and insert extra
silence INTO that gap. Because both sides are already silent, there is no
waveform discontinuity — no audible seam (unlike cutting through speech).

Used by the takeaway-emphasis system to give hero points room to land.

Usage (library):
  from emphasis_pause import add_pauses_at_silences
  add_pauses_at_silences(master_mp3, [(target_sec, pause_len), ...])
"""
import re
import subprocess
from pathlib import Path


def _duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def _silences(path, noise_db=-35, min_dur=0.20):
    r = subprocess.run(["ffmpeg", "-i", str(path), "-af",
                        f"silencedetect=n={noise_db}dB:d={min_dur}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def _nearest_silence_midpoint(silences, target, window=1.2):
    """Find the silence gap whose span is closest to (and ideally just before) target."""
    best, best_d = None, window + 1
    for s, e in silences:
        mid = (s + e) / 2
        # prefer a gap that ends at/just before the target (the gap before the line)
        d = abs(e - target) if s <= target else abs(mid - target)
        if d < best_d and d <= window:
            best, best_d = (s + e) / 2, d
    return best


def add_pauses_at_silences(master_path, pauses, noise_db=-35):
    """Insert silence into existing gaps. pauses: list of (target_sec, pause_len).
    Inserts are applied back-to-front so earlier offsets stay valid.
    Returns the new duration. No-op for any pause whose gap can't be found."""
    master_path = Path(master_path)
    sil = _silences(master_path, noise_db)
    # Resolve each target to an actual silence midpoint
    points = []
    for target, plen in pauses:
        mid = _nearest_silence_midpoint(sil, target)
        if mid is not None and plen > 0:
            points.append((mid, plen))
    if not points:
        return _duration(master_path)
    points.sort(key=lambda x: x[0], reverse=True)

    work = master_path.with_suffix(".work.mp3")
    subprocess.run(["cp", str(master_path), str(work)], check=True)
    tmp = master_path.parent
    for at, plen in points:
        head = tmp / "_eh.wav"
        tail = tmp / "_et.wav"
        s = tmp / "_es.wav"
        subprocess.run(["ffmpeg", "-y", "-i", str(work), "-filter_complex",
                        f"[0:a]atrim=0:{at},asetpts=N/SR/TB[h]", "-map", "[h]",
                        "-ar", "44100", str(head)], capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(work), "-filter_complex",
                        f"[0:a]atrim=start={at},asetpts=N/SR/TB[t]", "-map", "[t]",
                        "-ar", "44100", str(tail)], capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"anullsrc=r=44100:cl=mono:d={plen}", "-ar", "44100", str(s)],
                       capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(head), "-i", str(s), "-i", str(tail),
                        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[o]",
                        "-map", "[o]", "-c:a", "libmp3lame", "-q:a", "2", str(work)],
                       capture_output=True)
        for f in (head, tail, s):
            f.unlink(missing_ok=True)
    subprocess.run(["cp", str(work), str(master_path)], check=True)
    work.unlink(missing_ok=True)
    return _duration(master_path)
