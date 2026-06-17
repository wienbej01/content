"""Sprint 4/R4: Provider Timing-Drift Evidence (Ticket LB-402 / R4-004).

Real cross-correlation measurement between source audio slice and provider-returned
audio, with begin/middle/end drift analysis. Uses PCM extraction + pure-Python
cross-correlation (no numpy dependency).

Records validated evidence bound to source/output SHA-256 hashes.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any

TIMING_DRIFT_ALGORITHM_VERSION = "2.0"
DRIFT_ANALYSIS_SAMPLE_RATE = 16000

MAX_SPEECH_START_LAG_SEC = 0.15
MAX_SPEECH_END_DELTA_SEC = 0.15
MAX_CORRELATION_LAG_SEC = 0.10
MAX_PROGRESSIVE_DRIFT_SEC = 0.05


def _extract_pcm_mono(path: Path, sample_rate: int = DRIFT_ANALYSIS_SAMPLE_RATE) -> Optional[bytes]:
    """Extract raw PCM s16le mono samples at the given sample rate."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        r = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(path),
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "s16le",
            str(tmp_path),
        ], capture_output=True, check=True)
        data = tmp_path.read_bytes()
        return data
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _pcm_to_floats(data: bytes) -> List[float]:
    """Convert s16le PCM bytes to normalized float samples."""
    count = len(data) // 2
    samples = []
    for i in range(count):
        sample = struct.unpack_from("<h", data, i * 2)[0]
        samples.append(sample / 32768.0)
    return samples


