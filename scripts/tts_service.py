"""Sprint 5: TTS and timing service.

AUD-501  TTS artifact + provenance migration
AUD-502  Alignment and timing spans
PLAN-503 Production storyboard reconciliation
PLAN-504 Render-plan compilation
BUD-505  Budget and spend approval
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

import production_db as _db
import production_repo as _repo
from authoring_service import get_creative_beats, request_approval
from stage_runner import save_document_revision

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# AUD-501  TTS artifact and provenance
# ---------------------------------------------------------------------------

def record_tts_artifact(
    production_id: str,
    audio_path: str | Path,
    script_revision_id: str,
    voice_id: str,
    model: str,
    voice_settings: dict,
    request_fingerprint: str,
    provider_request_id: Optional[str] = None,
    actual_cost_usd: float = 0.0,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Register the master TTS audio file and record full voice provenance (LB-200).

    Reuse rule: Returns existing artifact if script_revision_id, voice_id, model,
    voice_settings, and request_fingerprint exactly match an active record, and the
    stored bytes exist with a matching checksum.

    Returns the artifact row.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)

    # 1. Check for exact fingerprint match to enable idempotent reuse.
    #    S1-T04: query the artifact's metadata_json directly instead of a
    #    fragile JSON-content LIKE join across document_revisions ↔ artifacts.
    #    The TTS artifact's metadata (registered via register_artifact) contains
    #    script_revision_id, voice_id, model, voice_settings, request_fingerprint.
    row = conn.execute(
        """SELECT id, uri, sha256, metadata_json
           FROM artifacts
           WHERE production_id=? AND kind='tts_master' AND deleted_at IS NULL
           ORDER BY created_at DESC LIMIT 1""",
        (production_id,)
    ).fetchone()

    existing = None
    if row:
        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        if (meta.get("script_revision_id") == script_revision_id and
            meta.get("voice_id") == voice_id and
            meta.get("model") == model and
            meta.get("voice_settings") == voice_settings and
            meta.get("request_fingerprint") == request_fingerprint):
            existing = {
                "artifact_id": row["id"],
                "uri": row["uri"],
                "sha256": row["sha256"],
            }

    if existing:
        # The metadata match was already confirmed above. Now verify the stored
        # bytes exist and checksum matches. A mismatch means the immutable master
        # was tampered with or replaced on disk — it must NOT be silently reused,
        # and the corrupt bytes must NOT be registered as a new media artifact.
        # Require explicit regeneration instead.
        art_path = Path(existing["uri"])
        if art_path.exists():
            if _repo._sha256_file(art_path) == existing["sha256"]:
                conn.close()
                return {
                    "id": existing["artifact_id"],
                    "uri": existing["uri"],
                    "sha256": existing["sha256"],
                    "reused": True
                }
            conn.close()
            raise RuntimeError(
                "BLOCKED: TTS_MASTER_CHECKSUM_MISMATCH_REGENERATION_REQUIRED — "
                f"stored master {art_path} no longer matches recorded sha256 "
                f"{existing['sha256']}; the immutable master was altered. "
                "Regenerate TTS before reuse.")

    conn.close()

    # 2. No match or checksum failed: register as new immutable artifact
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"TTS audio not found: {audio_path}")

    # Probe media for sample rate, channels, sample count, duration
    media_info = _repo._probe_media(audio_path)
    fmt = media_info.get("format", {})
    streams = media_info.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    
    duration_ms = int(float(fmt.get("duration", 0)) * 1000) if fmt.get("duration") else None
    sample_rate = int(audio_stream.get("sample_rate", 0)) or None
    channels = int(audio_stream.get("channels", 0)) or None
    sample_count = int(audio_stream.get("nb_samples", 0)) or None

    art = _repo.register_artifact(
        production_id, audio_path, "tts_master",
        stage_run_id=stage_run_id,
        extra_metadata={
            "script_revision_id": script_revision_id,
            "voice_id": voice_id,
            "model": model,
            "voice_settings": voice_settings,
            "request_fingerprint": request_fingerprint,
            "provider_request_id": provider_request_id,
            "sample_rate": sample_rate,
            "channels": channels,
            "sample_count": sample_count,
            "duration_ms": duration_ms,
            "actual_cost_usd": actual_cost_usd,
        },
        db_path=db_path,
    )

    # Record a document with full TTS provenance (enables invalidation when any param changes)
    save_document_revision(
        production_id, "tts_artifact",
        {
            "artifact_id": art["id"],
            "audio_uri": art["uri"],
            "sha256": art["sha256"],
            "script_revision_id": script_revision_id,
            "voice_id": voice_id,
            "model": model,
            "voice_settings": voice_settings,
            "request_fingerprint": request_fingerprint,
            "provider_request_id": provider_request_id,
            "duration_ms": duration_ms,
        },
        stage_run_id=stage_run_id,
        db_path=db_path,
    )
    
    # Link script → tts dependency
    _link_document_dependency(production_id, "tts_artifact", "script", db_path=db_path)

    art["reused"] = False
    return art


def _link_document_dependency(
    production_id: str, dependent_kind: str, dependency_kind: str, db_path=None
) -> None:
    """Record that the active revision of dependent_kind depends on dependency_kind."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    dep_row = conn.execute(
        """SELECT id FROM document_revisions
           WHERE production_id=? AND kind=? AND status='active'
           ORDER BY revision DESC LIMIT 1""",
        (production_id, dependent_kind),
    ).fetchone()
    src_row = conn.execute(
        """SELECT id FROM document_revisions
           WHERE production_id=? AND kind=? AND status='active'
           ORDER BY revision DESC LIMIT 1""",
        (production_id, dependency_kind),
    ).fetchone()
    conn.close()

    if dep_row and src_row:
        with _db.transaction(db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO document_dependencies
                   (document_revision_id, depends_on_document_revision_id, dependency_role)
                   VALUES (?,?,?)""",
                (dep_row["id"], src_row["id"], f"{dependent_kind}_depends_on_{dependency_kind}"),
            )


# ---------------------------------------------------------------------------
# AUD-502  Alignment: timing map → timeline spans
# ---------------------------------------------------------------------------

def commit_timing_spans_from_map(
    production_id: str,
    tts_artifact_id: str,
    timing_map: list[dict],
    db_path=None,
) -> list[dict]:
    """Convert an audio timing map into committed timeline_spans.

    timing_map: list of {beat_id/label, start_ms, end_ms, narration_text}

    Delegates to production_repo.commit_timeline_spans() which enforces
    no-overlap and positive duration invariants.
    """
    if not timing_map:
        raise ValueError("timing_map must not be empty")

    # Normalize: ensure integer ms
    spans = []
    for entry in timing_map:
        start_ms = int(entry.get("start_ms") or round(float(entry.get("start_sec", 0)) * 1000))
        end_ms = int(entry.get("end_ms") or round(float(entry.get("end_sec", 0)) * 1000))
        spans.append({
            "label": entry.get("label") or entry.get("beat_id"),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "narration_text": entry.get("narration_text") or entry.get("text"),
        })

    committed = _repo.commit_timeline_spans(
        production_id, spans, tts_artifact_id=tts_artifact_id, db_path=db_path
    )
    # Save timing document (export projection for legacy compat)
    save_document_revision(
        production_id, "timing_map",
        {"tts_artifact_id": tts_artifact_id, "spans": spans},
        db_path=db_path,
    )
    _link_document_dependency(production_id, "timing_map", "tts_artifact", db_path=db_path)
    return committed


# ---------------------------------------------------------------------------
# PLAN-503  Production storyboard reconciliation
# ---------------------------------------------------------------------------

def reconcile_storyboard_with_timing(
    production_id: str,
    db_path=None,
) -> dict:
    """Reconcile active creative beats with measured timeline spans.

    For each active timeline span, find the matching creative beat by label and
    link creative_beat_id → timeline span. Returns a reconciliation summary.

    Raises if active spans are missing.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    spans = conn.execute(
        "SELECT * FROM timeline_spans WHERE production_id=? AND status='active' ORDER BY ordinal",
        (production_id,),
    ).fetchall()
    if not spans:
        conn.close()
        raise RuntimeError(f"No active timeline spans for production {production_id}")

    beats = conn.execute(
        """SELECT cb.* FROM creative_beats cb
           JOIN document_revisions dr ON cb.storyboard_revision_id = dr.id
           WHERE dr.production_id=? AND dr.status='active'
           ORDER BY cb.ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()

    beat_by_label = {b["label"]: b["id"] for b in beats}
    matched = 0
    unmatched = []
    now = _db._now()

    with _db.transaction(db_path) as conn:
        for span in spans:
            cb_id = beat_by_label.get(span["label"])
            if cb_id:
                conn.execute(
                    "UPDATE timeline_spans SET creative_beat_id=? WHERE id=?", (cb_id, span["id"])
                )
                matched += 1
            else:
                unmatched.append(span["label"])

    return {
        "total_spans": len(spans),
        "matched": matched,
        "unmatched": unmatched,
    }


# ---------------------------------------------------------------------------
# PLAN-504  Render-plan compilation
# ---------------------------------------------------------------------------

def compile_render_plan(
    production_id: str,
    span_specs: list[dict],
    estimated_cost_usd: float = 0.0,
    db_path=None,
) -> dict:
    """Compile timeline spans → render units and save as a render_plan document.

    span_specs: same format as production_repo.plan_render_units()

    Returns {"render_units": [...], "plan_revision_id": str, "estimated_usd": float}
    """
    units = _repo.plan_render_units(production_id, span_specs, db_path=db_path)

    plan_payload = {
        "production_id": production_id,
        "render_units": [
            {
                "id": u["id"],
                "label": u["label"],
                "ordinal": u["ordinal"],
                "asset_type": u["asset_type"],
                "model": u["model"],
                "audio_policy": u["audio_policy"],
                "required_start_ms": u["required_start_ms"],
                "required_end_ms": u["required_end_ms"],
                "required_duration_ms": u["required_duration_ms"],
            }
            for u in units
        ],
        "estimated_usd": estimated_cost_usd,
    }
    plan_doc = save_document_revision(production_id, "render_plan", plan_payload, db_path=db_path)
    _link_document_dependency(production_id, "render_plan", "timing_map", db_path=db_path)

    return {
        "render_units": units,
        "plan_revision_id": plan_doc["id"],
        "estimated_usd": estimated_cost_usd,
    }


# ---------------------------------------------------------------------------
# BUD-505  Budget and spend approval
# ---------------------------------------------------------------------------

def request_spend_approval(
    production_id: str,
    plan_revision_id: str,
    estimated_usd: float,
    db_path=None,
) -> dict:
    """Request spend approval for a render plan, keyed to the plan's sha256."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    plan_row = conn.execute(
        "SELECT payload_sha256 FROM document_revisions WHERE id=?", (plan_revision_id,)
    ).fetchone()
    conn.close()
    if not plan_row:
        raise ValueError(f"render_plan revision {plan_revision_id} not found")

    return request_approval(
        production_id,
        gate_name="gate_a_spend",
        subject_type="render_plan",
        subject_id=plan_revision_id,
        subject_sha256=plan_row["payload_sha256"],
        db_path=db_path,
    )


def record_cost_event(
    production_id: str,
    operation: str,
    provider: str,
    estimated_usd: Optional[float] = None,
    actual_usd: Optional[float] = None,
    stage_run_id: Optional[str] = None,
    provider_job_id: Optional[str] = None,
    db_path=None,
) -> str:
    """Append an immutable cost event. Returns the event id."""
    cost_id = _db._id("cost")
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO cost_events
               (id, production_id, stage_run_id, provider_job_id, provider, operation,
                estimated_usd, actual_usd, currency, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                cost_id, production_id, stage_run_id, provider_job_id,
                provider, operation, estimated_usd, actual_usd, "USD", _db._now(),
            ),
        )
    return cost_id


def get_total_spend(production_id: str, db_path=None) -> dict:
    """Return estimated and actual spend totals for a production."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT
             COALESCE(SUM(estimated_usd), 0) AS total_estimated,
             COALESCE(SUM(actual_usd), 0)    AS total_actual,
             COUNT(*) AS event_count
           FROM cost_events WHERE production_id=?""",
        (production_id,),
    ).fetchone()
    conn.close()
    return dict(row)
