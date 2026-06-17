"""Sprint 6: Safe-Boundary Validation (Ticket LB-602).

Evaluates whether video cut points align with safe visual boundaries
(mouth closure, blinks, low motion) and avoids cutting through active speech
or unstable provider frames.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

import production_db as _db

# Thresholds for safe boundary validation
UNSTABLE_START_SEC = 0.5  # Avoid cuts in the first 0.5s of a clip
UNSTABLE_END_SEC = 0.5    # Avoid cuts in the last 0.5s of a clip
HIGH_ENERGY_THRESHOLD = 0.05  # Audio energy threshold to detect active speech


def _get_file_hash(path: Path) -> str:
    """Get SHA-256 hash of a file."""
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_video_duration(path: Path) -> float:
    """Get video duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _estimate_audio_energy_at(path: Path, time_sec: float, window_sec: float = 0.2) -> float:
    """Estimate audio energy (RMS) at a specific time point."""
    start = max(0.0, time_sec - window_sec / 2)
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-t", str(window_sec),
        "-i", str(path), "-af", "astats=metadata=1:reset=1", "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    import re
    rms_values = [float(m) for m in re.findall(r"lavfi\.astats\.Overall\.RMS_level=(-?\d+\.?\d*)", result.stderr)]
    if not rms_values:
        return 0.0
    linear_values = [10 ** (rms / 20.0) for rms in rms_values if rms > -100.0]
    return sum(linear_values) / len(linear_values) if linear_values else 0.0


def validate_safe_boundaries(
    video_path: Path,
    audio_path: Path,
    cut_points_sec: List[float],
    approved_return_intervals: Optional[List[Dict[str, float]]] = None,
    model_version: str = "heuristic_v1",
) -> Dict[str, Any]:
    """
    Validate that cut points align with safe visual and audio boundaries.
    
    Returns a structured dict with:
    - status: "pass", "fail", or "review_required"
    - issues: list of specific boundary violations
    - input_artifact_hashes: dict
    - algorithm_version: str
    """
    issues = []
    
    if not video_path.exists() or not audio_path.exists():
        return {
            "status": "fail",
            "issues": ["Input artifacts missing"],
            "input_artifact_hashes": {"video": "missing", "audio": "missing"},
            "algorithm_version": model_version
        }
        
    video_duration = _get_video_duration(video_path)
    if video_duration <= 0:
        return {
            "status": "fail",
            "issues": ["Failed to probe video duration"],
            "input_artifact_hashes": {"video": _get_file_hash(video_path), "audio": _get_file_hash(audio_path)},
            "algorithm_version": model_version
        }

    for i, cut_sec in enumerate(cut_points_sec):
        # Check 1: No unstable startup or terminal provider frames
        if cut_sec < UNSTABLE_START_SEC:
            issues.append(f"Cut {i} at {cut_sec:.2f}s is in unstable startup region (<{UNSTABLE_START_SEC}s)")
        if cut_sec > (video_duration - UNSTABLE_END_SEC):
            issues.append(f"Cut {i} at {cut_sec:.2f}s is in unstable terminal region (>{video_duration - UNSTABLE_END_SEC:.2f}s)")
            
        # Check 2: No cut inside a high-confidence phoneme (active speech)
        # We use audio energy as a proxy for active speech/mouth movement
        energy = _estimate_audio_energy_at(audio_path, cut_sec)
        if energy > HIGH_ENERGY_THRESHOLD:
            issues.append(f"Cut {i} at {cut_sec:.2f}s cuts through active speech (energy={energy:.3f})")
            
        # Check 3: Approved return-to-hero interval
        # If the cut is a "return to hero" point, it must be within an approved interval
        if approved_return_intervals:
            is_approved = False
            for interval in approved_return_intervals:
                if interval["start_sec"] <= cut_sec <= interval["end_sec"]:
                    is_approved = True
                    break
            if not is_approved:
                issues.append(f"Cut {i} at {cut_sec:.2f}s is not within any approved return-to-hero interval")
                
        # Note: Mouth closure and blink detection are placeholders for ML integration.
        # In this heuristic, we assume low audio energy correlates with mouth closure.
        # A real implementation would use MediaPipe or similar for facial landmarks.

    status = "pass" if not issues else "fail"
    # If there are issues but they are minor (e.g., just return interval warnings), 
    # we could route to review, but for now we fail closed on any boundary violation.
    
    return {
        "status": status,
        "issues": issues,
        "input_artifact_hashes": {
            "video": _get_file_hash(video_path),
            "audio": _get_file_hash(audio_path)
        },
        "algorithm_version": model_version
    }


def record_safe_boundary_evidence(
    production_id: str,
    render_unit_id: str,
    video_path: Path,
    audio_path: Path,
    cut_points_sec: List[float],
    db_path=None,
) -> Dict[str, Any]:
    """
    Run safe boundary validation and record the evidence in the database.
    """
    evidence = validate_safe_boundaries(video_path, audio_path, cut_points_sec)
    
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO validations 
               (id, production_id, subject_type, subject_id, validator_name, status, 
                ruleset_version, evidence_json, created_at)
               VALUES (?, ?, 'safe_boundary', ?, ?, ?, ?, ?, ?)""",
            (
                f"val_bound_{render_unit_id}",
                production_id,
                render_unit_id,
                "safe_boundary_v1",
                evidence["status"],
                evidence["algorithm_version"],
                json.dumps(evidence),
                _db._now()
            )
        )
        
    return evidence
