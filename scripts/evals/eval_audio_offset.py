#!/usr/bin/env python3
"""Provider audio offset ledger for S08-T001.

Measures the cross-correlation offset between source slice audio and
provider diagnostic audio for HERO_SYNC_LOCKED render units.

Records evidence as 'audio_offset' validations and updates provider_job
convenience columns.

Usage:
  python3 scripts/evals/eval_audio_offset.py --provider-job-id <id> --out <json>
  python3 scripts/evals/eval_audio_offset.py --backfill --production-id <id> --out <json>
"""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

SR = 16000  # Normalized sample rate for correlation


def _load_wav(path: Path, target_sr: int = SR) -> np.ndarray:
    """Load audio file as mono PCM at target sample rate via ffmpeg."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(target_sr), "-ac", "1",
            tmp.name,
        ], capture_output=True, check=True, timeout=60)
        import struct
        data = Path(tmp.name).read_bytes()
        di = data.find(b"data")
        if di < 0:
            return np.array([], dtype=np.float64)
        hd = struct.unpack_from("<I", data, di + 4)[0]
        raw = data[di + 8:di + 8 + hd]
        return np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def _probe_duration(path: Path) -> float:
    """Get duration in seconds via ffprobe."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode == 0:
        data = json.loads(r.stdout)
        return float(data.get("format", {}).get("duration", 0))
    return 0.0


def compute_offset(source_path: Path, diagnostic_path: Path) -> dict:
    """Compute cross-correlation offset between source and diagnostic audio.

    Returns dict with offset_ms, confidence, and metadata.
    Sign convention: negative offset means diagnostic audio LEADS source.
    """
    if not source_path.exists():
        return {"error": f"source_slice not found: {source_path}"}
    if not diagnostic_path.exists():
        return {"error": f"diagnostic_audio not found: {diagnostic_path}"}

    source = _load_wav(source_path)
    diagnostic = _load_wav(diagnostic_path)

    if len(source) == 0 or len(diagnostic) == 0:
        return {"error": "empty audio after loading"}

    src_dur = len(source) / SR
    diag_dur = len(diagnostic) / SR

    # Silence detection
    def _find_speech(samples, threshold=0.01):
        env = np.abs(samples)
        ns = np.where(env > threshold * np.max(env))[0]
        if len(ns) == 0:
            return len(samples) / SR, len(samples) / SR
        return ns[0] / SR, (len(samples) - ns[-1]) / SR

    src_lead, src_trail = _find_speech(source)
    diag_lead, diag_trail = _find_speech(diagnostic)

    # Cross-correlation
    min_len = min(len(source), len(diagnostic))
    if min_len < 1600:
        return {"error": f"audio too short for correlation: {min_len} samples"}

    s_norm = (source[:min_len] - np.mean(source[:min_len])) / (np.std(source[:min_len]) + 1e-10)
    d_norm = (diagnostic[:min_len] - np.mean(diagnostic[:min_len])) / (np.std(diagnostic[:min_len]) + 1e-10)
    corr = np.correlate(s_norm, d_norm, mode="same")
    peak = int(np.argmax(np.abs(corr)))
    center = min_len // 2
    offset_samples = peak - center
    offset_ms = round(offset_samples / SR * 1000, 2)
    confidence = round(float(np.max(np.abs(corr)) / (min_len + 1e-10)), 4)
    confidence = min(1.0, max(0.0, confidence))

    return {
        "offset_ms": offset_ms,
        "confidence": confidence,
        "source_duration_ms": round(src_dur * 1000, 1),
        "diagnostic_duration_ms": round(diag_dur * 1000, 1),
        "source_leading_silence_ms": round(src_lead * 1000, 1),
        "source_trailing_silence_ms": round(src_trail * 1000, 1),
        "diagnostic_leading_silence_ms": round(diag_lead * 1000, 1),
        "diagnostic_trailing_silence_ms": round(diag_trail * 1000, 1),
        "sample_rate": SR,
        "method": "numpy_cross_correlation",
        "sign_convention": "negative = diagnostic LEADS source",
    }


def record_offset(production_id: str, render_unit_id: str, provider_job_id: str,
                   source_artifact_id: str, diagnostic_artifact_id: str,
                   offset_result: dict, db_path: str = None) -> str:
    """Record offset evidence as a validation row and update provider_job."""
    import production_db as _db
    path = db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")

    # Build validation evidence dict
    validation_evidence = {
        "eval_name": "audio_offset",
        "algorithm_version": "numpy_cross_correlation_v1",
        "sample_rate": SR,
        "normalized_format": "mono_16bit_pcm",
        **offset_result,
    }

    # Create validation record
    val_id = _db._id("val")
    with _db.transaction(path) as conn:
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id,
                validator_name, status, evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (val_id, production_id, "provider_job", provider_job_id,
             "audio_offset", "pass" if offset_result.get("error") is None else "fail",
             json.dumps(validation_evidence), _db._now()),
        )

        # Update provider_job convenience columns (idempotent — overwrites)
        conn.execute(
            """UPDATE provider_jobs SET
               source_slice_vs_diagnostic_offset_ms=?,
               audio_offset_confidence=?,
               source_slice_artifact_id=?,
               diagnostic_audio_artifact_id=?
               WHERE id=?""",
            (offset_result.get("offset_ms"),
             offset_result.get("confidence"),
             source_artifact_id,
             diagnostic_artifact_id,
             provider_job_id),
        )

    return val_id


