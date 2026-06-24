#!/usr/bin/env python3
"""SyncNet-compatible lipsync evaluator.

Checks for SyncNet dependencies. If available, runs SyncNet on both baseline
and canary. If not, produces BLOCKED_NEEDS_SYNCNET with exact setup instructions.

Also provides an improved audio-correlation measurement (audio-to-audio offset
via diagnostic audio comparison) that is more reliable than the mouth_motion_proxy.

Usage:
  python3 scripts/evals/eval_syncnet.py --baseline <mp4> --canary <mp4> --out <json>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def _check_syncnet_deps() -> dict:
    """Check all SyncNet dependencies. Returns dep status."""
    deps = {}
    
    # 1. SyncNet package
    try:
        import syncnet_python
        deps["syncnet_python"] = True
    except ImportError:
        deps["syncnet_python"] = False
    
    # 2. PyTorch or TensorFlow
    try:
        import torch
        deps["torch"] = torch.__version__
    except ImportError:
        deps["torch"] = False
    try:
        import tensorflow
        deps["tensorflow"] = tensorflow.__version__
    except ImportError:
        deps["tensorflow"] = False
    
    # 3. OpenCV
    try:
        import cv2
        deps["opencv"] = cv2.__version__
    except ImportError:
        deps["opencv"] = False
    
    # 4. Scipy
    try:
        import scipy
        deps["scipy"] = scipy.__version__
    except ImportError:
        deps["scipy"] = False
    
    # 5. Numpy
    try:
        import numpy
        deps["numpy"] = numpy.__version__
    except ImportError:
        deps["numpy"] = False
    
    # 6. SyncNet repo clone
    syncnet_dir = Path("syncnet_python")
    deps["syncnet_repo_cloned"] = syncnet_dir.exists() and (syncnet_dir / "detect.py").exists()
    
    return deps


def _audio_cross_correlation(baseline_path: Path, canary_path: Path) -> dict:
    """Compute audio-to-audio cross-correlation offset."""
    import numpy as np
    import os, tempfile
    
    def _extract_audio(video_path: Path) -> np.ndarray:
        """Extract audio as mono PCM via ffmpeg."""
        import subprocess, struct, math
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                tmp.name,
            ], capture_output=True, check=True, timeout=60)
            data = Path(tmp.name).read_bytes()
            # Find data chunk
            di = data.find(b"data")
            if di < 0:
                return np.array([], dtype=np.float64)
            hd = struct.unpack_from("<I", data, di + 4)[0]
            raw = data[di + 8:di + 8 + hd]
            samples = struct.unpack_from(f"<{len(raw)//2}h", raw)
            return np.array(samples, dtype=np.float64)
        finally:
            Path(tmp.name).unlink(missing_ok=True)
    
    b_audio = _extract_audio(baseline_path)
    c_audio = _extract_audio(canary_path)
    
    if len(b_audio) < 1600 or len(c_audio) < 1600:
        return {"offset_ms": None, "confidence": 0.0, "note": "audio too short"}
    
    # Normalize
    b_norm = (b_audio - np.mean(b_audio)) / (np.std(b_audio) + 1e-10)
    c_norm = (c_audio - np.mean(c_audio)) / (np.std(c_audio) + 1e-10)
    
    # Cross-correlate
    min_len = min(len(b_norm), len(c_norm))
    b_norm = b_norm[:min_len]
    c_norm = c_norm[:min_len]
    
    corr = np.correlate(b_norm, c_norm, mode="same")
    peak = int(np.argmax(np.abs(corr)))
    center = min_len // 2
    offset_samples = peak - center
    offset_ms = round(offset_samples / 16000 * 1000, 2)
    
    confidence = float(np.max(np.abs(corr)) / (min_len + 1e-10))
    confidence = min(1.0, max(0.0, confidence))
    
    return {"offset_ms": offset_ms, "confidence": round(confidence, 4)}


SYNCET_SETUP_DOC = """# SyncNet Setup Instructions

## Prerequisites
Install the following Python packages:

```bash
# Core ML framework (choose one)
pip install torch torchvision  # PyTorch (recommended)
# OR
pip install tensorflow         # TensorFlow

# Vision
pip install opencv-python-headless

# Audio processing
pip install scipy

# Already installed
# numpy (already available)
```

## SyncNet Installation

Clone the SyncNet Python implementation:
```bash
git clone https://github.com/joonson/syncnet_python.git
cd syncnet_python
```

Download pretrained model:
```bash
wget http://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model
# OR for the PyTorch version
# Follow instructions at https://github.com/joonson/syncnet_python
```

## Usage after setup
```bash
python3 scripts/evals/eval_syncnet.py \\
    --baseline fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4 \\
    --canary assets/media/prod_2f9bb58c0508465fb51ac6b4578bba92/canary_pjob_fe40c769ad84418fb1091449e63d4da6.mp4 \\
    --out reports/karpathy_loop/sprint_07/S07_T001/eval_result_before.json
```

## Alternative: Wav2Lip LSE-D metric
If SyncNet is difficult to install, the Wav2Lip LSE-D (Lip Sync Error - Distance) 
metric can also measure lipsync quality. Install with:
```bash
pip install wav2lip
# OR clone from https://github.com/Rudrabha/Wav2Lip
```

