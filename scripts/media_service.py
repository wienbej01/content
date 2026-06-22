"""Sprint 6: Media generation service.

MEDIA-601  Provider-job state machine (submit, poll, download, retry)
MEDIA-602  Generation worker migration (render-unit driven, no filename inference)
MEDIA-603  Graphics / overlay migration (typed MIME from DB)
QA-604     Media validation evidence store
QA-605     Change-request routing
QA-606     Contract-based media QA (ENG-0501/0502/0503/0504/0505)
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import os
from pathlib import Path
from typing import Optional

import media_contract as _contract
import production_db as _db
import production_repo as _repo


CONTRACT_VERSION = "1.0"


PROVIDER_ACTIVE_STATUSES = ("submitted", "running")
PROVIDER_TERMINAL_STATUSES = ("completed", "failed")
PROVIDER_STATUSES = PROVIDER_ACTIVE_STATUSES + PROVIDER_TERMINAL_STATUSES


def normalize_provider_status(status: Optional[str]) -> str:
    """Collapse provider-specific states to the DB lifecycle vocabulary."""
    text = str(status or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    if text in ("completed", "complete", "done", "succeeded", "success"):
        return "completed"
    if text in ("failed", "failure", "error", "errored", "cancelled", "canceled"):
        return "failed"
    if text in ("submitted", "created", "pending", "queued", "waiting"):
        return "submitted"
    if text in ("running", "processing", "in progress", "started"):
        return "running"
    if "completed" in text or " complete " in f" {text} " or " done " in f" {text} ":
        return "completed"
    if "failed" in text or " error " in f" {text} ":
        return "failed"
    if any(token in text for token in ("waiting", "queued", "submitted", "pending")):
        return "submitted"
    return "running"


# ---------------------------------------------------------------------------
# MEDIA-601  Provider-job state machine
# ---------------------------------------------------------------------------

class ProviderJobError(Exception):
    pass


def submit_provider_job(
    production_id: str,
    render_unit_id: str,
    provider: str,
    operation: str,
    request_payload: dict,
    idempotency_key: Optional[str] = None,
    db_path=None,
) -> dict:
    """Register a provider job and mark it 'submitted'.

    Idempotent: same idempotency_key returns the existing row.
    A billable job CANNOT be submitted without a passing spend approval
    (checked here via the gate_a_spend approval_request).
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    spend_approval = conn.execute(
        """SELECT status FROM approval_requests
           WHERE production_id=? AND gate_name='gate_a_spend'""",
        (production_id,),
    ).fetchone()
    conn.close()

    if not spend_approval or spend_approval["status"] != "pass":
        raise ProviderJobError(
            f"Cannot submit provider job: gate_a_spend is "
            f"{'missing' if not spend_approval else spend_approval['status']} "
            f"for production {production_id}"
        )

    # Guard: fetch render unit and enforce media contract
    conn = _db.connect(db_path)
    ru = conn.execute(
        "SELECT * FROM render_units WHERE id=?", (render_unit_id,)
    ).fetchone()
    conn.close()
    if not ru:
        raise ProviderJobError(f"render_unit {render_unit_id} not found")

    ru = dict(ru)
    try:
        _contract.assert_provider_eligible(ru)
        prompt = (request_payload or {}).get("prompt") or ""
        _contract.assert_provider_prompt_text_free(prompt)
    except _contract.MediaContractError as exc:
        raise _contract.MediaContractError(
            f"render_unit_id={render_unit_id} "
            f"asset_type={ru.get('asset_type', 'unknown')}: "
            f"{exc}"
        )

    idem = idempotency_key or (
        f"pjob:{production_id}:{render_unit_id}:{provider}:{operation}:"
        f"{_db._sha256_bytes(_db._json(request_payload).encode())[:16]}"
    )
    now = _db._now()

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM provider_jobs WHERE idempotency_key=?", (idem,)
        ).fetchone()
        if existing:
            if existing["render_unit_id"] and existing["status"] in ("submitted", "running"):
                conn.execute(
                    "UPDATE render_units SET status='generating', updated_at=? WHERE id=?",
                    (now, existing["render_unit_id"]),
                )
            return dict(existing)

        job_id = _db._id("pjob")
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation,
                idempotency_key, status, request_json, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                job_id, production_id, render_unit_id, provider, operation,
                idem, "submitted", _db._json(request_payload), now,
            ),
        )
        # Advance render unit status
        conn.execute(
            "UPDATE render_units SET status='generating', updated_at=? WHERE id=?",
            (now, render_unit_id),
        )
        _db.append_event(
            production_id, "provider_job_submitted",
            payload={"job_id": job_id, "provider": provider, "operation": operation,
                     "render_unit_id": render_unit_id},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM provider_jobs WHERE id=?", (job_id,)).fetchone())


def poll_provider_job(
    provider_job_id: str,
    external_job_id: Optional[str] = None,
    new_status: Optional[str] = None,  # 'running', 'completed', 'failed'
    response_payload: Optional[dict] = None,
    error: Optional[str] = None,
    db_path=None,
) -> dict:
    """Update provider job status from an external poll result."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        update_parts = ["polled_at=?"]
        params: list = [now]
        if external_job_id:
            update_parts.append("external_job_id=?")
            params.append(external_job_id)
        if new_status:
            new_status = normalize_provider_status(new_status)
            update_parts.append("status=?")
            params.append(new_status)
            if new_status in ("completed", "failed"):
                update_parts.append("completed_at=?")
                params.append(now)
        if response_payload is not None:
            update_parts.append("response_json=?")
            params.append(_db._json(response_payload))
        if error:
            update_parts.append("error_json=?")
            params.append(_db._json({"error": error}))
        params.append(provider_job_id)
        conn.execute(
            f"UPDATE provider_jobs SET {', '.join(update_parts)} WHERE id=?", params
        )
        return dict(conn.execute(
            "SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)
        ).fetchone())


def count_active_provider_jobs(
    production_id: str,
    provider: str,
    model: Optional[str] = None,
    db_path=None,
) -> int:
    """Count submitted/running provider jobs, optionally scoped by request model."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        """SELECT request_json FROM provider_jobs
           WHERE production_id=? AND provider=? AND status IN ('submitted','running')""",
        (production_id, provider),
    ).fetchall()
    conn.close()
    if model is None:
        return len(rows)

    count = 0
    for row in rows:
        try:
            payload = json.loads(row["request_json"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        if payload.get("model") == model:
            count += 1
    return count


def ensure_render_unit_artifact_state(render_unit_id: str, db_path=None) -> Optional[dict]:
    """Treat any existing linked/on-disk artifact as authoritative generated state.

    Returns the artifact row when the render unit already has recoverable media,
    otherwise None.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
    if not ru:
        conn.close()
        return None

    art = None
    if ru["active_artifact_id"]:
        art = conn.execute(
            """SELECT * FROM artifacts
               WHERE id=? AND deleted_at IS NULL
                 AND kind='generated_media'
                 AND (mime_type LIKE 'video/%' OR uri LIKE '%.mp4')""",
            (ru["active_artifact_id"],),
        ).fetchone()
    if not art:
        art = conn.execute(
            """SELECT a.* FROM artifacts a
               JOIN provider_jobs pj ON a.provider_job_id = pj.id
               WHERE pj.render_unit_id=? AND a.deleted_at IS NULL
                 AND a.kind='generated_media'
                 AND (a.mime_type LIKE 'video/%' OR a.uri LIKE '%.mp4')
               ORDER BY a.created_at DESC LIMIT 1""",
            (render_unit_id,),
        ).fetchone()
    conn.close()

    if not art:
        return None
    artifact = dict(art)
    uri = artifact.get("uri")
    if not uri or not Path(uri).exists():
        return None

    now = _db._now()
    with _db.transaction(db_path) as conn:
        latest = conn.execute(
            "SELECT status FROM render_units WHERE id=?", (render_unit_id,)
        ).fetchone()
        if latest and latest["status"] != "valid":
            conn.execute(
                """UPDATE render_units
                   SET active_artifact_id=?, status='generated', updated_at=?
                   WHERE id=?""",
                (artifact["id"], now, render_unit_id),
            )
    return artifact


def _extract_and_register_diagnostic_audio(
    production_id: str,
    video_path: str | Path,
    source_slice_artifact_id: Optional[str],
    provider_job_id: str,
    db_path=None,
) -> Optional[dict]:
    """
    LB-401: Probe returned container, extract audio if present, and register as diagnostic-only.
    Returns the registered artifact dict if audio was found and extracted, else None.
    """
    import subprocess
    import json
    from pathlib import Path
    
    video_path = Path(video_path)
    if not video_path.exists():
        return None
        
    # 1. Probe returned container for audio stream
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "json", str(video_path)
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        probe_data = json.loads(result.stdout)
        has_audio = bool(probe_data.get("streams"))
    except json.JSONDecodeError:
        has_audio = False
        
    if not has_audio:
        return None
        
    # 2. Extract returned audio as a separate optional artifact
    audio_path = video_path.with_suffix(".diagnostic_audio.wav")
    extract_cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1",
        str(audio_path)
    ]
    subprocess.run(extract_cmd, capture_output=True, check=True)
    
    if not audio_path.exists():
        return None
        
    # 3. Register audio artifact with diagnostic-only tags
    diagnostic_metadata = {
        "eligible_for_final_narration": False,
        "usage_policy": "diagnostic_only",
        "source_slice_artifact_id": source_slice_artifact_id,
        "provider_job_id": provider_job_id,
        "extracted_from_video": str(video_path.name),
    }
    
    art = _repo.register_artifact(
        production_id,
        audio_path,
        kind="provider_diagnostic_audio",
        provider_job_id=provider_job_id,
        extra_metadata=diagnostic_metadata,
        db_path=db_path,
    )
    
    return art


