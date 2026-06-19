#!/usr/bin/env python3
"""Sprint 2/R2: Production repository services.

Higher-level services built on top of production_db.py:
  - TimelineSpanService  : no-gap/no-overlap validated timeline spans (ID-202)
  - RenderUnitService    : convert spans into render units with exact windows (ID-203)
  - ArtifactRegistry     : immutable artifact store with checksum + media probe (ART-204)
  - HeroGroupService     : deterministic hero render groups (R3-003)
  - ValidationService    : typed QA record keeping (R2-001)
  - ChangeRequestService : typed change request with evidence (R2-001)

All writes go through production_db.transaction() so they are atomic.
R2 hardening: all render_unit inserts call validate_render_unit(); no legacy defaults.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

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
# R2-003: Typed media probe output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MediaProbe:
    duration_ms: int = 0
    width: int = 0
    height: int = 0
    has_audio: int = 0
    sample_rate: int = 0
    channels: int = 0

    @classmethod
    def from_path(cls, path: Path) -> Optional["MediaProbe"]:
        raw = _probe_media(path)
        if not raw:
            return None
        fmt = raw.get("format", {})
        streams = raw.get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        return cls(
            duration_ms=int(float(fmt.get("duration", 0)) * 1000),
            width=int(video_streams[0].get("width", 0)) if video_streams else 0,
            height=int(video_streams[0].get("height", 0)) if video_streams else 0,
            has_audio=1 if audio_streams else 0,
            sample_rate=int(audio_streams[0].get("sample_rate", 0)) if audio_streams else 0,
            channels=int(audio_streams[0].get("channels", 0)) if audio_streams else 0,
        )


def probe_media(path: Path) -> Optional[MediaProbe]:
    """Typed media probe returning MediaProbe or None for non-media."""
    return MediaProbe.from_path(path)


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
    validate_hero_slicing_intervals(render_unit)
    # Temporal edit validation is context-dependent and called during assembly/QA


def validate_hero_slicing_intervals(render_unit: dict) -> None:
    """Validate hero slicing intervals (Ticket LB-300)."""
    if render_unit.get("audio_policy") != "HERO_SYNC_LOCKED":
        return

    speech_start = render_unit.get("speech_start_sample")
    speech_end = render_unit.get("speech_end_sample")
    gen_start = render_unit.get("generation_start_sample")
    gen_end = render_unit.get("generation_end_sample")
    visible_start = render_unit.get("visible_start_sample")
    visible_end = render_unit.get("visible_end_sample")
    master_dur = render_unit.get("master_duration_samples")

    any_interval = any(x is not None for x in (speech_start, speech_end, gen_start, gen_end))
    if not any_interval:
        return

    if None in (speech_start, speech_end, gen_start, gen_end):
        raise PolicyValidationError("HERO_SYNC_LOCKED units require complete speech and generation sample intervals")

    lead_silence = render_unit.get("leading_silence_samples", 0) or 0
    trail_silence = render_unit.get("trailing_silence_samples", 0) or 0

    expected_gen_start = speech_start - lead_silence
    expected_gen_end = speech_end + trail_silence

    if gen_start != expected_gen_start or gen_end != expected_gen_end:
        raise PolicyValidationError(
            f"Generation interval [{gen_start}, {gen_end}] does not match speech [{speech_start}, {speech_end}] "
            f"plus silence [{lead_silence}, {trail_silence}]"
        )

    if visible_start is not None and visible_end is not None:
        if visible_start < gen_start or visible_end > gen_end:
            raise PolicyValidationError(
                f"Visible interval [{visible_start}, {visible_end}] exceeds generation interval [{gen_start}, {gen_end}]"
            )

    if master_dur is not None:
        if gen_end > master_dur:
            raise PolicyValidationError(
                f"Generation end {gen_end} exceeds master duration {master_dur}"
            )


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
        span_id            : timeline_spans.id (required)
        asset_type         : 'lipsync_video', 'still_kenburns', 'local_graphic', ...
        model              : e.g. 'seedance_2_0'
        audio_policy       : canonical policy (HERO_SYNC_LOCKED, BROLL_FLEX, etc.) — required
        final_audio_source : master_narration, provider_audio, none
        provider_audio_usage: diagnostic_only, final_mix, discarded
        text_policy        : NO_VISIBLE_TEXT, POST_COMPOSITE, etc.
        lipsync_required   : bool
        slots              : list of slot dicts (optional; if absent, one slot = whole span)
        speech_start_sample, speech_end_sample, generation_start_sample,
        generation_end_sample, visible_start_sample, visible_end_sample,
        leading_silence_samples, trailing_silence_samples,
        master_audio_artifact_id, master_audio_sha256, boundary_reason, boundary_confidence
        prompt_revision_id : optional document_revision_id for the prompt
        label              : optional display label
        metadata           : optional dict merged into metadata_json
        # R7 semantic fields:
        visual_function, narrative_claim, information_to_show, viewer_takeaway,
        required_action, forbidden_cliches, distinctness_requirement,
        semantic_acceptance_criteria, render_mode, concept_key, concept_hash,
        graphic_text_content, graphic_text_hash

    Atomically inserts all units.  Each unit is validated (audio/text/hero-slicing policy)
    before the INSERT.  Legacy defaults are rejected — caller must supply all policy fields.
    """
    if not span_render_specs:
        raise RenderUnitError("span_render_specs must not be empty")

    now = _now()
    results = []
    with _db.transaction(db_path) as conn:
        span_ids = [s["span_id"] for s in span_render_specs]
        ph = ",".join("?" * len(span_ids))
        span_rows = {
            r["id"]: dict(r)
            for r in conn.execute(
                f"SELECT * FROM timeline_spans WHERE id IN ({ph})", span_ids
            ).fetchall()
        }

        # D-015: a new render-plan supersedes the prior one. Mark this production's
        # existing (non-stale) units 'stale' in the SAME transaction — render units are
        # immutable history, never deleted — and remember the prior unit per span so the
        # new units can record parentage. Without this, re-compiling after an upstream
        # invalidation appends a second active set, so generate (status='ordered') and
        # assembly see a doubled timeline / duplicate paid jobs.
        prior_by_span = {
            r["timeline_span_id"]: r["id"]
            for r in conn.execute(
                "SELECT id, timeline_span_id FROM render_units "
                "WHERE production_id=? AND status!='stale'",
                (production_id,),
            ).fetchall()
        }
        if prior_by_span:
            conn.execute(
                "UPDATE render_units SET status='stale', updated_at=? "
                "WHERE production_id=? AND status!='stale'",
                (now, production_id),
            )

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

                audio_policy = spec.get("audio_policy")
                final_audio_source = spec.get("final_audio_source")
                provider_audio_usage = spec.get("provider_audio_usage")
                text_policy = spec.get("text_policy")
                lipsync_required = int(bool(spec.get("lipsync_required", False)))

                unit = {
                    "id": unit_id,
                    "audio_policy": audio_policy,
                    "final_audio_source": final_audio_source,
                    "provider_audio_usage": provider_audio_usage,
                    "text_policy": text_policy,
                    "lipsync_required": lipsync_required,
                    "speech_start_sample": spec.get("speech_start_sample"),
                    "speech_end_sample": spec.get("speech_end_sample"),
                    "generation_start_sample": spec.get("generation_start_sample"),
                    "generation_end_sample": spec.get("generation_end_sample"),
                    "visible_start_sample": spec.get("visible_start_sample"),
                    "visible_end_sample": spec.get("visible_end_sample"),
                    "leading_silence_samples": spec.get("leading_silence_samples"),
                    "trailing_silence_samples": spec.get("trailing_silence_samples"),
                    "master_audio_artifact_id": spec.get("master_audio_artifact_id"),
                    "master_audio_sha256": spec.get("master_audio_sha256"),
                    "master_duration_samples": spec.get("master_duration_samples"),
                    "boundary_reason": spec.get("boundary_reason"),
                    "boundary_confidence": spec.get("boundary_confidence"),
                    "replacement_asset_spec": spec.get("replacement_asset_spec"),
                    "source_artifact_id": spec.get("source_artifact_id"),
                    "visual_function": spec.get("visual_function"),
                    "narrative_claim": spec.get("narrative_claim"),
                    "information_to_show": spec.get("information_to_show"),
                    "viewer_takeaway": spec.get("viewer_takeaway"),
                    "required_action": spec.get("required_action"),
                    "forbidden_cliches": spec.get("forbidden_cliches"),
                    "distinctness_requirement": spec.get("distinctness_requirement"),
                    "semantic_acceptance_criteria": spec.get("semantic_acceptance_criteria"),
                    "render_mode": spec.get("render_mode") or "generated_video",
                    "concept_key": spec.get("concept_key"),
                    "concept_hash": spec.get("concept_hash"),
                    "graphic_text_content": spec.get("graphic_text_content"),
                    "graphic_text_hash": spec.get("graphic_text_hash"),
                }
                validate_render_unit(unit)

                if audio_policy not in ("HERO_SYNC_LOCKED",) and spec.get("asset_type") in ("generated_video", "generated_still"):
                    from broll_semantic import validate_broll_semantics
                    broll_issues = validate_broll_semantics(spec, spec.get("asset_type"), audio_policy)
                    if broll_issues:
                        raise RenderUnitError("B-roll semantic contract violations for " + spec.get("label", "?") + ":\n" + "\n".join(broll_issues))

                md = {"prompt_revision_id": spec.get("prompt_revision_id")}
                if spec.get("metadata"):
                    md.update(spec["metadata"])

                conn.execute(
                    """INSERT INTO render_units
                       (id, production_id, timeline_span_id, ordinal, label, asset_type, model,
                        audio_policy, final_audio_source, provider_audio_usage, text_policy,
                        lipsync_required, required_start_ms, required_end_ms,
                        required_duration_ms, slot_index, slot_total, status,
                        speech_start_sample, speech_end_sample,
                        generation_start_sample, generation_end_sample,
                        visible_start_sample, visible_end_sample,
                        leading_silence_samples, trailing_silence_samples,
                        master_audio_artifact_id, master_audio_sha256,
                        boundary_reason, boundary_confidence,
                        visual_function, narrative_claim, information_to_show, viewer_takeaway,
                        required_action, forbidden_cliches, distinctness_requirement,
                        semantic_acceptance_criteria, render_mode, concept_key, concept_hash,
                        graphic_text_content, graphic_text_hash,
                        metadata_json, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,
                               ?,?,?,?,?,?,?,
                               ?,?,?,?,?,?,?,
                               ?,?,?,?,?,?,?,
                               ?,?,?,?,?,?,?,
                               ?,?,?,?,?,?,?,
                               ?,?,?,?)""",
                    (
                        unit_id, production_id, span_id, ordinal,
                        spec.get("label") or span.get("label"),
                        spec["asset_type"], spec.get("model"),
                        audio_policy, final_audio_source, provider_audio_usage, text_policy,
                        lipsync_required,
                        start_ms, end_ms, end_ms - start_ms,
                        slot.get("slot_index"), slot.get("slot_total"),
                        "ordered",
                        spec.get("speech_start_sample"), spec.get("speech_end_sample"),
                        spec.get("generation_start_sample"), spec.get("generation_end_sample"),
                        spec.get("visible_start_sample"), spec.get("visible_end_sample"),
                        spec.get("leading_silence_samples"), spec.get("trailing_silence_samples"),
                        spec.get("master_audio_artifact_id"), spec.get("master_audio_sha256"),
                        spec.get("boundary_reason"), spec.get("boundary_confidence"),
                        spec.get("visual_function"), spec.get("narrative_claim"),
                        spec.get("information_to_show"), spec.get("viewer_takeaway"),
                        spec.get("required_action"), spec.get("forbidden_cliches"),
                        spec.get("distinctness_requirement"), spec.get("semantic_acceptance_criteria"),
                        spec.get("render_mode") or "generated_video",
                        spec.get("concept_key"), spec.get("concept_hash"),
                        spec.get("graphic_text_content"), spec.get("graphic_text_hash"),
                        _json(md),
                        now, now,
                    ),
                )
                # Traceability: link the new unit to the unit it replaced (same span), if any.
                _parent = prior_by_span.get(span_id)
                if _parent:
                    conn.execute(
                        "UPDATE render_units SET parent_render_unit_id=? WHERE id=?",
                        (_parent, unit_id),
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
    3. Probe media metadata via typed MediaProbe (ffprobe); fails for non-media if kind
       implies media (video, audio, image).
    4. Allocate the canonical URI (absolute resolved path).
    5. Insert into artifacts with UNIQUE(production_id, uri, sha256).
    6. If a row with the same (production_id, uri, sha256) already exists, return it.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ArtifactRegistryError(f"artifact file not found: {p}")

    sha = _sha256_file(p)
    size = p.stat().st_size
    probe = probe_media(p)

    media_kinds = {"tts_master", "lipsync_video", "generated_video", "master_audio",
                   "narration_master", "music_bed", "deliverable_video"}
    if kind in media_kinds and probe is None:
        raise ArtifactRegistryError(
            f"media artifact kind '{kind}' requires valid media file; "
            f"ffprobe could not parse {p}"
        )
    if kind in media_kinds and probe.has_audio == 0 and kind in {"tts_master", "narration_master", "master_audio"}:
        raise ArtifactRegistryError(
            f"audio artifact kind '{kind}' requires an audio stream; none found in {p}"
        )

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
                probe.duration_ms if probe else None,
                probe.width if probe else None,
                probe.height if probe else None,
                probe.has_audio if probe else None,
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
    """Set the active artifact for a render unit and advance status to 'generated'.

    Rejects change if the render unit already has an active artifact —
    a change request with replacement evidence is required first (R6-004 path).
    """
    now = _now()
    with _db.transaction(db_path) as conn:
        art = conn.execute(
            "SELECT production_id FROM artifacts WHERE id=?", (artifact_id,)
        ).fetchone()
        ru = conn.execute(
            "SELECT production_id, active_artifact_id, status FROM render_units WHERE id=?", (render_unit_id,)
        ).fetchone()
        if not art or not ru:
            raise ArtifactRegistryError("artifact or render_unit not found")
        if art["production_id"] != ru["production_id"]:
            raise ArtifactRegistryError("artifact and render_unit belong to different productions")
        if ru["active_artifact_id"] is not None:
            raise ArtifactRegistryError(
                f"render_unit {render_unit_id} already has active_artifact; "
                "a qualified replacement change request is required to change it (R6-004)"
            )
        conn.execute(
            "UPDATE render_units SET active_artifact_id=?, status='generated', updated_at=? WHERE id=?",
            (artifact_id, now, render_unit_id),
        )


# ---------------------------------------------------------------------------
# R3-003  Hero render group persistence
# ---------------------------------------------------------------------------

class HeroGroupError(ValueError):
    pass


def persist_hero_render_groups(
    production_id: str,
    groups: list[dict],
    db_path=None,
) -> list[dict]:
    """Persist deterministic hero render groups into hero_render_groups + members + covered.

    Each group dict:
        hero_render_group_id     : str (deterministic hash, not random UUID)
        generation_start_sample  : int
        generation_end_sample    : int
        generation_duration_samples: int
        source_audio_artifact_id : optional str
        source_audio_sha256      : optional str
        prompt_revision_id       : optional str
        prompt_sha256            : optional str
        model                    : str
        requested_duration_sec   : float
        regeneration_blast_radius: optional list[str]
        temporal_edit_policy     : str (default HERO_SYNC_LOCKED)
        continuity_benefit       : optional str
        scene_consistent         : bool
        master_audio_artifact_id : optional str
        master_audio_sha256      : optional str
        member_visible_intervals : list[{start_sample, end_sample, render_unit_id, beat_id}]
        covered_intervals        : optional list[{start_sample, end_sample, beat_id, kind}]
    """
    if not groups:
        raise HeroGroupError("groups must not be empty")

    now = _now()
    results = []
    with _db.transaction(db_path) as conn:
        # Supersede existing active groups
        conn.execute(
            "UPDATE hero_render_groups SET status='stale', updated_at=? WHERE production_id=? AND status='active'",
            (now, production_id),
        )
        last_ord = conn.execute(
            "SELECT COALESCE(MAX(group_ordinal), -1) FROM hero_render_groups WHERE production_id=?",
            (production_id,),
        ).fetchone()[0]

        for gi, g in enumerate(groups):
            ordinal = last_ord + 1 + gi
            conn.execute(
                """INSERT INTO hero_render_groups
                   (id, production_id, group_ordinal, group_hash,
                    generation_start_sample, generation_end_sample, generation_duration_samples,
                    source_audio_artifact_id, source_audio_sha256,
                    prompt_revision_id, prompt_sha256, model, requested_duration_sec,
                    regeneration_blast_radius_json, temporal_edit_policy,
                    continuity_benefit, scene_consistent,
                    master_audio_artifact_id, master_audio_sha256,
                    status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                           ?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    g["hero_render_group_id"], production_id, ordinal, g.get("group_hash", g["hero_render_group_id"]),
                    g["generation_start_sample"], g["generation_end_sample"],
                    g.get("generation_duration_samples", g["generation_end_sample"] - g["generation_start_sample"]),
                    g.get("source_audio_artifact_id"), g.get("source_audio_sha256"),
                    g.get("prompt_revision_id"), g.get("prompt_sha256"),
                    g.get("model", "seedance_2_0"), g.get("requested_duration_sec", 0.0),
                    _json(g.get("regeneration_blast_radius", [])),
                    g.get("temporal_edit_policy", "HERO_SYNC_LOCKED"),
                    g.get("continuity_benefit"), int(bool(g.get("scene_consistent", True))),
                    g.get("master_audio_artifact_id"), g.get("master_audio_sha256"),
                    "active", now, now,
                ),
            )

            # Members
            members = g.get("member_visible_intervals", [])
            for mi, m in enumerate(members):
                conn.execute(
                    """INSERT INTO hero_group_members
                       (id, hero_render_group_id, render_unit_id, member_ordinal,
                        visible_start_sample, visible_end_sample, beat_id)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        _id("hgm"), g["hero_render_group_id"], m["render_unit_id"], mi,
                        m["start_sample"], m["end_sample"], m.get("beat_id"),
                    ),
                )

            # Covered intervals
            covered = g.get("covered_intervals", [])
            for ci, c in enumerate(covered):
                conn.execute(
                    """INSERT INTO hero_covered_intervals
                       (id, hero_render_group_id, interval_ordinal,
                        start_sample, end_sample, beat_id, interval_kind)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        _id("hci"), g["hero_render_group_id"], ci,
                        c["start_sample"], c["end_sample"], c.get("beat_id"),
                        c.get("kind", "broll_covered"),
                    ),
                )

            row = conn.execute(
                "SELECT * FROM hero_render_groups WHERE id=?", (g["hero_render_group_id"],)
            ).fetchone()
            results.append(dict(row))

        _db.append_event(
            production_id, "hero_groups_persisted",
            payload={"count": len(results)}, conn=conn,
        )
    return results


def get_active_hero_groups(production_id: str, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM hero_render_groups WHERE production_id=? AND status='active' ORDER BY group_ordinal",
        (production_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# R2-001  Validation record keeping
# ---------------------------------------------------------------------------

def record_validation(
    production_id: str,
    subject_type: str,
    subject_id: str,
    validator_name: str,
    status: str,
    ruleset_version: Optional[str] = None,
    evidence: Optional[dict] = None,
    stage_run_id: Optional[str] = None,
    artifact_sha256: Optional[str] = None,
    algorithm_version: Optional[str] = None,
    threshold_version: Optional[str] = None,
    db_path=None,
) -> dict:
    """Record a validation with integrity columns."""
    now = _now()
    with _db.transaction(db_path) as conn:
        val_id = _id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                ruleset_version, evidence_json, created_by_stage_run_id, created_at,
                artifact_sha256, algorithm_version, threshold_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                val_id, production_id, subject_type, subject_id, validator_name, status,
                ruleset_version, _json(evidence or {}), stage_run_id, now,
                artifact_sha256, algorithm_version, threshold_version,
            ),
        )
        return dict(conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone())


# ---------------------------------------------------------------------------
# R2-001  Change request record keeping (sets up R6-004)
# ---------------------------------------------------------------------------

class ChangeRequestError(ValueError):
    pass


def record_change_request(
    production_id: str,
    subject_type: str,
    subject_id: str,
    change_type: str,
    requested_by_stage: str,
    target_stage: str,
    reason: str,
    status: str = "open",
    failure_evidence: Optional[dict] = None,
    replacement_subject_type: Optional[str] = None,
    replacement_subject_id: Optional[str] = None,
    repair_routing_stage: Optional[str] = None,
    db_path=None,
) -> dict:
    if not change_type:
        raise ChangeRequestError("change_type is required")
    if not requested_by_stage:
        raise ChangeRequestError("requested_by_stage is required")
    now = _now()
    with _db.transaction(db_path) as conn:
        cr_id = _id("cr")
        conn.execute(
            """INSERT INTO change_requests
               (id, production_id, subject_type, subject_id, change_type,
                requested_by_stage, target_stage, reason, status,
                failure_evidence_json, replacement_subject_type, replacement_subject_id,
                repair_routing_stage, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cr_id, production_id, subject_type, subject_id, change_type,
                requested_by_stage, target_stage, reason, status,
                _json(failure_evidence) if failure_evidence else None,
                replacement_subject_type, replacement_subject_id,
                repair_routing_stage, now,
            ),
        )
        return dict(conn.execute("SELECT * FROM change_requests WHERE id=?", (cr_id,)).fetchone())


def resolve_change_request(
    cr_id: str,
    resolution: dict,
    db_path=None,
) -> dict:
    now = _now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            """UPDATE change_requests SET status='resolved', resolution_json=?, resolved_at=?
               WHERE id=?""",
            (_json(resolution), now, cr_id),
        )
        row = conn.execute("SELECT * FROM change_requests WHERE id=?", (cr_id,)).fetchone()
        if not row:
            raise ChangeRequestError(f"change_request {cr_id} not found")
        return dict(row)
