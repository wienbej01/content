#!/usr/bin/env python3
"""Sprint 2: Production repository services.

Higher-level services built on top of production_db.py:
  - TimelineSpanService  : no-gap/no-overlap validated timeline spans (ID-202)
  - RenderUnitService    : convert spans into render units with exact windows (ID-203)
  - ArtifactRegistry     : immutable artifact store with checksum + media probe (ART-204)

All writes go through production_db.transaction() so they are atomic.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

import production_db as _db

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return _db._now()


def _json(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe_media(path: Path) -> dict:
    """ffprobe a media file. Returns {} on any error (non-media files)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True, text=True, check=True
        ).stdout
        return json.loads(out)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Sprint 1: Policy-Aware Repository Validation (Ticket LB-102)
# ---------------------------------------------------------------------------

VALID_AUDIO_POLICIES = {
    "HERO_SYNC_LOCKED",
    "BROLL_FLEX",
    "BROLL_SYNCED_ACTION",
    "AMBIENCE_OR_SFX",
    "MUSIC_BED",
    "SILENT_GRAPHIC",
}

VALID_FINAL_AUDIO_SOURCES = {"master_narration", "provider_audio", "none"}
VALID_PROVIDER_AUDIO_USAGES = {"diagnostic_only", "final_mix", "discarded"}

VALID_TEXT_POLICIES = {
    "NO_VISIBLE_TEXT",
    "UNREADABLE_BACKGROUND",
    "POST_COMPOSITE",
    "REAL_SCREEN_CAPTURE",
    "DETERMINISTIC_GRAPHIC",
}


class PolicyValidationError(ValueError):
    """Raised when a render unit violates audio or text policy constraints."""
    pass


def validate_audio_policy(render_unit: dict) -> None:
    """Validate that the render unit has a valid audio policy and consistent audio fields."""
    policy = render_unit.get("audio_policy")
    if not policy or policy not in VALID_AUDIO_POLICIES:
        raise PolicyValidationError(f"Invalid or missing audio_policy: {policy}")
    
    final_audio = render_unit.get("final_audio_source")
    if final_audio and final_audio not in VALID_FINAL_AUDIO_SOURCES:
        raise PolicyValidationError(f"Invalid final_audio_source: {final_audio}")
        
    provider_usage = render_unit.get("provider_audio_usage")
    if provider_usage and provider_usage not in VALID_PROVIDER_AUDIO_USAGES:
        raise PolicyValidationError(f"Invalid provider_audio_usage: {provider_usage}")
        
    # Enforce invariant: HERO_SYNC_LOCKED must use master_narration
    if policy == "HERO_SYNC_LOCKED":
        if final_audio != "master_narration":
            raise PolicyValidationError("HERO_SYNC_LOCKED requires final_audio_source='master_narration'")
        if provider_usage != "diagnostic_only":
            raise PolicyValidationError("HERO_SYNC_LOCKED requires provider_audio_usage='diagnostic_only'")


def validate_text_policy(render_unit: dict) -> None:
    """Validate that the render unit has a valid text policy if it bears text."""
    text_policy = render_unit.get("text_policy")
    if text_policy and text_policy not in VALID_TEXT_POLICIES:
        raise PolicyValidationError(f"Invalid text_policy: {text_policy}")
    
    # Enforce invariant: POST_COMPOSITE requires a replacement asset spec
    if text_policy == "POST_COMPOSITE" and not render_unit.get("replacement_asset_spec"):
        raise PolicyValidationError("POST_COMPOSITE text_policy requires a replacement_asset_spec")
        
    # Enforce invariant: REAL_SCREEN_CAPTURE requires a source artifact
    if text_policy == "REAL_SCREEN_CAPTURE" and not render_unit.get("source_artifact_id"):
        raise PolicyValidationError("REAL_SCREEN_CAPTURE text_policy requires a source_artifact_id")


def validate_temporal_edit_policy(render_unit: dict, operation: str) -> None:
    """Validate that the requested temporal edit is permitted for this render unit."""
    policy = render_unit.get("audio_policy")
    if policy == "HERO_SYNC_LOCKED":
        forbidden = {"setpts", "speed_change", "interpolation", "loop", "reverse", "freeze_extension", "atempo", "trim_through_speech"}
        if operation in forbidden:
            raise PolicyValidationError(
                f"BLOCKED: HERO_TEMPORAL_EDIT_FORBIDDEN\n"
                f"render_unit_id={render_unit.get('id')}\n"
                f"operation={operation}\n"
                f"reason: HERO_SYNC_LOCKED units forbid all temporal transformations."
            )


