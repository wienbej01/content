#!/usr/bin/env python3
"""Audio continuity evaluation for S13-T004.

Evaluates audio seams between hero/b-roll clips for an assembled video.

Three checks, each with a different (honest) signal source:

- **Gaps**: silent periods between speech regions, measured from the decoded
  audio waveform. Fails if any gap exceeds ``gap_threshold_ms`` (default 500 ms).

- **Overlaps**: overlapping audio-segment intervals, measured DETERMINISTICALLY
  from segment timeline metadata. Energy-based waveform detection cannot see two
  mixed voices as separate regions, so overlap is checked against the timeline.
  Fails if any two segments overlap by more than ``overlap_threshold_ms``.

- **Clicks**: transient discontinuities at segment joins ("island seams"),
  measured from the decoded audio at the known seam positions derived from the
  segment timeline. RMS-window detection cannot see short transients (they are
  averaged away), so clicks are measured as peak / local-RMS at each seam.
  Fails if any seam exceeds ``click_threshold_db``.

Overlap and click checks require segment timeline metadata (``segments``).
When ``segments`` is not supplied only gap detection runs and overlap/click are
reported as ``skipped`` — this is intentional and explicit, never a silent pass.

Usage:
  python3 scripts/evals/eval_audio_continuity.py <assembled_video.mp4>
  python3 scripts/evals/eval_audio_continuity.py <video.mp4> --segments segs.json
  python3 scripts/evals/eval_audio_continuity.py <video.mp4> --out report.json
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import numpy as np


SR = 16000  # Normalized decode sample rate
GAP_THRESHOLD_MS = 500      # Maximum allowed silent gap between speech regions
OVERLAP_THRESHOLD_MS = 0    # Any segment-timeline overlap fails
CLICK_THRESHOLD_DB = 20     # Maximum allowed peak/local-RMS at a seam
CLICK_REF_MS = 30           # Reference window length before a seam
CLICK_SEARCH_MS = 15        # Half-width search window around a nominal seam
CLICK_REF_FLOOR = 50        # int16 units; below this the reference is "silence"


# ---------------------------------------------------------------------------
# Audio loading
# ---------------------------------------------------------------------------
def _load_audio(path: Path, target_sr: int = SR) -> Tuple[np.ndarray, float]:
    """Decode the audio track of a media file to mono PCM at ``target_sr``.

    Returns ``(samples_float64, duration_seconds)``. On any failure (missing
    file, no audio stream, ffmpeg error) returns ``(empty, 0.0)`` so the caller
    can report an explicit failure rather than crash.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(path),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", str(target_sr), "-ac", "1",
                tmp.name,
            ],
            capture_output=True, check=True, timeout=60,
        )
        data = Path(tmp.name).read_bytes()
        di = data.find(b"data")
        if di < 0:
            return np.array([]), 0.0
        hd = int.from_bytes(data[di + 4:di + 8], "little")
        raw = data[di + 8:di + 8 + hd]
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        return samples, len(samples) / target_sr
    except (subprocess.CalledProcessError, FileNotFoundError):
        return np.array([]), 0.0
    except Exception:
        return np.array([]), 0.0
    finally:
        Path(tmp.name).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Gap detection (raw audio)
# ---------------------------------------------------------------------------
def _detect_silence_regions(audio: np.ndarray, sr: int = SR,
                            threshold_db: float = -50.0,
                            min_duration: float = 0.1) -> List[Tuple[float, float]]:
    """Return silent regions as ``(start_sec, end_sec)``."""
    if len(audio) == 0:
        return []
    max_amplitude = np.max(np.abs(audio)) or 1.0
    threshold_amp = 10 ** (threshold_db / 20.0) * max_amplitude

    below = np.abs(audio) < threshold_amp
    regions: List[Tuple[float, float]] = []
    in_silence = False
    start = 0
    for i, is_silent in enumerate(below):
        if is_silent and not in_silence:
            start = i / sr
            in_silence = True
        elif not is_silent and in_silence:
            end = i / sr
            if end - start >= min_duration:
                regions.append((start, end))
            in_silence = False
    if in_silence:
        end = len(below) / sr
        if end - start >= min_duration:
            regions.append((start, end))
    return regions