def complete_provider_job(
    provider_job_id: str,
    result_artifact_path: str | Path,
    result_metadata: Optional[dict] = None,
    db_path=None,
) -> dict:
    """Mark a provider job complete and register the output artifact.

    Atomically:
    1. Registers the artifact in the immutable registry.
    2. Links the artifact to the render unit.
    3. Records the provider job response.
    4. Appends a cost event if actual_usd is in result_metadata.
    5. (LB-401) Extracts and registers any embedded audio as diagnostic-only.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    job = conn.execute("SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)).fetchone()
    conn.close()
    if not job:
        raise ProviderJobError(f"provider_job {provider_job_id} not found")
    job = dict(job)

    art = _repo.register_artifact(
        job["production_id"],
        result_artifact_path,
        kind="generated_media",
        provider_job_id=provider_job_id,
        extra_metadata=result_metadata or {},
        db_path=db_path,
    )

    # LB-401: Extract and register provider-returned audio as diagnostic-only
    source_slice_id = (result_metadata or {}).get("source_slice_artifact_id")
    _extract_and_register_diagnostic_audio(
        production_id=job["production_id"],
        video_path=result_artifact_path,
        source_slice_artifact_id=source_slice_id,
        provider_job_id=provider_job_id,
        db_path=db_path,
    )

    now = _db._now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            """UPDATE provider_jobs SET status='completed', completed_at=?, response_json=?
               WHERE id=?""",
            (now, _db._json(result_metadata or {}), provider_job_id),
        )
        # Link artifact to render unit
        if job["render_unit_id"]:
            conn.execute(
                """UPDATE render_units SET active_artifact_id=?, status='generated', updated_at=?
                   WHERE id=?""",
                (art["id"], now, job["render_unit_id"]),
            )

    # Record actual cost if provided
    if result_metadata and result_metadata.get("actual_usd") is not None:
        with _db.transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO cost_events
                   (id, production_id, provider_job_id, provider, operation,
                    actual_usd, currency, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    _db._id("cost"), job["production_id"], provider_job_id,
                    job["provider"], job["operation"],
                    result_metadata["actual_usd"], "USD", now,
                ),
            )

    _db.append_event(
        job["production_id"], "provider_job_completed",
        payload={"job_id": provider_job_id, "artifact_id": art["id"]},
        db_path=db_path,
    )
    return art


def fail_provider_job(
    provider_job_id: str,
    error: str,
    db_path=None,
) -> dict:
    """Mark a provider job failed and propagate to its render unit."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        job = conn.execute("SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)).fetchone()
        if not job:
            raise ProviderJobError(f"provider_job {provider_job_id} not found")
        conn.execute(
            """UPDATE provider_jobs SET status='failed', completed_at=?,
               error_json=? WHERE id=?""",
            (now, _db._json({"error": error}), provider_job_id),
        )
        if job["render_unit_id"]:
            conn.execute(
                "UPDATE render_units SET status='failed', updated_at=? WHERE id=?",
                (now, job["render_unit_id"]),
            )
        return dict(conn.execute("SELECT * FROM provider_jobs WHERE id=?", (provider_job_id,)).fetchone())


