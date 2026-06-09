#!/usr/bin/env python3
"""scripts/audio_qa.py — Lightweight narration quality report.

Measures duration, WPS, and structural text warnings per segment.
No new dependencies: uses only ffprobe + Python stdlib.
Optional librosa pitch analysis if already installed.

Usage:
  python3 scripts/audio_qa.py scripts/generated/james_growth_system_teaser_02.json
  python3 scripts/audio_qa.py scripts/generated/james_growth_system_teaser_02.json --output qa.json
  python3 scripts/audio_qa.py scripts/generated/james_growth_system_teaser_02.json --text-only
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Reference MP3: the gold standard for James narration pace
REF_MP3 = ROOT / "Videos/Input_audio/20260608_trailer" / \
    "ElevenLabs_2026-06-08T03_39_17_James Harrington_gen_sp105_s50_sb75_se12_b_m2.mp3"
REF_TEXT = (
    # Text from the reference MP3 (12s clip covering all 3 trailer segments)
    "You won't find my face on a stage or my name in a bestseller list. "
    "But over thirty-five years — consulting, the City, two startups, "
    "and a decade in venture capital — I've built one thing worth sharing: "
    "systems that compound. "
    "This is Leverage Mind. The unfair advantage is a system."
)
# WPS bands (from constraints.json)
WPS_CALM_MIN, WPS_CALM_MAX = 2.2, 2.6
WPS_TEASER_MIN, WPS_TEASER_MAX = 2.6, 3.0
WPS_FLAG_BELOW, WPS_FLAG_ABOVE = 2.0, 3.2
# Tail buffer minimum: narration should have at least this much natural tail
MIN_TAIL_PAD = 0.15  # seconds


def probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def word_count(text):
    return len(text.split())


def text_warnings(text, seg_id):
    """Structural/punctuation warnings for narration text."""
    warnings = []
    words = text.split()
    wc = len(words)

    # Long run-on sentences (>40 words without a break)
    sentences = re.split(r'[.!?]', text)
    for s in sentences:
        clauses = re.split(r'[,;—–]', s)
        for c in clauses:
            cwords = len(c.split())
            if cwords > 25:
                warnings.append(f"long_clause ({cwords} words without punctuation break)")
                break

    # Ends abruptly without terminal punctuation
    stripped = text.strip()
    if stripped and stripped[-1] not in '.!?':
        warnings.append("no_terminal_punctuation (may cause abrupt ending)")

    # Very short segment (<5 words)
    if wc < 5:
        warnings.append(f"very_short_segment ({wc} words)")

    return warnings


def pitch_analysis(audio_path):
    """Basic pitch metrics using librosa if available. Returns dict or None."""
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(str(audio_path), sr=16000, mono=True)
        f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=400, sr=sr)
        voiced = f0[voiced_flag]
        if len(voiced) == 0:
            return None
        return {
            "mean_pitch_hz": round(float(np.mean(voiced)), 1),
            "pitch_std_hz": round(float(np.std(voiced)), 1),
            "voiced_pct": round(float(np.sum(voiced_flag) / len(voiced_flag) * 100), 1),
        }
    except ImportError:
        return None
    except Exception:
        return None


def analyze_segment(seg_id, text, audio_path, ref_wps):
    """Analyze one segment. Returns report dict."""
    wc = word_count(text)
    dur = probe_dur(audio_path) if audio_path and Path(audio_path).exists() else None
    wps = round(wc / dur, 3) if dur and dur > 0 else None
    wps_delta = round(wps - ref_wps, 3) if wps and ref_wps else None

    warnings = text_warnings(text, seg_id)

    if wps:
        if wps < WPS_FLAG_BELOW:
            warnings.append(f"too_slow (WPS {wps:.2f} < {WPS_FLAG_BELOW})")
        elif wps > WPS_FLAG_ABOVE:
            warnings.append(f"too_fast (WPS {wps:.2f} > {WPS_FLAG_ABOVE})")
        elif wps < WPS_CALM_MIN:
            warnings.append(f"below_calm_band (WPS {wps:.2f} < {WPS_CALM_MIN})")
        elif wps > WPS_TEASER_MAX:
            warnings.append(f"above_teaser_band (WPS {wps:.2f} > {WPS_TEASER_MAX})")

    if dur and dur < 1.0:
        warnings.append("final_tail_too_short (audio < 1s — check for truncation)")

    pitch = pitch_analysis(audio_path) if audio_path and Path(audio_path).exists() else None
    if pitch:
        if pitch["pitch_std_hz"] < 8:
            warnings.append(f"too_flat (pitch std {pitch['pitch_std_hz']:.1f}Hz — may sound monotone)")
        if pitch["voiced_pct"] < 40:
            warnings.append(f"low_voiced_pct ({pitch['voiced_pct']:.0f}% — check for silence/noise)")

    entry = {
        "segment_id": seg_id,
        "word_count": wc,
        "audio_duration_s": round(dur, 3) if dur else None,
        "wps": wps,
        "ref_wps_delta": wps_delta,
        "audio_exists": Path(audio_path).exists() if audio_path else False,
        "warnings": warnings,
    }
    if pitch:
        entry["pitch"] = pitch
    return entry


def run_qa(script_path, text_only=False):
    script_path = Path(script_path).resolve()
    base = script_path.parent

    with open(script_path) as f:
        script = json.load(f)

    # Compute reference WPS from reference MP3
    ref_dur = probe_dur(REF_MP3) if REF_MP3.exists() else None
    ref_wc = word_count(REF_TEXT)
    ref_wps = round(ref_wc / ref_dur, 3) if ref_dur else None

    # Resolve narration dir
    output_dir_rel = script.get("output_dir", f"Videos/Projects/{script['project_id']}")
    output_dir = (base / output_dir_rel).resolve()
    narration_dir = output_dir / "narration"

    fmt = script.get("defaults", {}).get("format", "mp3")
    segments_report = []

    for seg in script["segments"]:
        seg_id = seg["id"]
        text = seg.get("text", "")
        mode = seg.get("audio_mode", "generated_tts")

        if text_only:
            # Text-only analysis — no audio file needed
            entry = {
                "segment_id": seg_id,
                "audio_mode": mode,
                "word_count": word_count(text),
                "warnings": text_warnings(text, seg_id),
            }
        else:
            audio_path = narration_dir / f"{seg_id}.{fmt}" if mode == "generated_tts" else None
            # For baked_in, try to find the narration file anyway (may exist)
            if audio_path is None:
                candidate = narration_dir / f"{seg_id}.{fmt}"
                if candidate.exists():
                    audio_path = candidate

            entry = analyze_segment(seg_id, text, audio_path, ref_wps)
            entry["audio_mode"] = mode

        segments_report.append(entry)

    report = {
        "project_id": script["project_id"],
        "reference": {
            "file": str(REF_MP3.name) if REF_MP3.exists() else "not_found",
            "duration_s": round(ref_dur, 3) if ref_dur else None,
            "word_count": ref_wc,
            "wps": ref_wps,
        },
        "target_settings": {
            "model": "eleven_multilingual_v2",
            "speed": 1.0,
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.12,
            "use_speaker_boost": True,
        },
        "wps_bands": {
            "calm": [WPS_CALM_MIN, WPS_CALM_MAX],
            "teaser": [WPS_TEASER_MIN, WPS_TEASER_MAX],
            "flag_below": WPS_FLAG_BELOW,
            "flag_above": WPS_FLAG_ABOVE,
        },
        "segments": segments_report,
        "summary": {
            "total_segments": len(segments_report),
            "segments_with_warnings": sum(1 for s in segments_report if s.get("warnings")),
            "total_warnings": sum(len(s.get("warnings", [])) for s in segments_report),
        },
    }
    return report


def main():
    ap = argparse.ArgumentParser(description="Lightweight narration audio QA report.")
    ap.add_argument("script", help="Path to reviewed script JSON")
    ap.add_argument("--output", default=None, help="Write JSON report to this path")
    ap.add_argument("--text-only", action="store_true", help="Structural text analysis only, no audio")
    args = ap.parse_args()

    report = run_qa(args.script, text_only=args.text_only)

    # Print summary
    ref = report["reference"]
    print(f"Reference WPS: {ref['wps']} ({ref['duration_s']}s, {ref['word_count']} words)")
    print()
    for seg in report["segments"]:
        wps_str = f"{seg['wps']:.2f} wps" if seg.get("wps") else "no audio"
        delta_str = f" (Δ{seg['ref_wps_delta']:+.2f})" if seg.get("ref_wps_delta") is not None else ""
        warn_str = f"  ⚠ {'; '.join(seg['warnings'])}" if seg.get("warnings") else ""
        print(f"  [{seg['segment_id']}] {seg['word_count']}w  {wps_str}{delta_str}{warn_str}")

    s = report["summary"]
    print(f"\n  {s['total_segments']} segments, {s['segments_with_warnings']} with warnings, "
          f"{s['total_warnings']} total warnings")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  report: {out}")
    elif not args.text_only:
        # Default: write alongside the script
        out = Path(args.script).with_name(f"{Path(args.script).stem}_audio_qa.json")
        with open(out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  report: {out}")


if __name__ == "__main__":
    main()