def get_artifacts_for_job(provider_job_id: str, render_unit_id: str,
                           production_id: str, db_path: str = None) -> dict:
    """Find source slice and diagnostic audio artifacts for a job."""
    import sqlite3
    path = db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Diagnostic audio for this provider job
    diag = conn.execute(
        "SELECT id, sha256, size_bytes, uri FROM artifacts "
        "WHERE kind='provider_diagnostic_audio' AND provider_job_id=? "
        "ORDER BY created_at DESC LIMIT 1",
        (provider_job_id,),
    ).fetchone()

    # Source slice via render_unit's source_slice_sha256 + hero_audio_slice artifact
    slice_art = conn.execute(
        "SELECT a.id, a.sha256, a.size_bytes, a.uri FROM artifacts a "
        "JOIN render_units ru ON 1=1 "
        "WHERE a.kind='hero_audio_slice' AND a.production_id=? "
        "AND (a.uri LIKE '%' || ? || '%' OR ru.source_slice_sha256=a.sha256) "
        "LIMIT 1",
        (production_id, render_unit_id),
    ).fetchone()

    conn.close()

    return {
        "diagnostic": dict(diag) if diag else None,
        "source_slice": dict(slice_art) if slice_art else None,
    }


def process_job(provider_job_id: str, production_id: str = None,
                 render_unit_id: str = None, db_path: str = None) -> dict:
    """Process a single provider job: compute offset and record evidence."""
    import sqlite3
    path = db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")

    # Load job
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    job = conn.execute(
        "SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)
    ).fetchone()
    if not job:
        conn.close()
        return {"error": f"Provider job not found: {provider_job_id}"}

    pj = dict(job)
    pid = pj.get("production_id") or production_id
    ru_id = pj.get("render_unit_id") or render_unit_id

    # Validate it's a HERO_SYNC_LOCKED unit
    ru = conn.execute(
        "SELECT audio_policy FROM render_units WHERE id=?", (ru_id,)
    ).fetchone()
    conn.close()

    if ru and ru["audio_policy"] != "HERO_SYNC_LOCKED":
        return {"error": f"Render unit {ru_id} is not HERO_SYNC_LOCKED (policy={ru['audio_policy']})"}

    # Find artifacts
    arts = get_artifacts_for_job(pj["id"], ru_id, pid, db_path=path)
    if not arts["diagnostic"]:
        return {"error": "No provider_diagnostic_audio artifact for this job"}
    if not arts["source_slice"]:
        return {"error": "No hero_audio_slice artifact for this render unit"}

    diag_path = Path(arts["diagnostic"]["uri"])
    source_path = Path(arts["source_slice"]["uri"])

    # Compute offset
    offset_result = compute_offset(source_path, diag_path)
    if offset_result.get("error"):
        return offset_result

    # Add artifact hashes
    offset_result["source_slice_artifact_id"] = arts["source_slice"]["id"]
    offset_result["source_slice_sha256"] = arts["source_slice"]["sha256"]
    offset_result["diagnostic_audio_artifact_id"] = arts["diagnostic"]["id"]
    offset_result["diagnostic_audio_sha256"] = arts["diagnostic"]["sha256"]
    offset_result["provider_job_id"] = pj["id"]
    offset_result["render_unit_id"] = ru_id
    offset_result["production_id"] = pid

    # Record in DB
    val_id = record_offset(
        pid, ru_id, pj["id"],
        arts["source_slice"]["id"], arts["diagnostic"]["id"],
        offset_result, db_path=path,
    )
    offset_result["validation_id"] = val_id

    return offset_result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Provider audio offset ledger")
    ap.add_argument("--provider-job-id", default=None, help="Single provider job ID")
    ap.add_argument("--backfill", action="store_true", help="Backfill all completed HERO jobs")
    ap.add_argument("--production-id", default="prod_2f9bb58c0508465fb51ac6b4578bba92")
    ap.add_argument("--render-unit-id", default=None)
    ap.add_argument("--out", type=Path,
                    default=Path("reports/karpathy_loop/sprint_08/S08_T001/eval_result_before.json"))
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    db_path = args.db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")

    if args.provider_job_id:
        results = [process_job(args.provider_job_id, args.production_id,
                                args.render_unit_id, db_path)]
    elif args.backfill:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        jobs = conn.execute("""
            SELECT pj.id, pj.render_unit_id, pj.production_id
            FROM provider_jobs pj
            JOIN render_units ru ON pj.render_unit_id = ru.id
            WHERE ru.audio_policy='HERO_SYNC_LOCKED'
              AND pj.status='completed'
              AND ru.status='valid'
            ORDER BY pj.created_at DESC
        """).fetchall()
        conn.close()
        results = []
        for j in jobs:
            r = process_job(j["id"], j["production_id"], j["render_unit_id"], db_path)
            results.append(r)
    else:
        # Default: process the canary S000 job
        results = [process_job("pjob_fe40c769ad84418fb1091449e63d4da6",
                                args.production_id,
                                "render_f91a245c14b341b6a7975e2a8d5716fc",
                                db_path)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))

    for r in results:
        if r.get("error"):
            print(f"  [✗] {r.get('provider_job_id', '?')[:24]}: {r['error']}")
        else:
            print(f"  [✓] {r.get('provider_job_id', '?')[:24]}: "
                  f"offset={r.get('offset_ms')}ms conf={r.get('confidence')} "
                  f"validation={r.get('validation_id', '?')[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