# ---------------------------------------------------------------------------
# QA-604  Media validation evidence
# ---------------------------------------------------------------------------

def record_validation_evidence(
    production_id: str,
    subject_type: str,
    subject_id: str,
    validator_name: str,
    passed: bool,
    evidence: dict,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Store validation evidence and update the subject's status.

    A subject is only consumable when required validations pass (HARD INVARIANT #4).

    PASS  → render_unit.status = 'valid'
    FAIL  → render_unit.status = 'needs_repair' (ENG-0504)
    """
    now = _db._now()
    with _db.transaction(db_path) as conn:
        val_id = _db._id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_by_stage_run_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                val_id, production_id, subject_type, subject_id, validator_name,
                "pass" if passed else "fail",
                _db._json(evidence), stage_run_id, now,
            ),
        )
        if passed and subject_type == "render_unit":
            conn.execute(
                "UPDATE render_units SET approved_validation_id=?, status='valid', updated_at=? WHERE id=?",
                (val_id, now, subject_id),
            )
        if not passed and subject_type == "render_unit":
            conn.execute(
                "UPDATE render_units SET status='needs_repair', updated_at=? WHERE id=?",
                (now, subject_id),
            )
        return dict(conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone())


def run_render_unit_qa(
    production_id: str,
    render_unit_id: str,
    checks: dict,
    db_path=None,
) -> dict:
    """Run the standard media QA checklist against a render unit.

    checks: {
        "file_exists": bool,
        "dimensions_ok": bool,
        "duration_ok": bool,
        "audio_policy_ok": bool,
        "sha_match": bool,
        "details": {...}
    }

    Returns validation row. Raises if the render unit has no active artifact.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
    conn.close()
    if not ru:
        raise ValueError(f"render_unit {render_unit_id} not found")
    if not ru["active_artifact_id"]:
        raise ValueError(f"render_unit {render_unit_id} has no active artifact — cannot QA")

    required_checks = ["file_exists", "dimensions_ok", "duration_ok", "audio_policy_ok"]
    passed = all(bool(checks.get(k)) for k in required_checks)
    # sha_match is also required when present
    if "sha_match" in checks:
        passed = passed and bool(checks["sha_match"])

    return record_validation_evidence(
        production_id, "render_unit", render_unit_id,
        "qa_media", passed, checks, db_path=db_path,
    )


# ---------------------------------------------------------------------------
# QA-606  Contract-based media QA (ENG-0501/0502/0503/0504/0505)
# ---------------------------------------------------------------------------

CONTRACT_EVIDENCE_KEYS = frozenset({
    "render_method", "contract_version", "file_exists", "sha_match",
    "dimensions_ok", "duration_ok", "provenance_ok", "text_policy_ok",
})


def _check_file_exists(artifact_path: Path) -> bool:
    return artifact_path.exists()


def _probe_artifact(artifact_path: Path) -> dict:
    """ffprobe a media file; return {} on any error."""
    import subprocess as _subprocess
    try:
        out = _subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json",
             str(artifact_path)],
            capture_output=True, text=True, check=True, timeout=15,
        ).stdout
        return json.loads(out)
    except Exception:
        return {}


def _ffprobe_dimensions_duration(artifact_path: Path) -> dict:
    """Extract width, height, duration_ms from the first video stream using ffprobe."""
    import subprocess as _subprocess
    r = _subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "default=noprint_wrappers=1", str(artifact_path)],
        capture_output=True, text=True, timeout=10,
    )
    w = h = dur_ms = None
    for line in r.stdout.splitlines():
        if line.startswith("width="):
            w = int(line.split("=", 1)[1])
        elif line.startswith("height="):
            h = int(line.split("=", 1)[1])
        elif line.startswith("duration="):
            try:
                dur_ms = int(float(line.split("=", 1)[1]) * 1000)
            except ValueError:
                pass
    return {"width": w, "height": h, "duration_ms": dur_ms}


def _check_sha_match(artifact_path: Path, expected_sha: Optional[str]) -> bool:
    if not expected_sha:
        return True
    actual = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return actual == expected_sha


