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
import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from frame_sampling import FrameSamplingError as _FrameSamplingError
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


_FREEZEDETECT_FILTER = "freezedetect=n=0.003:d=0.5"

# thresholds as documented code constants
_MAX_FREEZE_PCT = 50.0
_MAX_SCENE_CHANGES = 20
_SCENE_DETECT_THRESHOLD = "0.3"
_MAX_SCENE_CHANGES_BY_FORMAT: Dict[str, int] = {
    "short": 25,
    "explainer": 15,
}


def check_broll_technical(video_path: Path, video_type: str = None) -> Dict[str, Any]:
    """Model-free technical QA for b-roll clips.

    Runs ffmpeg-only checks (no vision model):
      - frozen-frame detection via freezedetect
      - gibberish detection via scene-change count

    Returns dict with status ('pass'|'fail'), issues list, and metrics.
    """
    result: Dict[str, Any] = {
        "status": "pass",
        "issues": [],
        "frozen": {"total_freeze_sec": 0.0, "freeze_pct": 0.0},
        "gibberish": {"scene_changes": 0},
    }

    if not video_path.exists():
        result["status"] = "fail"
        result["issues"].append("Video file missing")
        return result

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
    ], capture_output=True, text=True)
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        duration = None

    # frozen-frame detection
    freeze_issues = _detect_frozen_frames(video_path, duration)
    result["issues"].extend(freeze_issues)
    result["frozen"].update({"total_freeze_sec": 0.0, "freeze_pct": 0.0})
    if freeze_issues and duration:
        result["status"] = "fail"

    # gibberish detection via scene changes
    gibberish_result = _detect_excessive_scene_changes(video_path, video_type)
    result["gibberish"]["scene_changes"] = gibberish_result["scene_changes"]
    result["gibberish"]["threshold"] = gibberish_result.get("threshold", "0.3")
    if gibberish_result["is_gibberish"]:
        result["status"] = "fail"
        result["issues"].append(gibberish_result["issue"])

    return result


def _detect_frozen_frames(video_path: Path, duration: Optional[float]) -> list[str]:
    """Detect frozen/static video using ffmpeg freezedetect filter."""
    issues: list[str] = []
    r = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", _FREEZEDETECT_FILTER,
        "-an", "-f", "null", "-",
    ], capture_output=True, text=True)
    import re
    freeze_durs = re.findall(r"freeze_duration:\s*([\d.]+)", r.stderr)
    freeze_starts = re.findall(r"freeze_start:\s*([\d.]+)", r.stderr)
    total_freeze = sum(float(d) for d in freeze_durs)
    if freeze_starts and not freeze_durs and duration:
        total_freeze = duration - float(freeze_starts[0])
    if duration and duration > 0 and total_freeze > 0:
        freeze_pct = (total_freeze / duration) * 100
        if freeze_pct >= _MAX_FREEZE_PCT:
            issues.append(
                f"FROZEN_VIDEO: {freeze_pct:.0f}% frozen "
                f"({total_freeze:.1f}s of {duration:.1f}s)"
            )
    return issues


def _detect_excessive_scene_changes(video_path: Path, video_type: str = None) -> Dict[str, Any]:
    """Detect likely gibberish via excessive scene-change count.

    Uses _SCENE_DETECT_THRESHOLD (0.3) for standard scene detection.
    Legitimate pans/dollies produce <5 scene changes at 0.3 sensitivity;
    rapid flicker/gibberish produces many.
    """
    r = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{_SCENE_DETECT_THRESHOLD})',metadata=print",
        "-an", "-f", "null", "-",
    ], capture_output=True, text=True)
    import re
    scores = [float(m) for m in re.findall(r"scene_score=([\d.]+)", r.stderr)]
    max_changes = _MAX_SCENE_CHANGES_BY_FORMAT.get(video_type or "", _MAX_SCENE_CHANGES)
    result = {
        "scene_changes": len(scores),
        "is_gibberish": len(scores) > max_changes,
        "threshold": _SCENE_DETECT_THRESHOLD,
        "issue": "",
    }
    if result["is_gibberish"]:
        result["issue"] = (
            f"Excessive scene changes ({len(scores)}/{max_changes}), likely gibberish"
        )
    return result


DUPLICATE_HAMMING_THRESHOLD: int = 10
MAX_DUPLICATE_PAIRS: int = 100


