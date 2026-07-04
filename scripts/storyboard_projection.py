"""Canonical-to-legacy storyboard projection.

Projects Sonnet-authored canonical shots and overlays into legacy beat-level
fields required by the existing compiler, DB projection, review, and assembly
code. The projection is deterministic, traceable back to canonical shot_id
and overlay_id, and never reads raw script visual_brief.

Usage:
    from storyboard_projection import project_canonical
    legacy = project_canonical(canonical_storyboard)

Raises ProjectionError on missing semantic source fields.
"""
from __future__ import annotations

from typing import Any


class ProjectionError(ValueError):
    """Raised when a canonical shot lacks required semantic source fields."""


# ---------------------------------------------------------------------------
# Known legacy shot_type values (schema beat.definitions.beat.shot_type enum)
# ---------------------------------------------------------------------------
_LEGACY_SHOT_TYPES = frozenset({
    "hero_lipsync", "hero_cutaway",
    "broll_archival", "broll_metaphorical", "broll_environment", "broll_tactical",
    "graphic_progressive", "graphic_title_card", "kinetic_text",
    "ui_insert", "still_kenburns",
})

# Mapping from canonical visual_role value to legacy shot_type when the role
# already uses a legacy-compatible value.
# Fallback: infer from literal_vs_metaphorical + generation signals.

_VISUAL_ROLE_TO_SHOT_TYPE: dict[str, str] = {
    "host_present_speaking": "hero_lipsync",
    "host_present_cutaway": "hero_cutaway",
    "hero_lipsync": "hero_lipsync",
    "hero_cutaway": "hero_cutaway",
    "broll_archival": "broll_archival",
    "broll_metaphorical": "broll_metaphorical",
    "broll_environment": "broll_environment",
    "broll_tactical": "broll_tactical",
    "graphic_progressive": "graphic_progressive",
    "graphic_title_card": "graphic_title_card",
    "kinetic_text": "kinetic_text",
    "ui_insert": "ui_insert",
    "still_kenburns": "still_kenburns",
}

_MODEL_BY_SHOT_TYPE: dict[str, str] = {
    "hero_lipsync": "seedance_2_0",
    "hero_cutaway": "kling3_0",
    "broll_archival": "kling3_0",
    "broll_metaphorical": "kling3_0",
    "broll_environment": "kling3_0",
    "broll_tactical": "kling3_0",
    "graphic_progressive": "local_graphic",
    "graphic_title_card": "local_graphic",
    "kinetic_text": "local_graphic",
    "ui_insert": "local_graphic",
    "still_kenburns": "still_kenburns",
}

_ASSET_TYPE_BY_SHOT_TYPE: dict[str, str] = {
    "hero_lipsync": "generated_video",
    "hero_cutaway": "generated_video",
    "broll_archival": "generated_video",
    "broll_metaphorical": "generated_video",
    "broll_environment": "generated_video",
    "broll_tactical": "generated_video",
    "graphic_progressive": "local_graphic",
    "graphic_title_card": "local_graphic",
    "kinetic_text": "local_graphic",
    "ui_insert": "local_graphic",
    "still_kenburns": "generated_still",
}

_LITERAL_TO_PROMPT_CLASS: dict[str, str] = {
    "literal": "descriptive",
    "metaphorical": "conceptual",
    "hybrid": "narrative",
}

_CANONICAL_SEMANTIC_REQUIRED = frozenset({"why_this_visual", "narrative_alignment"})

# Fields from the canonical shot that are carried directly into the legacy beat
# without transformation.
_SHOT_CARRY_FIELDS = (
    "segment_id", "must_show", "must_avoid", "claim_refs",
    "qa_requirements", "planned_duration_sec",
    "min_usable_duration_sec", "max_usable_duration_sec",
    "duration_drift_policy", "assembly_fit_policy",
)


def _resolve_shot_type(shot: dict) -> str:
    """Maps canonical visual_role to a legacy shot_type."""
    role = shot.get("visual_role", "")
    if role in _VISUAL_ROLE_TO_SHOT_TYPE:
        return _VISUAL_ROLE_TO_SHOT_TYPE[role]
    lit = shot.get("literal_vs_metaphorical", "literal")
    if lit == "metaphorical":
        return "broll_metaphorical"
    fallback = (shot.get("fallback_strategy") or "").lower()
    if "still" in fallback:
        return "still_kenburns"
    if role and role.startswith("broll"):
        return "broll_environment"
    return "hero_cutaway"