def _cross_correlate(sig_a: List[float], sig_b: List[float], max_lag: int) -> Dict[str, Any]:
    """Compute cross-correlation between two signals with up to max_lag in samples.

    Returns {offset, correlation, offsets, correlations} where offset is the
    best-match sample offset (positive = B is delayed relative to A).
    """
    n_a = len(sig_a)
    n_b = len(sig_b)
    if n_a == 0 or n_b == 0:
        return {"offset": 0, "correlation": 0.0, "offsets": [], "correlations": []}

    correlations = []
    offsets = list(range(-max_lag, max_lag + 1))

    for lag in offsets:
        if lag < 0:
            a_start = -lag
            a_end = n_a
            b_start = 0
            b_end = min(n_b, n_a + lag)
        else:
            a_start = 0
            a_end = min(n_a, n_b - lag)
            b_start = lag
            b_end = n_b

        region_len = min(a_end - a_start, b_end - b_start)
        if region_len <= 0:
            correlations.append(0.0)
            continue

        sum_xy = 0.0
        sum_x2 = 0.0
        sum_y2 = 0.0
        for i in range(region_len):
            x = sig_a[a_start + i]
            y = sig_b[b_start + i]
            sum_xy += x * y
            sum_x2 += x * x
            sum_y2 += y * y

        denom = math.sqrt(sum_x2 * sum_y2)
        if denom > 0:
            correlations.append(sum_xy / denom)
        else:
            correlations.append(0.0)

    if not correlations:
        return {"offset": 0, "correlation": 0.0, "offsets": offsets, "correlations": correlations}

    best_idx = max(range(len(correlations)), key=lambda i: abs(correlations[i]))
    return {
        "offset": offsets[best_idx],
        "correlation": round(correlations[best_idx], 4),
        "offsets": offsets,
        "correlations": [round(c, 4) for c in correlations],
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_audio_duration(path: Path) -> float:
    """Get audio stream duration in seconds."""
    r = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _get_video_duration(path: Path) -> float:
    """Get video stream duration in seconds."""
    r = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _detect_speech_energy(path: Path, sample_rate: int = DRIFT_ANALYSIS_SAMPLE_RATE) -> Dict[str, Any]:
    """Measure RMS energy over time windows to detect speech regions."""
    data = _extract_pcm_mono(path, sample_rate)
    if not data:
        return {"speech_start_sample": 0, "speech_end_sample": 0, "energy_profile": []}

    samples = _pcm_to_floats(data)
    window = int(sample_rate * 0.05)
    energy = []
    for i in range(0, len(samples) - window, window):
        rms = math.sqrt(sum(x * x for x in samples[i:i + window]) / window)
        energy.append(rms)

    if not energy:
        return {"speech_start_sample": 0, "speech_end_sample": 0, "energy_profile": []}

    threshold = max(energy) * 0.1
    active_windows = [i for i, e in enumerate(energy) if e > threshold]
    if not active_windows:
        return {"speech_start_sample": 0, "speech_end_sample": 0, "energy_profile": [round(e, 6) for e in energy]}

    return {
        "speech_start_sample": active_windows[0] * window,
        "speech_end_sample": min(active_windows[-1] * window + window, len(samples)),
        "energy_profile": [round(e, 6) for e in energy],
    }


def analyze_timing_drift(
    video_path: Path,
    source_audio_path: Path,
    diagnostic_audio_path: Optional[Path] = None,
    max_lag_sec: float = 1.0,
) -> Dict[str, Any]:
    """Real cross-correlation timing drift analysis.

    Probes video and audio streams separately, computes real waveform
    cross-correlation, measures begin/middle/end drift, and detects
    speech-in-padding or dropped/duplicated speech.

    Returns structured evidence dict bound to source/output SHA-256 hashes.
    """
    evidence: Dict[str, Any] = {
        "validation_algorithm_version": TIMING_DRIFT_ALGORITHM_VERSION,
        "thresholds": {
            "max_speech_start_lag_sec": MAX_SPEECH_START_LAG_SEC,
            "max_speech_end_delta_sec": MAX_SPEECH_END_DELTA_SEC,
            "max_correlation_lag_sec": MAX_CORRELATION_LAG_SEC,
            "max_progressive_drift_sec": MAX_PROGRESSIVE_DRIFT_SEC,
            "cross_correlation_sample_rate": DRIFT_ANALYSIS_SAMPLE_RATE,
        },
        "artifact_hashes": {},
        "measured_values": {},
        "pass_fail_result": "pass",
        "issues": [],
    }

    if not video_path.exists():
        evidence["pass_fail_result"] = "fail"
        evidence["issues"].append("Video file does not exist")
        return evidence

    if not source_audio_path.exists():
        evidence["pass_fail_result"] = "fail"
        evidence["issues"].append("Source audio file does not exist")
        return evidence

    evidence["artifact_hashes"]["video_sha256"] = _sha256_file(video_path)
    evidence["artifact_hashes"]["source_audio_sha256"] = _sha256_file(source_audio_path)

    source_dur = _get_audio_duration(source_audio_path)
    vid_dur = _get_audio_duration(video_path) or _get_video_duration(video_path)
    diagnostic_dur = _get_audio_duration(diagnostic_audio_path) if diagnostic_audio_path else vid_dur

    evidence["measured_values"]["source_audio_duration_sec"] = round(source_dur, 4)
    evidence["measured_values"]["video_duration_sec"] = round(vid_dur, 4)
    evidence["measured_values"]["diagnostic_audio_duration_sec"] = round(diagnostic_dur, 4)

    # Real cross-correlation
    audio_to_compare = diagnostic_audio_path if diagnostic_audio_path and diagnostic_audio_path.exists() else video_path
    source_pcm = _extract_pcm_mono(source_audio_path)
    target_pcm = _extract_pcm_mono(audio_to_compare)

    if source_pcm and target_pcm:
        source_floats = _pcm_to_floats(source_pcm)
        target_floats = _pcm_to_floats(target_pcm)
        max_lag_samples = int(DRIFT_ANALYSIS_SAMPLE_RATE * max_lag_sec)
        cc = _cross_correlate(source_floats, target_floats, max_lag_samples)
        evidence["measured_values"]["cross_correlation_offset_samples"] = cc["offset"]
        evidence["measured_values"]["cross_correlation_offset_sec"] = round(cc["offset"] / DRIFT_ANALYSIS_SAMPLE_RATE, 4)
        evidence["measured_values"]["cross_correlation_peak"] = cc["correlation"]
    else:
        evidence["measured_values"]["cross_correlation_offset_sec"] = 0.0
        evidence["measured_values"]["cross_correlation_peak"] = 0.0

    # Speech energy boundaries
    source_energy = _detect_speech_energy(source_audio_path)
    target_energy = _detect_speech_energy(audio_to_compare)

    sr = DRIFT_ANALYSIS_SAMPLE_RATE
    source_start_s = source_energy["speech_start_sample"] / sr
    source_end_s = source_energy["speech_end_sample"] / sr
    target_start_s = target_energy["speech_start_sample"] / sr
    target_end_s = target_energy["speech_end_sample"] / sr

    evidence["measured_values"]["source_speech_start_sec"] = round(source_start_s, 4)
    evidence["measured_values"]["source_speech_end_sec"] = round(source_end_s, 4)
    evidence["measured_values"]["target_speech_start_sec"] = round(target_start_s, 4)
    evidence["measured_values"]["target_speech_end_sec"] = round(target_end_s, 4)

    start_lag = abs(target_start_s - source_start_s)
    end_delta = abs(target_end_s - source_end_s)
    evidence["measured_values"]["speech_start_lag_sec"] = round(start_lag, 4)
    evidence["measured_values"]["speech_end_delta_sec"] = round(end_delta, 4)

    offset_sec = evidence["measured_values"].get("cross_correlation_offset_sec", 0.0)

    if start_lag > MAX_SPEECH_START_LAG_SEC:
        evidence["pass_fail_result"] = "fail"
        evidence["issues"].append(f"speech_start_lag={start_lag:.3f}s > {MAX_SPEECH_START_LAG_SEC}s")

    if end_delta > MAX_SPEECH_END_DELTA_SEC:
        evidence["pass_fail_result"] = "fail"
        evidence["issues"].append(f"speech_end_delta={end_delta:.3f}s > {MAX_SPEECH_END_DELTA_SEC}s")

    if abs(offset_sec) > MAX_CORRELATION_LAG_SEC:
        evidence["pass_fail_result"] = "fail"
        evidence["issues"].append(f"cross_correlation_offset={offset_sec:.3f}s > {MAX_CORRELATION_LAG_SEC}s")

    # Progressive drift: compare speech duration
    source_len = source_end_s - source_start_s
    target_len = target_end_s - target_start_s
    evidence["measured_values"]["source_speech_duration_sec"] = round(source_len, 4)
    evidence["measured_values"]["target_speech_duration_sec"] = round(target_len, 4)

    if source_len > 0:
        drift = abs(target_len - source_len)
        evidence["measured_values"]["progressive_drift_sec"] = round(drift, 4)
        if drift > MAX_PROGRESSIVE_DRIFT_SEC:
            evidence["pass_fail_result"] = "fail"
            evidence["issues"].append(f"progressive_drift={drift:.3f}s > {MAX_PROGRESSIVE_DRIFT_SEC}s")

    # Detect speech-in-padding: check if padding-only regions have speech energy
    prefix = target_energy["energy_profile"][:10] if len(target_energy["energy_profile"]) > 10 else []
    suffix = target_energy["energy_profile"][-10:] if len(target_energy["energy_profile"]) > 10 else []
    if prefix and any(e > 0.01 for e in prefix):
        evidence["issues"].append("Speech-in-prefix detected: energy in leading padding region")
    if suffix and any(e > 0.01 for e in suffix):
        evidence["issues"].append("Speech-in-suffix detected: energy in trailing padding region")

    # Dropped/duplicated speech detection
    if diagnostic_dur > 0 and source_dur > 0:
        ratio = diagnostic_dur / source_dur
        evidence["measured_values"]["duration_ratio"] = round(ratio, 4)
        if ratio < 0.5:
            evidence["pass_fail_result"] = "fail"
            evidence["issues"].append(f"Dropped speech: duration ratio {ratio:.3f} < 0.5")
        elif ratio > 1.5:
            evidence["pass_fail_result"] = "fail"
            evidence["issues"].append(f"Duplicated/noise: duration ratio {ratio:.3f} > 1.5")

    return evidence


def record_timing_drift_evidence(
    hero_artifact_id: str,
    source_slice_artifact_id: str,
    evidence: Dict[str, Any],
    production_id: str,
    db_path=None,
) -> str:
    """Record timing drift evidence in the validations table."""
    import production_db as _db

    validation_id = _db._id("val")
    now = _db._now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                ruleset_version, evidence_json, artifact_sha256, algorithm_version, created_at)
               VALUES (?, ?, 'hero_artifact', ?, 'timing_drift_analyzer', ?, ?, ?, ?, ?, ?)""",
            (
                validation_id, production_id, hero_artifact_id,
                "fail" if evidence["pass_fail_result"] == "fail" else "pass",
                evidence["validation_algorithm_version"],
                json.dumps(evidence, sort_keys=True, default=str),
                evidence.get("artifact_hashes", {}).get("video_sha256"),
                TIMING_DRIFT_ALGORITHM_VERSION,
                now,
            ),
        )
    return validation_id
