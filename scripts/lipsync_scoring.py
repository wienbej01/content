"""Sprint 6/R6: Audiovisual Lipsync Scoring (Tickets LB-601 / R6-001, R6-002).

R6-001: Heuristic scoring NEVER returns PASS on the release path. Until a real
model is loaded, all scores return REVIEW_REQUIRED with the reason "NO_REAL_MODEL_LOADED".
Only a calibrated ML model (SyncNet or equivalent) may emit PASS.

R6-002: Model adapter interface for real AV sync models. Models are loaded via
a registered adapter, scored against labelled fixtures, and produce structured
results with model checksum, version, and environment metadata.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import production_db as _db

PASS_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.50
ALGORITHM_VERSION = "3.0_review_required_no_model"


def _get_file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _estimate_audio_energy(path: Path) -> float:
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-af", "astats=metadata=1:reset=1", "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    import re
    rms_values = [float(m) for m in re.findall(r"lavfi\.astats\.Overall\.RMS_level=(-?\d+\.?\d*)", result.stderr)]
    if not rms_values:
        block = result.stderr
        overall_start = block.find("Overall")
        if overall_start != -1:
            block = block[overall_start:]
            rms_values = [float(m) for m in re.findall(r"RMS level dB:\s+(-?\d+\.?\d*)", block)]
    if not rms_values:
        return 0.0
    linear_values = [10 ** (rms / 20.0) for rms in rms_values if rms > -100.0]
    return sum(linear_values) / len(linear_values) if linear_values else 0.0


# ---------------------------------------------------------------------------
# R6-002  AV sync model adapter interface
# ---------------------------------------------------------------------------

class SyncModelAdapter(ABC):
    """Abstract adapter for a real AV sync model (SyncNet, Wav2Lip, etc.)."""

    @abstractmethod
    def load(self) -> bool:
        """Load model weights. Returns True on success."""
        ...

    @abstractmethod
    def score(self, video_path: Path, audio_path: Path) -> Dict[str, Any]:
        """Run the model and return structured scoring result."""
        ...

    @property
    @abstractmethod
    def model_info(self) -> Dict[str, Any]:
        """Return {name, version, checksum, environment, thresholds}."""
        ...


class NoModelLoaded(SyncModelAdapter):
    """Fail-closed: no real model loaded. All scores return REVIEW_REQUIRED."""

    def load(self) -> bool:
        return False

    def score(self, video_path: Path, audio_path: Path) -> Dict[str, Any]:
        return {
            "score": 0.0,
            "offset_estimate_ms": 0,
            "confidence": 0.0,
            "per_window_scores": [],
            "progressive_drift_ms": 0,
            "visible_face_confidence": 0.0,
            "multiple_faces_detected": False,
            "occlusion_confidence": 0.0,
        }

    @property
    def model_info(self) -> Dict[str, Any]:
        return {
            "name": "none",
            "version": "NO_REAL_MODEL_LOADED",
            "checksum": "",
            "environment": {},
        }


_registered_model: Optional[SyncModelAdapter] = None


def register_sync_model(model: SyncModelAdapter) -> None:
    global _registered_model
    _registered_model = model


def get_sync_model() -> SyncModelAdapter:
    if _registered_model is not None:
        return _registered_model
    return NoModelLoaded()


# ---------------------------------------------------------------------------
# R6-001  Fail-closed scoring
# ---------------------------------------------------------------------------

def score_lipsync(
    video_path: Path,
    audio_path: Path,
    model_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Score audiovisual lipsync synchronization.

    R6-001 guarantee: NEVER returns PASS without a real loaded model.
    Without a model, returns REVIEW_REQUIRED / BLOCKED.
    """
    model = get_sync_model()
    info = model.model_info
    version = model_version or info.get("version", ALGORITHM_VERSION)

    result: Dict[str, Any] = {
        "score": 0.0,
        "offset_estimate_ms": 0,
        "confidence": 0.0,
        "algorithm_version": version,
        "model_info": info,
        "input_artifact_hashes": {
            "video": _get_file_hash(video_path),
            "audio": _get_file_hash(audio_path),
        },
        "pass_threshold": PASS_THRESHOLD,
        "review_threshold": REVIEW_THRESHOLD,
        "failure_reason": None,
        "result_state": "NOT_APPLICABLE",
        "per_window_scores": [],
        "progressive_drift_ms": 0,
        "visible_face_confidence": 0.0,
        "multiple_faces_detected": False,
        "occlusion_confidence": 0.0,
    }

    if not video_path.exists() or not audio_path.exists():
        result["failure_reason"] = "Input artifacts missing"
        result["result_state"] = "BLOCKED"
        return result

    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "stream=width,height,duration,codec_type",
        "-of", "json", str(video_path),
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        probe_data = json.loads(probe_result.stdout)
        streams = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"]
        if not streams:
            result["failure_reason"] = "No video stream found"
            result["result_state"] = "BLOCKED"
            return result
        duration = float(streams[0].get("duration", 0))
        if duration < 0.5:
            result["failure_reason"] = "Video too short for reliable lipsync analysis"
            result["result_state"] = "REVIEW_REQUIRED"
            result["confidence"] = 0.1
            return result
    except json.JSONDecodeError:
        result["failure_reason"] = "Failed to probe video metadata"
        result["result_state"] = "BLOCKED"
        return result

    if not model.load():
        result["failure_reason"] = "NO_REAL_MODEL_LOADED: placeholder heuristic blocked by R6-001 interlock"
        result["result_state"] = "REVIEW_REQUIRED"
        result["confidence"] = 0.0
        return result

    model_result = model.score(video_path, audio_path)
    result["score"] = model_result["score"]
    result["offset_estimate_ms"] = model_result.get("offset_estimate_ms", 0)
    result["confidence"] = model_result.get("confidence", 0.0)
    result["per_window_scores"] = model_result.get("per_window_scores", [])
    result["progressive_drift_ms"] = model_result.get("progressive_drift_ms", 0)
    result["visible_face_confidence"] = model_result.get("visible_face_confidence", 0.0)
    result["multiple_faces_detected"] = model_result.get("multiple_faces_detected", False)
    result["occlusion_confidence"] = model_result.get("occlusion_confidence", 0.0)

    if result["score"] >= PASS_THRESHOLD:
        result["result_state"] = "PASS"
    elif result["score"] >= REVIEW_THRESHOLD:
        result["result_state"] = "REVIEW_REQUIRED"
        result["failure_reason"] = result["failure_reason"] or "Lipsync score below pass threshold"
    else:
        result["result_state"] = "BLOCKED"
        result["failure_reason"] = result["failure_reason"] or "Lipsync score critically low"

    return result


def record_lipsync_evidence(
    production_id: str,
    render_unit_id: str,
    video_path: Path,
    audio_path: Path,
    db_path=None,
) -> Dict[str, Any]:
    evidence = score_lipsync(video_path, audio_path)

    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                ruleset_version, evidence_json, artifact_sha256, algorithm_version, created_at)
               VALUES (?, ?, 'lipsync_score', ?, 'lipsync_scoring', ?, ?, ?, ?, ?, ?)""",
            (
                f"val_lip_{render_unit_id}",
                production_id,
                render_unit_id,
                "pass" if evidence["result_state"] == "PASS" else "fail",
                evidence["algorithm_version"],
                json.dumps(evidence, sort_keys=True, default=str),
                evidence["input_artifact_hashes"].get("video"),
                evidence["algorithm_version"],
                _db._now(),
            ),
        )
    return evidence