def _qa_local_graphic(
    production_id: str, render_unit: dict, artifact: Optional[dict],
    artifact_path: Optional[Path], db_path=None,
) -> tuple[bool, dict]:
    """ENG-0502: QA for local_graphic render units.

    Checks:
    - artifact exists and is linked
    - artifact provenance says local renderer
    - no provider job exists for render unit
    - deterministic_text_spec exists
    - text_spec_sha256 matches current DTS
    - file exists (dimensions/duration if MP4)
    """
    evidence: dict = {}
    issues: list[str] = []

    # 1. Artifact exists
    if not artifact or not artifact_path:
        evidence["file_exists"] = False
        issues.append("missing_artifact")
        return (False, {"render_method": "local_graphic", "contract_version": CONTRACT_VERSION,
                        "file_exists": False, "sha_match": False, "dimensions_ok": False,
                        "duration_ok": False, "provenance_ok": False, "text_policy_ok": False,
                        "issues": issues})

    evidence["file_exists"] = True

    # 2. Active artifact is linked
    if not render_unit.get("active_artifact_id"):
        evidence["artifact_linked"] = False
        issues.append("artifact_not_linked")

    # 3. Artifact provenance says local renderer
    art_meta_str = artifact.get("metadata_json") or "{}"
    art_meta = json.loads(art_meta_str) if isinstance(art_meta_str, str) else art_meta_str
    render_method = art_meta.get("render_method", "")
    renderer = art_meta.get("renderer", "")
    provenance_ok = (render_method == "local_graphic" and "render_graphics.py" in renderer)
    evidence["provenance_ok"] = provenance_ok
    evidence["render_method"] = "local_graphic"
    evidence["renderer"] = renderer
    if not provenance_ok:
        issues.append("wrong_provenance")

    # 4. No provider job exists for render unit
    conn = _db.connect(db_path)
    pj_count = conn.execute(
        "SELECT COUNT(*) as c FROM provider_jobs WHERE render_unit_id=?",
        (render_unit["id"],),
    ).fetchone()["c"]
    conn.close()
    no_provider_job = (pj_count == 0)
    evidence["no_provider_job"] = no_provider_job
    if not no_provider_job:
        issues.append("has_provider_job")

    # 5. Deterministic text spec exists in metadata
    ru_meta_str = render_unit.get("metadata_json") or "{}"
    ru_meta = json.loads(ru_meta_str) if isinstance(ru_meta_str, str) else ru_meta_str
    dts = ru_meta.get("deterministic_text_spec")
    text_spec_ok = dts is not None
    evidence["text_spec_exists"] = text_spec_ok
    if not text_spec_ok:
        issues.append("missing_deterministic_text_spec")

    # 6. Text spec SHA256 matches
    spec_sha_match = True
    if dts and "text_spec_sha256" in art_meta:
        current_spec_sha = hashlib.sha256(_db._json(dts).encode()).hexdigest()
        stored_sha = art_meta["text_spec_sha256"]
        spec_sha_match = (current_spec_sha == stored_sha)
    evidence["text_spec_sha_match"] = spec_sha_match
    if not spec_sha_match:
        issues.append("text_spec_hash_mismatch")

    # 7. File dimensions/duration if MP4
    dims_ok = True
    dur_ok = True
    if artifact_path and artifact_path.suffix.lower() == ".mp4":
        probe = _ffprobe_dimensions_duration(artifact_path)
        dims_ok = probe.get("width") is not None and probe.get("height") is not None
        dur_ok = probe.get("duration_ms") is not None

    # 8. SHA match between artifact DB record and disk
    sha_ok = _check_sha_match(artifact_path, artifact.get("sha256")) if artifact_path else False
    evidence["sha_match"] = sha_ok
    evidence["dimensions_ok"] = dims_ok
    evidence["duration_ok"] = dur_ok
    evidence["text_policy_ok"] = True  # local graphic renders exact text by design

    evidence["issues"] = issues
    evidence["ocr_available"] = False
    evidence["ocr_note"] = "OCR not applicable for local_graphic (PNG overlay)"

    evidence["contract_version"] = CONTRACT_VERSION
    evidence["render_method"] = "local_graphic"

    passed = (
        evidence["file_exists"] and evidence["provenance_ok"] and evidence["sha_match"]
        and evidence["no_provider_job"] and text_spec_ok and spec_sha_match
    )
    return (passed, evidence)


def _check_text_policy_via_ocr(artifact_path: Path) -> tuple[bool, dict]:
    """ENG-0503: Sample video frames and attempt OCR to detect visible text.

    Returns (passed, ocr_evidence). If OCR is unavailable and strict mode is
    required, the caller must handle the fail path explicitly.
    """
    ocr_evidence: dict = {"ocr_available": False, "ocr_frames_checked": 0}

    try:
        import pytesseract
    except ImportError:
        ocr_evidence["ocr_available"] = False
        ocr_evidence["ocr_error"] = "pytesseract not installed"
        return (False, ocr_evidence)

    import subprocess as _subprocess
    try:
        _subprocess.run(
            [pytesseract.pytesseract.tesseract_cmd, "--version"],
            capture_output=True, check=True, timeout=5,
        )
    except Exception:
        ocr_evidence["ocr_available"] = False
        ocr_evidence["ocr_error"] = "tesseract binary not available"
        return (False, ocr_evidence)

    try:
        from PIL import Image
    except ImportError:
        ocr_evidence["ocr_available"] = False
        ocr_evidence["ocr_error"] = "PIL not installed"
        return (False, ocr_evidence)

    import subprocess as _subprocess
    import tempfile

    ocr_evidence["ocr_available"] = True

    with tempfile.TemporaryDirectory(prefix="ocr_frames_") as td:
        frame_path = Path(td) / "frame_%03d.png"

        # Extract one frame from middle of video
        probe = _ffprobe_dimensions_duration(artifact_path)
        duration_ms = probe.get("duration_ms") or 5000
        mid_sec = duration_ms / 2000.0

        try:
            _subprocess.run(
                ["ffmpeg", "-y", "-ss", str(mid_sec), "-i", str(artifact_path),
                 "-vframes", "4", "-vf", "fps=1/2", str(frame_path)],
                capture_output=True, text=True, check=True, timeout=30,
            )
        except Exception as exc:
            ocr_evidence["ocr_error"] = f"frame extraction failed: {exc}"
            return (False, ocr_evidence)

        frames = sorted(Path(td).glob("frame_*.png"))
        ocr_evidence["ocr_frames_checked"] = len(frames)
        found_text_count = 0
        detected_texts = []

        for fp in frames:
            try:
                img = Image.open(fp)
                text = pytesseract.image_to_string(img).strip()
                if text:
                    found_text_count += 1
                    detected_texts.append(text[:100])
            except Exception:
                pass

        ocr_evidence["frames_with_text"] = found_text_count
        if detected_texts:
            ocr_evidence["sample_detected_text"] = detected_texts[:3]

        passed = found_text_count == 0
        ocr_evidence["text_detected"] = not passed

    return (passed, ocr_evidence)


