"""Sprint R9: B-Roll Runtime QA (R9-001, R9-002, R9-003).

Post-generation QA checkpoints for B-roll units:
  R9-001 — semantic relevance evidence (does the clip show claimed info?)
  R9-002 — visual duplicate detection (near-duplicate across episode)
  R9-003 — gibberish / malformed-object detection

Uses a pluggable vision model adapter (similar to R6-001/R6-003). Without a real
model loaded, returns REVIEW_REQUIRED — never PASS.

R9-004 — cause-specific repair routing reuses R6-004 repair service with B-roll
specific failure causes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import production_db as _db


class VisionModel(ABC):
    """Abstract vision model for B-roll semantic analysis."""

    @abstractmethod
    def load(self) -> bool:
        ...

    @abstractmethod
    def detect_objects(self, frame_path: Path) -> List[str]:
        """Return list of detected object labels."""
        ...

    @abstractmethod
    def embedding(self, frame_path: Path) -> Optional[List[float]]:
        """Return visual embedding for duplicate detection."""
        ...

    @property
    @abstractmethod
    def model_info(self) -> Dict[str, Any]:
        ...


class NoVisionModel(VisionModel):
    def load(self) -> bool:
        return False

    def detect_objects(self, frame_path: Path) -> List[str]:
        return []

    def embedding(self, frame_path: Path) -> Optional[List[float]]:
        return None

    @property
    def model_info(self) -> Dict[str, Any]:
        return {"name": "none", "version": "NO_REAL_VISION_MODEL_LOADED"}


_registered_vision: Optional[VisionModel] = None


def register_vision_model(model: VisionModel) -> None:
    global _registered_vision
    _registered_vision = model


def get_vision_model() -> VisionModel:
    return _registered_vision or NoVisionModel()


def _frame_hash(frame_path: Path) -> str:
    if not frame_path.exists():
        return ""
    h = hashlib.sha256()
    with open(frame_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_midpoint_frame(video_path: Path, output_path: Path) -> bool:
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
    ], capture_output=True, text=True)
    try:
        dur = float(probe.stdout.strip())
    except ValueError:
        return False
    mid = dur / 2.0
    subprocess.run([
        "ffmpeg", "-y", "-ss", f"{mid:.3f}",
        "-i", str(video_path), "-vframes", "1",
        "-q:v", "2", str(output_path),
    ], capture_output=True)
    return output_path.exists() and output_path.stat().st_size > 0


def extract_sample_frames(video_path: Path, output_dir: Path, count: int = 3) -> List[Path]:
    """Extract evenly-spaced sample frames."""
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
    ], capture_output=True, text=True)
    try:
        dur = float(probe.stdout.strip())
    except ValueError:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(count):
        t = (dur * (i + 1)) / (count + 1)
        out = output_dir / f"frame_{i}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{t:.3f}",
            "-i", str(video_path), "-vframes", "1",
            "-q:v", "2", str(out),
        ], capture_output=True)
        if out.exists() and out.stat().st_size > 0:
            frames.append(out)
    return frames


def check_semantic_relevance(
    video_path: Path,
    information_to_show: str,
    viewer_takeaway: str,
    db_path=None,
) -> Dict[str, Any]:
    """R9-001: Check if the generated B-roll clip shows the claimed information.

    Uses vision model if loaded, otherwise returns REVIEW_REQUIRED.
    """
    model = get_vision_model()
    result: Dict[str, Any] = {
        "status": "review_required",
        "semantic_relevance_score": 0.0,
        "detected_objects": [],
        "information_to_show": information_to_show,
        "viewer_takeaway": viewer_takeaway,
        "model_info": model.model_info,
        "issues": [],
    }

    if not video_path.exists():
        result["status"] = "fail"
        result["issues"].append("Video file missing")
        return result

    if not model.load():
        result["issues"].append("NO_REAL_VISION_MODEL_LOADED: semantic relevance cannot be verified")
        return result

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        frame_path = Path(tmp.name)

    if _extract_midpoint_frame(video_path, frame_path):
        result["detected_objects"] = model.detect_objects(frame_path)
        info_lower = information_to_show.lower()
        keywords = set(info_lower.replace(",", " ").split())
        detected_set = {o.lower() for o in result["detected_objects"]}
        matches = keywords & detected_set

        if matches:
            result["semantic_relevance_score"] = min(1.0, len(matches) / max(1, len(keywords)))
        else:
            result["semantic_relevance_score"] = 0.0
            result["issues"].append(f"No semantic match: keywords={keywords}, detected={detected_set}")

        if result["semantic_relevance_score"] < 0.3:
            result["status"] = "fail"
            result["issues"].append("Generated clip does not show the claimed information")
        else:
            result["status"] = "pass"
    else:
        result["status"] = "fail"
        result["issues"].append("Failed to extract frame from video")

    try:
        frame_path.unlink()
    except OSError:
        pass

    return result


def check_visual_duplicates(
    video_paths: List[Path],
    tolerance: float = 0.95,
) -> Dict[str, Any]:
    """R9-002: Detect visual near-duplicates across the episode.

    Uses vision model embeddings if loaded. Cosine similarity > tolerance → duplicate.
    """
    model = get_vision_model()
    result: Dict[str, Any] = {
        "status": "review_required",
        "duplicates": [],
        "embedding_dim": None,
        "model_info": model.model_info,
        "issues": [],
    }

    if not model.load():
        result["issues"].append("NO_REAL_VISION_MODEL_LOADED: duplicate detection is advisory only")
        return result

    import math
    import tempfile

    embeddings: Dict[str, List[float]] = {}
    for vp in video_paths:
        if not vp.exists():
            continue
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            frame_path = Path(tmp.name)
        if _extract_midpoint_frame(vp, frame_path):
            emb = model.embedding(frame_path)
            if emb:
                embeddings[str(vp)] = emb
        try:
            frame_path.unlink()
        except OSError:
            pass

    if embeddings:
        result["embedding_dim"] = len(next(iter(embeddings.values())))
        keys = list(embeddings.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a = embeddings[keys[i]]
                b = embeddings[keys[j]]
                dot = sum(x * y for x, y in zip(a, b))
                norm_a = math.sqrt(sum(x * x for x in a))
                norm_b = math.sqrt(sum(y * y for y in b))
                sim = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
                if sim > tolerance:
                    result["duplicates"].append({
                        "path_a": keys[i],
                        "path_b": keys[j],
                        "similarity": round(sim, 4),
                    })
                    result["issues"].append(f"Duplicate: {Path(keys[i]).name} ~ {Path(keys[j]).name} (sim={sim:.3f})")

    if result["duplicates"]:
        result["status"] = "fail"
    else:
        result["status"] = "pass"

    return result


def check_gibberish_objects(
    video_path: Path,
) -> Dict[str, Any]:
    """R9-003: Detect malformed objects or gibberish frames.

    Uses ffmpeg scene-change detection as a proxy for frame quality.
    Without a real model, returns REVIEW_REQUIRED.
    """
    model = get_vision_model()
    result: Dict[str, Any] = {
        "status": "review_required",
        "malformed_frames": 0,
        "scene_changes": 0,
        "issues": [],
        "model_info": model.model_info,
    }

    if not video_path.exists():
        result["status"] = "fail"
        result["issues"].append("Video missing")
        return result

    r = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", "select='gt(scene,0.01)',metadata=print",
        "-f", "null", "-",
    ], capture_output=True, text=True)
    import re
    scores = [float(m) for m in re.findall(r"scene_score=([\d.]+)", r.stderr)]
    result["scene_changes"] = len(scores)

    if len(scores) > 30:
        result["status"] = "fail"
        result["issues"].append(f"Excessive scene changes ({len(scores)}), likely gibberish")

    if not model.load():
        result["issues"].append("NO_REAL_VISION_MODEL_LOADED: gibberish detection is heuristic-only")
        return result

    import tempfile
    frames = extract_sample_frames(video_path, Path(tempfile.mkdtemp(prefix="gb_")), count=3)
    for fp in frames:
        objects = model.detect_objects(fp)
        if len(objects) == 0:
            result["malformed_frames"] += 1

    if result["malformed_frames"] >= 2:
        result["status"] = "fail"
        result["issues"].append(f"{result['malformed_frames']}/3 frames have no detectable objects")

    for fp in frames:
        try:
            fp.unlink()
        except OSError:
            pass

    return result
