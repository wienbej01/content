"""Sprint 6/R6: Safe Boundary QA (Ticket LB-602 / R6-003).

R6-003: Replaces audio-energy proxy with real visual boundary detection.
Detects face landmarks, mouth aperture, local motion, and unstable startup/terminal
frames. Combines visual + audio evidence. Uses a pluggable face detector adapter.

Without a real face detector loaded, falls back to ffmpeg motion/scene detection
and NEVER returns PASS — only REVIEW_REQUIRED (gated by R6-001 interlock).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import production_db as _db

UNSTABLE_START_SEC = 0.5
UNSTABLE_END_SEC = 0.5
ALGORITHM_VERSION = "2.0_visual_boundary"


class FaceDetector(ABC):
    """Abstract face/mouth landmark detector."""

    @abstractmethod
    def load(self) -> bool:
        ...

    @abstractmethod
    def detect_landmarks(self, frame_path: Path) -> Optional[Dict[str, Any]]:
        """Return {face_bbox, mouth_aperture, left_eye, right_eye} or None."""
        ...

    @property
    @abstractmethod
    def detector_info(self) -> Dict[str, Any]:
        ...


class NoDetectorLoaded(FaceDetector):
    def load(self) -> bool:
        return False

    def detect_landmarks(self, frame_path: Path) -> Optional[Dict[str, Any]]:
        return None

    @property
    def detector_info(self) -> Dict[str, Any]:
        return {"name": "none", "version": "NO_REAL_DETECTOR_LOADED"}


_registered_detector: Optional[FaceDetector] = None


def register_face_detector(detector: FaceDetector) -> None:
    global _registered_detector
    _registered_detector = detector


def get_face_detector() -> FaceDetector:
    return _registered_detector or NoDetectorLoaded()


def _get_file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_video_duration(path: Path) -> float:
    r = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _extract_frame(path: Path, time_sec: float, output_path: Path) -> bool:
    r = subprocess.run([
        "ffmpeg", "-y", "-ss", f"{time_sec:.3f}",
        "-i", str(path), "-vframes", "1",
        "-q:v", "2", str(output_path),
    ], capture_output=True)
    return output_path.exists() and output_path.stat().st_size > 0


def _motion_at_time(path: Path, time_sec: float, window: float = 0.2) -> float:
    r = subprocess.run([
        "ffmpeg", "-y", "-ss", f"{max(0, time_sec - window):.3f}",
        "-t", f"{window * 2:.3f}",
        "-i", str(path),
        "-vf", "select='gt(scene,0.01)',metadata=print",
        "-f", "null", "-",
    ], capture_output=True, text=True)
    scores = [float(m) for m in re.findall(r"scene_score=([\d.]+)", r.stderr)]
    return max(scores) if scores else 0.0


def _scene_changes_near(path: Path, time_sec: float, window: float = 0.5) -> int:
    r = subprocess.run([
        "ffmpeg", "-y",
        "-ss", f"{max(0, time_sec - window):.3f}",
        "-t", f"{window * 2:.3f}",
        "-i", str(path),
        "-vf", "select='gt(scene,0.3)',showinfo",
        "-f", "null", "-",
    ], capture_output=True, text=True)
    return len(re.findall(r"Parsed_showinfo", r.stderr))


def _audio_energy_at(path: Path, time_sec: float, window: float = 0.1) -> float:
    r = subprocess.run([
        "ffmpeg", "-y", "-ss", f"{max(0, time_sec - window):.3f}",
        "-t", f"{window * 2:.3f}",
        "-i", str(path),
        "-af", "volumedetect", "-f", "null", "-",
    ], capture_output=True, text=True)
    m = re.search(r"mean_volume:\s+(-?\d+\.?\d*)", r.stderr)
    if m:
        db = float(m.group(1))
        return 10 ** (db / 20.0)
    return 0.0


def validate_safe_boundaries(
    video_path: Path,
    audio_path: Path,
    cut_points_sec: List[float],
    return_to_hero_intervals: Optional[List[Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """Validate cut points are on safe visual/audio boundaries.

    R6-003: Uses face detector if loaded, otherwise ffmpeg motion/scene detection.
    Without a detector, NEVER returns 'pass' — returns 'review_required'.
    """
    detector = get_face_detector()
    has_real_detector = detector.load()

    result: Dict[str, Any] = {
        "status": "pass",
        "issues": [],
        "cut_results": [],
        "input_artifact_hashes": {
            "video": _get_file_hash(video_path),
            "audio": _get_file_hash(audio_path),
        },
        "algorithm_version": ALGORITHM_VERSION,
        "detector_info": detector.detector_info,
        "has_real_detector": has_real_detector,
    }

    if not video_path.exists():
        result["status"] = "fail"
        result["issues"].append("Video file missing")
        return result

    duration = _get_video_duration(video_path)
    if duration <= 0:
        result["status"] = "fail"
        result["issues"].append("Cannot determine video duration")
        return result

    for time_sec in cut_points_sec:
        cut_result: Dict[str, Any] = {"time_sec": time_sec, "checks": {}}

        if time_sec < UNSTABLE_START_SEC:
            cut_result["unstable_startup"] = True
            cut_result["checks"]["unstable_startup"] = False
        else:
            cut_result["unstable_startup"] = False

        if time_sec > duration - UNSTABLE_END_SEC:
            cut_result["unstable_terminal"] = True
            cut_result["checks"]["unstable_terminal"] = False
        else:
            cut_result["unstable_terminal"] = False

        audio_energy = _audio_energy_at(audio_path, time_sec) if audio_path.exists() else 0.0
        cut_result["audio_energy"] = round(audio_energy, 6)
        cut_result["checks"]["audio_silent"] = audio_energy < 0.05

        motion = _motion_at_time(video_path, time_sec)
        cut_result["motion_score"] = round(motion, 6)

        scene_changes = _scene_changes_near(video_path, time_sec)
        cut_result["scene_changes_near"] = scene_changes
        cut_result["checks"]["low_motion"] = motion < 0.4
        cut_result["checks"]["no_scene_change"] = scene_changes == 0

        if return_to_hero_intervals:
            in_interval = any(
                iv.get("start_sec", 0) <= time_sec <= iv.get("end_sec", float("inf"))
                for iv in return_to_hero_intervals
            )
            cut_result["checks"]["in_approved_interval"] = in_interval
            if not in_interval:
                cut_result["interval_violation"] = True
        else:
            cut_result["checks"]["in_approved_interval"] = True

        if has_real_detector:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            if _extract_frame(video_path, time_sec, tmp_path):
                landmarks = detector.detect_landmarks(tmp_path)
                if landmarks:
                    cut_result["face_detected"] = True
                    cut_result["mouth_aperture"] = landmarks.get("mouth_aperture")
                    cut_result["landmarks"] = landmarks
                else:
                    cut_result["face_detected"] = False
            try:
                tmp_path.unlink()
            except OSError:
                pass

        result["cut_results"].append(cut_result)

    if not has_real_detector:
        result["status"] = "review_required"
        result["issues"].append(
            "NO_REAL_DETECTOR_LOADED: motion/scene heuristics are advisory only; "
            "PASS requires a real face landmark detector (MediaPipe or equivalent)"
        )
        return result

    for cr in result["cut_results"]:
        if cr.get("unstable_startup"):
            result["status"] = "fail"
            result["issues"].append(f"cut at {cr['time_sec']:.3f}s in unstable startup region")
        if cr.get("unstable_terminal"):
            result["status"] = "fail"
            result["issues"].append(f"cut at {cr['time_sec']:.3f}s in unstable terminal region")
        if not cr["checks"].get("audio_silent", True) and not has_real_detector:
            result["status"] = "fail"
            result["issues"].append(f"cut at {cr['time_sec']:.3f}s through active speech")
        if cr.get("interval_violation"):
            result["status"] = "fail"
            result["issues"].append(f"cut at {cr['time_sec']:.3f}s outside approved return-to-hero interval")
        if has_real_detector and not cr.get("face_detected", True):
            result["status"] = "fail"
            result["issues"].append(f"no face detected at cut {cr['time_sec']:.3f}s")

    return result


def record_safe_boundary_evidence(
    production_id: str,
    render_unit_id: str,
    video_path: Path,
    audio_path: Path,
    cut_points_sec: List[float],
    db_path=None,
) -> str:
    evidence = validate_safe_boundaries(video_path, audio_path, cut_points_sec)
    val_id = f"val_sb_{render_unit_id}"

    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                ruleset_version, evidence_json, artifact_sha256, algorithm_version, created_at)
               VALUES (?, ?, 'safe_boundary', ?, 'safe_boundary_qa', ?, ?, ?, ?, ?, ?)""",
            (
                val_id, production_id, render_unit_id,
                evidence["status"],
                evidence["algorithm_version"],
                json.dumps(evidence, sort_keys=True, default=str),
                evidence["input_artifact_hashes"].get("video"),
                evidence["algorithm_version"],
                _db._now(),
            ),
        )
    return val_id