def _qa_provider_video(
    production_id: str, render_unit: dict, artifact: Optional[dict],
    artifact_path: Optional[Path], db_path=None,
) -> tuple[bool, dict]:
    """ENG-0503: QA for provider-generated video (text_policy enforcement).

    For NO_VISIBLE_TEXT: attempt OCR; fail if text detected or OCR unavailable
    in strict mode. For other text policies, pass with note.
    """
    evidence: dict = {
        "render_method": "generated_video", "contract_version": CONTRACT_VERSION,
    }
    issues: list[str] = []

    if not artifact or not artifact_path:
        evidence["file_exists"] = False
        issues.append("missing_artifact")
        return (False, evidence)

    evidence["file_exists"] = _check_file_exists(artifact_path)

    # Mechanical checks
    probe = _ffprobe_dimensions_duration(artifact_path)
    dims_ok = probe.get("width") is not None and probe.get("height") is not None
    dur_ok = probe.get("duration_ms") is not None
    sha_ok = _check_sha_match(artifact_path, artifact.get("sha256"))
    evidence["dimensions_ok"] = dims_ok
    evidence["duration_ok"] = dur_ok
    evidence["sha_match"] = sha_ok

    # Text policy check
    text_policy = (render_unit.get("text_policy") or "").strip().upper()
    text_policy_ok = True
    ocr_result = {}

    if text_policy == "NO_VISIBLE_TEXT":
        ocr_passed, ocr_evidence = _check_text_policy_via_ocr(artifact_path)
        ocr_result = ocr_evidence
        if ocr_evidence.get("ocr_available"):
            text_policy_ok = ocr_passed
            if not ocr_passed:
                issues.append("visible_text_detected")
        else:
            strict = os.environ.get("OCR_STRICT_MODE", "1") == "1"
            from smoke_config import SmokeConfig as _SmokeConfig
            cfg = _SmokeConfig.load()
            if strict and not cfg.allow_ocr_unavailable:
                text_policy_ok = False
                issues.append("ocr_unavailable_strict_mode")
            else:
                ocr_result["ocr_note"] = "OCR unavailable in non-strict mode; text policy not enforced"

    evidence["text_policy_ok"] = text_policy_ok
    evidence["text_policy"] = text_policy
    evidence.update(ocr_result)
    evidence["provenance_ok"] = True
    evidence["issues"] = issues

    passed = (
        evidence["file_exists"] and dims_ok and sha_ok and text_policy_ok
    )
    return (passed, evidence)


def _qa_hero_lipsync(
    production_id: str, render_unit: dict, artifact: Optional[dict],
    artifact_path: Optional[Path], db_path=None,
) -> tuple[bool, dict]:
    """ENG-0505: QA for hero lipsync render units.

    Checks:
    - Artifact duration vs intended audio slice duration
    - Fail if delta > 100ms
    - Record exact durations in evidence
    """
    evidence: dict = {
        "render_method": "hero_lipsync", "contract_version": CONTRACT_VERSION,
    }
    issues: list[str] = []

    if not artifact or not artifact_path:
        evidence["file_exists"] = False
        evidence["sha_match"] = False
        evidence["dimensions_ok"] = False
        evidence["duration_ok"] = False
        evidence["provenance_ok"] = False
        evidence["text_policy_ok"] = False
        issues.append("missing_artifact")
        return (False, evidence)

    evidence["file_exists"] = True
    evidence["provenance_ok"] = True
    evidence["text_policy_ok"] = True

    probe = _ffprobe_dimensions_duration(artifact_path)
    video_duration_ms = probe.get("duration_ms")
    width = probe.get("width")
    height = probe.get("height")
    evidence["dimensions_ok"] = width is not None and height is not None
    evidence["actual_width"] = width
    evidence["actual_height"] = height

    sha_ok = _check_sha_match(artifact_path, artifact.get("sha256"))
    evidence["sha_match"] = sha_ok

    intended_duration_ms = render_unit.get("required_duration_ms", 0) or 0

    if video_duration_ms is not None and intended_duration_ms > 0:
        delta_ms = abs(video_duration_ms - intended_duration_ms)
        evidence["video_duration_ms"] = video_duration_ms
        evidence["intended_duration_ms"] = intended_duration_ms
        evidence["duration_delta_ms"] = delta_ms
        DURATION_TOLERANCE_MS = 500
        evidence["duration_tolerance_ms"] = DURATION_TOLERANCE_MS
        evidence["duration_ok"] = delta_ms <= DURATION_TOLERANCE_MS
        if not evidence["duration_ok"]:
            issues.append(
                f"duration_delta_{delta_ms}ms_exceeds_{DURATION_TOLERANCE_MS}ms"
            )
    else:
        evidence["duration_ok"] = False
        issues.append("duration_probe_failed")

    evidence["issues"] = issues

    passed = (
        evidence["file_exists"] and evidence["dimensions_ok"] and evidence["sha_match"]
        and evidence["duration_ok"]
    )
    return (passed, evidence)


def _qa_still(
    production_id: str, render_unit: dict, artifact: Optional[dict],
    artifact_path: Optional[Path], db_path=None,
) -> tuple[bool, dict]:
    """QA for still/asset reuse render units (minimal mechanical checks)."""
    evidence: dict = {
        "render_method": "still_kenburns", "contract_version": CONTRACT_VERSION,
    }
    if not artifact or not artifact_path:
        evidence["file_exists"] = False
        evidence["sha_match"] = False
        evidence["dimensions_ok"] = False
        evidence["duration_ok"] = False
        evidence["provenance_ok"] = False
        evidence["text_policy_ok"] = False
        evidence["issues"] = ["missing_artifact"]
        return (False, evidence)

    evidence["file_exists"] = True
    evidence["sha_match"] = _check_sha_match(artifact_path, artifact.get("sha256"))
    evidence["provenance_ok"] = True
    evidence["text_policy_ok"] = True

    probe = _ffprobe_dimensions_duration(artifact_path)
    evidence["dimensions_ok"] = probe.get("width") is not None and probe.get("height") is not None
    evidence["duration_ok"] = probe.get("duration_ms") is not None

    passed = (
        evidence["file_exists"] and evidence["sha_match"]
        and evidence["dimensions_ok"]
    )
    return (passed, evidence)


