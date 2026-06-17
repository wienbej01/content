"""Sprint 5: Policy-Complete Assembly DTOs (Ticket LB-500).

Constructs and validates a complete DTO for hero assembly, ensuring
no hero command can be constructed from incomplete or stale data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import production_db as _db


@dataclass
class HeroAssemblyDTO:
    render_unit_id: str
    hero_render_group_id: Optional[str]
    approved_video_artifact_id: str
    exact_timeline_placement: Dict[str, int]  # {"start_ms": int, "end_ms": int}
    visible_intervals: List[Dict[str, int]]
    broll_cover_intervals: List[Dict[str, int]]
    master_narration_reference: str  # artifact_id or uri
    audio_policy: str
    text_policy: str
    permitted_spatial_transforms: List[str]
    forbidden_temporal_transforms: List[str]
    boundary_evidence_ids: List[str]
    lipsync_evidence_ids: List[str]


class AssemblyDTOValidationError(ValueError):
    """Raised when a hero assembly DTO is incomplete or invalid."""
    pass


def build_hero_assembly_dto(
    production_id: str,
    render_unit_id: str,
    db_path=None,
) -> HeroAssemblyDTO:
    """
    Build and validate a complete HeroAssemblyDTO for a specific render unit.
    Raises AssemblyDTOValidationError if any required data is missing or stale.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    
    # 1. Fetch render unit data
    ru = conn.execute(
        """SELECT id, active_artifact_id, audio_policy, text_policy,
                  required_start_ms, required_end_ms
           FROM render_units WHERE id=? AND production_id=?""",
        (render_unit_id, production_id)
    ).fetchone()
    
    if not ru:
        raise AssemblyDTOValidationError(f"Render unit {render_unit_id} not found")
    
    if not ru["active_artifact_id"]:
        raise AssemblyDTOValidationError(f"Render unit {render_unit_id} has no approved video artifact")
        
    if not ru["audio_policy"]:
        raise AssemblyDTOValidationError(f"Render unit {render_unit_id} is missing audio_policy")

    # 2. Validate QA evidence (boundary and lipsync)
    validations = conn.execute(
        """SELECT id, subject_type, status FROM validations 
           WHERE production_id=? AND (subject_id=? OR subject_id=?)""",
        (production_id, render_unit_id, ru["active_artifact_id"])
    ).fetchall()
    
    boundary_evidence_ids = [v["id"] for v in validations if "boundary" in v["subject_type"].lower() and v["status"] == "pass"]
    lipsync_evidence_ids = [v["id"] for v in validations if "lipsync" in v["subject_type"].lower() and v["status"] == "pass"]
    
    if not boundary_evidence_ids:
        raise AssemblyDTOValidationError(f"Missing or failing boundary QA evidence for {render_unit_id}")
    if not lipsync_evidence_ids and ru["audio_policy"] == "HERO_SYNC_LOCKED":
        raise AssemblyDTOValidationError(f"Missing or failing lipsync QA evidence for hero unit {render_unit_id}")

    # 3. Fetch master narration reference
    master_art = conn.execute(
        """SELECT id FROM artifacts WHERE production_id=? AND kind='tts_master' ORDER BY created_at DESC LIMIT 1""",
        (production_id,)
    ).fetchone()
    
    if not master_art:
        raise AssemblyDTOValidationError("No master narration artifact found for production")

    # 4. Fetch visible and B-roll intervals (from render_units or related tables)
    # For now, we assume these are stored in the render_units table or can be derived
    visible_intervals = [{"start_ms": ru["required_start_ms"], "end_ms": ru["required_end_ms"]}]
    broll_cover_intervals = []  # TODO: Fetch from dedicated B-roll coverage table if available

    # 5. Define permitted/forbidden transforms based on policy
    permitted_spatial = ["crop", "scale", "pad", "grade", "denoise", "sharpen", "subtitles", "graphic_overlay"]
    forbidden_temporal = ["setpts", "speed_change", "interpolation", "loop", "reverse", "freeze_extension", "trim_through_speech", "audio_retime"]
    
    if ru["audio_policy"] != "HERO_SYNC_LOCKED":
        # B-roll might allow some temporal transforms, but hero strictly forbids them
        pass

    conn.close()
    
    dto = HeroAssemblyDTO(
        render_unit_id=ru["id"],
        hero_render_group_id=None,  # TODO: Derive from metadata or dedicated grouping table if needed
        approved_video_artifact_id=ru["active_artifact_id"],
        exact_timeline_placement={
            "start_ms": ru["required_start_ms"],
            "end_ms": ru["required_end_ms"]
        },
        visible_intervals=visible_intervals,
        broll_cover_intervals=broll_cover_intervals,
        master_narration_reference=str(master_art["id"]),
        audio_policy=ru["audio_policy"],
        text_policy=ru["text_policy"] or "NO_VISIBLE_TEXT",
        permitted_spatial_transforms=permitted_spatial,
        forbidden_temporal_transforms=forbidden_temporal,
        boundary_evidence_ids=boundary_evidence_ids,
        lipsync_evidence_ids=lipsync_evidence_ids,
    )
    
    return dto


def validate_dto_staleness(dto: HeroAssemblyDTO, production_id: str, db_path=None) -> None:
    """
    Validate that the artifact and validations referenced in the DTO are not stale.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    
    # Check artifact staleness (must not be deleted and must be the active one)
    art = conn.execute(
        """SELECT id FROM artifacts WHERE id=? AND deleted_at IS NULL""", 
        (dto.approved_video_artifact_id,)
    ).fetchone()
    
    if not art:
        raise AssemblyDTOValidationError(f"Artifact {dto.approved_video_artifact_id} is stale or deleted")
        
    # Verify it's still the active artifact for this render unit
    ru_check = conn.execute(
        """SELECT active_artifact_id FROM render_units WHERE id=? AND production_id=?""",
        (dto.render_unit_id, production_id)
    ).fetchone()
    
    if not ru_check or ru_check["active_artifact_id"] != dto.approved_video_artifact_id:
        raise AssemblyDTOValidationError(f"Artifact {dto.approved_video_artifact_id} is no longer active for {dto.render_unit_id}")
        
    # Check validation staleness
    for val_id in dto.boundary_evidence_ids + dto.lipsync_evidence_ids:
        val = conn.execute(
            "SELECT status FROM validations WHERE id=?", (val_id,)
        ).fetchone()
        if not val or val["status"] != "pass":
            raise AssemblyDTOValidationError(f"Validation evidence {val_id} is stale or failing")
            
    conn.close()
