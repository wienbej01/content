"""Failure class → repair action map (S04-T001).

Maps each Karpathy-loop failure class to:
  - target_stage: the pipeline stage that should re-run
  - change_type: the kind of change needed (re-generate, re-plan, re-slice, block, etc.)
  - description: what the repair should do

This is the authoritative mapping for the repair loop.
"""
from typing import Optional

REPAIR_MAP: dict[str, dict] = {
    # ─────────────────────────────────────────────────────────────────
    # Lipsync and audio provenance
    # ─────────────────────────────────────────────────────────────────
    "F-LIP-001": {
        "target_stage": "render_media",
        "change_type": "re_generate",
        "description": "Mouth/audio offset: re-submit hero unit to provider after verifying source audio slice and master window alignment",
    },
    "F-LIP-002": {
        "target_stage": "render_media",
        "change_type": "re_generate",
        "description": "No face track: regenerate hero unit with clearer close-up face or reference-image constraints",
    },
    "F-LIP-003": {
        "target_stage": "render_media",
        "change_type": "re_generate",
        "description": "Provider output audio mismatch: inspect provider request payload, re-submit with correct audio_path",
    },
    "F-LIP-004": {
        "target_stage": "audio_timing",
        "change_type": "re_slice",
        "description": "Master window mismatch: re-run audio_timing/reconcile_timing/assemble, not provider render first",
    },
    # ─────────────────────────────────────────────────────────────────
    # Assembly/timing
    # ─────────────────────────────────────────────────────────────────
    "F-ASM-001": {
        "target_stage": "render_media",
        "change_type": "re_generate",
        "description": "Hero temporal edit: regenerate exact-duration hero unit, change timeline split not video speed",
    },
    "F-ASM-002": {
        "target_stage": "assemble",
        "change_type": "re_assemble",
        "description": "Visual bed duration mismatch: regenerate short clips, split long spans, fix timeline contract",
    },
    "F-ASM-003": {
        "target_stage": "assemble",
        "change_type": "re_assemble",
        "description": "Static hold excessive: split graphic into progressive beats or add animation/motion treatment",
    },
    # ─────────────────────────────────────────────────────────────────
    # Graphics/text
    # ─────────────────────────────────────────────────────────────────
    "F-GFX-001": {
        "target_stage": "graphics_compositing",
        "change_type": "re_plan",
        "description": "Static graphic hold excessive: re-plan graphic duration or split graphic into multiple beats",
    },
    "F-GFX-002": {
        "target_stage": "graphics_compositing",
        "change_type": "re_plan",
        "description": "Graphic editorial value weak: revise text, add hierarchy, or redesign graphic spec",
    },
    "F-GFX-003": {
        "target_stage": "graphics_compositing",
        "change_type": "re_render_local",
        "description": "Missing deterministic text spec: re-render local graphic with proper DTS and text hash",
    },
    "F-TEXT-001": {
        "target_stage": "render_media",
        "change_type": "re_generate",
        "description": "Provider text risk: regenerate b-roll with stricter NO_VISIBLE_TEXT prompt or replace with local/still",
    },
    # ─────────────────────────────────────────────────────────────────
    # QA/evidence
    # ─────────────────────────────────────────────────────────────────
    "F-QA-001": {
        "target_stage": "qa_final",
        "change_type": "add_gate",
        "description": "Fake-green QA: add missing lipsync/text-policy gate to contract validators",
    },
    "F-QA-002": {
        "target_stage": "qa_final",
        "change_type": "block_pipeline",
        "description": "Missing eval artifact: block pipeline, do not repair media until eval harness exists",
    },
    "F-PROV-001": {
        "target_stage": "audio_slicing",
        "change_type": "fix_provenance",
        "description": "Broken provenance: ensure source slice hash + path are recorded before provider submission",
    },
    "F-PROV-002": {
        "target_stage": "production_db",
        "change_type": "fix_column",
        "description": "Wrong hash target: fix provenance field to store correct hash type (source slice, not generated video)",
    },
    # ─────────────────────────────────────────────────────────────────
    # Provider/spend
    # ─────────────────────────────────────────────────────────────────
    "F-SPEND-001": {
        "target_stage": "production_db",
        "change_type": "unlock_render",
        "description": "Render lock violation: clear unlock file, verify render readiness checklist",
    },
    "F-SPEND-002": {
        "target_stage": "production_db",
        "change_type": "add_idempotency",
        "description": "Non-idempotent provider request: add stable idempotency key to provider request payload",
    },
}


def get_repair(failure_class: str) -> Optional[dict]:
    """Look up repair action for a failure class. Returns None if unknown."""
    return REPAIR_MAP.get(failure_class)


def change_type_for(failure_class: str) -> Optional[str]:
    """Get the change type for a failure class."""
    repair = get_repair(failure_class)
    return repair["change_type"] if repair else None


def target_stage_for(failure_class: str) -> Optional[str]:
    """Get the target stage for a failure class."""
    repair = get_repair(failure_class)
    return repair["target_stage"] if repair else None
