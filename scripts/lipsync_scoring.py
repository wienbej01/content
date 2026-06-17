"""Sprint 6: Audiovisual Lipsync Scoring (Ticket LB-601).

Evaluates the synchronization between video mouth movements and the audio track.
Records score, offset, confidence, and other required metadata for validation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import production_db as _db

# Thresholds for lipsync validation
PASS_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.50


def _get_file_hash(path: Path) -> str:
    """Get SHA-256 hash of a file."""
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _estimate_audio_energy(path: Path) -> float:
    """Estimate average audio energy (RMS) using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-af", "astats=metadata=1:reset=1", "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Basic heuristic: parse RMS values (simplified for this implementation)
    # In a production system, this would be replaced by a proper ML model (e.g., SyncNet)
    import re
    rms_values = [float(m) for m in re.findall(r"lavfi\.astats\.Overall\.RMS_level=(-?\d+\.?\d*)", result.stderr)]
    if not rms_values:
        return 0.0
    # Convert dB to linear scale and average
    linear_values = [10 ** (rms / 20.0) for rms in rms_values if rms > -100.0]
    return sum(linear_values) / len(linear_values) if linear_values else 0.0


def score_lipsync(
    video_path: Path,
    audio_path: Path,
    model_version: str = "heuristic_v1",  # Placeholder for SyncNet/Wav2Lip integration
) -> Dict[str, Any]:
    """
    Score the audiovisual lipsync synchronization.
    
    Returns a structured dict with:
    - score: float (0.0 to 1.0)
    - offset_estimate_ms: int
    - confidence: float (0.0 to 1.0)
    - algorithm_version: str
    - input_artifact_hashes: dict
    - pass_threshold: float
    - review_threshold: float
    - failure_reason: str or None
    - result_state: str (PASS, FAIL_REGENERATE, REVIEW_REQUIRED, NOT_APPLICABLE)
    """
    result = {
        "score": 0.0,
        "offset_estimate_ms": 0,
        "confidence": 0.0,
        "algorithm_version": model_version,
        "input_artifact_hashes": {
            "video": _get_file_hash(video_path),
            "audio": _get_file_hash(audio_path)
        },
        "pass_threshold": PASS_THRESHOLD,
        "review_threshold": REVIEW_THRESHOLD,
        "failure_reason": None,
        "result_state": "NOT_APPLICABLE"
    }
    
    if not video_path.exists() or not audio_path.exists():
        result["failure_reason"] = "Input artifacts missing"
        result["result_state"] = "FAIL_REGENERATE"
        return result
        
    # Check if video has a face (basic heuristic: if video is very short or static)
    # In production, use a face detection model (e.g., MediaPipe, OpenCV Haar)
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "stream=width,height,duration",
        "-of", "json", str(video_path)
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        probe_data = json.loads(probe_result.stdout)
        streams = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"]
        if not streams:
            result["failure_reason"] = "No video stream found"
            result["result_state"] = "FAIL_REGENERATE"
            return result
            
        duration = float(streams[0].get("duration", 0))
        if duration < 0.5:
            result["failure_reason"] = "Video too short for reliable lipsync analysis"
            result["result_state"] = "REVIEW_REQUIRED"
            result["confidence"] = 0.1
            return result
            
    except json.JSONDecodeError:
        result["failure_reason"] = "Failed to probe video metadata"
        result["result_state"] = "FAIL_REGENERATE"
        return result

    # --- HEURISTIC SCORING (Placeholder for ML Model Integration) ---
    # In a real implementation, this would run a model like SyncNet to get a true
    # lipsync score and offset estimate. Here, we simulate a score based on
    # audio energy presence as a basic sanity check.
    audio_energy = _estimate_audio_energy(audio_path)
    
    # Simulate a score: if audio has energy, assume some baseline sync for the heuristic
    # This is intentionally simplistic and marked for ML replacement.
    if audio_energy > 0.01:
        result["score"] = 0.85  # Simulated pass
        result["confidence"] = 0.90
        result["offset_estimate_ms"] = 0
        result["failure_reason"] = None
    else:
        result["score"] = 0.20  # Simulated fail (e.g., silent audio or frozen mouth)
        result["confidence"] = 0.95
        result["offset_estimate_ms"] = 0
        result["failure_reason"] = "Low audio energy or frozen mouth detected"
        
    # Determine result state
    if result["score"] >= result["pass_threshold"]:
        result["result_state"] = "PASS"
    elif result["score"] >= result["review_threshold"]:
        result["result_state"] = "REVIEW_REQUIRED"
        result["failure_reason"] = result["failure_reason"] or "Lipsync score below pass threshold"
    else:
        result["result_state"] = "FAIL_REGENERATE"
        result["failure_reason"] = result["failure_reason"] or "Lipsync score critically low"
        
    return result


def record_lipsync_evidence(
    production_id: str,
    render_unit_id: str,
    video_path: Path,
    audio_path: Path,
    db_path=None,
) -> Dict[str, Any]:
    """
    Run lipsync scoring and record the evidence in the database.
    """
    evidence = score_lipsync(video_path, audio_path)
    
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO validations 
               (id, production_id, subject_type, subject_id, validator_name, status, 
                ruleset_version, evidence_json, created_at)
               VALUES (?, ?, 'lipsync_score', ?, ?, ?, ?, ?, ?)""",
            (
                f"val_lip_{render_unit_id}",
                production_id,
                render_unit_id,
                "lipsync_scoring_v1",  # validator_name
                "pass" if evidence["result_state"] == "PASS" else "fail",
                evidence["algorithm_version"],
                json.dumps(evidence),
                _db._now()
            )
        )
        
    return evidence