def _resolve_model(shot_type: str, shot: dict) -> str:
    if _is_reused_footage(shot):
        return "reused"
    model = _MODEL_BY_SHOT_TYPE.get(shot_type, "kling3_0")
    fallback = (shot.get("fallback_strategy") or "").lower()
    if "still" in fallback and model not in ("local_graphic", "still_kenburns"):
        model = "still_kenburns"
    return model


def _resolve_asset_type(shot_type: str, shot: dict) -> str:
    if _is_reused_footage(shot):
        return "reused"
    return _ASSET_TYPE_BY_SHOT_TYPE.get(shot_type, "generated_video")


def _is_reused_footage(shot: dict) -> bool:
    """Detect canonical intent to preserve existing footage, not generate anew."""
    text = " ".join(str(shot.get(k, "")) for k in (
        "prompt_intent", "assembly_fit_policy", "fallback_strategy", "generation_risk",
    )).lower()
    return any(marker in text for marker in (
        "existing baked-in-audio footage",
        "existing recorded footage",
        "pre-recorded baked-in-audio footage",
        "no new generation required",
        "not a generation task",
    ))


def _resolve_prompt_class(shot: dict) -> str:
    lit = shot.get("literal_vs_metaphorical", "literal")
    return _LITERAL_TO_PROMPT_CLASS.get(lit, "descriptive")


def _compose_visual_brief(shot: dict) -> str:
    """Compose visual_brief from canonical shot fields only.

    Never reads raw script visual_brief. Uses visual_concept, must_show,
    prompt_intent, and narrative_alignment to build a deterministic,
    traceable brief.
    """
    concept = shot.get("visual_concept", "").strip()
    intent = shot.get("prompt_intent", "").strip()
    must_show = shot.get("must_show", [])
    parts = []
    if concept:
        parts.append(concept)
    if intent:
        parts.append(intent)
    if must_show:
        parts.append("Including: " + ", ".join(must_show))
    return ". ".join(parts) if parts else concept


def _compose_visual_intent(shot: dict) -> dict:
    """Compose visual_intent dict from canonical semantic fields."""
    from broll_semantic import derive_concept_key, compute_concept_key

    concept = shot.get("visual_concept", "")
    alignment = shot.get("narrative_alignment", "")
    why = shot.get("why_this_visual", "")
    must_show = shot.get("must_show", [])
    primary_subject = must_show[0] if must_show else ""
    action = shot.get("prompt_intent", "") or concept

    derived_key = derive_concept_key(concept, primary_subject, action)
    derived_hash = compute_concept_key(concept, primary_subject, action)

    intent = {
        "visual_function": "demonstrate" if _resolve_shot_type(shot).startswith("graphic") else "illustrate",
        "concept_key": derived_key,
        "concept_hash": derived_hash,
        "narrative_claim": alignment or why or concept,
        "information_to_show": concept,
        "viewer_takeaway": why or alignment,
        "required_action": action,
        "distinctness_requirement": "Specific to the canonical shot; no generic stock.",
        "semantic_acceptance_criteria": alignment or why,
        "why_this_visual": shot.get("why_this_visual", ""),
        "narrative_alignment": shot.get("narrative_alignment", ""),
        "shot_id": shot.get("shot_id", ""),
    }
    if _is_reused_footage(shot):
        intent["asset_type"] = "reused"
        intent["audio_policy"] = "HERO_PROVIDER_AUDIO_ISLAND"
        intent["reuse"] = {
            "allowed": True,
            "source": "canonical_existing_footage_intent",
            "reused_asset_id": shot.get("source_artifact_id"),
        }
    return intent


def _resolve_reference_required(shot: dict, shot_type: str) -> bool:
    if shot_type in ("hero_lipsync", "hero_cutaway"):
        return True
    return bool(shot.get("claim_refs"))


def _resolve_text_policy(shot: dict) -> str:
    must_avoid = [s.lower() for s in shot.get("must_avoid", [])]
    qa = [s.lower() for s in shot.get("qa_requirements", [])]
    all_rules = must_avoid + qa
    if any("no readable" in r or "no text" in r or "no readable text" in r for r in all_rules):
        return "no_readable_text"
    if any("post_overlay" in r for r in all_rules):
        return "post_overlay"
    return "none"