def _detect_speech_regions(audio: np.ndarray, sr: int = SR,
                           threshold_db: float = -50.0,
                           min_duration: float = 0.1) -> List[Tuple[float, float]]:
    """Return speech regions (complement of silence regions)."""
    if len(audio) == 0:
        return []
    silence = _detect_silence_regions(audio, sr, threshold_db, min_duration)
    total = len(audio) / sr
    if not silence:
        return [(0.0, total)]

    speech: List[Tuple[float, float]] = []
    if silence[0][0] > min_duration:
        speech.append((0.0, silence[0][0]))
    for i in range(len(silence) - 1):
        a, b = silence[i][1], silence[i + 1][0]
        if b - a >= min_duration:
            speech.append((a, b))
    if silence[-1][1] < total - min_duration:
        speech.append((silence[-1][1], total))
    return speech


def detect_gaps(audio: np.ndarray, sr: int = SR,
                threshold_ms: float = GAP_THRESHOLD_MS) -> List[Dict[str, Any]]:
    """Detect silent gaps between speech regions exceeding ``threshold_ms``."""
    speech = _detect_speech_regions(audio, sr)
    gaps: List[Dict[str, Any]] = []
    for i in range(len(speech) - 1):
        gap_start = speech[i][1]
        gap_end = speech[i + 1][0]
        dur_ms = (gap_end - gap_start) * 1000
        if dur_ms > threshold_ms:
            gaps.append({
                "position_sec": round(gap_start, 3),
                "duration_ms": round(dur_ms, 1),
                "threshold_ms": threshold_ms,
            })
    return gaps


# ---------------------------------------------------------------------------
# Overlap detection (segment-timeline metadata — deterministic)
# ---------------------------------------------------------------------------
def detect_timeline_overlaps(segments: List[Dict[str, Any]],
                             threshold_ms: float = OVERLAP_THRESHOLD_MS
                             ) -> List[Dict[str, Any]]:
    """Detect overlapping segment intervals in the timeline.

    ``segments`` is a list of ``{"start": sec, "end": sec}`` (``"duration"`` is
    also accepted and converted against the previous segment's end). Returns one
    entry per overlapping pair whose overlap exceeds ``threshold_ms``.

    This is deterministic and does not depend on the audio waveform: two mixed
    voices cannot be separated by energy detection, so the timeline is the only
    honest source of overlap truth.
    """
    if not segments:
        return []

    # Normalize to explicit [start, end] intervals.
    intervals: List[Tuple[float, float]] = []
    cursor = 0.0
    for seg in segments:
        if "start" in seg and "end" in seg:
            s, e = float(seg["start"]), float(seg["end"])
        elif "start" in seg and "duration" in seg:
            s = float(seg["start"]); e = s + float(seg["duration"])
        elif "duration" in seg:
            s = cursor; e = cursor + float(seg["duration"])
            cursor = e
        else:
            continue
        if e > s:
            intervals.append((s, e))
            cursor = e

    overlaps: List[Dict[str, Any]] = []
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            a0, a1 = intervals[i]
            b0, b1 = intervals[j]
            ov_start = max(a0, b0)
            ov_end = min(a1, b1)
            dur_ms = (ov_end - ov_start) * 1000
            if dur_ms > threshold_ms:
                overlaps.append({
                    "position_sec": round(ov_start, 3),
                    "duration_ms": round(dur_ms, 1),
                    "threshold_ms": threshold_ms,
                    "segments": [i, j],
                })
    return overlaps


def _seam_positions(segments: List[Dict[str, Any]]) -> List[float]:
    """Internal boundary positions (s): where one segment ends and next begins."""
    intervals: List[Tuple[float, float]] = []
    cursor = 0.0
    for seg in segments:
        if "start" in seg and "end" in seg:
            s, e = float(seg["start"]), float(seg["end"])
        elif "start" in seg and "duration" in seg:
            s = float(seg["start"]); e = s + float(seg["duration"])
        elif "duration" in seg:
            s = cursor; e = cursor + float(seg["duration"])
            cursor = e
        else:
            continue
        if e > s:
            intervals.append((s, e)); cursor = e
    # seams are the internal boundaries (every end except the last)
    return [interval[1] for interval in intervals[:-1]]