def validate_render_unit(render_unit: dict) -> None:
    """Master validation function for a render unit before any repository write."""
    validate_audio_policy(render_unit)
    validate_text_policy(render_unit)
    # Temporal edit validation is context-dependent and called during assembly/QA


# ---------------------------------------------------------------------------
# ID-202  Timeline span service
# ---------------------------------------------------------------------------

class TimelineSpanError(ValueError):
    pass


def commit_timeline_spans(
    production_id: str,
    spans: list[dict],
    tts_artifact_id: Optional[str] = None,
    creative_beat_map: Optional[dict[str, str]] = None,
    db_path=None,
) -> list[dict]:
    """Write a complete ordered set of timeline spans for one production.

    Rules enforced:
    - end_ms > start_ms (CHECK constraint in schema)
    - duration_ms == end_ms - start_ms (CHECK constraint)
    - No two spans may overlap (start < other.end AND end > other.start)
    - No negative or zero durations
    - Ordinals are unique within the production (UNIQUE constraint)

    Existing spans for the production are superseded (status='stale') before
    the new set is inserted so the revision is atomic.

    Args:
        production_id: target production row id
        spans: list of dicts with keys: label, start_ms, end_ms, narration_text
               optional: creative_beat_id, parent_span_id, split_index, split_total
        tts_artifact_id: the timing-source artifact
        creative_beat_map: {label: creative_beat_id} override
        db_path: optional override

    Returns:
        list of committed span dicts (as returned from DB)
    """
    if not spans:
        raise TimelineSpanError("spans list must not be empty")

    # Validate before touching the DB
    for i, s in enumerate(spans):
        start = s.get("start_ms")
        end = s.get("end_ms")
        if start is None or end is None:
            raise TimelineSpanError(f"span[{i}] missing start_ms or end_ms")
        if not isinstance(start, int) or not isinstance(end, int):
            raise TimelineSpanError(f"span[{i}] start_ms/end_ms must be integers (ms)")
        if end <= start:
            raise TimelineSpanError(f"span[{i}] end_ms ({end}) must be > start_ms ({start})")

    # Check for overlaps (O(n²) is fine for typical span counts ≤200)
    for i, a in enumerate(spans):
        for j, b in enumerate(spans):
            if i >= j:
                continue
            if a["start_ms"] < b["end_ms"] and a["end_ms"] > b["start_ms"]:
                raise TimelineSpanError(
                    f"spans[{i}] ({a['start_ms']}-{a['end_ms']}) overlaps "
                    f"spans[{j}] ({b['start_ms']}-{b['end_ms']})"
                )

    now = _now()
    with _db.transaction(db_path) as conn:
        # Supersede existing spans
        conn.execute(
            "UPDATE timeline_spans SET status='stale' WHERE production_id=? AND status='active'",
            (production_id,),
        )
        # Compute next ordinal base (after any remaining ordinals for idempotency safety)
        max_ord = conn.execute(
            "SELECT COALESCE(MAX(ordinal), -1) FROM timeline_spans WHERE production_id=?",
            (production_id,),
        ).fetchone()[0]
        results = []
        for i, s in enumerate(spans):
            span_id = _id("span")
            ordinal = max_ord + 1 + i
            start_ms = int(s["start_ms"])
            end_ms = int(s["end_ms"])
            duration_ms = end_ms - start_ms
            cb_id = (creative_beat_map or {}).get(s.get("label", "")) or s.get("creative_beat_id")
            sha = _db._sha256_bytes((s.get("narration_text") or "").encode()) or None
            conn.execute(
                """INSERT INTO timeline_spans
                   (id, production_id, creative_beat_id, parent_span_id, ordinal, label,
                    start_ms, end_ms, duration_ms, split_index, split_total,
                    narration_text_sha256, timing_source_artifact_id, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    span_id, production_id, cb_id,
                    s.get("parent_span_id"), ordinal, s.get("label"),
                    start_ms, end_ms, duration_ms,
                    s.get("split_index"), s.get("split_total"),
                    sha, tts_artifact_id, "active",
                ),
            )
            results.append(dict(conn.execute(
                "SELECT * FROM timeline_spans WHERE id=?", (span_id,)
            ).fetchone()))
        _db.append_event(
            production_id, "timeline_spans_committed",
            payload={"count": len(results), "tts_artifact_id": tts_artifact_id},
            conn=conn,
        )
    return results


def get_active_timeline_spans(production_id: str, db_path=None) -> list[dict]:
    """Return all active timeline spans in ordinal order."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        """SELECT * FROM timeline_spans WHERE production_id=? AND status='active'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# ID-203  Render-unit planning service
# ---------------------------------------------------------------------------

class RenderUnitError(ValueError):
    pass


def plan_render_units(
    production_id: str,
    span_render_specs: list[dict],
    db_path=None,
) -> list[dict]:
    """Convert timeline spans into render units.

    Each entry in span_render_specs:
        span_id         : timeline_spans.id
        asset_type      : 'lipsync_video', 'still_kenburns', 'local_graphic', ...
        model           : e.g. 'seedance_2_0'
        audio_policy    : 'baked_in', 'generated_tts', 'strip', 'ambient'
        lipsync_required: bool
        slots           : list of slot dicts  (optional; if absent, one slot = whole span)
            Each slot: {slot_index, slot_total, start_ms, end_ms}
        prompt_revision_id: optional document_revision_id for the prompt
        label           : optional display label

    Atomically inserts all render units; existing units for the same spans
    are NOT superseded here — call invalidate_render_units() first if re-planning.
    """
    if not span_render_specs:
        raise RenderUnitError("span_render_specs must not be empty")

    now = _now()
    results = []
    with _db.transaction(db_path) as conn:
        # Pre-fetch all spans in one query
        span_ids = [s["span_id"] for s in span_render_specs]
        ph = ",".join("?" * len(span_ids))
        span_rows = {
            r["id"]: dict(r)
            for r in conn.execute(
                f"SELECT * FROM timeline_spans WHERE id IN ({ph})", span_ids
            ).fetchall()
        }

        for spec in span_render_specs:
            span_id = spec["span_id"]
            span = span_rows.get(span_id)
            if not span:
                raise RenderUnitError(f"timeline_span {span_id} not found")
            if span["status"] != "active":
                raise RenderUnitError(f"timeline_span {span_id} is not active (status={span['status']})")

            slots = spec.get("slots") or [
                {
                    "slot_index": None,
                    "slot_total": None,
                    "start_ms": span["start_ms"],
                    "end_ms": span["end_ms"],
                }
            ]
            for slot in slots:
                unit_id = _id("render")
                start_ms = int(slot.get("start_ms", span["start_ms"]))
                end_ms = int(slot.get("end_ms", span["end_ms"]))
                if end_ms <= start_ms:
                    raise RenderUnitError(
                        f"render unit for span {span_id}: end_ms ({end_ms}) <= start_ms ({start_ms})"
                    )
                ordinal = conn.execute(
                    "SELECT COALESCE(MAX(ordinal), -1) + 1 FROM render_units WHERE production_id=?",
                    (production_id,),
                ).fetchone()[0]
                conn.execute(
                    """INSERT INTO render_units
                       (id, production_id, timeline_span_id, ordinal, label, asset_type, model,
                        audio_policy, lipsync_required, required_start_ms, required_end_ms,
                        required_duration_ms, slot_index, slot_total, status,
                        metadata_json, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        unit_id, production_id, span_id, ordinal,
                        spec.get("label") or span.get("label"),
                        spec["asset_type"], spec.get("model"),
                        spec.get("audio_policy", "strip"),
                        int(bool(spec.get("lipsync_required", False))),
                        start_ms, end_ms, end_ms - start_ms,
                        slot.get("slot_index"), slot.get("slot_total"),
                        "ordered",
                        _json({
                            "prompt_revision_id": spec.get("prompt_revision_id"),
                        }),
                        now, now,
                    ),
                )
                results.append(dict(conn.execute(
                    "SELECT * FROM render_units WHERE id=?", (unit_id,)
                ).fetchone()))

        _db.append_event(
            production_id, "render_units_planned",
            payload={"count": len(results)},
            conn=conn,
        )
    return results


def invalidate_render_units(
    production_id: str, span_ids: list[str], reason: str = "re-plan", db_path=None
) -> int:
    """Mark all render units for the given timeline_span_ids as stale."""
    if not span_ids:
        return 0
    now = _now()
    ph = ",".join("?" * len(span_ids))
    with _db.transaction(db_path) as conn:
        cur = conn.execute(
            f"""UPDATE render_units SET status='stale', updated_at=?
                WHERE production_id=? AND timeline_span_id IN ({ph})""",
            (now, production_id, *span_ids),
        )
        _db.append_event(
            production_id, "render_units_invalidated",
            payload={"span_ids": span_ids, "reason": reason}, conn=conn,
        )
        return cur.rowcount


def get_render_units(
    production_id: str,
    status: Optional[str] = None,
    db_path=None,
) -> list[dict]:
    """Return render units in ordinal order, optionally filtered by status."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    if status:
        rows = conn.execute(
            "SELECT * FROM render_units WHERE production_id=? AND status=? ORDER BY ordinal",
            (production_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM render_units WHERE production_id=? ORDER BY ordinal",
            (production_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# ART-204  Immutable artifact registry
# ---------------------------------------------------------------------------

class ArtifactRegistryError(ValueError):
    pass


def register_artifact(
    production_id: str,
    path: str | Path,
    kind: str,
    stage_run_id: Optional[str] = None,
    provider_job_id: Optional[str] = None,
    extra_metadata: Optional[dict] = None,
    db_path=None,
) -> dict:
    """Atomically register a file in the immutable artifact store.

    1. Verify the file exists.
    2. Compute SHA-256.
    3. Probe media metadata (ffprobe; no-op for non-media).
    4. Allocate the canonical URI (absolute resolved path).
    5. Insert into artifacts with UNIQUE(production_id, uri, sha256).
    6. If a row with the same (production_id, uri, sha256) already exists, return it.

    A changed file at the same URI creates a NEW artifact row (different sha256).
    The old row is NOT deleted — immutability is maintained.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ArtifactRegistryError(f"artifact file not found: {p}")

    sha = _sha256_file(p)
    size = p.stat().st_size
    probe = _probe_media(p)

    # Guess MIME
    suffix = p.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".json": "application/json", ".srt": "text/plain",
    }
    mime = mime_map.get(suffix)

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM artifacts WHERE production_id=? AND uri=? AND sha256=?",
            (production_id, str(p), sha),
        ).fetchone()
        if existing:
            return dict(existing)

        art_id = _id("art")
        conn.execute(
            """INSERT INTO artifacts
               (id, production_id, kind, uri, storage_backend, mime_type, sha256,
                size_bytes, duration_ms, width, height, has_audio,
                created_by_stage_run_id, provider_job_id, metadata_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                art_id, production_id, kind, str(p), "local", mime, sha, size,
                probe.get("duration_ms"), probe.get("width"), probe.get("height"),
                probe.get("has_audio"),
                stage_run_id, provider_job_id,
                _json(extra_metadata or {}), _now(),
            ),
        )
        return dict(conn.execute("SELECT * FROM artifacts WHERE id=?", (art_id,)).fetchone())


def get_artifact(artifact_id: str, db_path=None) -> Optional[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_artifact_on_disk(artifact_id: str, db_path=None) -> tuple[bool, str]:
    """Check that an artifact file still exists at its URI with matching SHA-256."""
    art = get_artifact(artifact_id, db_path=db_path)
    if not art:
        return False, f"artifact {artifact_id} not in DB"
    p = Path(art["uri"])
    if not p.exists():
        return False, f"file missing: {p}"
    if art["sha256"]:
        current = _sha256_file(p)
        if current != art["sha256"]:
            return False, f"sha256 mismatch at {p}"
    return True, "ok"


def link_artifact_to_render_unit(
    artifact_id: str, render_unit_id: str, db_path=None
) -> None:
    """Set the active artifact for a render unit and advance status to 'generated'."""
    now = _now()
    with _db.transaction(db_path) as conn:
        art = conn.execute(
            "SELECT production_id FROM artifacts WHERE id=?", (artifact_id,)
        ).fetchone()
        ru = conn.execute(
            "SELECT production_id FROM render_units WHERE id=?", (render_unit_id,)
        ).fetchone()
        if not art or not ru:
            raise ArtifactRegistryError("artifact or render_unit not found")
        if art["production_id"] != ru["production_id"]:
            raise ArtifactRegistryError("artifact and render_unit belong to different productions")
        conn.execute(
            "UPDATE render_units SET active_artifact_id=?, status='generated', updated_at=? WHERE id=?",
            (artifact_id, now, render_unit_id),
        )
