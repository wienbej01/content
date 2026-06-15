#!/usr/bin/env python3
"""normalize_pacing.py — automatic audio pacing normalization (system stage).

Codifies the manual calibration learnings so no script needs hand-tuning:

  1. WPS NORMALIZATION: detect spoken phrases whose words-per-second deviates from
     the target band and time-stretch JUST that phrase (cuts taken inside the
     surrounding silence gaps -> no seam). Fixes the "short punchy sentence rushed
     by ElevenLabs" problem (e.g. a 4-word payoff at 4.0 WPS vs 2.4 target).

  2. PAUSE NORMALIZATION: detect silence gaps longer than a max and trim them to a
     natural length (trim taken from the MIDDLE of the silence -> no seam). Fixes the
     "em-dash / dramatic comma renders an over-long pause" problem.

Operates on ONE continuous master (never re-generates, never splices through
speech). Uses silence boundaries as edit points so there is never an audible cut.

Usage:
  python3 scripts/normalize_pacing.py <master.mp3> --words <N> [--target-wps 2.4]
  (library) from normalize_pacing import normalize_master
"""
import argparse
import os
import re
import subprocess
from pathlib import Path

TARGET_WPS = 2.4
WPS_FAST_RATIO = 1.30      # phrase >30% over target -> slow it
MAX_PAUSE_SEC = 0.95       # silence gaps longer than this get trimmed
NATURAL_PAUSE_SEC = 0.45   # trim long gaps down to this
SILENCE_DB = -35
MIN_GAP = 0.15


def _dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def _silences(p):
    r = subprocess.run(["ffmpeg", "-i", str(p), "-af",
                        f"silencedetect=n={SILENCE_DB}dB:d={MIN_GAP}", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", r.stderr)]
    e = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", r.stderr)]
    return sorted(zip(s, e))


def _speech_spans(p):
    total = _dur(p)
    sil = _silences(p)
    spans, prev = [], 0.0
    for s, e in sil:
        if s - prev > 0.1:
            spans.append((prev, s))
        prev = e
    if total - prev > 0.1:
        spans.append((prev, total))
    return spans, sil


def _apply_edits(master, edits):
    """edits: list of {a, b, tempo}. Span a..b replaced by itself at tempo
    (tempo=None deletes the span). Edit points lie in silence. Applied back-to-front."""
    edits = sorted(edits, key=lambda x: x["a"], reverse=True)
    pd = Path(master).parent
    for ed in edits:
        a, b, tempo = ed["a"], ed["b"], ed.get("tempo")
        h, m, t = pd / "_nh.wav", pd / "_nm.wav", pd / "_nt.wav"
        subprocess.run(["ffmpeg", "-y", "-i", str(master), "-filter_complex",
                        f"[0:a]atrim=0:{a},asetpts=N/SR/TB[x]", "-map", "[x]", "-ar", "44100", str(h)],
                       capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(master), "-filter_complex",
                        f"[0:a]atrim=start={b},asetpts=N/SR/TB[x]", "-map", "[x]", "-ar", "44100", str(t)],
                       capture_output=True)
        parts = [h]
        if tempo is not None:
            subprocess.run(["ffmpeg", "-y", "-i", str(master), "-filter_complex",
                            f"[0:a]atrim={a}:{b},atempo={tempo},asetpts=N/SR/TB[x]", "-map", "[x]",
                            "-ar", "44100", str(m)], capture_output=True)
            parts.append(m)
        parts.append(t)
        n = len(parts)
        inputs = []
        for pp in parts:
            inputs += ["-i", str(pp)]
        fc = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[o]"
        subprocess.run(["ffmpeg", "-y"] + inputs + ["-filter_complex", fc, "-map", "[o]",
                        "-c:a", "libmp3lame", "-q:a", "2", str(pd / "_nout.mp3")], capture_output=True)
        os.replace(str(pd / "_nout.mp3"), str(master))
        for f in (h, m, t):
            f.unlink(missing_ok=True)


def normalize_master(master, total_words, target_wps=TARGET_WPS,
                     max_pause=MAX_PAUSE_SEC, dry_run=False):
    """Normalize WPS outliers + over-long pauses. Returns a report dict."""
    master = str(master)
    spans, sil = _speech_spans(master)
    span_durs = [e - s for s, e in spans]
    tot = sum(span_durs) or 1
    span_words = [max(1, round(total_words * d / tot)) for d in span_durs]

    edits, wps_fixes = [], []
    for (s, e), w in zip(spans, span_words):
        d = e - s
        wps = w / d if d else 0
        if wps > target_wps * WPS_FAST_RATIO and d > 0.4:
            desired = w / target_wps
            tempo = max(0.5, d / desired)
            edits.append({"a": round(max(0, s - 0.10), 3), "b": round(e + 0.10, 3),
                          "tempo": round(tempo, 3)})
            wps_fixes.append({"span": [round(s, 2), round(e, 2)], "wps": round(wps, 2),
                              "tempo": round(tempo, 3)})

    pause_fixes = []
    for s, e in sil:
        gap = e - s
        if gap > max_pause:
            trim = gap - NATURAL_PAUSE_SEC
            mid = (s + e) / 2
            edits.append({"a": round(mid - trim / 2, 3), "b": round(mid + trim / 2, 3), "tempo": None})
            pause_fixes.append({"gap": [round(s, 2), round(e, 2)], "len": round(gap, 2),
                                "trimmed_to": NATURAL_PAUSE_SEC})

    report = {"target_wps": target_wps, "wps_fixes": wps_fixes, "pause_fixes": pause_fixes,
              "edits": len(edits)}
    if not dry_run and edits:
        _apply_edits(master, edits)
        report["new_duration"] = round(_dur(master), 2)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Normalize audio pacing (WPS + pauses).")
    ap.add_argument("master")
    ap.add_argument("--words", type=int, required=True, help="Total spoken word count")
    ap.add_argument("--target-wps", type=float, default=TARGET_WPS)
    ap.add_argument("--max-pause", type=float, default=MAX_PAUSE_SEC)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    rep = normalize_master(args.master, args.words, args.target_wps, args.max_pause, args.dry_run)
    print(f"  pacing: {len(rep['wps_fixes'])} WPS fixes, {len(rep['pause_fixes'])} pause fixes"
          f"{' (dry-run)' if args.dry_run else ''}")
    for f in rep["wps_fixes"]:
        print(f"    WPS {f['wps']} @ {f['span']} -> tempo {f['tempo']}")
    for f in rep["pause_fixes"]:
        print(f"    pause {f['len']}s @ {f['gap']} -> {f['trimmed_to']}s")
    if rep.get("new_duration"):
        print(f"  new duration: {rep['new_duration']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