# ---------------------------------------------------------------------------
# Click detection (raw audio at known seams — evidence-based)
# ---------------------------------------------------------------------------
def detect_seam_clicks(audio: np.ndarray, sr: int,
                       seam_positions_sec: List[float],
                       threshold_db: float = CLICK_THRESHOLD_DB,
                       ref_ms: float = CLICK_REF_MS,
                       search_ms: float = CLICK_SEARCH_MS,
                       ref_floor: float = CLICK_REF_FLOOR
                       ) -> List[Dict[str, Any]]:
    """Detect transient clicks at known segment seams.

    At each nominal seam position, search ±``search_ms`` for the peak sample and
    compare it to the RMS of the ``ref_ms`` window immediately preceding the
    search region. A click is flagged when the peak exceeds the local reference
    by more than ``threshold_db`` AND the reference is above ``ref_floor`` (a
    silence reference is unreliable and reported as ambiguous, not a click).
    """
    if len(audio) == 0 or not seam_positions_sec:
        return []

    ref_n = int(ref_ms / 1000 * sr)
    search_n = int(search_ms / 1000 * sr)

    clicks: List[Dict[str, Any]] = []
    for seam in seam_positions_sec:
        center = int(seam * sr)
        lo = center - search_n
        hi = center + search_n
        ref_start = lo - ref_n
        if ref_start < 0 or hi >= len(audio):
            continue
        search_region = audio[lo:hi]
        peak = float(np.max(np.abs(search_region)))
        ref_region = audio[ref_start:lo]
        ref_rms = float(np.sqrt(np.mean(ref_region ** 2)))

        if ref_rms < ref_floor:
            # Reference is silence: ratio is unreliable; record as ambiguous.
            clicks.append({
                "position_sec": round(seam, 3),
                "peak": round(peak, 0),
                "ref_rms": round(ref_rms, 1),
                "amplitude_change_db": None,
                "type": "ambiguous_silence_reference",
                "note": "reference window is silence; cannot measure transient",
            })
            continue

        ratio_db = 20 * np.log10(peak / ref_rms)
        if ratio_db > threshold_db:
            clicks.append({
                "position_sec": round(seam, 3),
                "peak": round(peak, 0),
                "ref_rms": round(ref_rms, 1),
                "amplitude_change_db": round(ratio_db, 1),
                "type": "seam_transient",
            })
    return clicks