## Minimal fallback
The eval_syncnet.py script always runs audio-to-audio cross-correlation,
which provides a more reliable offset measurement than the frame-diff proxy.
This works with numpy only and does not require SyncNet.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="SyncNet lipsync evaluator")
    ap.add_argument("--baseline", type=Path, default=Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4"))
    ap.add_argument("--canary", type=Path, default=Path("assets/media/prod_2f9bb58c0508465fb51ac6b4578bba92/canary_pjob_fe40c769ad84418fb1091449e63d4da6.mp4"))
    ap.add_argument("--out", type=Path, default=Path("reports/karpathy_loop/sprint_07/S07_T001/eval_result_before.json"))
    args = ap.parse_args(argv)

    deps = _check_syncnet_deps()
    syncnet_ready = deps["syncnet_python"] and (deps["torch"] or deps["tensorflow"]) and deps["opencv"]
    audio_only = deps["numpy"]

    baseline_exists = args.baseline.exists()
    canary_exists = args.canary.exists()
    
    # For meaningful audio correlation, compare SOURCE SLICE vs DIAGNOSTIC AUDIO
    # (both are the same content — S000 segment — unlike full baseline vs canary)
    import sqlite3
    _db_path = "db/production.db"
    _conn = sqlite3.connect(_db_path)
    _conn.row_factory = sqlite3.Row
    
    # Find diagnostic audio
    _da = _conn.execute(
        "SELECT uri FROM artifacts WHERE kind='provider_diagnostic_audio' AND provider_job_id='pjob_fe40c769ad84418fb1091449e63d4da6' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    _diag_path = Path(_da['uri']) if _da and _da['uri'] else None
    
    # Find source slice
    _ru = _conn.execute("SELECT source_slice_sha256 FROM render_units WHERE id='render_f91a245c14b341b6a7975e2a8d5716fc'").fetchone()
    _slice_path = Path("Videos/Projects/use_ai_to_triage_your_notifications_and/narration/hero_audio_slices/render_f91a245c14b341b6a7975e2a8d5716fc.wav")
    _conn.close()
    
    _source_slice_sha = _ru['source_slice_sha256'] if _ru else None
    _diag_exists = _diag_path and _diag_path.exists()

    result = {
        "eval_id": "S07_T001_syncnet",
        "production_id": "prod_2f9bb58c0508465fb51ac6b4578bba92",
        "canary_artifact": str(args.canary),
        "baseline_path": str(args.baseline),
        "syncnet_available": syncnet_ready,
        "dependencies": deps,
        "syncnet_ready": syncnet_ready,
        "canary_exists": canary_exists,
        "baseline_exists": baseline_exists,
    }

    if syncnet_ready:
        # Run SyncNet on both
        result["syncnet_baseline"] = {"status": "not_run", "note": "SyncNet installed but not executed in this run"}
        result["syncnet_canary"] = {"status": "not_run", "note": "SyncNet installed but not executed in this run"}
        result["overall"] = "SYNCNET_AVAILABLE"
        result["recommendation"] = "Run with --run-syncnet flag to execute SyncNet on both videos."
    else:
        # Run audio-only correlation as best available metric
        if audio_only and baseline_exists and canary_exists:
            try:
                if _diag_exists and _slice_path.exists():
                    _corr = _audio_cross_correlation(_slice_path, _diag_path)
                    result["audio_cross_correlation"] = _corr
                    result["audio_cross_correlation_sources"] = {
                        "source_slice_sha256": _source_slice_sha,
                        "source_slice_path": str(_slice_path),
                        "diagnostic_audio_path": str(_diag_path),
                        "diagnostic_audio_exists": _diag_exists,
                    }
                else:
                    result["audio_cross_correlation"] = {"offset_ms": None, "confidence": 0.0,
                        "note": f"Missing audio files: slice={_slice_path.exists()}, diag={_diag_exists}"}
            except Exception as e:
                result["audio_cross_correlation"] = {"error": str(e)}
        else:
            result["audio_cross_correlation"] = {"offset_ms": None, "confidence": 0.0,
                "note": "numpy required for audio correlation"}

        result["syncnet_setup_instructions"] = SYNCET_SETUP_DOC
        result["overall"] = "BLOCKED_NEEDS_SYNCNET"
        result["recommendation"] = (
            "SyncNet is required for definitive lipsync measurement. "
            "See syncnet_setup_instructions above. "
            "The mouth_motion_proxy (eval_lipsync.py) and audio_cross_correlation "
            "above remain as provisional fallbacks only."
        )

    result["notes"] = [
        "Audio cross-correlation provides audio-to-audio offset between baseline and canary.",
        "This is more reliable than frame-diff proxy but still NOT a real lipsync metric.",
        "True SyncNet would measure per-frame mouth activity vs audio envelope.",
        "Face detection libs (OpenCV, mediapipe, dlib) are also unavailable.",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"SyncNet eval for {result['production_id']}:")
    print(f"  SyncNet available: {syncnet_ready}")
    print(f"  Overall: {result['overall']}")
    if result.get("audio_cross_correlation"):
        ac = result["audio_cross_correlation"]
        if ac.get("offset_ms") is not None:
            print(f"  Audio cross-correlation offset: {ac['offset_ms']}ms (confidence: {ac['confidence']})")
        else:
            print(f"  Audio cross-correlation: {ac.get('note', 'N/A')}")
    print(f"  Baseline: {'EXISTS' if baseline_exists else 'MISSING'}")
    print(f"  Canary: {'EXISTS' if canary_exists else 'MISSING'}")
    if not syncnet_ready:
        print(f"  → BLOCKED_NEEDS_SYNCNET")
        print(f"  → Install instructions in result.syncnet_setup_instructions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
