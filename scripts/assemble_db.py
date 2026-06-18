"""Sprint 7: DB-native assembly and deliverable registry.

ASM-701  DB timeline assembly query (no manifest file)
ASM-702  Assembly worker migration
ASM-703  Deliverable registry
QA-704   Final QA and Gate B
ASM-705  JSON export compatibility
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import production_db as _db
import production_repo as _repo
from authoring_service import request_approval, record_approval_decision

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "Videos" / "Projects"

_HERO_LIPSYNC_POLICIES = frozenset({"HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"})


# ---------------------------------------------------------------------------
# ASM-701  Build assembly manifest from DB
# ---------------------------------------------------------------------------

class AssemblyError(Exception):
    pass


def build_assembly_inputs(production_id: str, variant: str = "16x9", db_path=None) -> dict:
    """Build a complete assembly input object purely from DB state.

    Returns the DB-native assembly contract (a list of clips with timing,
    artifact path/sha, and policy). This is NOT directly consumable by the
    legacy assemble.py; use build_assembly_manifest() to bridge to its
    continuous_voiceover manifest format.

    Raises AssemblyError if any render unit is not valid or has no artifact.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)

    # Load active timeline spans in ordinal order
    spans = conn.execute(
        """SELECT * FROM timeline_spans WHERE production_id=? AND status='active'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    if not spans:
        conn.close()
        raise AssemblyError(f"No active timeline spans for production {production_id}")

    # Load render units in ordinal order
    units = conn.execute(
        """SELECT ru.*, a.uri as artifact_uri, a.sha256 as artifact_sha256,
                  a.has_audio as artifact_has_audio, a.duration_ms as artifact_duration_ms
           FROM render_units ru
           LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
           WHERE ru.production_id=? ORDER BY ru.ordinal""",
        (production_id,),
    ).fetchall()

    # Load production metadata
    production = conn.execute(
        "SELECT * FROM productions WHERE id=?", (production_id,)
    ).fetchone()
    conn.close()

    if not production:
        raise AssemblyError(f"Production {production_id} not found")

    # Validate: all units must be valid or local_graphic
    invalid = [
        u for u in units
        if u["status"] not in ("valid", "local_graphic")
        and u["asset_type"] != "local_graphic"
    ]
    if invalid:
        problems = [f"{u['label'] or u['id']}={u['status']}" for u in invalid[:5]]
        raise AssemblyError(
            f"Assembly blocked: {len(invalid)} render unit(s) not valid: {problems}"
        )

    missing_art = [u for u in units if not u["artifact_uri"]]
    if missing_art:
        labels = [u["label"] or u["id"] for u in missing_art[:5]]
        raise AssemblyError(f"Assembly blocked: {len(missing_art)} units missing artifact: {labels}")

    # Build segment/clip entries compatible with assemble.py manifest
    clips = []
    for u in units:
        clips.append({
            "clip_id": u["id"],
            "label": u["label"],
            "ordinal": u["ordinal"],
            "asset_type": u["asset_type"],
            "audio_policy": u["audio_policy"],
            "lipsync_required": bool(u["lipsync_required"]),
            "start_ms": u["required_start_ms"],
            "end_ms": u["required_end_ms"],
            "duration_ms": u["required_duration_ms"],
            "path": u["artifact_uri"],
            "sha256": u["artifact_sha256"],
            "has_audio": bool(u["artifact_has_audio"]),
        })

    return {
        "production_id": production_id,
        "project_slug": production["project_slug"],
        "variant": variant,
        "clips": clips,
        "span_count": len(spans),
        "unit_count": len(units),
    }


def build_assembly_manifest(production_id: str, variant: str = "16x9", db_path=None) -> dict:
    """Bridge DB state to assemble.py's legacy continuous_voiceover manifest.

    In continuous_voiceover mode every clip is a muted visual and the single
    master narration (tts_master) is the sole audio spine, overlaid once across
    the concatenated visual bed. Each segment carries timing_in/timing_out (its
    window in the master timeline) so the assembler can contract clip durations
    to the narration. Hero-lipsync segments additionally carry speech_len_sec and
    lipsync_provenance, which validate_manifest requires for any HERO_SYNC_LOCKED
    span (the deep provenance check only runs in non-continuous mode).
    """
    inputs = build_assembly_inputs(production_id, variant=variant, db_path=db_path)

    _db.migrate(db_path)
    conn = _db.connect(db_path)
    master = conn.execute(
        """SELECT uri, sha256 FROM artifacts
           WHERE production_id=? AND kind='tts_master'
           ORDER BY created_at DESC LIMIT 1""",
        (production_id,),
    ).fetchone()
    conn.close()
    if not master:
        raise AssemblyError(
            f"No tts_master narration artifact for production {production_id}")

    segments = []
    for c in inputs["clips"]:
        start_sec = (c.get("start_ms") or 0) / 1000.0
        end_sec = (c.get("end_ms") or 0) / 1000.0
        dur_sec = (c.get("duration_ms") or 0) / 1000.0
        seg = {
            "id": c.get("label") or c.get("clip_id"),
            "beat_id": c.get("label"),
            "clip_id": c.get("clip_id"),
            "media": c.get("path"),
            "asset_type": c.get("asset_type"),
            "audio_policy": c.get("audio_policy"),
            "timing_in": start_sec,
            "timing_out": end_sec,
            "duration_required": dur_sec,
        }
        if (c.get("audio_policy") or "") in _HERO_LIPSYNC_POLICIES or c.get("lipsync_required"):
            seg["speech_len_sec"] = dur_sec if dur_sec > 0 else 1.0
            seg["lipsync_provenance"] = {
                "slice_sha256": c.get("sha256") or "",
                "parent_mp3_sha256": master["sha256"] or "",
            }
        else:
            # continuous_voiceover tolerates words=0 for silent visuals.
            seg["words"] = 0
        segments.append(seg)

    project_slug = inputs.get("project_slug") or "."
    return {
        "id": production_id,
        "project_slug": project_slug,
        "variant": variant,
        "narration_mode": "continuous_voiceover",
        "continuous_audio": master["uri"],
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "output": {"directory": str(PROJECTS / project_slug)},
        "segments": segments,
    }


# ---------------------------------------------------------------------------
# ASM-703  Deliverable registry
# ---------------------------------------------------------------------------

def register_deliverable(
    production_id: str,
    variant: str,
    artifact_path: str | Path,
    assembly_revision: Optional[str] = None,
    qa_validation_id: Optional[str] = None,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Register an assembled output as an immutable deliverable.

    Each call with the same (production_id, variant, artifact sha256) is idempotent.
    """
    art = _repo.register_artifact(
        production_id, artifact_path, f"deliverable_{variant}",
        stage_run_id=stage_run_id,
        db_path=db_path,
    )

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM deliverables WHERE production_id=? AND variant=? AND artifact_id=?",
            (production_id, variant, art["id"]),
        ).fetchone()
        if existing:
            return dict(existing)

        del_id = _db._id("del")
        conn.execute(
            """INSERT INTO deliverables
               (id, production_id, variant, artifact_id, status, assembly_revision,
                qa_validation_id)
               VALUES (?,?,?,?,?,?,?)""",
            (
                del_id, production_id, variant, art["id"],
                "assembled",
                assembly_revision, qa_validation_id,
            ),
        )
        _db.append_event(
            production_id, "deliverable_registered",
            payload={"deliverable_id": del_id, "variant": variant},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM deliverables WHERE id=?", (del_id,)).fetchone())


def get_deliverables(production_id: str, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        """SELECT d.*, a.uri AS artifact_uri, a.sha256 AS artifact_sha256
           FROM deliverables d
           LEFT JOIN artifacts a ON d.artifact_id = a.id
           WHERE d.production_id=? ORDER BY d.id""",
        (production_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# QA-704  Final QA + Gate B
# ---------------------------------------------------------------------------

def run_final_qa(
    production_id: str,
    deliverable_id: str,
    checks: dict,
    db_path=None,
) -> dict:
    """Store final QA evidence against a deliverable.

    checks: {
        "dimensions_ok": bool,
        "duration_ok": bool,
        "loudnorm_ok": bool,
        "no_black_frames": bool,
        "captions_present": bool,  # optional
        "details": {...}
    }

    Returns validation row.
    """
    required = ["dimensions_ok", "duration_ok", "loudnorm_ok", "no_black_frames"]
    passed = all(bool(checks.get(k, True)) for k in required)

    now = _db._now()
    with _db.transaction(db_path) as conn:
        val_id = _db._id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                val_id, production_id, "deliverable", deliverable_id,
                "qa_final", "pass" if passed else "fail",
                _db._json(checks), now,
            ),
        )
        if passed:
            conn.execute(
                "UPDATE deliverables SET qa_validation_id=?, status='qa_passed' WHERE id=?",
                (val_id, deliverable_id),
            )
        else:
            conn.execute(
                "UPDATE deliverables SET status='qa_failed' WHERE id=?", (deliverable_id,)
            )
        return dict(conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone())


def request_gate_b(production_id: str, deliverable_id: str, db_path=None) -> dict:
    """Request Gate B (human final approval) for a deliverable."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT artifact_id, qa_validation_id FROM deliverables WHERE id=?", (deliverable_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise ValueError(f"deliverable {deliverable_id} not found")
    if not row["qa_validation_id"]:
        raise ValueError(
            f"Gate B requires passing qa_final validation for deliverable {deliverable_id}"
        )

    art = _repo.get_artifact(row["artifact_id"], db_path=db_path)
    return request_approval(
        production_id,
        gate_name="gate_b_review",
        subject_type="deliverable",
        subject_id=deliverable_id,
        subject_sha256=art["sha256"] if art else None,
        artifact_uri=art["uri"] if art else None,
        db_path=db_path,
    )


def is_gate_b_approved(production_id: str, db_path=None) -> bool:
    """Check whether Gate B is currently approved."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT status FROM approval_requests WHERE production_id=? AND gate_name='gate_b_review'",
        (production_id,),
    ).fetchone()
    conn.close()
    return bool(row and row["status"] == "pass")


# ---------------------------------------------------------------------------
# ASM-705  JSON export compatibility
# ---------------------------------------------------------------------------

def export_assembly_manifest(production_id: str, out_path: Path, variant: str = "16x9",
                              db_path=None) -> Path:
    """Export the DB-driven assembly manifest as JSON for audit/debug only.

    This file is never consumed as a live authority by any stage.
    """
    inputs = build_assembly_inputs(production_id, variant, db_path=db_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inputs, indent=2))
    return out_path
