#!/usr/bin/env python3
"""TKT-104: SyncNet scorer drift check + calibration pin.

Imports the scorer from the PPQ sprint (scripts/sync_scorer/scorer.py) and runs
it on a set of fixture clips to verify offsets match pinned expected values.

Outputs a calibration report to `reports/tkt104-calibration.json`.
Exits 0 if offsets are within tolerance (no drift).
Exits 2 if offsets deviate beyond tolerance (drift detected — BLOCKED).

Usage:
    python3 scripts/evals/check_sync_scorer_drift.py --dir <fixture_dir> --tolerance 40
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.sync_scorer.scorer import FixtureSyncBackend, SyncScore

# Pinned baseline offsets from PPQ TKT-104 calibration (ms per fixture clip)
_PINNED = {
    "freeze_clip": {"offset_ms": 10.0, "confidence": 0.80, "face_track_found": True},
    "moving_clip": {"offset_ms": 15.0, "confidence": 0.75, "face_track_found": True},
    "text_clip":   {"offset_ms": 20.0, "confidence": 0.70, "face_track_found": True},
    "face_clip":   {"offset_ms": 12.0, "confidence": 0.85, "face_track_found": True},
}

_TOLERANCE_MS = 40.0


def _probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _generate_fixture(tmpdir: Path, name: str) -> Path:
    """Generate a deterministic synthetic MP4 clip per fixture name."""
    out = tmpdir / f"{name}.mp4"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    specs = {
        "freeze_clip": {"color": "c=blue", "rate": "1", "dur": "5"},
        "moving_clip": {"color": "testsrc", "rate": "24", "dur": "5"},
        "text_clip":   {"color": "c=darkblue", "rate": "1", "dur": "5"},
        "face_clip":   {"color": "c= darkred", "rate": "1", "dur": "5"},
    }
    spec = specs.get(name, {"color": "c=blue", "rate": "1", "dur": "5"})
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color={spec['color']}:s=320x240:d={spec['dur']}:r={spec['rate']}",
         "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=16000:d={spec['dur']}",
         "-shortest", str(out)],
        check=True,
    )
    return out


def _make_silent_audio(tmpdir: Path, video: Path) -> Path:
    out = tmpdir / f"{video.stem}_audio.wav"
    if out.exists():
        return out
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", str(out)],
        check=True,
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="TKT-104 SyncNet drift check")
    ap.add_argument("--fixtures", default=[], nargs="*",
                    help="Fixture clip names to check (default: built-in set)")
    ap.add_argument("--tolerance", type=float, default=_TOLERANCE_MS,
                    help="Tolerance in ms")
    ap.add_argument("--json", default="reports/tkt104-calibration.json")
    ap.add_argument("--pin-file", default="configs/lipsync_checker.pin",
                    help="JSON file containing pinned offsets")
    args = ap.parse_args()

    fixtures = args.fixtures or list(_PINNED.keys())
    pin = dict(_PINNED)
    pin_path = Path(args.pin_file)
    if pin_path.exists():
        pin.update(json.loads(pin_path.read_text()))

    backend = FixtureSyncBackend()
    if not backend.availability():
        print("SKIP: Fixture backend not available", file=sys.stderr)
        return 0

    tmpdir = Path(tempfile.mkdtemp(prefix="tkt104_drift_"))
    results = []
    drift_detected = False

    for name in fixtures:
        video = _generate_fixture(tmpdir, name)
        audio = _make_silent_audio(tmpdir, video)
        score: SyncScore = backend.score(video, audio)
        expected = pin.get(name)
        if expected is None:
            continue
        error = abs(score.offset_ms - expected["offset_ms"])
        passed = error <= args.tolerance
        if not passed:
            drift_detected = True
        results.append({
            "fixture": name,
            "expected_offset_ms": expected["offset_ms"],
            "observed_offset_ms": score.offset_ms,
            "error_ms": round(error, 2),
            "confidence": score.confidence,
            "face_track_found": score.face_track_found,
            "passed": passed,
        })
        status = "PASS" if passed else "DRIFT"
        print(f"  {name}: expected={expected['offset_ms']:.1f}ms "
              f"observed={score.offset_ms:.1f}ms "
              f"error={error:.1f}ms [{status}]")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scorer_backend": "FixtureSyncBackend",
        "tolerance_ms": args.tolerance,
        "drift_detected": drift_detected,
        "results": results,
        "pin_hash": hashlib.sha256(json.dumps(pin, sort_keys=True).encode()).hexdigest()[:16],
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(report, indent=2))
    print()
    print(f"Report: {args.json}")
    if drift_detected:
        print("DRIFT DETECTED — exiting non-zero")
        return 2
    print("OK — no drift detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
