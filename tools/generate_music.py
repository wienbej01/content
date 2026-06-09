#!/usr/bin/env python3
"""generate_music.py — synthesize an ORIGINAL piano + violin music bed.

Why this exists
---------------
Faceless brand videos need a music bed, but downloading third-party tracks
risks Content-ID claims / demonetization (BUSINESS_PLAN Ch.6/17 non-negotiable).
So we GENERATE original music: zero licensing risk, owned IP, continuous (no
audible loop), tunable to the brand mood (elegant, dignified — "old money").

Instruments (physically-motivated synthesis, not plain sine pads):
  - PIANO: struck string. Fast attack, per-harmonic exponential decay (high
    harmonics die faster), slight inharmonicity (stretched partials) — the
    detail that makes a piano sound like a piano, not a synth. Chords are
    gently rolled (arpeggiated onsets) for an elegant touch.
  - VIOLIN: bowed string. Sawtooth-rich spectrum, slow swelling attack, and
    vibrato (pitch + amplitude). Sustains the top voice as a singing line.

Arrangement: piano plays the chord voicing (rolled, decaying); violin sustains
the upper notes over it. Hall reverb + gentle low-pass for warmth and space.

Usage
-----
  python3 tools/generate_music.py --duration 26 --out bed.wav
  python3 tools/generate_music.py --duration 26 --out bed.wav --mood pensive
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48000

_NOTE = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4,
         "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}


def freq(note: str, octave: int = 4) -> float:
    semis = _NOTE[note] + (octave - 4) * 12
    return 440.0 * (2 ** (semis / 12.0))


PROGRESSIONS = {
    # elegant / dignified — Imaj7 - vi7 - IVmaj7 - V7
    "calm": [
        [("D", 3), ("F#", 4), ("A", 4), ("C#", 5)],
        [("B", 2), ("D", 4), ("F#", 4), ("A", 4)],
        [("G", 2), ("B", 3), ("D", 4), ("F#", 4)],
        [("A", 2), ("C#", 4), ("E", 4), ("G", 4)],
    ],
    # contemplative minor — i7 - VImaj7 - IIImaj7 - V7
    "pensive": [
        [("A", 2), ("C", 4), ("E", 4), ("G", 4)],
        [("F", 2), ("A", 3), ("C", 4), ("E", 4)],
        [("C", 3), ("E", 4), ("G", 4), ("B", 4)],
        [("G", 2), ("B", 3), ("D", 4), ("F", 4)],
    ],
}

CHORD_SECONDS = 6.0
CHORD_XFADE = 2.5
ROLL_MS = 45        # piano arpeggio-roll stagger per note


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
def piano_note(f: float, n: int, vel: float = 1.0) -> np.ndarray:
    """Struck-string piano tone: fast attack, per-harmonic exponential decay,
    slight inharmonicity. n samples."""
    t = np.arange(n) / SR
    B = 0.0004                      # inharmonicity coefficient
    out = np.zeros(n)
    n_partials = 10
    for h in range(1, n_partials + 1):
        fh = f * h * np.sqrt(1.0 + B * h * h)
        if fh > SR / 2:
            break
        amp = (0.62 ** (h - 1)) / (1.0 + 0.15 * h)   # spectral tilt
        tau = max(0.28, 3.2 / h)                     # high harmonics decay faster
        env = np.exp(-t / tau)
        out += amp * env * np.sin(2 * np.pi * fh * t)
    # fast strike attack (~4 ms)
    a = int(0.004 * SR)
    out[:a] *= np.linspace(0, 1, a)
    return out * vel


def violin_note(f: float, n: int, vel: float = 1.0) -> np.ndarray:
    """Bowed-string violin tone: sawtooth-rich spectrum, slow attack, vibrato."""
    t = np.arange(n) / SR
    # vibrato eases in after ~0.35 s
    vib_rate, vib_depth = 5.6, 0.005
    onset = np.clip((t - 0.35) / 0.4, 0, 1)
    inst_f = f * (1.0 + vib_depth * onset * np.sin(2 * np.pi * vib_rate * t))
    phase = 2 * np.pi * np.cumsum(inst_f) / SR
    saw = np.zeros(n)
    h = 1
    while f * h < SR / 2 and h <= 16:
        saw += (1.0 / h) * np.sin(h * phase)
        h += 1
    # bowed amplitude shimmer
    saw *= 1.0 + 0.05 * np.sin(2 * np.pi * 4.3 * t)
    # swell attack / release envelope
    env = np.ones(n)
    att = int(0.16 * SR)
    rel = int(0.45 * SR)
    env[:att] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, att))
    env[-rel:] = np.linspace(1, 0, rel) ** 1.3
    return saw * env * vel * 0.5


# ---------------------------------------------------------------------------
# DSP helpers (vectorized)
# ---------------------------------------------------------------------------
def lowpass_fft(x: np.ndarray, cutoff: float, order: int = 4) -> np.ndarray:
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(len(x), 1.0 / SR)
    H = 1.0 / np.sqrt(1.0 + (fr / cutoff) ** (2 * order))
    return np.fft.irfft(X * H, n=len(x))


def reverb(x: np.ndarray, mix: float = 0.28) -> np.ndarray:
    out = x.copy()
    for delay_ms, gain in [(43, 0.36), (61, 0.30), (83, 0.24), (113, 0.18), (149, 0.12)]:
        d = int(SR * delay_ms / 1000)
        echo = np.zeros_like(x)
        echo[d:] = x[:-d] * gain
        out += echo
    return (1 - mix) * x + mix * (out / 1.8)


# ---------------------------------------------------------------------------
# Arrangement
# ---------------------------------------------------------------------------
def build_channel(prog, total_n: int, detune_cents: float) -> np.ndarray:
    chord_n = int(CHORD_SECONDS * SR)
    xf_n = int(CHORD_XFADE * SR)
    step = chord_n - xf_n
    roll = int(ROLL_MS / 1000 * SR)
    buf = np.zeros(total_n + chord_n + SR, dtype=np.float64)

    fade_in = np.linspace(0, 1, xf_n)
    fade_out = np.linspace(1, 0, xf_n)
    dt = 2 ** (detune_cents / 1200.0)

    pos = 0
    idx = 0
    while pos < total_n:
        chord = prog[idx % len(prog)]
        seg = np.zeros(chord_n)

        # PIANO: sub-octave root + rolled chord voicing, decaying
        root_f = freq(*chord[0]) / 2 * dt
        seg += 0.5 * piano_note(root_f, chord_n, vel=0.9)
        for j, (note, octv) in enumerate(chord):
            ns = piano_note(freq(note, octv) * dt, chord_n - j * roll, vel=0.85)
            seg[j * roll: j * roll + len(ns)] += ns

        # VIOLIN: sustain the top two voices as a singing line over the piano
        for (note, octv) in chord[-2:]:
            seg += 0.55 * violin_note(freq(note, octv) * dt, chord_n, vel=0.8)

        # crossfade envelope at the chord seams
        env = np.ones(chord_n)
        env[:xf_n] *= fade_in
        env[-xf_n:] *= fade_out
        seg *= env

        buf[pos:pos + chord_n] += seg
        pos += step
        idx += 1
    return buf[:total_n]


def generate(duration: float, key_mood: str = "calm", seed: int | None = 7) -> np.ndarray:
    if seed is not None:
        np.random.seed(seed)
    prog = PROGRESSIONS.get(key_mood, PROGRESSIONS["calm"])
    n = int(duration * SR)

    left = build_channel(prog, n, +5.0)
    right = build_channel(prog, n, -5.0)

    # warmth + hall space
    left = reverb(lowpass_fft(left, 3200))
    right = reverb(lowpass_fft(right, 3200))

    # overall swell in / fade out
    env = np.ones(n)
    fin, fout = int(2.2 * SR), int(2.0 * SR)
    env[:fin] = np.linspace(0, 1, fin) ** 1.4
    env[-fout:] = np.linspace(1, 0, fout) ** 1.4
    left *= env
    right *= env

    stereo = np.stack([left, right], axis=1)
    peak = np.max(np.abs(stereo)) or 1.0
    stereo = stereo / peak * (10 ** (-3 / 20))   # -3 dBFS peak
    return stereo


def write_wav(stereo: np.ndarray, path: Path):
    pcm = np.clip(stereo, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an original piano+violin music bed.")
    ap.add_argument("--duration", type=float, required=True, help="seconds")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mood", default="calm", choices=sorted(PROGRESSIONS))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    stereo = generate(args.duration, args.mood, args.seed)
    write_wav(stereo, Path(args.out))
    print(f"wrote {args.out}  ({len(stereo)/SR:.1f}s, {args.mood}, piano+violin, original)")


if __name__ == "__main__":
    main()