def compute_dhash(frame_path: Path) -> str:
    """Compute a 64-bit difference hash (dHash) for an image file.

    Uses PIL to convert to grayscale, resize to 9x8, then compares adjacent
    horizontal pixels to produce a 64-bit hash. Same-image hashes are identical;
    visually distinct images produce different hashes.

    Returns a 16-character hex string representing the 64-bit hash.
    """
    from PIL import Image
    img = Image.open(frame_path).convert("L")
    img = img.resize((9, 8), Image.LANCZOS)
    bits = []
    for y in range(8):
        row_start = y * 9
        row_pixels = list(img.getdata())[row_start:row_start + 9]
        for x in range(8):
            bits.append("1" if row_pixels[x] > row_pixels[x + 1] else "0")
    hex_str = hex(int("".join(bits), 2))[2:]
    return hex_str.zfill(16)


def _hamming_distance(hash_a: str, hash_b: str) -> int:
    """Compute Hamming distance (number of differing bits) between two hex hashes."""
    val_a = int(hash_a, 16)
    val_b = int(hash_b, 16)
    xor_val = val_a ^ val_b
    return xor_val.bit_count()


def _frame_hashes_from_bundle(artifact_path: Path) -> List[str]:
    """Extract perceptual hashes for all frames in the TKT-201 frame bundle.

    Uses the existing frame_bundle.build_frame_bundle to get deterministic
    frame paths, then computes a dHash for each frame.
    """
    from frame_bundle import build_frame_bundle
    frame_paths = build_frame_bundle(artifact_path)
    return [compute_dhash(fp) for fp in frame_paths]


def check_broll_duplicate(
    production_id: str,
    render_unit_id: str,
    artifact_path: Path,
    db_path=None,
) -> Dict[str, Any]:
    """Cross-clip near-duplicate detection via perceptual hashing.

    Computes dHash values for sampled frames of the current render unit,
    then compares against all other generated-video render units in the
    same production. If the mean Hamming distance across frame pairs is
    at or below DUPLICATE_HAMMING_THRESHOLD (default 10), the unit is
    flagged as a near-duplicate.

    Pair count is bounded by MAX_DUPLICATE_PAIRS to cap O(n) cost.

    Returns:
        Dict with status ('pass'|'fail'), duplicates list, threshold, and issues.
    """
    result: Dict[str, Any] = {
        "status": "pass",
        "duplicates": [],
        "threshold": DUPLICATE_HAMMING_THRESHOLD,
        "max_pairs": MAX_DUPLICATE_PAIRS,
        "issues": [],
        "pairs_checked": 0,
    }

    if not artifact_path or not artifact_path.exists():
        result["issues"].append("artifact_path missing or does not exist")
        return result

    current_hashes = _frame_hashes_from_bundle(artifact_path)
    if not current_hashes:
        result["issues"].append("no frames could be extracted for hash comparison")
        return result

    _db.migrate(db_path)
    conn = _db.connect(db_path)
    other_units = conn.execute(
        "SELECT ru.id AS ru_id, art.uri AS artifact_uri "
        "FROM render_units ru "
        "JOIN artifacts art ON ru.active_artifact_id = art.id "
        "WHERE ru.production_id=? AND ru.id!=? AND ru.asset_type='broll' "
        "AND ru.status='generated' AND art.uri IS NOT NULL",
        (production_id, render_unit_id),
    ).fetchall()
    conn.close()

    pairs_checked = 0
    for row in other_units:
        other_path = Path(row["artifact_uri"])
        if not other_path.exists():
            continue
        if pairs_checked >= MAX_DUPLICATE_PAIRS:
            result["issues"].append(
                f"pairwise cap ({MAX_DUPLICATE_PAIRS}) reached; remaining units skipped"
            )
            break
        try:
            other_hashes = _frame_hashes_from_bundle(other_path)
        except (_FrameSamplingError, OSError, ValueError) as e:
            msg = f"skipped unit {row['ru_id']} hash extraction: {e}"
            result["issues"].append(msg)
            logging.getLogger(__name__).warning(msg)
            continue
        if not other_hashes:
            continue

        distances = []
        for ch in current_hashes:
            for oh in other_hashes:
                distances.append(_hamming_distance(ch, oh))
                pairs_checked += 1
                if pairs_checked >= MAX_DUPLICATE_PAIRS:
                    break
            if pairs_checked >= MAX_DUPLICATE_PAIRS:
                break

        if not distances:
            continue

        mean_distance = sum(distances) / len(distances)
        if mean_distance <= DUPLICATE_HAMMING_THRESHOLD:
            result["duplicates"].append({
                "conflicting_unit": row["ru_id"],
                "mean_hamming_distance": round(mean_distance, 2),
                "pairs_compared": len(distances),
            })
            result["issues"].append(
                f"NEAR_DUPLICATE: unit {row['ru_id']} "
                f"(mean hamming distance {mean_distance:.1f} <= {DUPLICATE_HAMMING_THRESHOLD})"
            )

    result["pairs_checked"] = pairs_checked
    if result["duplicates"]:
        result["status"] = "fail"

    return result