def _project_shot_to_beat(shot: dict, shot_overlays: list[dict]) -> dict:
    """Project one canonical shot into a legacy beat dict."""
    shot_id = shot.get("shot_id", "")
    missing = [_f for _f in _CANONICAL_SEMANTIC_REQUIRED if not shot.get(_f)]
    if missing:
        raise ProjectionError(
            f"Canonical shot {shot_id!r} missing required semantic source "
            f"fields: {missing}"
        )

    shot_type = _resolve_shot_type(shot)
    beat: dict[str, Any] = {
        "beat_id": shot_id,
        "source_beat_id": shot_id,
        "canonical_shot_id": shot_id,
        "segment_id": shot.get("segment_id", ""),
        "shot_type": shot_type,
        "asset_type": _resolve_asset_type(shot_type, shot),
        "model": _resolve_model(shot_type, shot),
        "prompt_class": _resolve_prompt_class(shot),
        "visual_brief": _compose_visual_brief(shot),
        "visual_intent": _compose_visual_intent(shot),
        "reference_required": _resolve_reference_required(shot, shot_type),
        "text_policy": _resolve_text_policy(shot),
    }
    if beat["asset_type"] == "reused":
        beat["audio_policy"] = "HERO_PROVIDER_AUDIO_ISLAND"
        beat["lipsync_required"] = False
        beat["reuse"] = {
            "allowed": True,
            "source": "canonical_existing_footage_intent",
            "reused_asset_id": shot.get("source_artifact_id"),
        }

    for field in _SHOT_CARRY_FIELDS:
        if field in shot and shot[field] is not None:
            val = shot[field]
            if field == "claim_refs" and val:
                beat["reference_required"] = True
            beat[field] = val

    if shot_overlays:
        graphics_list = [_overlay_to_graphic(o) for o in shot_overlays]
        beat["graphics"] = graphics_list
        beat["graphic"] = graphics_list[0] if len(graphics_list) == 1 else {
            "required": True,
            "kind": "multi_overlay",
            "build_step": 1,
            "total_steps": len(graphics_list),
            "payload": {"overlay_ids": [o["overlay_id"] for o in shot_overlays]},
        }

    beat["projection_trace"] = {
        "canonical_shot_id": shot_id,
        "overlay_ids": [o.get("overlay_id", "") for o in shot_overlays],
    }

    return beat


def _overlay_to_graphic(overlay: dict) -> dict:
    """Project a canonical overlay into a legacy graphic dict.

    Returns a dict compatible with the legacy beat.graphic schema.
    """
    oid = overlay.get("overlay_id", "")
    return {
        "canonical_overlay_id": oid,
        "required": True,
        "kind": overlay.get("overlay_type", "lower_third"),
        "build_step": 1,
        "total_steps": 1,
        "payload": {
            "text": overlay.get("text", ""),
            "semantic_purpose": overlay.get("semantic_purpose", ""),
            "position": overlay.get("position", "lower_third"),
            "style_token": overlay.get("style_token", ""),
            "animation": overlay.get("animation", ""),
            "start_time_offset_sec": overlay.get("start_time_offset_sec", 0.0),
            "end_time_offset_sec": overlay.get("end_time_offset_sec", 0.0),
            "source_ref": overlay.get("source_ref", ""),
            "claim_refs": overlay.get("claim_refs", []),
            "overlay_id": oid,
            "safe_for_9x16": overlay.get("safe_for_9x16", True),
        },
    }


def project_canonical(canonical: dict) -> list[dict]:
    """Project a canonical Sonnet-authored storyboard into legacy beats.

    Args:
        canonical: A storyboard dict with storyboard_contract_version, shots,
                   and overlays (canonical mode).

    Returns:
        A list of legacy beat dicts, one per canonical shot.

    Raises:
        ProjectionError: If any shot is missing required semantic source fields.
        ValueError: If canonical is not in canonical mode.
    """
    if not canonical.get("storyboard_contract_version"):
        raise ValueError(
            "Input must be a canonical storyboard with storyboard_contract_version"
        )

    shots = canonical.get("shots", [])
    overlays = canonical.get("overlays", [])

    overlays_by_shot: dict[str, list[dict]] = {}
    for ov in overlays:
        sid = ov.get("shot_id", "")
        overlays_by_shot.setdefault(sid, []).append(ov)

    beats: list[dict] = []
    for shot in shots:
        shot_id = shot.get("shot_id", "")
        shot_overlays = overlays_by_shot.get(shot_id, [])
        beat = _project_shot_to_beat(shot, shot_overlays)
        beats.append(beat)

    return beats
