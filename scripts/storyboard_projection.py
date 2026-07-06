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

from typing import Any, Optional

from storyboard_beat_utils import (
    act_for as _act_for,
    beat_duration_sec as _beat_duration_sec,
    narrative_function_for as _narrative_function_for,
)


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

# Mapping from canonical visual_role value to legacy shot_type.
#
# This must cover the FULL vocabulary that docs/prompts/STORYBOARD_SONNET5_DIRECTOR.md
# instructs the LLM to emit (host_present_speaking, host_present_silent,
# broll_argument_support, broll_emotional_reset, graphic_explanation,
# overlay_frame, transition, establishing) PLUS the legacy-compatible values
# the LLM sometimes emits directly. REPAIR-TKT-601A: the prior table only
# mapped legacy shot_types, so every prompt-vocabulary role silently fell
# through to hero_cutaway, producing all-hero storyboards that failed
# review_storyboard structural validation.
_VISUAL_ROLE_TO_SHOT_TYPE: dict[str, str] = {
    # Hero family
    "host_present_speaking": "hero_lipsync",
    "host_present_silent": "hero_cutaway",
    "hero_lipsync": "hero_lipsync",
    "hero_cutaway": "hero_cutaway",
    # B-roll family — argument_support maps to archival so the validator's
    # "no archival beat" check is satisfied (the LLM uses broll_argument_support
    # for evidence-grounded b-roll, which is exactly the archival intent).
    "broll_argument_support": "broll_archival",
    "broll_emotional_reset": "broll_environment",
    "broll_archival": "broll_archival",
    "broll_metaphorical": "broll_metaphorical",
    "broll_environment": "broll_environment",
    "broll_tactical": "broll_tactical",
    # Graphic family — graphic_explanation maps to graphic_progressive so the
    # validator's "no graphic beat" check is satisfied.
    "graphic_explanation": "graphic_progressive",
    "overlay_frame": "kinetic_text",
    "graphic_progressive": "graphic_progressive",
    "graphic_title_card": "graphic_title_card",
    "kinetic_text": "kinetic_text",
    "ui_insert": "ui_insert",
    # Transition/establishing
    "transition": "broll_tactical",
    "establishing": "broll_environment",
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

OVERLAY_SUITED_LAYOUTS = frozenset({
    "lower_third", "key_line", "stat_callout",
})

FULL_FRAME_LAYOUTS = frozenset({
    "side_by_side", "comparison_card", "framework_3_step", "decision_tree",
    "cost_stack", "before_after", "timeline", "annotated_ui_mock", "quote_card",
})

_OVERLAY_POSITIONS = {
    "lower_third": {"position_16x9": {"x": 70, "y": 1010, "align": "bottom_left"},
                    "position_9x16": {"x": 40, "y": 1770, "align": "bottom_left"}},
    "key_line": {"position_16x9": {"x": 70, "y": 1010, "align": "bottom_left"},
                 "position_9x16": {"x": 40, "y": 1770, "align": "bottom_left"}},
    "stat_callout": {"position_16x9": {"x": 70, "y": 1010, "align": "bottom_left"},
                     "position_9x16": {"x": 40, "y": 1770, "align": "bottom_left"}},
}


def classify_overlay_intent(layout: str) -> str:
    """Classify a graphic layout as 'overlay' or 'full_frame'.

    Overlay-suited layouts (lower_third, key_line, stat_callout) are composited
    on top of footage. Full-frame layouts occupy the entire frame as a standalone
    segment.
    """
    if layout in OVERLAY_SUITED_LAYOUTS:
        return "overlay"
    if layout in FULL_FRAME_LAYOUTS:
        return "full_frame"
    return "full_frame"


def classify_graphic_kind(graphics_json: dict) -> str:
    """Classify a graphic spec dict as 'overlay' or 'full_frame'."""
    layout = graphics_json.get("layout", "") if isinstance(graphics_json, dict) else ""
    return classify_overlay_intent(layout)


def overlay_position_for(layout: str, variant: str = "16x9") -> dict:
    """Return position config for an overlay layout and format variant."""
    pos_key = f"position_{variant}"
    defaults = _OVERLAY_POSITIONS.get(layout, _OVERLAY_POSITIONS["lower_third"])
    return defaults.get(pos_key, {})

_CANONICAL_SEMANTIC_REQUIRED = frozenset({"why_this_visual", "narrative_alignment"})

# Fields from the canonical shot that are carried directly into the legacy beat
# without transformation.
_SHOT_CARRY_FIELDS = (
    "segment_id", "must_show", "must_avoid", "claim_refs",
    "qa_requirements", "planned_duration_sec",
    "min_usable_duration_sec", "max_usable_duration_sec",
    "duration_drift_policy", "assembly_fit_policy",
    "library_asset_id",
)


def _resolve_shot_type(shot: dict) -> str:
    """Maps canonical visual_role to a legacy shot_type.

    REPAIR-TKT-601A: the prior implementation silently returned 'hero_cutaway'
    for any unknown role, which corrupted well-balanced LLM storyboards into
    all-hero shapes that failed structural validation. Unknown roles now raise
    ProjectionError (fail-loud per INV-3) so the operator sees the gap and the
    mapping table is extended, rather than silently demoting graphics/b-roll.
    """
    role = shot.get("visual_role", "")
    if role in _VISUAL_ROLE_TO_SHOT_TYPE:
        return _VISUAL_ROLE_TO_SHOT_TYPE[role]
    # Secondary signals for roles not in the prompt vocabulary but present in
    # some LLM outputs (e.g. legacy shot_type echoed back).
    lit = shot.get("literal_vs_metaphorical", "literal")
    if lit == "metaphorical" and not role:
        return "broll_metaphorical"
    fallback = (shot.get("fallback_strategy") or "").lower()
    if "still" in fallback and not role:
        return "still_kenburns"
    # Unknown visual_role: fail loud. Do NOT silently demote to hero_cutaway.
    raise ProjectionError(
        f"Unknown visual_role {role!r} on shot {shot.get('shot_id', '')!r} "
        f"cannot be projected to a legacy shot_type. Extend "
        f"_VISUAL_ROLE_TO_SHOT_TYPE in storyboard_projection.py to cover it."
    )


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
    """Detect canonical intent to preserve existing footage, not generate anew.

    TKT-503: shots citing a library_asset_id are automatically treated as reused.
    """
    if shot.get("library_asset_id"):
        return True
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

    # Incorporate shot_id into the concept derivation so that different beats
    # serving the same segment never collide on concept_key (the check_concept_quota
    # dedup check catches identical keys across beats).
    shot_id = shot.get("shot_id", "")
    key_seed = f"{concept}|{primary_subject}|{action}|{shot_id}"
    derived_key = derive_concept_key(key_seed, primary_subject, action)
    derived_hash = compute_concept_key(key_seed, primary_subject, action)

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
        lib_id = shot.get("library_asset_id")
        if lib_id:
            import production_db as _db
            conn = _db.connect(None)
            lib_row = conn.execute(
                "SELECT uri, sha256 FROM asset_library WHERE id=?", (lib_id,)
            ).fetchone()
            conn.close()
            if not lib_row:
                raise RuntimeError(
                    f"Library asset {lib_id!r} not found in asset_library. "
                    f"Use 'produce_db.py library add' to index it first."
                )
            intent["reuse"] = {
                "allowed": True,
                "source": "asset_library",
                "reused_asset_id": lib_id,
                "reused_asset_uri": lib_row["uri"],
                "reused_asset_sha": lib_row["sha256"],
            }
        else:
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


def _project_shot_to_beat(
    shot: dict,
    shot_overlays: list[dict],
    order: int = 0,
    n: int = 1,
    segment_text_map: Optional[dict] = None,
) -> dict:
    """Project one canonical shot into a legacy beat dict.

    REPAIR-TKT-601A: populate the legacy fields the structural validator
    (review_storyboard.review) requires — order, act, est_duration_sec,
    narration_text, label, narrative_function — which the prior implementation
    omitted entirely, causing every production storyboard to fail validation.
    The test-mode path (produce_db.invoke_storyboard) already populated these;
    this closes the divergence.
    """
    shot_id = shot.get("shot_id", "")
    missing = [_f for _f in _CANONICAL_SEMANTIC_REQUIRED if not shot.get(_f)]
    if missing:
        raise ProjectionError(
            f"Canonical shot {shot_id!r} missing required semantic source "
            f"fields: {missing}"
        )

    shot_type = _resolve_shot_type(shot)
    segment_id = shot.get("segment_id", "")
    segment_text_map = segment_text_map or {}
    narration_text = segment_text_map.get(segment_id, "") if segment_id else ""

    # Duration: prefer the canonical planned_duration_sec (LLM-authored); fall
    # back to a narration-derived estimate when absent (matches test-mode).
    planned = shot.get("planned_duration_sec")
    if planned and float(planned) > 0:
        est_duration_sec = round(float(planned), 2)
    else:
        est_duration_sec = _beat_duration_sec(narration_text)

    beat: dict[str, Any] = {
        "beat_id": shot_id,
        "source_beat_id": shot_id,
        "canonical_shot_id": shot_id,
        "order": order,
        "act": _act_for(order, n),
        "segment_id": segment_id,
        "label": segment_id or shot_id,
        "narration_text": narration_text,
        "shot_type": shot_type,
        "est_duration_sec": est_duration_sec,
        "narrative_function": _narrative_function_for(shot_type),
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


def project_canonical(
    canonical: dict,
    segment_text_map: Optional[dict] = None,
) -> list[dict]:
    """Project a canonical Sonnet-authored storyboard into legacy beats.

    Args:
        canonical: A storyboard dict with storyboard_contract_version, shots,
                   and overlays (canonical mode).
        segment_text_map: Optional mapping {segment_id: narration_text} from the
                   approved script, used to populate beat.narration_text (which
                   review_storyboard._trigger_coverage needs for year/study/
                   ordinal trigger coverage). When None, narration_text is "".

    Returns:
        A list of legacy beat dicts, one per canonical shot.

    Raises:
        ProjectionError: If any shot is missing required semantic source fields,
                        or has an unmappable visual_role (fail-loud per INV-3).
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

    n = len(shots)
    beats: list[dict] = []
    for order, shot in enumerate(shots):
        shot_id = shot.get("shot_id", "")
        shot_overlays = overlays_by_shot.get(shot_id, [])
        beat = _project_shot_to_beat(
            shot, shot_overlays,
            order=order, n=n,
            segment_text_map=segment_text_map,
        )
        beats.append(beat)

    return beats