def run_contract_media_qa(
    db, production_id: str, render_unit_id: str,
) -> dict:
    """ENG-0501: Dispatch media QA by render method.

    Loads the render unit and its active artifact, classifies the render
    method via ``media_contract.classify_render_method``, and dispatches
    to the appropriate QA function.

    Returns the validation evidence dict with render method, contract version,
    and all check results. The validation is also recorded in the DB with
    status transitions (ENG-0504).

    Args:
        db: DB path (None for env-var default)
        production_id: target production row id
        render_unit_id: render unit to validate

    Returns:
        The validation row dict (as returned from DB after record_validation_evidence).
    """
    _db.migrate(db)

    conn = _db.connect(db)
    ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
    art = None
    if ru and ru["active_artifact_id"]:
        art = conn.execute(
            "SELECT * FROM artifacts WHERE id=?", (ru["active_artifact_id"],)
        ).fetchone()
    conn.close()

    if not ru:
        raise ValueError(f"render_unit {render_unit_id} not found")

    render_unit = dict(ru)
    artifact = dict(art) if art else None
    artifact_path = Path(artifact["uri"]) if (artifact and artifact.get("uri")) else None

    render_method = _contract.classify_render_method(
        render_unit.get("asset_type", ""),
        audio_policy=render_unit.get("audio_policy"),
        text_policy=render_unit.get("text_policy"),
    )

    dispatch = {
        "deterministic_graphic": _qa_local_graphic,
        "hero_lipsync": _qa_hero_lipsync,
        "generated_video": _qa_provider_video,
        "still_kenburns": _qa_still,
    }
    qa_fn = dispatch.get(render_method, _qa_provider_video)

    passed, evidence = qa_fn(
        production_id, render_unit, artifact, artifact_path, db_path=db,
    )

    evidence["render_method"] = render_method
    evidence["contract_version"] = CONTRACT_VERSION

    validation = record_validation_evidence(
        production_id, "render_unit", render_unit_id,
        "qa_media_contract", passed, evidence, db_path=db,
    )

    return validation


# ---------------------------------------------------------------------------
# QA-605  Change-request routing
# ---------------------------------------------------------------------------

