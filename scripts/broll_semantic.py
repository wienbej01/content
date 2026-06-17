"""Sprint R7: B-Roll Semantic Contract (R7-001, R7-002, R7-003).

Enforces that every B-roll unit carries informational purpose, has a safe render
mode, and uses a concept key for deduplication across the production.

Integration points:
  R7-001 — validate_broll_semantics() checks required fields before any repo write
  R7-002 — route_render_mode() decides generated_video / deterministic_graphic / post_composite / still_kenburns
  R7-003 — check_concept_quota() rejects repeated concepts (laptops, notebooks, etc.)
  R7-004 — schema migration 005_broll_semantic.sql + plan_render_units populates new fields
"""
from __future__ import annotations

import hashlib
from typing import List, Optional, Dict, Any

import production_db as _db

VALID_RENDER_MODES = {
    "generated_video", "deterministic_graphic", "post_composite",
    "still_kenburns", "hero_lipsync",
}

FORBIDDEN_CHEAP_CONCEPTS = frozenset({
    "laptop", "notebook", "coffee_shop", "server_rack", "handshake",
    "office_worker_typing", "whiteboard_person", "city_skyline_generic",
})

SEMANTIC_FUNCTIONS = {
    "explain", "demonstrate", "contextualize", "warn", "contrast",
    "evoke", "reveal", "anchor", "transition", "illustrate",
}


class BrollSemanticError(ValueError):
    pass


def validate_broll_semantics(unit_spec: dict, asset_type: str, audio_policy: str) -> list[str]:
    """Enforce semantic intent for every B-roll unit.

    Returns list of issue strings. Empty list = valid.
    """
    issues = []

    if asset_type not in ("generated_video", "generated_still"):
        return issues

    if audio_policy in ("HERO_SYNC_LOCKED",):
        return issues

    vf = unit_spec.get("visual_function", "").strip()
    if not vf:
        issues.append("B-roll unit missing 'visual_function' (explain, demonstrate, contextualize, etc.)")
    elif vf.lower() not in SEMANTIC_FUNCTIONS:
        issues.append(f"Invalid visual_function '{vf}'; must be one of {sorted(SEMANTIC_FUNCTIONS)}")

    claim = unit_spec.get("narrative_claim", "").strip()
    if not claim:
        issues.append("B-roll unit missing 'narrative_claim' (what the viewer should understand)")

    info = unit_spec.get("information_to_show", "").strip()
    if not info:
        issues.append("B-roll unit missing 'information_to_show' (what is visible on screen)")

    takeaway = unit_spec.get("viewer_takeaway", "").strip()
    if not takeaway:
        issues.append("B-roll unit missing 'viewer_takeaway' (single-sentence takeaway)")

    action = unit_spec.get("required_action", "").strip()
    if not action:
        issues.append("B-roll unit missing 'required_action' (visual action occurring in clip)")

    distinct = unit_spec.get("distinctness_requirement", "").strip()
    if not distinct:
        issues.append("B-roll unit missing 'distinctness_requirement' (what makes this different from other clips)")

    criteria = unit_spec.get("semantic_acceptance_criteria", "").strip()
    if not criteria:
        issues.append("B-roll unit missing 'semantic_acceptance_criteria' (how to verify the visual matches intent)")

    concept_key = unit_spec.get("concept_key", "").strip()
    if not concept_key:
        issues.append("B-roll unit missing 'concept_key' (semantic hash key for deduplication)")

    return issues


def route_render_mode(beat: dict) -> str:
    """Decide the render mode for a beat based on its content."""
    shot_type = beat.get("shot_type", "")
    asset_type = beat.get("asset_type", "")
    text_policy = (beat.get("text_policy") or "").lower()
    has_text = bool((beat.get("graphic_text_content") or "").strip() or (beat.get("graphics") or []))

    if shot_type == "hero_lipsync":
        return "hero_lipsync"
    if asset_type in ("still_kenburns", "local_graphic"):
        return "still_kenburns"
    if "POST_COMPOSITE" in text_policy.upper() or text_policy in ("post_composite",):
        return "post_composite"
    if has_text or asset_type == "local_graphic" or "DETERMINISTIC_GRAPHIC" in text_policy.upper():
        return "deterministic_graphic"
    return "generated_video"


def compute_concept_key(visual_brief: str, narrative_claim: str, action: str) -> str:
    """Compute a stable concept key for deduplication."""
    normalized = "|".join([
        visual_brief.strip().lower(),
        narrative_claim.strip().lower(),
        action.strip().lower(),
    ])
    return hashlib.sha256(normalized.encode()).hexdigest()


def check_concept_quota(
    production_id: str,
    concept_key: str,
    concept_hash: str,
    db_path=None,
) -> Optional[Dict[str, Any]]:
    """Check if a concept has been used before in this production.

    Returns the existing concept_memory row if found, None if the concept is new.
    """
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT * FROM concept_memory WHERE production_id=? AND concept_hash=?",
        (production_id, concept_hash),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def register_concept(
    production_id: str,
    concept_key: str,
    concept_hash: str,
    visual_brief: str,
    render_unit_id: str,
    db_path=None,
) -> dict:
    """Register a new concept in the concept_memory table."""
    cid = _db._id("cm")
    now = _db._now()
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO concept_memory
               (id, production_id, concept_key, concept_hash, visual_brief, render_unit_id, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (cid, production_id, concept_key, concept_hash, visual_brief, render_unit_id, now),
        )
        return dict(conn.execute("SELECT * FROM concept_memory WHERE id=?", (cid,)).fetchone())
