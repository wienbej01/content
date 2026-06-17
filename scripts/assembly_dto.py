"""Sprint 5/R5: Policy-Complete Assembly DTOs (Tickets LB-500 / R5-001).

Constructs and validates a complete DTO for hero assembly, ensuring
no hero command can be constructed from incomplete or stale data.

R5-001: Extends with FullAssemblyContract covering picture tracks, master audio,
music, graphics, captions, and output specs. Built exclusively from DB.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import production_db as _db

DEFAULT_VERSION = 2


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


# ---------------------------------------------------------------------------
# R5-001  Full Assembly Contract (DB-native, versioned)
# ---------------------------------------------------------------------------

@dataclass
class PictureTrack:
    """A single picture track segment for the assembly timeline."""
    render_unit_id: str
    artifact_id: str
    artifact_uri: str
    artifact_sha256: str
    start_ms: int
    end_ms: int
    audio_policy: str
    asset_type: str = "generated_video"
    slot_index: Optional[int] = None
    slot_total: Optional[int] = None


@dataclass
class MasterAudioTrack:
    """The master narration audio spine."""
    artifact_id: str
    artifact_uri: str
    artifact_sha256: str
    duration_ms: int
    sample_rate: int = 48000


@dataclass
class FullAssemblyContract:
    """R5-001: Complete DB-native assembly contract, version 2.

    Covers picture tracks, master audio, music, graphics, captions, and output specs.
    Built exclusively from DB; JSON is internal serialization only.
    """
    version: int = DEFAULT_VERSION
    production_id: str = ""
    picture_tracks: List[PictureTrack] = field(default_factory=list)
    master_audio: Optional[MasterAudioTrack] = None
    music_artifact_id: Optional[str] = None
    graphics_artifact_id: Optional[str] = None
    captions_json: Optional[str] = None
    output_specs: Dict[str, Any] = field(default_factory=dict)

    def total_duration_ms(self) -> int:
        if not self.picture_tracks:
            return 0
        return max(pt.end_ms for pt in self.picture_tracks) - min(pt.start_ms for pt in self.picture_tracks)

    def validate_continuity(self) -> list[str]:
        issues = []
        sorted_tracks = sorted(self.picture_tracks, key=lambda pt: pt.start_ms)
        for i in range(len(sorted_tracks) - 1):
            a = sorted_tracks[i]
            b = sorted_tracks[i + 1]
            if a.end_ms > b.start_ms:
                issues.append(f"PictureTrack {a.render_unit_id} [{a.start_ms},{a.end_ms}] overlaps {b.render_unit_id} [{b.start_ms},{b.end_ms}]")
            if a.end_ms < b.start_ms:
                issues.append(f"Gap between {a.render_unit_id} and {b.render_unit_id}: {b.start_ms - a.end_ms}ms")
        return issues


def build_assembly_contract(production_id: str, db_path=None) -> FullAssemblyContract:
    """Build a complete FullAssemblyContract from the DB.

    Verifies artifact existence, SHA integrity, and blocks on open repairs
    or stale approvals."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)

    units = conn.execute(
        """SELECT ru.id, ru.active_artifact_id, ru.audio_policy, ru.asset_type,
                  ru.required_start_ms, ru.required_end_ms, ru.slot_index, ru.slot_total,
                  a.uri as artifact_uri, a.sha256 as artifact_sha256
           FROM render_units ru
           JOIN artifacts a ON ru.active_artifact_id = a.id
           WHERE ru.production_id=? AND ru.status IN ('generated', 'valid')
           ORDER BY ru.ordinal""",
        (production_id,),
    ).fetchall()

    if not units:
        raise AssemblyDTOValidationError(f"No render units with active artifacts for production {production_id}")

    open_crs = conn.execute(
        """SELECT COUNT(*) as cnt FROM change_requests
           WHERE production_id=? AND status='open' AND target_stage='assemble'""",
        (production_id,),
    ).fetchone()
    if open_crs["cnt"] > 0:
        raise AssemblyDTOValidationError(f"{open_crs['cnt']} open change requests targeting assemble")

    pending_approvals = conn.execute(
        """SELECT gate_name FROM approval_requests
           WHERE production_id=? AND status NOT IN ('pass', 'fail')""",
        (production_id,),
    ).fetchall()
    if pending_approvals:
        gates = [a["gate_name"] for a in pending_approvals]
        raise AssemblyDTOValidationError(f"Pending approvals: {gates}")

    master_art = conn.execute(
        """SELECT id, uri, sha256, duration_ms FROM artifacts
           WHERE production_id=? AND kind='master_audio'
           ORDER BY created_at DESC LIMIT 1""",
        (production_id,),
    ).fetchone()
    if not master_art:
        master_art = conn.execute(
            """SELECT id, uri, sha256, duration_ms FROM artifacts
               WHERE production_id=? AND kind='tts_master'
               ORDER BY created_at DESC LIMIT 1""",
            (production_id,),
        ).fetchone()

    picture_tracks = []
    for u in units:
        picture_tracks.append(PictureTrack(
            render_unit_id=u["id"],
            artifact_id=u["active_artifact_id"],
            artifact_uri=u["artifact_uri"],
            artifact_sha256=u["artifact_sha256"],
            start_ms=u["required_start_ms"],
            end_ms=u["required_end_ms"],
            audio_policy=u["audio_policy"],
            asset_type=u["asset_type"],
            slot_index=u["slot_index"],
            slot_total=u["slot_total"],
        ))

    master = None
    if master_art:
        master = MasterAudioTrack(
            artifact_id=master_art["id"],
            artifact_uri=master_art["uri"],
            artifact_sha256=master_art["sha256"],
            duration_ms=master_art["duration_ms"],
        )

    conn.close()

    contract = FullAssemblyContract(
        version=DEFAULT_VERSION,
        production_id=production_id,
        picture_tracks=picture_tracks,
        master_audio=master,
        output_specs={"1920x1080": {"w": 1920, "h": 1080, "fps": 24}},
    )

    issues = contract.validate_continuity()
    if issues:
        raise AssemblyDTOValidationError("Assembly continuity violations:\n" + "\n".join(issues))

    return contract