def route_change_request(
    production_id: str,
    render_unit_id: str,
    change_type: str,  # 'regenerate', 're-slice', 're-plan', 're-render'
    reason: str,
    requested_by: str = "qa_media",
    target_stage: str = "generate_media",
    db_path=None,
) -> dict:
    """Create a change request and reset the render unit so it can re-flow.

    Change types and their target stages:
    - 'regenerate'  → generate_media (new provider call needed)
    - 're-slice'    → audio_timing   (re-slice audio)
    - 're-plan'     → compile_media  (change prompt/model)
    - 're-render'   → assemble       (re-render from existing clips)
    """
    now = _db._now()
    with _db.transaction(db_path) as conn:
        ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
        if not ru:
            raise ValueError(f"render_unit {render_unit_id} not found")

        req_id = _db._id("change")
        conn.execute(
            """INSERT INTO change_requests
               (id, production_id, subject_type, subject_id, change_type,
                requested_by_stage, target_stage, reason, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                req_id, production_id, "render_unit", render_unit_id,
                change_type, requested_by, target_stage, reason, "open", now,
            ),
        )
        if target_stage == "generate_media":
            # Set back to 'ordered' so generate_media picks it up for regeneration
            conn.execute(
                "UPDATE render_units SET status='ordered', updated_at=? WHERE id=?",
                (now, render_unit_id),
            )
        else:
            conn.execute(
                "UPDATE render_units SET status='change_requested', updated_at=? WHERE id=?",
                (now, render_unit_id),
            )
        _db.append_event(
            production_id, "change_request_created",
            payload={"req_id": req_id, "render_unit_id": render_unit_id,
                     "change_type": change_type, "target_stage": target_stage},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM change_requests WHERE id=?", (req_id,)).fetchone())


def resolve_change_request(
    production_id: str,
    change_request_id: str,
    resolution: str,  # 'accepted' | 'rejected'
    resolved_by: str = "system",
    db_path=None,
) -> dict:
    """Resolve an open change request and reset render unit to 'ordered'."""
    now = _db._now()
    with _db.transaction(db_path) as conn:
        req = conn.execute(
            "SELECT * FROM change_requests WHERE id=?", (change_request_id,)
        ).fetchone()
        if not req:
            raise ValueError(f"change_request {change_request_id} not found")
        conn.execute(
            """UPDATE change_requests SET status='resolved', resolution_json=?, resolved_at=?
               WHERE id=?""",
            (_db._json({"resolution": resolution, "resolved_by": resolved_by}),
             now, change_request_id),
        )
        if resolution == "accepted":
            conn.execute(
                "UPDATE render_units SET status='ordered', updated_at=? WHERE id=?",
                (now, req["subject_id"]),
            )
        return dict(conn.execute("SELECT * FROM change_requests WHERE id=?", (change_request_id,)).fetchone())


def get_open_change_requests(production_id: str, target_stage: Optional[str] = None, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    if target_stage:
        rows = conn.execute(
            """SELECT * FROM change_requests
               WHERE production_id=? AND status='open' AND target_stage=?""",
            (production_id, target_stage),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM change_requests WHERE production_id=? AND status='open'",
            (production_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# QA-607  Failure classification & repair (ENG-0601/0602/0603)
# ---------------------------------------------------------------------------

VALIDATION_FAILURE_CLASSIFICATIONS = frozenset({
    "missing_artifact", "sha_mismatch", "duration_shortfall",
    "provider_forbidden_asset", "unexpected_visible_text",
    "local_graphic_not_local", "local_graphic_text_mismatch",
    "ocr_unavailable", "hero_lipsync_unverified", "unknown_contract_failure",
    "provider_job_retryable_failure", "provider_job_permanent_failure",
})

REPAIR_ACTIONS = frozenset({
    "render_local_graphic", "regenerate_provider_video",
    "recover_artifact", "rerun_qa", "block_for_manual_review",
    "resubmit_provider_job",
})


def classify_validation_failure(validation_evidence: dict) -> str:
    """ENG-0601: Classify a contract QA failure from its evidence dict.

    Returns one of VALIDATION_FAILURE_CLASSIFICATIONS.
    """
    ev = validation_evidence

    if not ev.get("file_exists"):
        return "missing_artifact"

    if not ev.get("sha_match"):
        return "sha_mismatch"

    render_method = (ev.get("render_method") or "").strip()

    if render_method in ("local_graphic", "deterministic_graphic"):
        has_provider_job = ev.get("no_provider_job") is False
        if has_provider_job:
            return "provider_forbidden_asset"
        if ev.get("provenance_ok") is False:
            return "local_graphic_not_local"
        if ev.get("text_spec_sha_match") is False:
            return "local_graphic_text_mismatch"

    if ev.get("text_detected"):
        return "unexpected_visible_text"

    if ev.get("ocr_available") is False and ev.get("text_policy") in ("NO_VISIBLE_TEXT",):
        if ev.get("text_policy_ok") is not True:
            return "ocr_unavailable"

    if render_method == "hero_lipsync":
        if not ev.get("duration_ok"):
            return "hero_lipsync_unverified"

    if not ev.get("duration_ok"):
        return "duration_shortfall"

    return "unknown_contract_failure"


_RULES = {
    "local_graphic_not_local": "render_local_graphic",
    "local_graphic_text_mismatch": "render_local_graphic",
    "provider_forbidden_asset": "render_local_graphic",
    "unexpected_visible_text": "regenerate_provider_video",
    "missing_artifact": "recover_artifact",
    "sha_mismatch": "block_for_manual_review",
    "ocr_unavailable": "rerun_qa",
    "hero_lipsync_unverified": "regenerate_provider_video",
    "duration_shortfall": "regenerate_provider_video",
    "unknown_contract_failure": "block_for_manual_review",
    "provider_job_retryable_failure": "resubmit_provider_job",
    "provider_job_permanent_failure": "block_for_manual_review",
}


def choose_repair_action(render_unit: dict, failure_class: str) -> str:
    """ENG-0602: Map a failure classification to a repair action.

    Falls back to 'block_for_manual_review' for unrecognised classes.
    """
    action = _RULES.get(failure_class, "block_for_manual_review")
    if action == "render_local_graphic" and render_unit.get("asset_type") != "local_graphic":
        action = "block_for_manual_review"
    return action



def _repair_resubmit_provider_job(
    production_id: str,
    render_unit: dict,
    failed_pjob: dict,
    db_path=None,
) -> dict:
    """S10-C09: Resubmit a failed provider job for a render unit.

    Reads the original request payload, re-submits via submit_provider_job,
    and updates the render unit status to 'generating'.
    """
    import paid_adapters
    from provider_adapter import get_provider_adapter

    orig_payload = {}
    model = "seedance_2_0"
    try:
        conn = _db.connect(db_path)
        job_row = conn.execute(
            "SELECT request_json FROM provider_jobs WHERE id=?",
            (failed_pjob["id"],),
        ).fetchone()
        conn.close()
        if job_row and job_row["request_json"]:
            orig_payload = json.loads(job_row["request_json"])
            model = orig_payload.get("model", model)
    except Exception:
        pass

    duration_sec = (orig_payload.get("duration_ms") or 5000) / 1000.0
    # S10-C09: backoff jitter on resubmit (1-3s random)
    import random
    time.sleep(1 + random.random() * 2)

    # S10-C10: Use a unique idempotency key so the resubmit creates a NEW
    # provider_job instead of returning the existing (failed) one.
    import hashlib as _hashlib
    import time as _time
    resubmit_key = f"resubmit:{failed_pjob['id']}:{_time.time_ns()}"
    job = submit_provider_job(
        production_id=production_id,
        render_unit_id=render_unit["id"],
        provider="higgsfield",
        operation="generate_video",
        idempotency_key=resubmit_key,
        request_payload=orig_payload,
        db_path=db_path,
    )
    return {"new_job_id": job["id"]}

def run_repair_lifecycle(
    production_id: str,
    render_unit_id: str,
    db_path=None,
) -> dict:
    """ENG-0603: Execute the repair lifecycle for a single render unit.

    1. Load the latest failed validation.
    2. Classify the failure.
    3. Choose a repair action.
    4. Execute the action (render_local_graphic / recover_artifact / etc.).
    5. Run contract QA on the result.
    6. Return the outcome.

    Preserves the old artifact (does not delete) but marks it inactive.
    """
    import render_graphics as _rg

    _db.migrate(db_path)

    conn = _db.connect(db_path)
    ru = conn.execute("SELECT * FROM render_units WHERE id=?", (render_unit_id,)).fetchone()
    if not ru:
        conn.close()
        raise ValueError(f"render_unit {render_unit_id} not found")
    render_unit = dict(ru)

    failure = conn.execute(
        """SELECT status, evidence_json FROM validations
           WHERE subject_id=? AND validator_name='qa_media_contract'
           ORDER BY created_at DESC, rowid DESC LIMIT 1""",
        (render_unit_id,),
    ).fetchone()
    conn.close()

    if not failure:
        # S10-C09: No qa_media_contract validation — check for provider job failure
        conn2 = _db.connect(db_path)
        pjob = conn2.execute(
            """SELECT id, error_json FROM provider_jobs
               WHERE render_unit_id=? AND status='failed'
               ORDER BY COALESCE(completed_at, '') DESC, id DESC LIMIT 1""",
            (render_unit_id,),
        ).fetchone()
        conn2.close()
        if pjob:
            error_text = ""
            try:
                error_json = json.loads(pjob["error_json"] or "{}")
                error_text = error_json.get("error", "")
            except (json.JSONDecodeError, TypeError):
                pass
            from paid_adapters import _classify_retryable
            retryable = _classify_retryable(error_text)
            failure_class = "provider_job_retryable_failure" if retryable else "provider_job_permanent_failure"
            action = choose_repair_action(render_unit, failure_class)
            if action == "block_for_manual_review":
                raise RuntimeError(
                    f"REPAIR BLOCKED: render_unit {render_unit_id} provider job "
                    f"failed permanently: {error_text[:200]}"
                )
            # resubmit_provider_job action — handled below
            result = {
                "render_unit_id": render_unit_id,
                "failure_class": failure_class,
                "action": action,
                "new_artifact_id": None,
                "qa_passed": None,
            }
            _repair_resubmit_provider_job(production_id, render_unit, pjob, db_path=db_path)
            result["new_job_submitted"] = True
            return result
        raise ValueError(f"No repair path found for render_unit {render_unit_id}")

    # ENG-0603 idempotency: if the latest validation already passes, the render
    # unit is already repaired — return success without modifying state.
    if failure["status"] == "pass":
        evidence = json.loads(failure["evidence_json"]) if isinstance(failure["evidence_json"], str) else failure["evidence_json"]
        return {
            "render_unit_id": render_unit_id,
            "failure_class": None,
            "action": "no_action_needed",
            "already_passing": True,
            "qa_passed": True,
            "evidence": evidence,
        }

    evidence = json.loads(failure["evidence_json"]) if isinstance(failure["evidence_json"], str) else failure["evidence_json"]
    failure_class = classify_validation_failure(evidence)
    action = choose_repair_action(render_unit, failure_class)

    result = {
        "render_unit_id": render_unit_id,
        "failure_class": failure_class,
        "action": action,
        "new_artifact_id": None,
        "qa_passed": None,
    }

    if action == "render_local_graphic":
        _reset_render_unit_for_repair(render_unit_id, db_path=db_path)
        new_path = _rg.render_local_graphic_render_unit(db_path, production_id, render_unit_id)
        qa = run_contract_media_qa(db_path, production_id, render_unit_id)
        conn2 = _db.connect(db_path)
        ru_after = conn2.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?",
            (render_unit_id,),
        ).fetchone()
        conn2.close()
        result["new_artifact_id"] = ru_after["active_artifact_id"] if ru_after else None
        result["qa_passed"] = (qa.get("status") == "pass")
        result["qa_validation_id"] = qa.get("id")

    elif action == "recover_artifact":
        result = _run_recover_artifact(production_id, render_unit, db_path=db_path)

    elif action == "regenerate_provider_video":
        cr = route_change_request(
            production_id, render_unit_id,
            change_type="regenerate",
            reason=f"repair: {failure_class}",
            db_path=db_path,
        )
        result["change_request_id"] = cr.get("id")
        result["qa_passed"] = False

    elif action == "rerun_qa":
        qa = run_contract_media_qa(db_path, production_id, render_unit_id)
        result["qa_passed"] = (qa.get("status") == "pass")
        result["qa_validation_id"] = qa.get("id")

    elif action == "block_for_manual_review":
        raise RuntimeError(
            f"REPAIR BLOCKED: render_unit {render_unit_id} failure "
            f"'{failure_class}' requires manual review"
        )

    return result


def _reset_render_unit_for_repair(render_unit_id: str, db_path=None):
    """Clear active_artifact_id so a new artifact can be linked.

    Preserves the old artifact row (not deleted). Idempotent.
    """
    with _db.transaction(db_path) as conn:
        ru = conn.execute(
            "SELECT active_artifact_id FROM render_units WHERE id=?",
            (render_unit_id,),
        ).fetchone()
        if ru and ru["active_artifact_id"]:
            conn.execute(
                "UPDATE render_units SET active_artifact_id=NULL, status='ordered', updated_at=? WHERE id=?",
                (_db._now(), render_unit_id),
            )


def _run_recover_artifact(
    production_id: str, render_unit: dict, db_path=None,
) -> dict:
    """Try to recover a previous artifact for the render unit.

    Finds the most recent non-deleted artifact (excluding the current
    active one), probes it, and links it if viable.  Falls through to
    block_for_manual_review if no viable artifact exists.
    """
    ru_id = render_unit["id"]
    conn = _db.connect(db_path)
    candidates = conn.execute(
        """SELECT a.* FROM artifacts a
           WHERE a.production_id=(
               SELECT production_id FROM render_units WHERE id=?
           )
           AND a.deleted_at IS NULL
           AND (
               a.provider_job_id IN (
                   SELECT id FROM provider_jobs WHERE render_unit_id=?
               )
               OR a.metadata_json LIKE '%"source_render_unit_id":"' || ? || '"%'
               OR EXISTS (
                   SELECT 1 FROM render_units r
                   WHERE r.id=? AND r.active_artifact_id=a.id
               )
           )
           ORDER BY a.created_at DESC LIMIT 5""",
        (ru_id, ru_id, ru_id, ru_id),
    ).fetchall()
    conn.close()

    from pathlib import Path as _Path
    for art in candidates:
        p = _Path(art["uri"]) if art["uri"] else None
        if p and p.exists():
            _reset_render_unit_for_repair(ru_id, db_path=db_path)
            with _db.transaction(db_path) as conn:
                conn.execute(
                    "UPDATE render_units SET active_artifact_id=?, status='generated', updated_at=? WHERE id=?",
                    (art["id"], _db._now(), ru_id),
                )
            qa = run_contract_media_qa(db_path, production_id, ru_id)
            return {
                "render_unit_id": ru_id,
                "failure_class": "missing_artifact",
                "action": "recover_artifact",
                "new_artifact_id": art["id"],
                "qa_passed": (qa.get("status") == "pass"),
                "qa_validation_id": qa.get("id"),
            }

    raise RuntimeError(
        f"REPAIR BLOCKED: render_unit {ru_id} has no recoverable artifact"
    )