# ---------------------------------------------------------------------------
# Top-level evaluation
# ---------------------------------------------------------------------------
def evaluate_audio_continuity(video_path: Path,
                             segments: Optional[List[Dict[str, Any]]] = None,
                             gap_threshold_ms: float = GAP_THRESHOLD_MS,
                             overlap_threshold_ms: float = OVERLAP_THRESHOLD_MS,
                             click_threshold_db: float = CLICK_THRESHOLD_DB
                             ) -> Dict[str, Any]:
    """Evaluate audio continuity of an assembled video.

    Args:
        video_path: assembled video file.
        segments: optional timeline ``[{"start": sec, "end": sec}, ...]``. When
            supplied, overlap + click checks run; otherwise they are skipped.
        gap_threshold_ms: max allowed silent gap between speech regions.
        overlap_threshold_ms: max allowed segment-timeline overlap.
        click_threshold_db: max allowed peak/local-RMS at a seam.

    Returns a dict with ``status`` (``pass``/``fail``), per-check results, and
    ``checks_run`` describing exactly which checks executed (so a caller can
    never mistake a skipped check for a passed one).
    """
    if not video_path.exists():
        return {
            "status": "fail",
            "issues": [f"Video file does not exist: {video_path}"],
            "video_path": str(video_path),
            "checks_run": [],
        }

    audio, duration = _load_audio(video_path)
    if len(audio) == 0:
        return {
            "status": "fail",
            "issues": ["Failed to extract audio from video (no audio stream or decode error)"],
            "video_path": str(video_path),
            "duration_sec": 0,
            "checks_run": [],
        }

    issues: List[str] = []
    checks_run: List[str] = []
    check_status: Dict[str, str] = {}

    # --- Gap detection (always runs on raw audio) ---
    gaps = detect_gaps(audio, SR, gap_threshold_ms)
    checks_run.append("gap_detection")
    check_status["gap_detection"] = "fail" if gaps else "pass"
    for g in gaps:
        issues.append(
            f"Audio gap at {g['position_sec']:.2f}s: {g['duration_ms']:.1f}ms "
            f"(exceeds {g['threshold_ms']}ms threshold)"
        )

    # --- Overlap detection (requires timeline metadata) ---
    if segments is not None:
        overlaps = detect_timeline_overlaps(segments, overlap_threshold_ms)
        checks_run.append("overlap_detection")
        check_status["overlap_detection"] = "fail" if overlaps else "pass"
        for o in overlaps:
            issues.append(
                f"Segment-timeline overlap at {o['position_sec']:.2f}s: "
                f"{o['duration_ms']:.1f}ms between segments {o['segments']} "
                f"(exceeds {o['threshold_ms']}ms threshold)"
            )
    else:
        overlaps = []
        check_status["overlap_detection"] = "skipped_no_segments"

    # --- Click detection (requires timeline metadata for seam positions) ---
    if segments is not None:
        seams = _seam_positions(segments)
        clicks = detect_seam_clicks(audio, SR, seams, click_threshold_db)
        checks_run.append("click_detection")
        flagged = [c for c in clicks if c.get("amplitude_change_db") is not None]
        check_status["click_detection"] = "fail" if flagged else "pass"
        for c in clicks:
            if c.get("amplitude_change_db") is not None:
                issues.append(
                    f"Seam click at {c['position_sec']:.2f}s: "
                    f"{c['amplitude_change_db']:.1f}dB peak/refRMS "
                    f"(exceeds {click_threshold_db}dB threshold)"
                )
            else:
                issues.append(
                    f"Seam at {c['position_sec']:.2f}s: {c['note']}"
                )
    else:
        clicks = []
        check_status["click_detection"] = "skipped_no_segments"

    return {
        "status": "pass" if not issues else "fail",
        "video_path": str(video_path),
        "duration_sec": round(duration, 2),
        "checks_run": checks_run,
        "check_status": check_status,
        "issues": issues,
        "gaps": gaps,
        "overlaps": overlaps,
        "clicks": clicks,
        "segments_provided": segments is not None,
        "thresholds": {
            "gap_ms": gap_threshold_ms,
            "overlap_ms": overlap_threshold_ms,
            "click_db": click_threshold_db,
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audio continuity evaluation for island joins")
    ap.add_argument("video", type=Path, help="Assembled video file to evaluate")
    ap.add_argument("--segments", type=Path, default=None,
                    help="JSON file with segment timeline [{'start':..,'end':..}, ...]")
    ap.add_argument("--gap-threshold-ms", type=float, default=GAP_THRESHOLD_MS)
    ap.add_argument("--overlap-threshold-ms", type=float, default=OVERLAP_THRESHOLD_MS)
    ap.add_argument("--click-threshold-db", type=float, default=CLICK_THRESHOLD_DB)
    ap.add_argument("--out", type=Path, help="Output JSON report path")
    args = ap.parse_args(argv)

    segments = None
    if args.segments:
        segments = json.loads(args.segments.read_text())

    result = evaluate_audio_continuity(
        args.video, segments=segments,
        gap_threshold_ms=args.gap_threshold_ms,
        overlap_threshold_ms=args.overlap_threshold_ms,
        click_threshold_db=args.click_threshold_db,
    )

    out_path = args.out or Path(
        f"reports/karpathy_loop/s13/S13_T004/audio_continuity_{args.video.stem}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))

    print(f"Audio continuity evaluation: {result['status'].upper()}")
    print(f"  Video: {args.video}")
    print(f"  Duration: {result.get('duration_sec', 0):.2f}s")
    print(f"  Checks run: {result.get('checks_run', [])}")
    print(f"  Check status: {result.get('check_status', {})}")
    print(f"  Gaps: {len(result.get('gaps', []))}  "
          f"Overlaps: {len(result.get('overlaps', []))}  "
          f"Clicks: {len([c for c in result.get('clicks', []) if c.get('amplitude_change_db') is not None])}")

    if result["status"] == "fail":
        print("\nIssues:")
        for issue in result.get("issues", []):
            print(f"  - {issue}")
    print(f"\nReport saved to: {out_path}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
